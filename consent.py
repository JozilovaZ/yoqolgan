"""Ommaviy oferta (OFERTA.md): matnni Telegram uchun tayyorlash va foydalanuvchi roziligini tekshirish."""
import os
import re
from html import escape

from aiogram.types import Message

import database as db
from config import (
    ADMIN_USERNAME,
    DATA_RETENTION_DAYS,
    FINDER_SHARE,
    HANDOVER_ASK_HOURS,
    HANDOVER_ESCALATE_HOURS,
    OFFER_URL,
    PAYMENT_EXPIRE_HOURS,
    SERVICE_FEE,
)
from i18n import t
from keyboards import terms_kb
from utils import money

OFFER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OFERTA.md")
TELEGRAM_LIMIT = 4000  # xabar chegarasi 4096, zaxira bilan

# Ruscha tarjima. "Tahrir:" sanasi OFERTA.md dagidan olinadi — matnni o'zgartirsangiz, ikkalasini ham yangilang
OFFER_PATHS = {"uz": OFFER_PATH, "ru": OFFER_PATH.replace("OFERTA.md", "OFERTA_RU.md")}


def summary(lang: str = "uz") -> str:
    return t("terms.summary", lang, fee=money(SERVICE_FEE), share=FINDER_SHARE, days=DATA_RETENTION_DAYS)


def _read(lang: str = "uz") -> str:
    with open(OFFER_PATHS.get(lang, OFFER_PATH), encoding="utf-8") as file:
        return file.read()


def offer_version() -> str:
    """Birinchi qatordagi "Tahrir: 2026-10-15". O'zgarsa — hammadan rozilik qaytadan so'raladi."""
    match = re.match(r"Tahrir:\s*(\S+)", _read())
    return match.group(1) if match else "1"


OFFER_VERSION = offer_version()


def offer_pages(lang: str = "uz") -> list[str]:
    """Oferta matni Telegram HTML ko'rinishida, 4096 belgidan oshmaydigan bo'laklarga bo'lingan."""
    text = _read(lang).format(
        fee=money(SERVICE_FEE),
        share_percent=FINDER_SHARE,
        share_amount=money(SERVICE_FEE * FINDER_SHARE // 100),
        expire_hours=PAYMENT_EXPIRE_HOURS,
        handover_hours=HANDOVER_ASK_HOURS + HANDOVER_ESCALATE_HOURS,
        retention_days=DATA_RETENTION_DAYS,
        admin=ADMIN_USERNAME or t("terms.via_bot", lang),
    )
    lines = []
    for line in text.splitlines():
        if line.startswith(("Tahrir:", "Редакция:")):
            lines.append(f"<i>{escape(line, quote=False)}</i>")
        elif line.startswith("#"):
            lines.append(f"<b>{escape(line.lstrip('# '), quote=False)}</b>")
        else:
            # Matndagi <b>...</b> qoladi, qolgan hamma narsa ekranlanadi
            lines.append(escape(line, quote=False).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>"))

    pages, current = [], ""
    for block in "\n".join(lines).split("\n\n"):  # bo'limlar orasida bo'lamiz
        if current and len(current) + len(block) + 2 > TELEGRAM_LIMIT:
            pages.append(current.strip())
            current = ""
        current += block + "\n\n"
    if current.strip():
        pages.append(current.strip())
    return pages


async def require_terms(message: Message, user_id: int, action: str, lang: str = "uz") -> bool:
    """True — rozilik bor, davom etish mumkin.
    False — rozilik so'raldi; "Roziman" bosilgach `action` (found / claim_15 / lostsub_phone) avtomatik davom etadi."""
    if await db.has_accepted_terms(user_id, OFFER_VERSION):
        return True
    await message.answer(summary(lang), reply_markup=terms_kb(action, OFFER_URL, lang))
    return False
