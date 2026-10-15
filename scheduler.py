"""Fonda muntazam ishlaydigan vazifalar: eslatmalar, muddati o'tganlarni yopish, eski ma'lumotlarni tozalash."""
import asyncio
import logging

from aiogram import Bot

import database as db
from config import (
    ADMIN_GROUP_ID,
    ADMIN_REMIND_HOURS,
    DATA_RETENTION_DAYS,
    PAYMENT_EXPIRE_HOURS,
    PAYMENT_REMIND_HOURS,
)
from keyboards import BTN_LOST
from matching import MATCH_DAYS
from services import request_payment
from utils import category_label, item_code, lost_code, safe_send

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 15 * 60  # soniya


async def expire_unpaid_claims(bot: Bot) -> None:
    """Tasdiqlangan, lekin muddatida to'lanmagan murojaatlar yopiladi — narsa boshqalar uchun yana ochiq."""
    for claim in await db.list_unpaid_claims(PAYMENT_EXPIRE_HOURS):
        await db.update_claim(claim["id"], status="expired")
        code = item_code(claim["item_id"])
        await safe_send(
            bot,
            claim["owner_id"],
            f"⌛ #{code} bo'yicha murojaatingiz {PAYMENT_EXPIRE_HOURS} soat ichida to'lov qilinmagani uchun yopildi.\n\n"
            "Narsa hali egasini kutayotgan bo'lsa, kanaldagi <b>«🙋 Bu meniki»</b> tugmasini qaytadan bosishingiz mumkin.",
        )
        await safe_send(
            bot, ADMIN_GROUP_ID, f"⌛ Murojaat №{claim['id']} (#{code}) to'lov qilinmagani uchun avtomatik yopildi."
        )
        logger.info("Murojaat №%s muddati o'tdi", claim["id"])


async def remind_unpaid_claims(bot: Bot) -> None:
    left = PAYMENT_EXPIRE_HOURS - PAYMENT_REMIND_HOURS
    for claim in await db.list_unpaid_claims(PAYMENT_REMIND_HOURS, only_not_reminded=True):
        await db.update_claim(claim["id"], owner_reminded=1)
        item = await db.get_item(claim["item_id"])
        if item["status"] != "published":
            continue  # narsa boshqa egaga qaytarilgan — to'lov endi kerak emas
        intro = (
            f"⏰ <b>Eslatma:</b> #{item_code(item['id'])} — {category_label(item['category'])} uchun to'lov hali qilinmagan.\n"
            f"Taxminan <b>{left} soat</b> ichida to'lanmasa, murojaat yopiladi.\n\n"
        )
        await request_payment(bot, claim, item, intro=intro)


async def remind_admins(bot: Bot) -> None:
    """Uzoq vaqt ko'rib chiqilmagan murojaatlar — bitta umumiy xabar."""
    claims = await db.list_stale_claims(ADMIN_REMIND_HOURS)
    if not claims:
        return
    labels = {"checking": "egasini tekshirish", "payment_review": "to'lov chekini tekshirish"}
    lines = [
        f"• Murojaat №{claim['id']} (#{item_code(claim['item_id'])}) — {labels[claim['status']]}" for claim in claims
    ]
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        f"⏳ <b>{ADMIN_REMIND_HOURS} soatdan beri javob kutayotgan murojaatlar:</b>\n\n"
        + "\n".join(lines)
        + "\n\nGuruhda «murojaat №» deb qidirib toping 🔎",
    )
    for claim in claims:
        await db.update_claim(claim["id"], admin_reminded=1)


async def close_outdated_lost_reports(bot: Bot) -> None:
    """Yo'qotilganiga MATCH_DAYS kun bo'lgan qidiruvlarga endi mos narsa chiqmaydi — yopiladi."""
    for report in await db.list_outdated_lost_reports(MATCH_DAYS):
        await db.update_lost_report(report["id"], status="closed")
        await safe_send(
            bot,
            report["owner_id"],
            f"⌛ #{lost_code(report['id'])} — {category_label(report['category'])} qidiruvingiz muddati tugadi "
            f"({MATCH_DAYS} kun).\n\nNarsangiz hali topilmagan bo'lsa, <b>«{BTN_LOST}»</b> bo'limida yangi e'lon qoldiring.",
        )


async def purge_personal_data(bot: Bot) -> None:
    counts = await db.purge_personal_data(DATA_RETENTION_DAYS)
    if any(counts.values()):
        logger.info("Eski shaxsiy ma'lumotlar tozalandi: %s", counts)


# Tartib muhim: avval muddati o'tganlar yopiladi, keyin eslatma — yopiladigan murojaatga eslatma bormasin
JOBS = [expire_unpaid_claims, remind_unpaid_claims, remind_admins, close_outdated_lost_reports, purge_personal_data]


async def run_scheduler(bot: Bot) -> None:
    while True:
        for job in JOBS:
            try:
                await job(bot)
            except Exception:  # bitta vazifadagi xato boshqalarini to'xtatmasin
                logger.exception("Fon vazifasi xato berdi: %s", job.__name__)
        await asyncio.sleep(CHECK_INTERVAL)
