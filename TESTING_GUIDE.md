# Model Context Protocol (MCP) Testing Guide

This document provides command-line examples (\`curl\`) to verify that the deployed MCP server is fully functional and successfully queries the Statistics Canada ODCAF dataset.

The server is hosted on Render and may experience a **30-60 second cold start delay** upon the first request if inactive.

**MCP Server URL:** https://mcp-statcan-odcaf.onrender.com/sse
**Protocol:** HTTP/SSE (Server-Sent Events)

---

## 1. Tool Discovery (\`list_tools\`)

This test verifies that the server responds to the initial MCP handshake and exposes the list of available tools.

\`\`\`bash
# Command to list all available tools
curl -X POST -H "Content-Type: application/json" -d "{\"event\": \"mcp.tool.list_tools.invoke\", \"id\": \"test_list\"}" https://mcp-statcan-odcaf.onrender.com/sse
\`\`\`

**Expected Result:** A response containing the definitions for \`get_schema\` and \`query_facilities\`.

---

## 2. Schema Introspection (\`get_schema\`)

This test validates that the \`get_schema\` tool can successfully connect to the SQLite database and return the column structure.

\`\`\`bash
# Command to fetch the database schema
curl --max-time 60 -X POST -H "Content-Type: application/json" -d "{\"event\": \"mcp.tool.invoke\", \"id\": \"test_schema\", \"data\": {\"tool_id\": \"get_schema\", \"parameters\": {}}}" https://mcp-statcan-odcaf.onrender.com/sse
\`\`\`

**Expected Result:** A response with \`event: mcp.tool.invoke.result\` containing the \`result\` body showing all column names (e.g., \`prov_terr\`, \`city\`, \`facility_name\`).

---

## 3. Data Query and Filtering (\`query_facilities\`)

This test confirms that the main query tool works, handles filtering (case-insensitive and trimming), and returns structured data (JSON).

### Test A: Query by City and Type (e.g., 3 Galleries in Montreal)

\`\`\`bash
# Command to find 3 galleries in Montreal
curl --max-time 60 -X POST -H "Content-Type: application/json" -d "{\"event\": \"mcp.tool.invoke\", \"id\": \"test_query_A\", \"data\": {\"tool_id\": \"query_facilities\", \"parameters\": {\"city\": \"Montreal\", \"facility_type\": \"gallery\", \"limit\": 3}}}" https://mcp-statcan-odcaf.onrender.com/sse
\`\`\`

**Expected Result:** A list of 3 facilities with \`odcaf_facility_type: gallery\` and \`city: montreal\`.

### Test B: Query by Province (e.g., 2 Museums in Alberta)

\`\`\`bash
# Command to find 2 museums in Alberta
curl --max-time 60 -X POST -H "Content-Type: application/json" -d "{\"event\": \"mcp.tool.invoke\", \"id\": \"test_query_B\", \"data\": {\"tool_id\": \"query_facilities\", \"parameters\": {\"province\": \"Alberta\", \"facility_type\": \"Museum\", \"limit\": 2}}}" https://mcp-statcan-odcaf.onrender.com/sse
\`\`\`

**Expected Result:** A list of 2 facilities with \`odcaf_facility_type: museum\` and \`prov_terr: ab\` (or similar province code).

---

## 4. Guardrails Test (Over-broad Query)

This test verifies that the server enforces limits and returns a human-readable error when a query is too broad.

\`\`\`bash
# Command to test over-broad filter (no parameters provided)
curl --max-time 60 -X POST -H "Content-Type: application/json" -d "{\"event\": \"mcp.tool.invoke\", \"id\": \"test_guardrail\", \"data\": {\"tool_id\": \"query_facilities\", \"parameters\": {}}}" https://mcp-statcan-odcaf.onrender.com/sse
\`\`\`

**Expected Result:** A response with \`event: mcp.tool.invoke.result\` and the \`result\` containing the error message: \`"Your filter is too broad; try adding province, city, or facility_type."\`
EOF
