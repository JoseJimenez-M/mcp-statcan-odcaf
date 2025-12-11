# ODCAF MCP Server  
A Machine Control Protocol (MCP) server that exposes the **Official Canadian Cultural Facilities Dataset (ODCAF)** through a clean and consistent MCP interface. This server allows ChatGPT and other MCP-compatible clients to query cultural facilities across Canada using JSON-RPC over HTTP + Server-Sent Events (SSE).

---

## Features

### Full MCP-Compatible API  
Implements:
- `initialize`
- `tools/list`
- `tools/call`
- Real SSE endpoint (`GET /sse`) emitting `notifications/initialized`.

### Tools Available  
This server exposes the following tools:

#### **1. get_schema**
Returns the full schema of the ODCAF `facilities` table.

#### **2. query_facilities**
Query facilities by:
- Province or territory  
- City  
- Facility type  
- Limit  

#### **3. search**
Keyword-based search across:
- Facility name  
- Facility type  
- City  
- Province  

#### **4. fetch**
Fetch the full record of a facility by its exact name.

---

## Dataset  
The ODCAF dataset contains cultural facility metadata including:
- Name, address, postal code
- City, province/territory  
- Facility type (normalized by ODCAF)  
- Coordinates (latitude, longitude)  
- Geographic identifiers (CSD, PRUID, etc.)  

This server uses:
- `ODCAF_v1.0.csv`  
- Preprocessed into `odcaf.db` via SQLite  

---

## Running the Server

### Local development
```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Production (Render / Cloud)

Set your app to run:
```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```
🛰 MCP Endpoint

SSE endpoint: GET /sse

JSON-RPC endpoint: POST / or POST /sse

All tool calls follow MCP's tools/call specification.

### License

This project wraps publicly available ODCAF data.
You are free to modify or extend this MCP server for research or production use.
