"""Fonda muntazam ishlaydigan vazifalar: eslatmalar, muddati o'tganlarni yopish, eski ma'lumotlarni tozalash."""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot

import database as db
import instagram
from alerts import report_error
from backup import send_backup
from config import (
    ADMIN_GROUP_ID,
    ADMIN_REMIND_HOURS,
    BACKUP_CHAT_ID,
    BACKUP_HOUR,
    DATA_RETENTION_DAYS,
    HANDOVER_ASK_HOURS,
    HANDOVER_ESCALATE_HOURS,
    PAYMENT_EXPIRE_HOURS,
    PAYMENT_REMIND_HOURS,
)
from i18n import t, user_lang
from keyboards import handover_kb
from matching import MATCH_DAYS
from services import report_dispute, request_payment
from utils import category_label, item_code, lost_code, safe_send

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 15 * 60  # soniya


async def expire_unpaid_claims(bot: Bot) -> None:
    """Tasdiqlangan, lekin muddatida to'lanmagan murojaatlar yopiladi — narsa boshqalar uchun yana ochiq."""
    for claim in await db.list_unpaid_claims(PAYMENT_EXPIRE_HOURS):
        await db.update_claim(claim["id"], status="expired")
        code = item_code(claim["item_id"])
        lang = await user_lang(claim["owner_id"])
        await safe_send(bot, claim["owner_id"], t("sch.expired", lang, code=code, hours=PAYMENT_EXPIRE_HOURS))
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
        lang = await user_lang(claim["owner_id"])
        intro = t("sch.remind", lang, code=item_code(item["id"]), category=category_label(item["category"], lang), left=left)
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


async def ask_handover(bot: Bot) -> None:
    """To'lovdan HANDOVER_ASK_HOURS o'tdi, egasi hali "oldim" demadi — ikkala tomondan so'raymiz."""
    for claim in await db.list_handovers_to_ask(HANDOVER_ASK_HOURS):
        await db.mark_handover_asked(claim["id"])
        item = await db.get_item(claim["item_id"])
        code = item_code(item["id"])
        if not claim["owner_answer"]:
            lang = await user_lang(claim["owner_id"])
            await safe_send(
                bot,
                claim["owner_id"],
                t("sch.ask_owner", lang, code=code, category=category_label(item["category"], lang)),
                reply_markup=handover_kb(claim["id"], "o", lang),
            )
        if not claim["finder_answer"]:
            lang = await user_lang(item["finder_id"])
            await safe_send(
                bot, item["finder_id"], t("sch.ask_finder", lang, code=code), reply_markup=handover_kb(claim["id"], "f", lang)
            )


async def escalate_handover(bot: Bot) -> None:
    """So'raldi, lekin egasi baribir javob bermadi — admin hal qiladi."""
    hours = HANDOVER_ASK_HOURS + HANDOVER_ESCALATE_HOURS
    for claim in await db.list_handovers_to_escalate(HANDOVER_ESCALATE_HOURS):
        await db.update_claim(claim["id"], handover_escalated=1)
        await report_dispute(bot, claim["id"], f"⏳ Egasi narsani olganini {hours} soatdan beri tasdiqlamadi.")


async def close_outdated_lost_reports(bot: Bot) -> None:
    """Yo'qotilganiga MATCH_DAYS kun bo'lgan qidiruvlarga endi mos narsa chiqmaydi — yopiladi."""
    for report in await db.list_outdated_lost_reports(MATCH_DAYS):
        await db.update_lost_report(report["id"], status="closed")
        lang = await user_lang(report["owner_id"])
        await safe_send(
            bot,
            report["owner_id"],
            t(
                "sch.search_expired",
                lang,
                code=lost_code(report["id"]),
                category=category_label(report["category"], lang),
                days=MATCH_DAYS,
                button=t("btn.lost", lang),
            ),
        )


async def daily_backup(bot: Bot) -> None:
    """Kuniga bir marta, BACKUP_HOUR dan keyin. Sana bazada saqlanadi — qayta ishga tushsa takrorlanmaydi."""
    now = datetime.now()
    if not BACKUP_CHAT_ID or now.hour < BACKUP_HOUR or await db.get_meta("last_backup") == now.date().isoformat():
        return
    await send_backup(bot)
    await db.set_meta("last_backup", now.date().isoformat())


async def purge_personal_data(bot: Bot) -> None:
    counts = await db.purge_personal_data(DATA_RETENTION_DAYS)
    if any(counts.values()):
        logger.info("Eski shaxsiy ma'lumotlar tozalandi: %s", counts)


# Tartib muhim: avval muddati o'tganlar yopiladi, keyin eslatma — yopiladigan murojaatga eslatma bormasin.
# Xuddi shunday: avval adminga xabar (escalate), keyin so'rash — so'rov va xabar bir vaqtda ketmasin
JOBS = [
    expire_unpaid_claims,
    remind_unpaid_claims,
    remind_admins,
    escalate_handover,
    ask_handover,
    close_outdated_lost_reports,
    purge_personal_data,
    daily_backup,
    instagram.process_queue,  # joylanmay qolganlar (limit, tarmoq xatosi) qayta uriniladi
]


async def run_scheduler(bot: Bot) -> None:
    while True:
        for job in JOBS:
            try:
                await job(bot)
            except Exception as error:  # bitta vazifadagi xato boshqalarini to'xtatmasin
                logger.exception("Fon vazifasi xato berdi: %s", job.__name__)
                await report_error(bot, f"fon vazifasi: {job.__name__}", error)
        await asyncio.sleep(CHECK_INTERVAL)
