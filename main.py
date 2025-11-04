import asyncio
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
from sse_starlette.sse import EventSourceResponse

# --- 1. Importar y configurar CORS ---
from fastapi.middleware.cors import CORSMiddleware
# --- Usar las herramientas de la documentación oficial ---
from database import search_tool, fetch_tool, get_schema_tool, query_facilities_tool

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- 2. Definir las herramientas 'search' y 'fetch' de la documentación ---
TOOL_DEFINITIONS = [
    {
        "id": "search",
        "description": "Search the Open Database of Cultural and Art Facilities (ODCAF) by keyword (e.g., name, city, province, or type).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search term (e.g., 'Museum', 'Toronto', 'Gallery')."},
                "limit": {"type": "integer", "description": "Max number of results to return.", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "id": "fetch",
        "description": "Fetch the full details for a specific cultural facility by its exact name (which is used as its ID).",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The exact name of the facility to fetch."}
            },
            "required": ["id"]
        }
    }
]


# --- 3. Lógica del Generador (Protocolo JSON-RPC Corregido) ---
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

                    # --- ¡CORRECCIÓN DE VERSIÓN! ---
                    client_protocol_version = body.get("params", {}).get("protocolVersion", "2025-03-26")
                    print(f"[LOG] Client requested protocol version: {client_protocol_version}")

                    response_payload = {
                        "protocolVersion": client_protocol_version,
                        # --- ¡CORRECCIÓN DE serverInfo! ---
                        "serverInfo": {
                            "name": "Servidor ODCAF (Estadísticas Canadá)",
                            "version": "1.0.0"
                        },
                        "capabilities": {}
                    }
                    print(f"[LOG] JSON-RPC: Sending RESULT for initialize")
                    yield json.dumps({
                        "jsonrpc": "2.0",
                        "id": event_id,
                        "result": response_payload
                    })

                # --- Manejar la solicitud 'list_tools' ---
                elif method_type == "mcp.tool.list_tools.invoke" or method_type == "tools/list":
                    print("[LOG] JSON-RPC: Handling 'mcp.tool.list_tools.invoke' (or 'tools/list').")
                    response_payload = {"tools": TOOL_DEFINITIONS}
                    print(f"[LOG] JSON-RPC: Sending RESULT for list_tools")
                    yield json.dumps({
                        "jsonrpc": "2.0",
                        "id": event_id,
                        "result": response_payload
                    })

                # --- Lógica para invocaciones de herramientas (PASO 6+) ---
                elif method_type == "mcp.tool.invoke":
                    tool_id = body.get("params", {}).get("tool_id")
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

            # --- LÓGICA PARA MCP (tu prueba de curl) ---
            elif event_type:
                # (Tu lógica de prueba original está bien aquí)
                response_event_name = None
                if event_type == "mcp.tool.list_tools.invoke":
                    print("[LOG] MCP: Handling mcp.tool.list_tools.invoke")
                    response_event_name = "mcp.tool.list_tools.result"
                    response_payload = {"tools": TOOL_DEFINITIONS}
                elif event_type == "mcp.tool.invoke":
                    tool_id = body.get("data", {}).get("tool_id")
                    params = body.get("data", {}).get("parameters", {})

                    if tool_id == "get_schema":
                        result_data = await get_schema_tool()
                    elif tool_id == "query_facilities":
                        result_data = await query_facilities_tool(**params)
                    else:
                        result_data = {"error": "Unknown tool for MCP test"}

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

    # --- ¡CORRECCIÓN! ELIMINAMOS EL BUCLE "keep-alive" ---
    # Al no tener un bucle "while True", el generador
    # terminará aquí, cerrará la conexión, y permitirá
    # que OpenAI envíe la *siguiente* solicitud.
    print("--- [LOG] Request handled. Closing connection. ---")


@app.post("/sse")
async def sse_endpoint(request: Request):
    return EventSourceResponse(mcp_event_generator(request), media_type="text/event-stream")


@app.get("/")
def root():
    return {"message": "MCP Server is running. Use the /sse endpoint."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)