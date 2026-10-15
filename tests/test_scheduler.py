"""Fon vazifalari: to'lov eslatmalari, admin eslatmalari, qidiruv muddati (scheduler.py)."""
import sqlite3

import database as db
import scheduler
from config import ADMIN_GROUP_ID
from tests.fakes import make_claim, make_item

OWNER = 30


def shift(path, table, column, row_id, hours):
    """Vaqtni "o'tkazish": ustundagi sanani `hours` soat orqaga suradi."""
    with sqlite3.connect(path) as con:
        con.execute(f"UPDATE {table} SET {column} = datetime('now', ?) WHERE id = ?", (f"-{hours} hours", row_id))


async def approved_claim():
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    return claim["id"]


async def test_payment_reminder_once_then_expire(tg, fresh_db):
    claim_id = await approved_claim()
    await scheduler.remind_unpaid_claims(tg.bot)
    assert not tg.calls  # hali erta

    shift(fresh_db, "claims", "approved_at", claim_id, 25)
    await scheduler.remind_unpaid_claims(tg.bot)
    assert "Eslatma" in tg.texts(OWNER)[0] and "24 soat" in tg.texts(OWNER)[0]
    tg.calls.clear()
    await scheduler.remind_unpaid_claims(tg.bot)
    assert not tg.calls  # ikkinchi marta eslatilmaydi

    shift(fresh_db, "claims", "approved_at", claim_id, 49)
    await scheduler.expire_unpaid_claims(tg.bot)
    assert (await db.get_claim(claim_id))["status"] == "expired"
    assert tg.texts(OWNER) and tg.admin
    assert await db.get_open_claim(OWNER, (await db.get_claim(claim_id))["item_id"]) is None  # qayta murojaat mumkin


async def test_time_counts_from_approval_not_creation(tg, fresh_db):
    claim_id = await approved_claim()
    shift(fresh_db, "claims", "created_at", claim_id, 100)  # murojaat eski, lekin hozir tasdiqlangan
    await scheduler.expire_unpaid_claims(tg.bot)
    await scheduler.remind_unpaid_claims(tg.bot)
    assert not tg.calls and (await db.get_claim(claim_id))["status"] == "awaiting_payment"


async def test_admin_reminder_counts_from_receipt(tg, fresh_db):
    claim_id = await approved_claim()
    shift(fresh_db, "claims", "approved_at", claim_id, 10)
    await db.save_receipt(claim_id, "RECEIPT")
    await scheduler.remind_admins(tg.bot)
    assert not tg.calls  # chek hozirgina keldi

    shift(fresh_db, "claims", "receipt_at", claim_id, 4)
    item = await make_item()
    checking = await make_claim(item["id"])
    shift(fresh_db, "claims", "created_at", checking["id"], 4)
    await scheduler.remind_admins(tg.bot)
    assert len(tg.admin) == 1 and f"№{claim_id}" in tg.admin[0] and f"№{checking['id']}" in tg.admin[0]
    tg.calls.clear()
    await scheduler.remind_admins(tg.bot)
    assert not tg.calls


async def test_outdated_lost_reports_closed(tg):
    old = await db.create_lost_report({"owner_id": 5, "category": "phone", "lost_day": "2025-01-01"})
    fresh = await db.create_lost_report({"owner_id": 6, "category": "phone", "lost_day": "2099-01-01"})
    await scheduler.close_outdated_lost_reports(tg.bot)
    assert (await db.get_lost_report(old))["status"] == "closed"
    assert (await db.get_lost_report(fresh))["status"] == "active"
    assert [call.chat_id for call in tg.sent()] == [5]


async def test_failing_job_is_reported_and_others_continue(tg, monkeypatch):
    async def broken(bot):
        raise RuntimeError("baza qulf")

    called = []

    async def healthy(bot):
        called.append(True)

    async def stop(seconds):
        raise SystemExit  # bitta aylanishdan keyin to'xtatamiz

    monkeypatch.setattr(scheduler, "JOBS", [broken, healthy])
    monkeypatch.setattr(scheduler.asyncio, "sleep", stop)
    try:
        await scheduler.run_scheduler(tg.bot)
    except SystemExit:
        pass
    assert called, "xato bergan vazifadan keyingisi ham ishlashi kerak"
    report = tg.texts(ADMIN_GROUP_ID)[0]
    assert "fon vazifasi: broken" in report and "baza qulf" in report
