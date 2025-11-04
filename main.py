import json

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from database import search_tool, fetch_tool, get_schema_tool, query_facilities_tool
from fastapi.responses import FileResponse

@app.get("/.well-known/ai-plugin.json")
async def serve_ai_plugin():
    return FileResponse(".well-known/ai-plugin.json", media_type="application/json")

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


@app.post("/sse")
async def sse_endpoint(request: Request):
    print("\n--- [LOG] NEW CONNECTION RECEIVED ---")

    try:
        body = await request.json()
        print(f"[LOG] JSON Body parsed: {body}")

        event_id = body.get("id", "mcp_event_1")
        method = body.get("method")
        is_json_rpc = body.get("jsonrpc") == "2.0"

        if not is_json_rpc:
            return Response(
                content=json.dumps({"error": "Invalid JSON-RPC format"}),
                media_type="application/json"
            )

        # 1️⃣ initialize
        if method == "initialize":
            print("[LOG] Handling initialize")
            result = {
                "protocolVersion": "2025-03-26",
                "serverInfo": {"name": "ODCAF MCP Server", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }
            response = {"jsonrpc": "2.0", "id": event_id, "result": result}

        # 2️⃣ notifications/initialized (no response expected)
        elif method == "notifications/initialized":
            print("[LOG] Handling notifications/initialized (no response needed)")
            response = {"jsonrpc": "2.0", "result": "ok"}

        # 3️⃣ list tools
        elif method in ["mcp.tool.list_tools.invoke", "tools/list"]:
            print("[LOG] Handling list_tools")
            result = {"tools": TOOL_DEFINITIONS}
            response = {"jsonrpc": "2.0", "id": event_id, "result": result}

        # 4️⃣ invoke tool
        elif method == "mcp.tool.invoke":
            print("[LOG] Handling tool invoke")
            params = body.get("params", {})
            tool_id = params.get("tool_name")
            args = params.get("parameters", {})

            if tool_id == "search":
                result = await search_tool(args.get("query", ""), args.get("limit", 5))
            elif tool_id == "fetch":
                result = await fetch_tool(args.get("id", ""))
            else:
                result = {"error": f"Unknown tool {tool_id}"}

            response = {"jsonrpc": "2.0", "id": event_id, "result": result}

        # 5️⃣ unknown method
        else:
            print(f"[LOG] Unknown method: {method}")
            response = {
                "jsonrpc": "2.0",
                "id": event_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            }

    except Exception as e:
        print(f"[ERROR] {e}")
        response = {
            "jsonrpc": "2.0",
            "id": "mcp_error",
            "error": {"code": -32000, "message": str(e)}
        }

    print("--- [LOG] Request handled. Closing connection. ---")
    return Response(content=json.dumps(response), media_type="application/json")


@app.get("/")
def root():
    return {"message": "MCP Server is running. Use the /sse endpoint."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
