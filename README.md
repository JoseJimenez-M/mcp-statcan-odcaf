\# MCP Server for Statistics Canada LODE Dataset (ODCAF)



This is a 48-hour challenge submission for DEV FORTRESS.



This project implements a Model Context Protocol (MCP) server that allows ChatGPT to interface with a Statistics Canada LODE dataset.



\## Live Server URL



The public, no-auth SSE endpoint is: 

`https://your-public-domain.com/sse` 

\*(Note: Replace this with your actual deployed URL)\*



\## Assigned Dataset



This server provides tools to query the following LODE dataset:



\* \*\*Dataset Name:\*\* The Open Database of Cultural and Art Facilities (ODCAF)

\* \*\*LODE Link:\*\* `https://www.statcan.gc.ca/en/lode/databases/odcaf`



\## Architecture and Implementation



This server is built in Python using \*\*FastAPI\*\* to provide the required HTTP/SSE endpoint.



To ensure fast query performance and reliability, the source `ODCAF\_v1.0.csv` file from Statistics Canada was pre-processed and ingested into a local \*\*SQLite\*\* database (`odcaf.db`). The server queries this SQLite database to respond to tool invocations.



\## Tools Exposed



The server exposes the following tools via MCP:



\* `get\_schema`: Provides the schema of the database table, including column names and data types.

\* `query\_facilities`: Allows querying for facilities with optional filters for `province`, `city`, and `facility\_type`.



\## License and Attribution



This project respects the dataset's attribution requirements. The data is provided under the \*\*Open Government Licence - Canada\*\*.



This server collects no PII, analytics, or tracking data.

