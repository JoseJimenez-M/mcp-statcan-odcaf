import asyncio
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
from sse_starlette.sse import EventSourceResponse

# --- 1. Importar y configurar CORS ---
from fastapi.middleware.cors import CORSMiddleware
from database import get_schema_tool, query_facilities_tool

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
        "id": "get_schema",
        "description": "Get the database schema, column names, and data types for the 'facilities' table."
    },
    {
        "id": "query_facilities",
        "description": "Query the Open Database of Cultural and Art Facilities (ODCAF).",
        "parameters": {
            "type": "object",
            "properties": {
                "province": {"type": "string",
                             "description": "Filter by province or territory (e.g., 'Ontario', 'Quebec')."},
                "city": {"type": "string", "description": "Filter by city (e.g., 'Toronto', 'Montreal')."},
                "facility_type": {"type": "string",
                                  "description": "Filter by facility type (e.g., 'Museum', 'Gallery')."},
                "limit": {"type": "integer", "description": "Max number of results to return.", "default": 5}
            },
            "required": []
        }
    }
]


# --- 2. Lógica del Generador (Protocolo Híbrido Corregido) ---
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

            # --- LÓGICA PARA JSON-RPC (ChatGPT) ---
            if is_json_rpc:

                # --- PASO 3 (Respuesta a 'initialize') ---
                if method_type == "initialize":
                    print("[LOG] JSON-RPC: Handling 'initialize'.")
                    response_payload = {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {}
                    }
                    print(f"[LOG] JSON-RPC: Sending RESULT for initialize")
                    yield json.dumps({
                        "jsonrpc": "2.0",
                        "id": event_id,
                        "result": response_payload
                    })

                    # --- ¡EL PASO 4 FALTANTE! Enviar la lista de herramientas proactivamente ---
                    print("[LOG] JSON-RPC: Proactively sending tool list (SSE)...")
                    yield json.dumps({
                        "event": "mcp.tool.list_tools.result",
                        "data": {"tools": TOOL_DEFINITIONS}
                    })
                    print("[LOG] JSON-RPC: Tool list sent.")

                # --- Lógica para invocaciones de herramientas (PASO 6+) ---
                elif method_type == "mcp.tool.invoke":
                    tool_id = body.get("params", {}).get("tool_id")
                    params = body.get("params", {}).get("parameters", {})
                    print(f"[LOG] JSON-RPC: Handling mcp.tool.invoke for {tool_id}")

                    if tool_id == "get_schema":
                        response_payload = await get_schema_tool()
                    elif tool_id == "query_facilities":
                        if not params.get("province") and not params.get("city") and not params.get("facility_type"):
                            response_payload = {"code": -32001, "message": "Your filter is too broad..."}
                            has_error = True
                        else:
                            response_payload = await query_facilities_tool(**params)
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

            # --- LÓGICA PARA MCP (tu prueba de curl) ---
            elif event_type:
                response_event_name = None
                if event_type == "mcp.tool.list_tools.invoke":
                    print("[LOG] MCP: Handling mcp.tool.list_tools.invoke")
                    response_event_name = "mcp.tool.list_tools.result"
                    response_payload = {"tools": TOOL_DEFINITIONS}
                elif event_type == "mcp.tool.invoke":
                    tool_id = body.get("data", {}).get("tool_id")
                    params = body.get("data", {}).get("parameters", {})
                    result_data = await query_facilities_tool(**params)
                    response_payload = {"tool_id": tool_id, "result": result_data}
                    response_event_name = "mcp.tool.invoke.result"

                print(f"[LOG] MCP: Sending response event: {response_event_name}")
                yield json.dumps({
                    "id": f"resp_for_{event_id}",
                    "event": response_event_name,
                    "data": response_payload
                })

            else:
                print(f"[LOG] Unknown protocol: {body}")

        except Exception as e:
            print(f"!!! [ERROR] Error processing JSON body: {e}")
            yield json.dumps({"jsonrpc": "2.0", "id": event_id, "error": {"code": -32000, "message": str(e)}})

    else:
        print("[LOG] Empty POST received. Connection established.")

    print("[LOG] Entering keep-alive loop...")
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        print("[LOG] Client disconnected. Closing keep-alive loop.")
    finally:
        print("--- [LOG] CONNECTION CLOSED ---")


@app.post("/sse")
async def sse_endpoint(request: Request):
    return EventSourceResponse(mcp_event_generator(request),
                               media_type="text/stream")  # Corregido a 'text/event-stream'


@app.get("/")
def root():
    return {"message": "MCP Server is running. Use the /sse endpoint."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)