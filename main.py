import asyncio
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
from sse_starlette.sse import EventSourceResponse

from fastapi.middleware.cors import CORSMiddleware
from database import search_tool, fetch_tool, get_schema_tool, query_facilities_tool

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

TOOL_DEFINITIONS = [
    {
        "name": "search",
        "description": "Search the Open Database of Cultural and Art Facilities (ODCAF) by keyword (e.g., name, city, province, or type).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search term (e.g., 'Museum', 'Toronto', 'Gallery')."},
                "limit": {"type": "integer", "description": "Max number of results to return.", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch",
        "description": "Fetch the full details for a specific cultural facility by its exact name (which is used as its ID).",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The exact name of the facility to fetch."}
            },
            "required": ["id"]
        }
    }
]


async def mcp_event_generator(request: Request):
    print("\n--- [LOG] NEW CONNECTION RECEIVED ---")
    session_id = "mcp_session_1"

    print("[LOG] Sending mcp.transport.session_created...")
    yield json.dumps({
        "event": "mcp.transport.session_created",
        "data": {"session_id": session_id}
    })

    content_length = request.headers.get('content-length')
    print(f"[LOG] Content-Length header: {content_length}")


    event_id = "mcp_event_unknown"

    if content_length is not None and int(content_length) > 0:
        try:
            body = await request.json()
            print(f"[LOG] JSON Body parsed: {body}")

            event_id = body.get("id", "mcp_event_1")
            is_json_rpc = body.get("jsonrpc") == "2.0"
            event_type = body.get("event")
            method_type = body.get("method")

            response_payload = None
            has_error = False

            if is_json_rpc:


                if method_type == "initialize":
                    print("[LOG] JSON-RPC: Handling 'initialize'.")

                    client_protocol_version = body.get("params", {}).get("protocolVersion", "2025-03-26")
                    print(f"[LOG] Client requested protocol version: {client_protocol_version}")

                    response_payload = {
                        "protocolVersion": client_protocol_version,
                        "serverInfo": {
                            "name": "Servidor ODCAF (Estadísticas Canadá)",
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                    print(f"[LOG] JSON-RPC: Sending RESULT for initialize")
                    yield json.dumps({
                        "jsonrpc": "2.0",
                        "id": event_id,
                        "result": response_payload
                    })


                elif method_type == "mcp.tool.list_tools.invoke" or method_type == "tools/list":
                    print("[LOG] JSON-RPC: Handling 'mcp.tool.list_tools.invoke' (or 'tools/list').")
                    response_payload = {"tools": TOOL_DEFINITIONS}
                    print(f"[LOG] JSON-RPC: Sending RESULT for list_tools")
                    yield json.dumps({
                        "jsonrpc": "2.0",
                        "id": event_id,
                        "result": response_payload
                    })


                elif method_type == "mcp.tool.invoke":
                    tool_id = body.get("params", {}).get("tool_name")
                    params = body.get("params", {}).get("parameters", {})
                    print(f"[LOG] JSON-RPC: Handling mcp.tool.invoke for {tool_id}")

                    if tool_id == "search":
                        query = params.get("query", "")
                        limit = params.get("limit", 5)
                        response_payload = await search_tool(query, limit)
                    elif tool_id == "fetch":
                        facility_id = params.get("id", "")
                        response_payload = await fetch_tool(facility_id)
                    else:
                        response_payload = {"code": -32002, "message": f"Unknown tool_id: {tool_id}"}
                        has_error = True

                    if isinstance(response_payload, dict) and 'error' in response_payload and not has_error:
                        response_payload = {"code": -32000, "message": response_payload['error']}
                        has_error = True

                    if has_error:
                        print(f"[LOG] JSON-RPC: Sending ERROR response: {response_payload}")
                        yield json.dumps({
                            "jsonrpc": "2.0",
                            "id": event_id,
                            "error": response_payload
                        })
                    else:
                        print(f"[LOG] JSON-RPC: Sending RESULT response for method {method_type}")
                        yield json.dumps({
                            "jsonrpc": "2.0",
                            "id": event_id,
                            "result": response_payload
                        })

            elif event_type:

                pass # (Abreviado por claridad)

            else:
                print(f"[LOG] Unknown protocol: {body}")

        except Exception as e:
            print(f"!!! [ERROR] Error processing JSON body: {e}")
            
            yield json.dumps({"jsonrpc": "2.0", "id": event_id, "error": {"code": -32000, "message": str(e)}})

    else:
        print("[LOG] Empty POST or GET received. Connection established.")


    print("--- [LOG] Request handled. Closing connection. ---")


@app.post("/sse")
async def sse_endpoint(request: Request):
    return EventSourceResponse(mcp_event_generator(request), media_type="text/event-stream")


@app.get("/")
def root():
    return {"message": "MCP Server is running. Use the /sse endpoint."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)