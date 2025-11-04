import aiosqlite

DB_FILE = 'odcaf.db'


async def get_db_connection():
    conn = await aiosqlite.connect(DB_FILE)
    conn.row_factory = aiosqlite.Row
    return conn


# --- HERRAMIENTA 'search' REQUERIDA POR LA DOCUMENTACIÓN ---
async def search_tool(query: str, limit: int = 5):
    conn = await get_db_connection()
    sql_query = """
    SELECT facility_name, odcaf_facility_type, city, prov_terr 
    FROM facilities 
    WHERE LOWER(TRIM(facility_name)) LIKE ? 
       OR LOWER(TRIM(odcaf_facility_type)) LIKE ? 
       OR LOWER(TRIM(city)) LIKE ?
       OR LOWER(TRIM(prov_terr)) LIKE ?
    LIMIT ?
    """
    search_term = f"%{query.lower().strip()}%"
    params = (search_term, search_term, search_term, search_term, limit)

    try:
        cursor = await conn.cursor()
        await cursor.execute(sql_query, params)
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            return {"error": "No results found for that query."}

        # Formatear la respuesta como lo pide la documentación oficial
        results = []
        for row in rows:
            results.append({
                # La documentación pide un 'id', usaremos el nombre como id
                "id": row['facility_name'],
                "content": [
                    {"type": "text",
                     "text": f"{row['facility_name']} ({row['odcaf_facility_type']}) in {row['city']}, {row['prov_terr']}"}
                ]
            })
        return results  # La documentación espera una lista de resultados

    except Exception as e:
        conn.close()
        return {"error": f"Query failed: {str(e)}"}


# --- HERRAMIENTA 'fetch' REQUERIDA POR LA DOCUMENTACIÓN ---
async def fetch_tool(facility_id: str):
    conn = await get_db_connection()
    # Usamos el 'id' (que definimos como el nombre) para buscar
    query = "SELECT * FROM facilities WHERE LOWER(TRIM(facility_name)) = ? LIMIT 1"

    try:
        cursor = await conn.cursor()
        await cursor.execute(query, (facility_id.lower().strip(),))
        row = await cursor.fetchone()
        await conn.close()

        if not row:
            return {"error": "Facility not found by that exact name/id."}

        # Formatear la respuesta como lo pide la documentación oficial
        return {
            "id": row['facility_name'],
            "content": [
                {"type": "text", "text": f"Name: {row['facility_name']}"},
                {"type": "text", "text": f"Type: {row['odcaf_facility_type']}"},
                {"type": "text", "text": f"Location: {row['city']}, {row['prov_terr']}"},
                {"type": "text", "text": f"Address: {row['street_no']} {row['street_name']}, {row['postal_code']}"},
                {"type": "text", "text": f"Provider: {row['provider']}"}
            ]
        }
    except Exception as e:
        conn.close()
        return {"error": f"Query failed: {str(e)}"}


# --- MANTENEMOS LAS HERRAMIENTAS ANTIGUAS PARA TUS PRUEBAS 'curl' ---
async def get_schema_tool():
    conn = await get_db_connection()
    cursor = await conn.cursor()
    await cursor.execute("PRAGMA table_info(facilities)")
    rows = await cursor.fetchall()
    await conn.close()
    schema = {}
    for row in rows:
        schema[row['name']] = row['type']
    return schema


async def query_facilities_tool(province=None, city=None, facility_type=None, limit=5):
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
    query += " LIMIT ?"
    params.append(limit)
    cursor = await conn.cursor()
    await cursor.execute(query, tuple(params))
    rows = await cursor.fetchall()
    await conn.close()
    if not rows:
        return {"error": "No results found for the specified filters."}
    return [dict(row) for row in rows]