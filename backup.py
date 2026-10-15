"""Bazaning zaxira nusxasi: izchil nusxa (SQLite backup API) -> gzip -> Telegram'ga fayl."""
import asyncio
import gzip
import logging
import os
import sqlite3
import tempfile
from datetime import datetime

from aiogram import Bot
from aiogram.types import BufferedInputFile

import database as db
from config import BACKUP_CHAT_ID

logger = logging.getLogger(__name__)


def _snapshot(path: str) -> bytes:
    """Bot ishlab turganda ham izchil nusxa (yozilayotgan tranzaksiya yarim qolmaydi)."""
    with tempfile.TemporaryDirectory() as folder:
        copy_path = os.path.join(folder, "copy.db")
        source, target = sqlite3.connect(path), sqlite3.connect(copy_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        with open(copy_path, "rb") as file:
            return gzip.compress(file.read())


async def send_backup(bot: Bot, chat_id: int | str | None = None) -> None:
    """Xato bo'lsa — exception (chaqiruvchi xabar beradi)."""
    data = await asyncio.to_thread(_snapshot, db.DB_PATH)
    stats = await db.get_period_stats("all")
    now = datetime.now()
    await bot.send_document(
        chat_id or BACKUP_CHAT_ID,
        BufferedInputFile(data, filename=f"izla-backup-{now:%Y-%m-%d-%H%M}.db.gz"),
        caption=(
            f"💾 <b>Baza zaxirasi</b> — {now:%d.%m.%Y %H:%M}\n"
            f"📦 E'lonlar: {stats['items']} · 🙋 Murojaatlar: {stats['claims']} · 👥 Foydalanuvchilar: {stats['users']}\n"
            f"Hajmi: {len(data) / 1024:.0f} KB\n\n"
            "⚠️ Ichida shaxsiy ma'lumotlar bor — tashqariga yubormang.\n"
            "Tiklash: DEPLOY.md → «Zaxiradan tiklash»"
        ),
    )
    logger.info("Zaxira yuborildi: %d KB", len(data) // 1024)
