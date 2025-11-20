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

MUSEUM_ALIASES = [
    "museum",
    "art gallery",
    "gallery",
    "art or cultural centre",
    "heritage or historic site",
    "interpretive centre",
    "heritage centre"
]

PROVINCE_MAP = {
    "british columbia": "bc",
    "bc": "bc",
    "ontario": "on",
    "on": "on",
    "quebec": "qc",
    "québec": "qc",
    "qc": "qc",
    "alberta": "ab",
    "ab": "ab",
    "manitoba": "mb",
    "mb": "mb",
    "saskatchewan": "sk",
    "sk": "sk",
    "nova scotia": "ns",
    "ns": "ns",
    "new brunswick": "nb",
    "nb": "nb",
    "newfoundland": "nl",
    "nl": "nl",
    "prince edward island": "pe",
    "pei": "pe",
    "pe": "pe",
    "yukon": "yt",
    "yt": "yt",
    "nunavut": "nu",
    "nu": "nu",
    "northwest territories": "nt",
    "nt": "nt"
}

def facility_type_matches(user_type: str, db_value: str) -> bool:
    if not user_type:
        return True
    u = normalize_text(user_type)
    d = normalize_text(db_value)
    if u == "museum" and d in [normalize_text(x) for x in MUSEUM_ALIASES]:
        return True
    return u in d

async def get_db_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_FILE)
    conn.row_factory = aiosqlite.Row
    return conn

async def get_schema() -> Dict[str, str]:
    conn = await get_db_connection()
    c = await conn.cursor()
    await c.execute("PRAGMA table_info(facilities)")
    rows = await c.fetchall()
    schema = {row["name"]: row["type"] for row in rows}
    await conn.close()
    return schema

async def list_cities() -> List[str]:
    conn = await get_db_connection()
    c = await conn.cursor()
    await c.execute("SELECT DISTINCT City FROM facilities")
    rows = await c.fetchall()
    await conn.close()
    return sorted([row["City"] for row in rows if row["City"]])

async def list_facility_types() -> List[str]:
    conn = await get_db_connection()
    c = await conn.cursor()
    await c.execute("SELECT DISTINCT ODCAF_Facility_Type FROM facilities")
    rows = await c.fetchall()
    await conn.close()
    return sorted([row["ODCAF_Facility_Type"] for row in rows if row["ODCAF_Facility_Type"]])

async def fetch_facility_by_id(facility_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_db_connection()
    c = await conn.cursor()
    norm = normalize_text(facility_id)
    sql = """
        SELECT *
        FROM facilities
        WHERE LOWER(REPLACE(REPLACE(REPLACE(Facility_Name, '-', ' '), '.', ' '), '''', ' ')) = ?
        LIMIT 1
    """
    await c.execute(sql, (norm,))
    row = await c.fetchone()
    await conn.close()
    if row:
        return dict(row)
    return None

async def search_facilities(query_text: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = await get_db_connection()
    c = await conn.cursor()
    norm = normalize_text(query_text)
    tokens = norm.split()

    base_sql = "SELECT * FROM facilities WHERE 1=1"
    params = []

    for token in tokens:
        like = f"%{token}%"
        base_sql += """
            AND (
                LOWER(REPLACE(REPLACE(REPLACE(City, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
                OR LOWER(REPLACE(REPLACE(REPLACE(Facility_Name, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
                OR LOWER(REPLACE(REPLACE(REPLACE(ODCAF_Facility_Type, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
            )
        """
        params.extend([like, like, like])

    base_sql += " LIMIT ?"
    params.append(limit)

    await c.execute(base_sql, tuple(params))
    rows = await c.fetchall()
    await conn.close()
    return [dict(row) for row in rows]

async def query_facilities(
    province: Optional[str] = None,
    city: Optional[str] = None,
    facility_type: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    MUSEUM_ALIASES = [
        "museum",
        "gallery",
        "art or cultural centre",
        "heritage or historic site",
        "library or archives",
        "miscellaneous"
    ]

    PROVINCE_MAP = {
        "british columbia": "bc",
        "bc": "bc",
        "ontario": "on",
        "on": "on",
        "quebec": "qc",
        "québec": "qc",
        "qc": "qc",
        "alberta": "ab",
        "ab": "ab",
        "manitoba": "mb",
        "mb": "mb",
        "saskatchewan": "sk",
        "sk": "sk",
        "nova scotia": "ns",
        "ns": "ns",
        "new brunswick": "nb",
        "nb": "nb",
        "newfoundland": "nl",
        "nl": "nl",
        "prince edward island": "pe",
        "pei": "pe",
        "pe": "pe",
        "yukon": "yt",
        "yt": "yt",
        "nunavut": "nu",
        "nu": "nu",
        "northwest territories": "nt",
        "nt": "nt"
    }

    if city:
        nc = normalize_text(city)
        if nc == "montreal" and province is None:
            province = "Quebec"

    conn = await get_db_connection()
    c = await conn.cursor()

    sql = "SELECT * FROM facilities WHERE 1=1"
    params = []

    if province:
        p = normalize_text(province)
        mapped = PROVINCE_MAP.get(p, p)
        sql += " AND LOWER(Prov_Terr) = ?"
        params.append(mapped)

    if city:
        norm_city = normalize_text(city)
        like_city = f"%{norm_city}%"
        sql += """
            AND (
                LOWER(REPLACE(REPLACE(REPLACE(City, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
                OR LOWER(REPLACE(REPLACE(REPLACE(CSD_Name, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
                OR LOWER(REPLACE(REPLACE(REPLACE(Provider, '-', ' '), '.', ' '), '''', ' ')) LIKE ?
            )
        """
        params.extend([like_city, like_city, like_city])

    if facility_type:
        norm_type = normalize_text(facility_type)
        if norm_type == "museum":
            alias_norm = [normalize_text(x) for x in MUSEUM_ALIASES]
            placeholders = ",".join(["?"] * len(alias_norm))
            sql += f" AND LOWER(ODCAF_Facility_Type) IN ({placeholders})"
            params.extend(alias_norm)
        else:
            sql += " AND LOWER(ODCAF_Facility_Type) LIKE ?"
            params.append(f"%{norm_type}%")

    prelimit = 5000 if facility_type else 1000
    sql += " LIMIT ?"
    params.append(prelimit)

    await c.execute(sql, tuple(params))
    rows = await c.fetchall()
    await conn.close()

    results = []
    for row in rows:
        results.append(dict(row))
        if len(results) >= limit:
            break

    return results


