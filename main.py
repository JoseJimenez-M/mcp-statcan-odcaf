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
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "query_facilities",
            "description": "Query facilities by optional province, city, and facility type.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "province": {
                        "type": "string",
                        "description": "Province or territory name or code.",
                    },
                    "city": {
                        "type": "string",
                        "description": "City name.",
                    },
                    "facility_type": {
                        "type": "string",
                        "description": "Facility type, for example museum or gallery.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "default": 5,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "search",
            "description": "Search facilities by keyword across name, type, city, and province.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to match name, type, city, or province.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "fetch",
            "description": "Fetch a single facility by its exact name.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "facility_id": {
                        "type": "string",
                        "description": "Exact facility name to look up.",
                    }
                },
                "required": ["facility_id"],
            },
        },
    ]


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
        return JSONResponse(error, status_code=400)

    jsonrpc_version = body.get("jsonrpc")
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
        return JSONResponse(error, status_code=400)

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
            else:
                error = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {name}",
                    },
                }
                return JSONResponse(error, status_code=400)

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
            return JSONResponse(error, status_code=500)

    error = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Unknown method: {method}",
        },
    }
    return JSONResponse(error, status_code=400)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
