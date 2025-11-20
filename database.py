import aiosqlite
import unicodedata
from typing import List, Dict, Any, Optional

DB_FILE = "odcaf.db"

def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("-", " ").replace("'", " ").replace(".", " ")
    return " ".join(text.split())

async def get_db_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_FILE)
    conn.row_factory = aiosqlite.Row
    return conn

async def get_schema() -> Dict[str, str]:
    conn = await get_db_connection()
    cursor = await conn.cursor()
    await cursor.execute("PRAGMA table_info(facilities)")
    rows = await cursor.fetchall()
    schema = {row["name"]: row["type"] for row in rows}
    await conn.close()
    return schema

async def list_cities() -> List[str]:
    conn = await get_db_connection()
    cursor = await conn.cursor()
    await cursor.execute("SELECT DISTINCT city FROM facilities")
    rows = await cursor.fetchall()
    await conn.close()
    return sorted([row["city"] for row in rows if row["city"]])

async def list_facility_types() -> List[str]:
    conn = await get_db_connection()
    cursor = await conn.cursor()
    await cursor.execute("SELECT DISTINCT odcaf_facility_type FROM facilities")
    rows = await cursor.fetchall()
    await conn.close()
    return sorted([row["odcaf_facility_type"] for row in rows if row["odcaf_facility_type"]])

MUSEUM_ALIASES = [
    "museum",
    "heritage centre",
    "interpretive centre",
    "art gallery",
    "cultural centre",
    "art or cultural centre"
]

def facility_type_matches(facility_type: str, db_value: str) -> bool:
    if not facility_type:
        return True
    norm_user = normalize_text(facility_type)
    norm_db = normalize_text(db_value)
    if norm_user == "museum" and norm_db in [normalize_text(x) for x in MUSEUM_ALIASES]:
        return True
    return norm_user in norm_db

async def search_facilities(query_text: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = await get_db_connection()
    cursor = await conn.cursor()
    norm = normalize_text(query_text)
    sql = """
        SELECT *
        FROM facilities
        WHERE LOWER(REPLACE(REPLACE(REPLACE(city, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
           OR LOWER(REPLACE(REPLACE(REPLACE(facility_name, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
           OR LOWER(REPLACE(REPLACE(REPLACE(odcaf_facility_type, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
        LIMIT ?
    """
    like = f"%{norm}%"
    await cursor.execute(sql, (like, like, like, limit))
    rows = await cursor.fetchall()
    await conn.close()
    return [dict(row) for row in rows]

async def fetch_facility_by_id(facility_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_db_connection()
    cursor = await conn.cursor()
    norm = normalize_text(facility_id)
    sql = """
        SELECT *
        FROM facilities
        WHERE LOWER(REPLACE(REPLACE(REPLACE(facility_name, '-', ' '), '.', ' '), '''', ' ')) = ?
        LIMIT 1
    """
    await cursor.execute(sql, (norm,))
    row = await cursor.fetchone()
    await conn.close()
    if row:
        return dict(row)
    return None

async def query_facilities(
    province: Optional[str] = None,
    city: Optional[str] = None,
    facility_type: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    conn = await get_db_connection()
    cursor = await conn.cursor()
    sql = "SELECT * FROM facilities WHERE 1=1"
    params = []

    if province:
        sql += " AND LOWER(prov_terr) LIKE ?"
        params.append(f"%{normalize_text(province)}%")

    if city:
        sql += " AND LOWER(REPLACE(REPLACE(REPLACE(city, '-', ' '), '.', ' '), '''', ' ')) LIKE ?"
        params.append(f"%{normalize_text(city)}%")

    await cursor.execute(sql)
    rows = await cursor.fetchall()
    filtered = []
    for row in rows:
        if facility_type_matches(facility_type, row["odcaf_facility_type"]):
            filtered.append(dict(row))
            if len(filtered) >= limit:
                break

    await conn.close()
    return filtered
