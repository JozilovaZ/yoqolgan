"""Testlar uchun umumiy sozlamalar: har bir test alohida bo'sh bazada, Telegram API soxta (tests/fakes.py)."""
import os
import sys

# config import qilinishidan OLDIN: .env dagi haqiqiy qiymatlar (token, to'lov va h.k.) testlarga ta'sir qilmasin.
# load_dotenv() mavjud o'zgaruvchilarni almashtirmaydi.
os.environ.update(
    BOT_TOKEN="123:test",
    ADMIN_GROUP_ID="-1001",
    CHANNEL_ID="-1002",
    CHANNEL_LINK="https://t.me/test_kanal",
    ADMIN_USERNAME="@admin",
    SERVICE_FEE="50000",
    FINDER_SHARE="50",
    CARD_NUMBER="8600 0000 0000 0000",
    CARD_OWNER="Test",
    PAYMENT_PROVIDER_TOKEN="",
    AUTO_PUBLISH="true",
    AUTO_VERIFY_DOCUMENTS="true",
    BACKUP_CHAT_ID="",
    BACKUP_HOUR="3",
    WEBHOOK_URL="",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import alerts  # noqa: E402
import database as db  # noqa: E402
import verify  # noqa: E402
from tests.fakes import Telegram  # noqa: E402


@pytest.fixture(autouse=True)
async def fresh_db(tmp_path, monkeypatch):
    """Har bir test uchun yangi bo'sh baza va toza xotira holati."""
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    alerts._last_sent.clear()
    verify._running.clear()
    await db.init_db()
    return path


@pytest.fixture
def tg():
    return Telegram()
