import aiosqlite

DB_FILE = 'odcaf.db'


async def get_db_connection():
    conn = await aiosqlite.connect(DB_FILE)
    conn.row_factory = aiosqlite.Row
    return conn


async def get_schema_tool():
    try:
        conn = await get_db_connection()
        cursor = await conn.cursor()

        await cursor.execute("PRAGMA table_info(facilities)")
        rows = await cursor.fetchall()

        await conn.close()

        schema = {}
        for row in rows:
            schema[row['name']] = row['type']

        if not schema:
            return {"error": "Could not find 'facilities' table. Did ingest.py run successfully?"}

        return schema
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def query_facilities_tool(province=None, city=None, facility_type=None, limit=5):
    try:
        conn = await get_db_connection()

        query = "SELECT facility_name, odcaf_facility_type, city, prov_terr FROM facilities WHERE 1=1"
        params = []

        if province:
            query += " AND LOWER(TRIM(prov_terr)) LIKE ?"
            params.append(f"%{province.lower()}%")

        if city:
            query += " AND LOWER(TRIM(city)) LIKE ?"
            params.append(f"%{city.lower()}%")

        if facility_type:
            query += " AND LOWER(TRIM(odcaf_facility_type)) LIKE ?"
            params.append(f"%{facility_type.lower()}%")

        try:
            limit_int = int(limit)
        except ValueError:
            limit_int = 5

        query += " LIMIT ?"
        params.append(limit_int)

        cursor = await conn.cursor()
        await cursor.execute(query, tuple(params))
        rows = await cursor.fetchall()
        await conn.close()

        results = [dict(row) for row in rows]

        if not results:
            return {"message": "No results found for the specified filters."}

        return results
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}