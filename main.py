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

    # Búfer para leer el stream de la solicitud
    buffer = ""

    try:
        # Bucle principal: leer el stream de la solicitud mientras esté vivo
        async for chunk in request.stream():
            buffer += chunk.decode('utf-8')

            # Intentar procesar uno o más JSONs completos en el búfer
            # El protocolo puede enviar múltiples mensajes concatenados
            while True:
                try:
                    # Buscar el fin de un objeto JSON (}) y el inicio del siguiente ({)
                    # Esta es una forma simple de parsear JSONs concatenados.
                    # Asume que los mensajes no contienen '{' o '}' en sus strings.
                    # Una implementación más robusta usaría un parser de stream JSON.

                    # Intentamos encontrar un JSON completo
                    body_str, rest = buffer.split('}', 1)
                    body_str += '}'
                    buffer = rest  # Guardar el resto para el próximo ciclo

                    body = json.loads(body_str)
                    print(f"[LOG] JSON Body parsed: {body}")

                    event_id = body.get("id", "mcp_event_1")
                    is_json_rpc = body.get("jsonrpc") == "2.0"
                    method_type = body.get("method")

                    response_payload = None
                    has_error = False

                    if is_json_rpc:
                        # --- PASO 3 (Respuesta a 'initialize') ---
                        if method_type == "initialize":
                            print("[LOG] JSON-RPC: Handling 'initialize'.")

                            # ¡FIX de Versión Dinámica!
                            client_protocol_version = body.get("params", {}).get("protocolVersion", "2025-03-26")
                            print(f"[LOG] Client requested protocol version: {client_protocol_version}")

                            response_payload = {
                                "protocolVersion": client_protocol_version,
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

                        # --- PASO 4 (Respuesta a 'list_tools') ---
                        elif method_type == "mcp.tool.list_tools.invoke":
                            print("[LOG] JSON-RPC: Handling 'mcp.tool.list_tools.invoke'.")
                            response_payload = {"tools": TOOL_DEFINITIONS}
                            print(f"[LOG] JSON-RPC: Sending RESULT for list_tools")
                            yield json.dumps({
                                "jsonrpc": "2.0",
                                "id": event_id,
                                "result": response_payload
                            })

                        # --- PASO 5 (Respuesta a 'invoke') ---
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

                        else:
                            print(f"[LOG] Unknown JSON-RPC method: {method_type}")

                    else:
                        print(f"[LOG] Unknown protocol: {body}")

                except (json.JSONDecodeError, ValueError):
                    # El JSON en el búfer no está completo, esperar más chunks
                    break

    except asyncio.CancelledError:
        print("[LOG] Client disconnected. Closing stream.")
    except Exception as e:
        print(f"!!! [ERROR] Error processing stream: {e}")
        yield json.dumps({"jsonrpc": "2.0", "id": "error", "error": {"code": -32000, "message": str(e)}})
    finally:
        print("--- [LOG] CONNECTION CLOSED ---")


@app.post("/sse")
async def sse_endpoint(request: Request):
    return EventSourceResponse(mcp_event_generator(request), media_type="text/event-stream")


@app.get("/")
def root():
    return {"message": "MCP Server is running. Use the /sse endpoint."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)