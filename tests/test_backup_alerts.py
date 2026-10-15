"""Bazaning zaxirasi (backup.py) va xatolar haqida adminga xabar (alerts.py)."""
import gzip
import sqlite3

import database as db
import scheduler
from aiogram.methods import SendDocument
from config import ADMIN_GROUP_ID
from tests.fakes import make_item


async def test_backup_is_valid_database(tg, tmp_path):
    item = await make_item()
    await tg.send("/backup")
    document = tg.to(ADMIN_GROUP_ID, SendDocument)[0]
    assert document.document.filename.endswith(".db.gz") and "Baza zaxirasi" in document.caption

    restored = tmp_path / "restored.db"
    restored.write_bytes(gzip.decompress(document.document.data))
    with sqlite3.connect(restored) as con:
        assert con.execute("SELECT finder_phone FROM items WHERE id = ?", (item["id"],)).fetchone()[0]


async def test_daily_backup_once_per_day(tg, monkeypatch):
    monkeypatch.setattr(scheduler, "BACKUP_HOUR", 0)
    await scheduler.daily_backup(tg.bot)
    assert len(tg.sent(SendDocument)) == 1
    tg.calls.clear()
    await scheduler.daily_backup(tg.bot)
    assert not tg.calls  # bugun allaqachon yuborilgan (sana bazada — qayta ishga tushsa ham)
    assert await db.get_meta("last_backup")


async def test_daily_backup_waits_for_hour_and_can_be_disabled(tg, monkeypatch):
    monkeypatch.setattr(scheduler, "BACKUP_HOUR", 25)  # hali vaqti kelmagan
    await scheduler.daily_backup(tg.bot)
    monkeypatch.setattr(scheduler, "BACKUP_HOUR", 0)
    monkeypatch.setattr(scheduler, "BACKUP_CHAT_ID", None)  # BACKUP_CHAT_ID=off
    await scheduler.daily_backup(tg.bot)
    assert not tg.calls


async def test_unexpected_error_reported_to_admin_and_user(tg, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("disk toldi")

    monkeypatch.setattr(db, "save_user", broken)
    await tg.send("/start", user_id=30)
    report = [text for text in tg.admin if "Botda xato" in text]
    assert report and "disk toldi" in report[0] and "foydalanuvchi 30" in report[0]
    assert "test_backup_alerts.py:" in report[0]  # xato chiqqan qator
    assert "Kutilmagan xatolik" in tg.texts(30)[0]  # foydalanuvchi javobsiz qolmadi

    # Bir xil xato qayta-qayta takrorlansa — admin guruh to'lib ketmaydi
    await tg.send("/start", user_id=31)
    assert not [text for text in tg.admin if "Botda xato" in text]
    assert tg.texts(31)  # foydalanuvchiga baribir javob
