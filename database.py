from datetime import date, timedelta

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
    -- checking | rejected | awaiting_payment | payment_review | completed | expired
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
    "ALTER TABLE items ADD COLUMN ocr_text TEXT",
    "ALTER TABLE claims ADD COLUMN payment_charge_id TEXT",
    "ALTER TABLE items ADD COLUMN closed_at TEXT",
    "ALTER TABLE claims ADD COLUMN approved_at TEXT",
    "ALTER TABLE claims ADD COLUMN owner_reminded INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE claims ADD COLUMN admin_reminded INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE claims ADD COLUMN receipt_at TEXT",
    "ALTER TABLE claims ADD COLUMN payout_at TEXT",
    "ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0",
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


async def _rowcount(query: str, params: tuple = ()) -> int:
    """UPDATE/DELETE: nechta qator o'zgardi."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.rowcount


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


async def get_user(user_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))


async def find_user_by_username(username: str) -> dict | None:
    return await _fetchone("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.lstrip("@"),))


async def set_banned(user_id: int, banned: bool) -> None:
    await _execute(
        "INSERT INTO users (user_id, banned) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET banned = excluded.banned",
        (user_id, int(banned)),
    )


async def is_banned(user_id: int) -> bool:
    return await _fetchone("SELECT 1 FROM users WHERE user_id = ? AND banned = 1", (user_id,)) is not None


async def list_broadcast_users() -> list[int]:
    return [row["user_id"] for row in await _fetchall("SELECT user_id FROM users WHERE banned = 0")]


# ---------- items ----------

async def create_item(data: dict) -> int:
    return await _insert("items", data)


async def get_item(item_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM items WHERE id = ?", (item_id,))


async def update_item(item_id: int, **fields) -> None:
    clause, params = _set_clause(fields)
    await _execute(f"UPDATE items SET {clause} WHERE id = ?", params + (item_id,))


async def close_item(item_id: int, status: str) -> None:
    """returned | removed | rejected. OCR matni (ism, hujjat raqami) endi kerak emas — darhol o'chiriladi."""
    await _execute(
        "UPDATE items SET status = ?, closed_at = CURRENT_TIMESTAMP, ocr_text = NULL WHERE id = ?",
        (status, item_id),
    )


async def list_user_items(user_id: int, limit: int = 10) -> list[dict]:
    return await _fetchall("SELECT * FROM items WHERE finder_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))


async def find_items_by_phone(digits: str, limit: int = 10) -> list[dict]:
    """digits — raqamning oxirgi 9 ta raqami (+998 bilan ham, usiz ham topiladi)."""
    return await _fetchall(
        "SELECT * FROM items WHERE REPLACE(REPLACE(finder_phone, '+', ''), ' ', '') LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{digits}", limit),
    )


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


async def approve_claim(claim_id: int) -> None:
    await _execute(
        "UPDATE claims SET status = 'awaiting_payment', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (claim_id,),
    )


async def list_item_claims(item_id: int) -> list[dict]:
    return await _fetchall("SELECT * FROM claims WHERE item_id = ? ORDER BY id", (item_id,))


async def list_user_claims(user_id: int, limit: int = 10) -> list[dict]:
    return await _fetchall("SELECT * FROM claims WHERE owner_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))


async def find_claims_by_phone(digits: str, limit: int = 10) -> list[dict]:
    return await _fetchall(
        "SELECT * FROM claims WHERE REPLACE(REPLACE(owner_phone, '+', ''), ' ', '') LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{digits}", limit),
    )


async def close_open_claims(item_id: int) -> list[dict]:
    """E'lon qo'lda yopilganda: hali tugallanmagan murojaatlar rad etiladi. Ular qaytariladi (xabar berish uchun)."""
    claims = await _fetchall(
        "SELECT * FROM claims WHERE item_id = ? AND status IN ('checking', 'awaiting_payment', 'payment_review')",
        (item_id,),
    )
    for claim in claims:
        await update_claim(claim["id"], status="rejected")
    return claims


async def mark_payout(claim_id: int) -> bool:
    """Suyunchi o'tkazildi. False — allaqachon belgilangan yoki murojaat yakunlanmagan."""
    changed = await _rowcount(
        "UPDATE claims SET payout_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'completed' AND payout_at IS NULL",
        (claim_id,),
    )
    return changed > 0


async def list_unpaid_payouts() -> list[dict]:
    """To'lov qilingan, lekin topuvchiga suyunchi hali o'tkazilmagan murojaatlar (e'lon ma'lumotlari bilan)."""
    return await _fetchall(
        "SELECT c.id AS claim_id, c.created_at AS claim_created_at, i.* FROM claims c "
        "JOIN items i ON i.id = c.item_id WHERE c.status = 'completed' AND c.payout_at IS NULL ORDER BY c.id"
    )


async def save_receipt(claim_id: int, photo_id: str) -> None:
    await _execute(
        "UPDATE claims SET status = 'payment_review', receipt_photo_id = ?, receipt_at = CURRENT_TIMESTAMP, "
        "admin_reminded = 0 WHERE id = ?",
        (photo_id, claim_id),
    )


async def get_open_claim(owner_id: int, item_id: int) -> dict | None:
    return await _fetchone(
        "SELECT * FROM claims WHERE owner_id = ? AND item_id = ? "
        "AND status IN ('checking', 'awaiting_payment', 'payment_review') ORDER BY id DESC LIMIT 1",
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


# ---------- fon vazifalari (scheduler.py) ----------

def _ago(hours: float) -> str:
    """SQLite uchun: datetime('now', '-24 hours')."""
    return f"-{hours} hours"


async def list_unpaid_claims(hours: float, only_not_reminded: bool = False) -> list[dict]:
    """Tasdiqlanganiga `hours` soat bo'lgan, lekin to'lanmagan murojaatlar."""
    query = (
        "SELECT * FROM claims WHERE status = 'awaiting_payment' "
        "AND COALESCE(approved_at, created_at) <= datetime('now', ?)"
    )
    if only_not_reminded:
        query += " AND owner_reminded = 0"
    return await _fetchall(query + " ORDER BY id", (_ago(hours),))


async def list_stale_claims(hours: float) -> list[dict]:
    """Admin `hours` soatdan beri ko'rib chiqmagan murojaatlar (isbot yoki to'lov cheki)."""
    period = _ago(hours)
    return await _fetchall(
        "SELECT * FROM claims WHERE admin_reminded = 0 AND ("
        "(status = 'checking' AND created_at <= datetime('now', ?)) OR "
        "(status = 'payment_review' AND COALESCE(receipt_at, created_at) <= datetime('now', ?))"
        ") ORDER BY id",
        (period, period),
    )


async def list_outdated_lost_reports(days: int) -> list[dict]:
    return await _fetchall(
        "SELECT * FROM lost_reports WHERE status = 'active' AND lost_day <= date('now', ?) ORDER BY id",
        (f"-{days} days",),
    )


async def purge_personal_data(days: int) -> dict:
    """Yopilganiga `days` kun bo'lgan e'lon va murojaatlardan shaxsiy ma'lumotlarni o'chiradi."""
    period = (f"-{days} days",)
    async with aiosqlite.connect(DB_PATH) as db:
        items = await db.execute(
            "UPDATE items SET finder_phone = NULL, finder_card = NULL, ocr_text = NULL, photo_id = '' "
            "WHERE status IN ('returned', 'removed', 'rejected') AND photo_id != '' "
            "AND COALESCE(closed_at, created_at) <= datetime('now', ?)",
            period,
        )
        claims = await db.execute(
            "UPDATE claims SET owner_phone = NULL, proof = NULL, receipt_photo_id = NULL "
            "WHERE status IN ('completed', 'rejected', 'expired') AND proof IS NOT NULL "
            "AND created_at <= datetime('now', ?)",
            period,
        )
        reports = await db.execute(
            "DELETE FROM lost_reports WHERE status = 'closed' AND created_at <= datetime('now', ?)", period
        )
        await db.commit()
        return {"items": items.rowcount, "claims": claims.rowcount, "lost_reports": reports.rowcount}


# ---------- statistika ----------

async def get_stats() -> dict:
    """Hozirgi holat."""
    row = await _fetchone(
        """
        SELECT
            (SELECT COUNT(*) FROM users) AS users,
            (SELECT COUNT(*) FROM users WHERE banned = 1) AS banned,
            (SELECT COUNT(*) FROM items WHERE status = 'pending') AS pending,
            (SELECT COUNT(*) FROM items WHERE status = 'published') AS published,
            (SELECT COUNT(*) FROM claims WHERE status IN ('checking', 'payment_review')) AS waiting_claims,
            (SELECT COUNT(*) FROM claims WHERE status = 'awaiting_payment') AS awaiting_payment,
            (SELECT COUNT(*) FROM claims WHERE status = 'completed' AND payout_at IS NULL) AS unpaid_payouts,
            (SELECT COUNT(*) FROM lost_reports WHERE status = 'active') AS lost_active
        """
    )
    return row or {}


# Davr: (boshlanishi, oldingi davr boshlanishi) — mahalliy vaqt bo'yicha, bazadagi UTC ga o'girilgan.
# "7 kun" — bugun va oldingi 6 kalendar kun (grafik bilan bir xil hisoblanadi).
# Oldingi davr solishtirish uchun: "bugun" — kecha bilan, "7 kun" — undan oldingi 7 kun bilan
PERIODS = {
    "today": ("datetime('now', 'localtime', 'start of day', 'utc')",
              "datetime('now', 'localtime', 'start of day', '-1 day', 'utc')"),
    "week": ("datetime('now', 'localtime', 'start of day', '-6 days', 'utc')",
             "datetime('now', 'localtime', 'start of day', '-13 days', 'utc')"),
    "month": ("datetime('now', 'localtime', 'start of day', '-29 days', 'utc')",
              "datetime('now', 'localtime', 'start of day', '-59 days', 'utc')"),
    "all": ("'0000-00-00'", None),
}


def _period_range(period: str, previous: bool) -> tuple[str, str]:
    start, previous_start = PERIODS[period]
    return (previous_start, start) if previous else (start, "'9999-12-31'")


async def get_period_stats(period: str, previous: bool = False) -> dict | None:
    """previous=True — oldingi davr (solishtirish uchun). "Jami" uchun oldingi davr yo'q — None."""
    if previous and PERIODS[period][1] is None:
        return None
    since, until = _period_range(period, previous)

    def between(column: str) -> str:
        return f"{column} >= {since} AND {column} < {until}"

    row = await _fetchone(
        f"""
        SELECT
            (SELECT COUNT(*) FROM users WHERE {between("created_at")}) AS users,
            (SELECT COUNT(*) FROM items WHERE {between("created_at")}) AS items,
            (SELECT COUNT(*) FROM items WHERE status = 'returned'
                AND {between("COALESCE(closed_at, created_at)")}) AS returned,
            (SELECT COUNT(*) FROM claims WHERE {between("created_at")}) AS claims,
            (SELECT COUNT(*) FROM claims c JOIN items i ON i.id = c.item_id
                WHERE c.status = 'completed' AND {between("COALESCE(i.closed_at, c.created_at)")}) AS paid,
            (SELECT COUNT(*) FROM lost_reports WHERE {between("created_at")}) AS lost_reports
        """
    )
    return row or {}


async def top_values(column: str, period: str, limit: int = 5) -> list[dict]:
    """Davr ichida eng ko'p uchragan turlar yoki hududlar."""
    assert column in ("category", "region")
    since, until = _period_range(period, previous=False)
    return await _fetchall(
        f"SELECT {column} AS value, COUNT(*) AS count FROM items "
        f"WHERE created_at >= {since} AND created_at < {until} AND COALESCE({column}, '') != '' "
        f"GROUP BY {column} ORDER BY count DESC LIMIT ?",
        (limit,),
    )


async def daily_counts(days: int) -> list[dict]:
    """Oxirgi `days` kun (mahalliy sana bo'yicha): har kuni berilgan va qaytarilgan e'lonlar.
    Bo'sh kunlar ham qaytariladi (0 bilan)."""
    since = f"datetime('now', 'localtime', 'start of day', '-{days - 1} days', 'utc')"
    created = await _fetchall(
        f"SELECT date(created_at, 'localtime') AS day, COUNT(*) AS count FROM items "
        f"WHERE created_at >= {since} GROUP BY day"
    )
    returned = await _fetchall(
        f"SELECT date(COALESCE(closed_at, created_at), 'localtime') AS day, COUNT(*) AS count FROM items "
        f"WHERE status = 'returned' AND COALESCE(closed_at, created_at) >= {since} GROUP BY day"
    )
    today = await _fetchone("SELECT date('now', 'localtime') AS day")
    created_by_day = {row["day"]: row["count"] for row in created}
    returned_by_day = {row["day"]: row["count"] for row in returned}

    last = date.fromisoformat(today["day"])
    result = []
    for offset in range(days - 1, -1, -1):
        day = (last - timedelta(days=offset)).isoformat()
        result.append({"day": day, "items": created_by_day.get(day, 0), "returned": returned_by_day.get(day, 0)})
    return result


async def export_table(table: str) -> list[dict]:
    assert table in ("items", "claims", "lost_reports", "users")
    return await _fetchall(f"SELECT * FROM {table} ORDER BY 1")
