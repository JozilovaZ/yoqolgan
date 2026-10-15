"""Onlayn to'lov (Telegram Payments: Click / Payme). To'lov tushishi bilan ikki tomon avtomatik bog'lanadi."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.types import Message, PreCheckoutQuery

import database as db
from config import ADMIN_GROUP_ID, ADMIN_USERNAME, SERVICE_FEE
from i18n import t
from keyboards import main_menu
from services import complete_claim
from utils import item_code, money, safe_send, user_link

logger = logging.getLogger(__name__)

router = Router()


async def _claim_from_payload(payload: str) -> dict | None:
    """Invoice payload: "claim:15"."""
    prefix, _, claim_id = payload.partition(":")
    if prefix != "claim" or not claim_id.isdigit():
        return None
    return await db.get_claim(int(claim_id))


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, lang: str):
    """To'lovdan oldingi oxirgi tekshiruv: Telegram 10 soniya ichida javob kutadi."""
    claim = await _claim_from_payload(query.invoice_payload)
    error = None
    if not claim or claim["owner_id"] != query.from_user.id or claim["status"] != "awaiting_payment":
        error = t("pay.err_inactive", lang)
    elif (await db.get_item(claim["item_id"]))["status"] != "published":
        error = t("pay.err_returned", lang)
    elif query.total_amount != SERVICE_FEE * 100:
        error = t("pay.err_fee", lang)
    await query.answer(ok=error is None, error_message=error)


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot, lang: str):
    payment = message.successful_payment
    charge_id = payment.provider_payment_charge_id or payment.telegram_payment_charge_id
    claim = await _claim_from_payload(payment.invoice_payload)
    if not claim:
        logger.error("To'lov keldi, lekin murojaat topilmadi: %s (%s)", payment.invoice_payload, charge_id)
        await safe_send(
            bot,
            ADMIN_GROUP_ID,
            f"⚠️ <b>Noma'lum to'lov</b>: {money(payment.total_amount // 100)} so'm\n"
            f"Kimdan: {user_link(message.from_user.id, message.from_user.full_name, message.from_user.username)}\n"
            f"To'lov ID: <code>{escape(charge_id)}</code>",
        )
        return

    await db.update_claim(claim["id"], payment_charge_id=charge_id)
    item = await db.get_item(claim["item_id"])

    # Tekshiruv bilan to'lov orasida holat o'zgargan bo'lishi mumkin (masalan, admin bekor qildi)
    if claim["status"] != "awaiting_payment" or item["status"] != "published":
        logger.warning("Murojaat №%s: to'lov keldi, lekin holat %s", claim["id"], claim["status"])
        await safe_send(
            bot,
            ADMIN_GROUP_ID,
            f"⚠️ <b>Pulni qaytarish kerak!</b> | murojaat №{claim['id']}, #{item_code(item['id'])}\n\n"
            f"To'lov tushdi, lekin murojaat endi faol emas.\n"
            f"Kimga: {user_link(claim['owner_id'], claim['owner_name'], claim['owner_username'])}\n"
            f"📞 {escape(claim['owner_phone'] or '')}\n"
            f"Summa: {money(payment.total_amount // 100)} so'm\n"
            f"To'lov ID: <code>{escape(charge_id)}</code>",
        )
        text = t("pay.refund_notice", lang)
        if ADMIN_USERNAME:
            text += "\n" + t("common.questions", lang, admin=ADMIN_USERNAME)
        await message.answer(text, reply_markup=main_menu(lang))
        return

    await complete_claim(bot, claim, item, charge_id=charge_id)
