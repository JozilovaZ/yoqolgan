"""Admin guruhdagi tugmalar: e'lonni chiqarish, egasini tasdiqlash, to'lovni tasdiqlash."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import database as db
import instagram
from config import ADMIN_GROUP_ID, ADMIN_USERNAME, CHANNEL_ID
from i18n import t, user_lang
from keyboards import moderation_kb, published_kb
from services import complete_claim, post_link, publish_item, request_payment
from utils import item_code, item_details, safe_send

logger = logging.getLogger(__name__)

router = Router()
# Tugmalarni faqat admin guruh a'zolari bosa oladi
router.callback_query.filter(F.message.chat.id == ADMIN_GROUP_ID)


@router.message(Command("id"))
async def cmd_id(message: Message):
    """Sozlash uchun: guruh va foydalanuvchi ID sini bilib olish."""
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>\nSizning ID: <code>{message.from_user.id}</code>")


async def _mark_done(callback: CallbackQuery, note: str):
    """Admin xabariga natijani yozib, tugmalarni olib tashlaydi."""
    who = escape(callback.from_user.full_name)
    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.html_text}\n\n{note} — <i>{who}</i>", reply_markup=None
        )
    except TelegramAPIError:
        await callback.message.edit_reply_markup(reply_markup=None)


# ---------- 1. Yangi e'lonni tekshirish ----------

@router.message(Command("pending"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_pending(message: Message):
    """Kanalga chiqmay qolgan e'lonlarni qayta ko'rsatadi."""
    items = await db.list_pending()
    if not items:
        await message.answer("✅ Tekshiruvda e'lon yo'q.")
        return
    for item in items:
        await message.answer_photo(
            item["photo_id"],
            caption="🆕 <b>E'LON — tekshiring</b>\n\n" + item_details(item),
            reply_markup=moderation_kb(item["id"]),
        )


@router.callback_query(F.data.startswith("mod:delete:"))
async def delete_item(callback: CallbackQuery, bot: Bot):
    item = await db.get_item(int(callback.data.split(":")[2]))
    if not item or item["status"] != "published":
        await callback.answer("Bu e'lon kanalda emas yoki allaqachon yopilgan", show_alert=True)
        return
    try:
        await bot.delete_message(CHANNEL_ID, item["channel_msg_id"])
    except TelegramAPIError as error:
        await callback.answer(f"Kanaldan o'chmadi: {error}", show_alert=True)
        return
    await db.close_item(item["id"], "removed")
    await _mark_done(callback, "🗑 Kanaldan o'chirildi" + instagram.removal_note(item))
    lang = await user_lang(item["finder_id"])
    await safe_send(bot, item["finder_id"], t("adm.removed", lang, code=item_code(item["id"])))
    await callback.answer("O'chirildi")


@router.callback_query(F.data.startswith("mod:"))
async def moderate_item(callback: CallbackQuery, bot: Bot):
    _, action, item_id = callback.data.split(":")
    item = await db.get_item(int(item_id))
    if not item or item["status"] != "pending":
        await callback.answer("Bu e'lon allaqachon ko'rib chiqilgan", show_alert=True)
        return

    code = item_code(item["id"])

    if action == "reject":
        await db.close_item(item["id"], "rejected")
        await _mark_done(callback, "❌ Rad etildi")
        await safe_send(bot, item["finder_id"], t("adm.rejected", await user_lang(item["finder_id"]), code=code))
        await callback.answer("Rad etildi")
        return

    try:
        message_id = await publish_item(bot, item, action)
    except Exception as error:  # Telegram xatosi yoki rasmni qayta ishlashdagi xato
        logger.error("Kanalga chiqmadi: %s", error)
        await callback.answer(f"Kanalga chiqmadi: {error}", show_alert=True)
        return

    mode_names = {"photo": "rasm bilan", "blur": "xira rasm bilan", "text": "rasmsiz"}
    await _mark_done(callback, f"📢 Kanalga chiqdi ({mode_names.get(action, action)})")
    await callback.message.edit_reply_markup(reply_markup=published_kb(item["id"]))
    text = t("adm.published", await user_lang(item["finder_id"]), code=code)
    if post_link(message_id):
        text += f"\n👉 {post_link(message_id)}"
    await safe_send(bot, item["finder_id"], text)
    await callback.answer("Kanalga chiqdi ✅")


# ---------- 2. Egasining isbotini tekshirish ----------

@router.callback_query(F.data.startswith("cl:undo:"))
async def undo_auto_approval(callback: CallbackQuery, bot: Bot):
    """OCR avtomatik tasdiqlagan murojaatni admin bekor qiladi (to'lovdan oldin)."""
    claim = await db.get_claim(int(callback.data.split(":")[2]))
    if not claim or claim["status"] != "awaiting_payment":
        await callback.answer("Bekor qilib bo'lmaydi: to'lov qilingan yoki murojaat yopilgan", show_alert=True)
        return
    await db.update_claim(claim["id"], status="rejected")
    await _mark_done(callback, "↩️ Avtomatik tasdiq bekor qilindi")
    lang = await user_lang(claim["owner_id"])
    text = t("adm.undo", lang, code=item_code(claim["item_id"]))
    if ADMIN_USERNAME:
        text += "\n" + t("common.if_mistake", lang, admin=ADMIN_USERNAME)
    await safe_send(bot, claim["owner_id"], text)
    await callback.answer("Bekor qilindi")


@router.callback_query(F.data.startswith("cl:"))
async def review_claim(callback: CallbackQuery, bot: Bot):
    _, action, claim_id = callback.data.split(":")
    claim = await db.get_claim(int(claim_id))
    if not claim or claim["status"] != "checking":
        await callback.answer("Bu murojaat allaqachon ko'rib chiqilgan", show_alert=True)
        return

    item = await db.get_item(claim["item_id"])
    code = item_code(item["id"])

    if action == "no" or item["status"] != "published":
        await db.update_claim(claim["id"], status="rejected")
        await _mark_done(callback, "❌ Rad etildi")
        lang = await user_lang(claim["owner_id"])
        text = t("adm.claim_rejected", lang, code=code)
        if ADMIN_USERNAME:
            text += "\n" + t("common.if_mistake", lang, admin=ADMIN_USERNAME)
        await safe_send(bot, claim["owner_id"], text)
        await callback.answer("Rad etildi")
        return

    await db.approve_claim(claim["id"])
    await _mark_done(callback, "✅ Egasi tasdiqlandi, to'lov kutilmoqda")
    await request_payment(bot, claim, item)
    await callback.answer("Tasdiqlandi ✅")


# ---------- 3. To'lov chekini tekshirish ----------

@router.callback_query(F.data.startswith("pay:"))
async def review_payment(callback: CallbackQuery, bot: Bot):
    _, action, claim_id = callback.data.split(":")
    claim = await db.get_claim(int(claim_id))
    if not claim or claim["status"] != "payment_review":
        await callback.answer("Bu to'lov allaqachon ko'rib chiqilgan", show_alert=True)
        return

    item = await db.get_item(claim["item_id"])
    code = item_code(item["id"])

    if action == "no":
        await db.update_claim(claim["id"], status="awaiting_payment", receipt_photo_id=None)
        await _mark_done(callback, "❌ To'lov topilmadi")
        lang = await user_lang(claim["owner_id"])
        text = t("adm.payment_missing", lang, code=code)
        if ADMIN_USERNAME:
            text += "\n" + t("common.questions", lang, admin=ADMIN_USERNAME)
        await safe_send(bot, claim["owner_id"], text)
        await callback.answer("Egasiga xabar berildi")
        return

    await _mark_done(callback, "✅ To'lov tasdiqlandi, ikki tomon bog'landi")
    await complete_claim(bot, claim, item)
    await callback.answer("Bog'landi ✅")
