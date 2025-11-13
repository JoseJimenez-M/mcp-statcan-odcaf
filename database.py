import aiosqlite
from typing import List, Dict, Any, Optional

DB_FILE = "odcaf.db"


async def get_db_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_FILE)
    conn.row_factory = aiosqlite.Row
    return conn


async def get_schema() -> Dict[str, str]:
    conn = await get_db_connection()
    try:
        cursor = await conn.cursor()
        await cursor.execute("PRAGMA table_info(facilities)")
        rows = await cursor.fetchall()
        schema: Dict[str, str] = {}
        for row in rows:
            schema[row["name"]] = row["type"]
        return schema
    finally:
        await conn.close()


async def query_facilities(
    province: Optional[str] = None,
    city: Optional[str] = None,
    facility_type: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        query = "SELECT facility_name, odcaf_facility_type, city, prov_terr FROM facilities WHERE 1=1"
        params: List[Any] = []
        if province:
            query += " AND LOWER(TRIM(prov_terr)) LIKE ?"
            params.append(f"%{province.lower().strip()}%")
        if city:
            query += " AND LOWER(TRIM(city)) LIKE ?"
            params.append(f"%{city.lower().strip()}%")
        if facility_type:
            query += " AND LOWER(TRIM(odcaf_facility_type)) LIKE ?"
            params.append(f"%{facility_type.lower().strip()}%")
        query += " LIMIT ?"
        params.append(limit)
        cursor = await conn.cursor()
        await cursor.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def search_facilities(query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        sql_query = (
            "SELECT facility_name, odcaf_facility_type, city, prov_terr "
            "FROM facilities "
            "WHERE LOWER(TRIM(facility_name)) LIKE ? "
            "OR LOWER(TRIM(odcaf_facility_type)) LIKE ? "
            "OR LOWER(TRIM(city)) LIKE ? "
            "OR LOWER(TRIM(prov_terr)) LIKE ? "
            "LIMIT ?"
        )
        search_term = f"%{query_text.lower().strip()}%"
        params = (search_term, search_term, search_term, search_term, limit)
        cursor = await conn.cursor()
        await cursor.execute(sql_query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def fetch_facility_by_id(facility_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        query = "SELECT * FROM facilities WHERE LOWER(TRIM(facility_name)) = ? LIMIT 1"
        cursor = await conn.cursor()
        await cursor.execute(query, (facility_id.lower().strip(),))
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        await conn.close()
