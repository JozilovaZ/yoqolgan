import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    username TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finder_id INTEGER NOT NULL,
    finder_name TEXT,
    finder_username TEXT,
    finder_phone TEXT,
    finder_card TEXT,
    category TEXT NOT NULL,
    photo_id TEXT NOT NULL,
    region TEXT,
    place TEXT,
    latitude REAL,
    longitude REAL,
    found_date TEXT,
    description TEXT,
    -- pending | published | rejected | removed | returned
    status TEXT NOT NULL DEFAULT 'pending',
    -- photo | text
    publish_mode TEXT,
    channel_msg_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    owner_id INTEGER NOT NULL,
    owner_name TEXT,
    owner_username TEXT,
    owner_phone TEXT,
    proof TEXT,
    receipt_photo_id TEXT,
    -- checking | rejected | awaiting_payment | payment_review | completed
    status TEXT NOT NULL DEFAULT 'checking',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lost_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    owner_name TEXT,
    owner_username TEXT,
    category TEXT NOT NULL,
    region TEXT,
    place TEXT,
    lost_day TEXT,  -- YYYY-MM-DD
    description TEXT,
    -- active | closed
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


# Eski bazaga yangi ustunlarni qo'shish (ustun bor bo'lsa xato beradi — e'tiborsiz qoldiramiz)
MIGRATIONS = [
    "ALTER TABLE items ADD COLUMN latitude REAL",
    "ALTER TABLE items ADD COLUMN longitude REAL",
]


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        for migration in MIGRATIONS:
            try:
                await db.execute(migration)
            except aiosqlite.OperationalError:
                pass
        await db.commit()


async def _execute(query: str, params: tuple = ()) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.lastrowid


async def _fetchone(query: str, params: tuple = ()) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def _fetchall(query: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def _insert(table: str, data: dict) -> int:
    columns = ", ".join(data)
    placeholders = ", ".join("?" for _ in data)
    return await _execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(data.values()))


def _set_clause(fields: dict) -> tuple[str, tuple]:
    return ", ".join(f"{key} = ?" for key in fields), tuple(fields.values())


# ---------- users ----------

async def save_user(user_id: int, full_name: str, username: str | None) -> None:
    await _execute(
        "INSERT INTO users (user_id, full_name, username) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET full_name = excluded.full_name, username = excluded.username",
        (user_id, full_name, username),
    )


# ---------- items ----------

async def create_item(data: dict) -> int:
    return await _insert("items", data)


async def get_item(item_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM items WHERE id = ?", (item_id,))


async def update_item(item_id: int, **fields) -> None:
    clause, params = _set_clause(fields)
    await _execute(f"UPDATE items SET {clause} WHERE id = ?", params + (item_id,))


async def list_pending() -> list[dict]:
    return await _fetchall("SELECT * FROM items WHERE status = 'pending' ORDER BY id")


async def list_published(category: str, limit: int = 10) -> list[dict]:
    return await _fetchall(
        "SELECT * FROM items WHERE status = 'published' AND category = ? ORDER BY id DESC LIMIT ?",
        (category, limit),
    )


# ---------- claims ----------

async def create_claim(data: dict) -> int:
    return await _insert("claims", data)


async def get_claim(claim_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM claims WHERE id = ?", (claim_id,))


async def update_claim(claim_id: int, **fields) -> None:
    clause, params = _set_clause(fields)
    await _execute(f"UPDATE claims SET {clause} WHERE id = ?", params + (claim_id,))


async def get_open_claim(owner_id: int, item_id: int) -> dict | None:
    return await _fetchone(
        "SELECT * FROM claims WHERE owner_id = ? AND item_id = ? "
        "AND status NOT IN ('rejected', 'completed') ORDER BY id DESC LIMIT 1",
        (owner_id, item_id),
    )


async def get_claim_awaiting_payment(owner_id: int) -> dict | None:
    return await _fetchone(
        "SELECT * FROM claims WHERE owner_id = ? AND status = 'awaiting_payment' ORDER BY id DESC LIMIT 1",
        (owner_id,),
    )


# ---------- yo'qotilgan narsalar ----------

async def create_lost_report(data: dict) -> int:
    return await _insert("lost_reports", data)


async def get_lost_report(report_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM lost_reports WHERE id = ?", (report_id,))


async def update_lost_report(report_id: int, **fields) -> None:
    clause, params = _set_clause(fields)
    await _execute(f"UPDATE lost_reports SET {clause} WHERE id = ?", params + (report_id,))


async def list_user_lost_reports(owner_id: int) -> list[dict]:
    return await _fetchall(
        "SELECT * FROM lost_reports WHERE owner_id = ? AND status = 'active' ORDER BY id",
        (owner_id,),
    )


async def list_active_lost_reports(category: str) -> list[dict]:
    return await _fetchall(
        "SELECT * FROM lost_reports WHERE category = ? AND status = 'active' ORDER BY id",
        (category,),
    )


async def close_owner_lost_reports(owner_id: int, category: str) -> None:
    await _execute(
        "UPDATE lost_reports SET status = 'closed' WHERE owner_id = ? AND category = ? AND status = 'active'",
        (owner_id, category),
    )


# ---------- statistika ----------

async def get_stats() -> dict:
    row = await _fetchone(
        """
        SELECT
            (SELECT COUNT(*) FROM users) AS users,
            (SELECT COUNT(*) FROM items) AS items,
            (SELECT COUNT(*) FROM items WHERE status = 'pending') AS pending,
            (SELECT COUNT(*) FROM items WHERE status = 'published') AS published,
            (SELECT COUNT(*) FROM items WHERE status = 'returned') AS returned,
            (SELECT COUNT(*) FROM claims WHERE status IN ('checking', 'payment_review')) AS waiting_claims,
            (SELECT COUNT(*) FROM lost_reports WHERE status = 'active') AS lost_active
        """
    )
    return row or {}
