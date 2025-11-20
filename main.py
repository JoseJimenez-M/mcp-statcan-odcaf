import asyncio
import json
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.responses import JSONResponse

from database import (
    get_schema,
    query_facilities,
    search_facilities,
    fetch_facility_by_id,
)

PROTOCOL_VERSION = "2024-11-05"

app = FastAPI(title="ODCAF MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "get_schema",
            "description": "Get the database schema for the ODCAF facilities table.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "query_facilities",
            "description": "Query facilities by optional province, city, and facility type with fuzzy matching.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "province": {"type": "string"},
                    "city": {"type": "string"},
                    "facility_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": [],
            },
        },
        {
            "name": "search",
            "description": "Keyword search across facility name, type, city, and province using fuzzy matching.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        },
        {
            "name": "fetch",
            "description": "Fetch a single facility by its exact name (fuzzy-normalized).",
            "inputSchema": {
                "type": "object",
                "properties": {"facility_id": {"type": "string"}},
                "required": ["facility_id"],
            },
        },
        {
            "name": "list_cities",
            "description": "List all unique city names available in the ODCAF dataset.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "list_facility_types",
            "description": "List all unique facility types in the ODCAF dataset.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        }
    ]



@app.get("/")
async def root() -> JSONResponse:
    data = {
        "message": "ODCAF MCP Server is running.",
        "server": {"name": "ODCAF MCP Server", "version": "1.0.0"},
        "protocolVersion": PROTOCOL_VERSION,
    }
    return JSONResponse(data)


@app.get("/health")
async def health() -> JSONResponse:
    tools = get_tools()
    info = {
        "status": "ok",
        "server": {"name": "ODCAF MCP Server", "version": "1.0.0"},
        "tools": [tool["name"] for tool in tools],
        "protocolVersion": PROTOCOL_VERSION,
    }
    return JSONResponse(info)


@app.get("/sse")
async def sse_endpoint(request: Request) -> EventSourceResponse:
    async def event_generator():
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {
                    "name": "ODCAF MCP Server",
                    "version": "1.0.0",
                },
                "capabilities": {"tools": {}},
            },
        }
        yield {
            "event": "message",
            "data": json.dumps(payload),
        }
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())


async def handle_get_schema() -> Dict[str, Any]:
    schema = await get_schema()
    payload = {"schema": schema}
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2),
            }
        ]
    }


async def handle_query_facilities(arguments: Dict[str, Any]) -> Dict[str, Any]:
    province = arguments.get("province")
    city = arguments.get("city")
    facility_type = arguments.get("facility_type")
    limit = int(arguments.get("limit", 5))
    rows = await query_facilities(
        province=province,
        city=city,
        facility_type=facility_type,
        limit=limit,
    )
    payload = {
        "filters": {
            "province": province,
            "city": city,
            "facility_type": facility_type,
            "limit": limit,
        },
        "count": len(rows),
        "facilities": rows,
    }
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2),
            }
        ]
    }


async def handle_search(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query_text = arguments.get("query", "")
    limit = int(arguments.get("limit", 5))
    rows = await search_facilities(query_text=query_text, limit=limit)
    payload = {
        "query": query_text,
        "limit": limit,
        "count": len(rows),
        "facilities": rows,
    }
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2),
            }
        ]
    }


async def handle_fetch(arguments: Dict[str, Any]) -> Dict[str, Any]:
    facility_id = arguments.get("facility_id", "")
    row = await fetch_facility_by_id(facility_id)
    if row is None:
        payload = {
            "facility_id": facility_id,
            "found": False,
            "message": "No facility found with that name.",
        }
    else:
        payload = {
            "facility_id": facility_id,
            "found": True,
            "facility": row,
        }
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2),
            }
        ]
    }


@app.post("/")
@app.post("/sse")
async def mcp_handler(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        error = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Invalid JSON in request body.",
            },
        }
        return JSONResponse(error)

    jsonrpc_version = body.get("jsonrpc") or "2.0"
    method = body.get("method")
    request_id = body.get("id")

    if jsonrpc_version != "2.0":
        error = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32600,
                "message": "Invalid JSON-RPC version.",
            },
        }
        return JSONResponse(error)

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": "ODCAF MCP Server", "version": "1.0.0"},
            "capabilities": {"tools": {}},
        }
        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        return JSONResponse(response)

    if method == "tools/list":
        tools = get_tools()
        result = {"tools": tools}
        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        return JSONResponse(response)

    if method == "tools/call":
        params = body.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}

        try:
            if name == "get_schema":
                result = await handle_get_schema()
            elif name == "query_facilities":
                result = await handle_query_facilities(arguments)
            elif name == "search":
                result = await handle_search(arguments)
            elif name == "fetch":
                result = await handle_fetch(arguments)
            elif name == "list_cities":
                result = await handle_list_cities()
            elif name == "list_facility_types":
                result = await handle_list_facility_types()
            else:
                error = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {name}",
                    },
                }
                return JSONResponse(error)

            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
            return JSONResponse(response)
        except Exception as exc:
            error = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": str(exc),
                },
            }
            return JSONResponse(error)

    error = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Unknown method: {method}",
        },
    }
    return JSONResponse(error)

async def handle_list_cities() -> Dict[str, Any]:
    cities = await list_cities()
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({"cities": cities}, indent=2)
            }
        ]
    }

async def handle_list_facility_types() -> Dict[str, Any]:
    types = await list_facility_types()
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({"facility_types": types}, indent=2)
            }
        ]
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
