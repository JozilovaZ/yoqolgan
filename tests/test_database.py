"""Baza: eski bazadan ko'chish (migratsiyalar) va shaxsiy ma'lumotlarni tozalash."""
import sqlite3

import database as db
from tests.fakes import make_claim, make_item

OLD_SCHEMA = """
CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, finder_id INTEGER NOT NULL, finder_name TEXT,
  finder_username TEXT, finder_phone TEXT, finder_card TEXT, category TEXT NOT NULL, photo_id TEXT NOT NULL,
  region TEXT, place TEXT, found_date TEXT, description TEXT, status TEXT NOT NULL DEFAULT 'pending',
  publish_mode TEXT, channel_msg_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE claims (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, owner_id INTEGER NOT NULL,
  owner_name TEXT, owner_username TEXT, owner_phone TEXT, proof TEXT, receipt_photo_id TEXT,
  status TEXT NOT NULL DEFAULT 'checking', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
INSERT INTO items (finder_id, category, photo_id, status) VALUES (20, 'phone', 'p', 'returned');
INSERT INTO claims (item_id, owner_id, status) VALUES (1, 30, 'completed');
INSERT INTO claims (item_id, owner_id, status) VALUES (1, 31, 'awaiting_payment');
"""


def sql(path, query, *params):
    with sqlite3.connect(path) as con:
        con.execute(query, params)


async def test_migration_from_first_version(tmp_path, monkeypatch):
    """Birinchi versiyadagi baza: yangi ustunlar qo'shiladi, eski yakunlangan murojaat suyunchisi to'xtamaydi."""
    path = str(tmp_path / "old.db")
    with sqlite3.connect(path) as con:
        con.executescript(OLD_SCHEMA)
    monkeypatch.setattr(db, "DB_PATH", path)

    await db.init_db()
    completed, waiting = await db.get_claim(1), await db.get_claim(2)
    assert completed["handover"] == "confirmed" and completed["completed_at"]
    assert waiting["handover"] is None  # faqat yakunlanganlar
    assert [row["claim_id"] for row in await db.list_unpaid_payouts()] == [1]

    # Qayta ishga tushirish: migratsiyalar xatosiz o'tadi, bir martalik belgilash takrorlanmaydi
    await db.update_claim(1, handover="refunded")
    await db.init_db()
    assert (await db.get_claim(1))["handover"] == "refunded"


async def test_close_item_removes_ocr_text_immediately():
    item = await make_item(category="passport", ocr_text="TOSHMATOV AA1234567")
    await db.close_item(item["id"], "returned")
    item = await db.get_item(item["id"])
    assert item["ocr_text"] is None and item["closed_at"] and item["finder_card"]  # karta suyunchi uchun qoladi


async def test_purge_counts_from_closing_day(fresh_db):
    item = await make_item(status="published")
    claim = await make_claim(item["id"])
    await db.update_claim(claim["id"], status="completed")
    await db.close_item(item["id"], "returned")
    report_id = await db.create_lost_report({"owner_id": 5, "category": "phone", "lost_day": "2026-01-01",
                                             "status": "closed"})
    open_item = await make_item()

    # E'lon 200 kun oldin berilgan, lekin kecha yopilgan — hali o'chmaydi (suyunchi o'tkazilmagan bo'lishi mumkin)
    sql(fresh_db, "UPDATE items SET created_at = datetime('now', '-200 days') WHERE id = ?", item["id"])
    await db.purge_personal_data(90)
    assert (await db.get_item(item["id"]))["finder_card"]

    sql(fresh_db, "UPDATE items SET closed_at = datetime('now', '-91 days') WHERE id = ?", item["id"])
    sql(fresh_db, "UPDATE claims SET created_at = datetime('now', '-91 days') WHERE id = ?", claim["id"])
    sql(fresh_db, "UPDATE lost_reports SET created_at = datetime('now', '-91 days') WHERE id = ?", report_id)
    counts = await db.purge_personal_data(90)
    assert counts == {"items": 1, "claims": 1, "lost_reports": 1}

    item, claim = await db.get_item(item["id"]), await db.get_claim(claim["id"])
    assert item["finder_phone"] is None and item["finder_card"] is None and item["photo_id"] == ""
    assert claim["proof"] is None and claim["owner_phone"] is None
    assert await db.get_lost_report(report_id) is None
    assert (await db.get_item(open_item["id"]))["finder_phone"]  # ochiq e'longa tegilmaydi


async def test_meta_survives_restart():
    await db.set_meta("last_backup", "2026-10-15")
    await db.init_db()
    assert await db.get_meta("last_backup") == "2026-10-15"
    assert await db.get_meta("yoq") is None
