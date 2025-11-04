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


# --- 2. Lógica del Generador Mejorada ---
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

    if content_length is None or content_length == '0':
        print("[LOG] Empty POST received. Holding open.")
        try:
            while True: await asyncio.sleep(60)
        except asyncio.CancelledError:
            print("[LOG] Client (empty connection) disconnected.")
        return

    # --- Este bloque SÍ se ejecutará ahora ---
    try:
        body = await request.json()
        print(f"[LOG] JSON Body parsed: {body}")

        # Obtener el ID de la solicitud (para JSON-RPC)
        event_id = body.get("id", "mcp_event_1")

        # --- ¡LA SOLUCIÓN! Comprobar ambos protocolos ---
        event_type = body.get("event")  # Para 'curl' tests
        method_type = body.get("method")  # Para ChatGPT

        response_data = None
        response_event = None

        # Manejar el 'initialize' de ChatGPT O el 'list_tools' de curl
        if method_type == "initialize" or event_type == "mcp.tool.list_tools.invoke":
            print(f"[LOG] Handling '{method_type or event_type}'. Sending tool list.")
            response_event = "mcp.tool.list_tools.result"
            response_data = {"tools": TOOL_DEFINITIONS}

        # Manejar 'mcp.tool.invoke' de ambos protocolos
        elif event_type == "mcp.tool.invoke" or method_type == "mcp.tool.invoke":

            params = {}
            tool_id = None

            if event_type == "mcp.tool.invoke":
                # Formato 'curl' test
                tool_id = body.get("data", {}).get("tool_id")
                params = body.get("data", {}).get("parameters", {})
            elif method_type == "mcp.tool.invoke":
                # Formato JSON-RPC de ChatGPT
                tool_id = body.get("params", {}).get("tool_id")
                params = body.get("params", {}).get("parameters", {})

            print(f"[LOG] Handling mcp.tool.invoke for tool_id: {tool_id}")

            response_event = "mcp.tool.invoke.result"
            result_data = None

            if tool_id == "get_schema":
                result_data = await get_schema_tool()
            elif tool_id == "query_facilities":
                if not params.get("province") and not params.get("city") and not params.get("facility_type"):
                    result_data = {"error": "Your filter is too broad; try adding province, city, or facility_type."}
                else:
                    result_data = await query_facilities_tool(**params)
            else:
                result_data = {"error": f"Unknown tool_id: {tool_id}"}

            response_data = {"tool_id": tool_id, "result": result_data}

        else:
            print(f"[LOG] Unknown event/method: {event_type} / {method_type}")
            response_event = "mcp.error"
            response_data = {"code": "unknown_event", "message": f"Unknown event/method: {event_type} / {method_type}"}

        print(f"[LOG] Sending response event: {response_event}")
        yield json.dumps({
            "id": f"resp_for_{event_id}",  # Responder con el mismo ID
            "event": response_event,
            "data": response_data
        })

    except Exception as e:
        print(f"!!! [ERROR] Error processing JSON body: {e}")
        yield json.dumps({
            "event": "mcp.error",
            "data": {"code": "internal_server_error", "message": str(e)}
        })
    finally:
        print("--- [LOG] JSON BODY CONNECTION CLOSED ---")


@app.post("/sse")
async def sse_endpoint(request: Request):
    return EventSourceResponse(mcp_event_generator(request), media_type="text/event-stream")


@app.get("/")
def root():
    return {"message": "MCP Server is running. Use the /sse endpoint."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)