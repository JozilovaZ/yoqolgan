"""Statistika (/stats): davr tugmalari, solishtirish, grafik — matn va grafik raqamlari bir xil."""
import random
import sqlite3

import database as db
from aiogram.methods import SendPhoto
from charts import daily_chart
from tests.fakes import buttons


def fill_random_history(path):
    """60 kunlik tasodifiy tarix: e'lonlar, qaytarilganlar, to'lovlar."""
    rng = random.Random(7)
    with sqlite3.connect(path) as con:
        for day in range(60):
            for _ in range(rng.randint(0, 4)):
                returned = rng.random() < 0.45 and day > 0
                cursor = con.execute(
                    "INSERT INTO items (finder_id, category, photo_id, region, status, created_at, closed_at) "
                    "VALUES (1, ?, 'p', ?, ?, datetime('now', ?), CASE WHEN ? THEN datetime('now', ?) END)",
                    (rng.choice(["phone", "wallet", "passport"]), rng.choice(["Toshkent", "Samarqand"]),
                     "returned" if returned else "published", f"-{day} days", returned,
                     f"-{max(day - rng.randint(0, 3), 0)} days"),
                )
                if returned:
                    con.execute("INSERT INTO claims (item_id, owner_id, status, handover) "
                                "VALUES (?, 2, 'completed', 'confirmed')", (cursor.lastrowid,))


async def test_text_and_chart_numbers_match(fresh_db):
    fill_random_history(fresh_db)
    rows = await db.daily_counts(30)
    assert len(rows) == 30
    for period, days in (("week", 7), ("month", 30)):
        stats = await db.get_period_stats(period)
        assert stats["items"] == sum(row["items"] for row in rows[-days:]), period
        assert stats["returned"] == sum(row["returned"] for row in rows[-days:]), period
    png = daily_chart(rows, "Oxirgi 30 kun")
    assert png.startswith(b"\x89PNG")
    assert daily_chart([{**row, "items": 0, "returned": 0} for row in rows], "Bo'sh").startswith(b"\x89PNG")


async def test_stats_tabs_and_chart(tg, fresh_db):
    fill_random_history(fresh_db)
    await tg.send("/stats")
    text = tg.last_text()
    assert "Statistika — 7 kun" in text and "oldingi 7 kunga nisbatan" in text and len(text) < 4096
    assert buttons(tg.sent()[-1]) == ["st:today", "st:week", "st:month", "st:all", "st:chart", "st:week"]

    await tg.press("st:today")
    assert "Statistika — Bugun" in tg.edits()[0] and "kechaga nisbatan" in tg.edits()[0]
    await tg.press("st:all")
    assert "Statistika — Jami" in tg.edits()[0] and "nisbatan" not in tg.edits()[0]
    await tg.press("st:chart")
    assert tg.sent(SendPhoto)[0].photo.filename == "statistika.png"


async def test_attention_marks(tg):
    await db.create_item({"finder_id": 1, "category": "phone", "photo_id": "p"})  # kanalga chiqmagan
    await tg.send("/stats")
    assert "⚠️ ⏳ Kanalga chiqmagan: 1 → /pending" in tg.last_text()
    assert "/payouts" not in tg.last_text()  # suyunchi qarzi yo'q
