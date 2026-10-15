"""Admin guruhdagi tugmalar: e'lonni chiqarish, egasini tasdiqlash, to'lovni tasdiqlash."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message

import database as db
from config import ADMIN_GROUP_ID, ADMIN_USERNAME, CARD_NUMBER, CARD_OWNER, CHANNEL_ID, FINDER_SHARE, SERVICE_FEE
from keyboards import moderation_kb, published_kb
from services import post_link, publish_item
from utils import category_label, channel_post_text, item_code, item_details, money, safe_send, user_link

logger = logging.getLogger(__name__)

router = Router()
# Tugmalarni faqat admin guruh a'zolari bosa oladi
router.callback_query.filter(F.message.chat.id == ADMIN_GROUP_ID)


@router.message(Command("id"))
async def cmd_id(message: Message):
    """Sozlash uchun: guruh va foydalanuvchi ID sini bilib olish."""
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>\nSizning ID: <code>{message.from_user.id}</code>")


@router.message(Command("stats"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_stats(message: Message):
    s = await db.get_stats()
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {s['users']}\n"
        f"📦 Jami e'lonlar: {s['items']}\n"
        f"⏳ Tekshiruvda: {s['pending']}\n"
        f"📢 Kanalda: {s['published']}\n"
        f"✅ Egasiga qaytarilgan: {s['returned']}\n"
        f"🙋 Kutilayotgan murojaatlar: {s['waiting_claims']}\n"
        f"🔔 Faol qidiruvlar: {s['lost_active']}"
    )


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
    await db.update_item(item["id"], status="removed")
    await _mark_done(callback, "🗑 Kanaldan o'chirildi")
    await safe_send(bot, item["finder_id"], f"😔 #{item_code(item['id'])} e'loningiz admin tomonidan olib tashlandi.")
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
        await db.update_item(item["id"], status="rejected")
        await _mark_done(callback, "❌ Rad etildi")
        await safe_send(bot, item["finder_id"], f"😔 #{code} e'loningiz admin tomonidan rad etildi.")
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
    text = f"📢 #{code} e'loningiz kanalga chiqdi! Egasi topilsa, sizga darhol xabar beramiz."
    if post_link(message_id):
        text += f"\n👉 {post_link(message_id)}"
    await safe_send(bot, item["finder_id"], text)
    await callback.answer("Kanalga chiqdi ✅")


# ---------- 2. Egasining isbotini tekshirish ----------

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
        text = f"😔 #{code} e'loni bo'yicha murojaatingiz tasdiqlanmadi. Ma'lumotlar mos kelmadi."
        if ADMIN_USERNAME:
            text += f"\nXato deb o'ylasangiz: {ADMIN_USERNAME}"
        await safe_send(bot, claim["owner_id"], text)
        await callback.answer("Rad etildi")
        return

    await db.update_claim(claim["id"], status="awaiting_payment")
    await _mark_done(callback, "✅ Egasi tasdiqlandi, to'lov kutilmoqda")
    await safe_send(
        bot,
        claim["owner_id"],
        f"🎉 <b>Tabriklaymiz!</b> #{code} — {category_label(item['category'])} sizniki ekanligi tasdiqlandi.\n\n"
        f"Topuvchi bilan bog'lanish uchun xizmat haqini to'lang:\n\n"
        f"💰 Summa: <b>{money(SERVICE_FEE)} so'm</b>\n"
        f"💳 Karta: <code>{escape(CARD_NUMBER)}</code>\n"
        f"👤 {escape(CARD_OWNER)}\n\n"
        f"🎁 Shundan {FINDER_SHARE}% narsangizni topgan insonga suyunchi sifatida beriladi.\n\n"
        "📸 To'lovdan so'ng <b>chek skrinshotini shu yerga yuboring.</b>",
    )
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
        text = (
            f"⚠️ #{code} bo'yicha to'lovingiz topilmadi.\n"
            "Iltimos, to'lovni tekshirib, chekni qaytadan yuboring."
        )
        if ADMIN_USERNAME:
            text += f"\nSavollar uchun: {ADMIN_USERNAME}"
        await safe_send(bot, claim["owner_id"], text)
        await callback.answer("Egasiga xabar berildi")
        return

    await db.update_claim(claim["id"], status="completed")
    await db.update_item(item["id"], status="returned")
    await db.close_owner_lost_reports(claim["owner_id"], item["category"])
    share = SERVICE_FEE * FINDER_SHARE // 100

    # Egasiga topuvchining kontakti
    await safe_send(
        bot,
        claim["owner_id"],
        f"✅ <b>To'lov tasdiqlandi!</b>\n\n"
        f"#{code} — {category_label(item['category'])} topgan inson bilan bog'laning:\n\n"
        f"👤 {user_link(item['finder_id'], item['finder_name'], item['finder_username'])}\n"
        f"📞 <b>{escape(item['finder_phone'] or '')}</b>\n\n"
        "Narsangizni olishda omad! 🍀",
    )

    # Topuvchiga egasining kontakti
    finder_text = (
        f"🎉 <b>#{code} e'loningiz egasi topildi!</b>\n\n"
        f"👤 {user_link(claim['owner_id'], claim['owner_name'], claim['owner_username'])}\n"
        f"📞 <b>{escape(claim['owner_phone'] or '')}</b>\n\n"
        "U siz bilan bog'lanadi. Narsani topshirishda shaxsini tekshirib oling.\n\n"
        f"🎁 Suyunchi: <b>{money(share)} so'm</b> "
    )
    if item["finder_card"]:
        finder_text += f"kartangizga ({escape(item['finder_card'])}) o'tkaziladi."
    else:
        finder_text += "— olish uchun karta raqamingizni adminga yuboring"
        finder_text += f": {ADMIN_USERNAME}." if ADMIN_USERNAME else "."
    finder_text += "\n\nYaxshilik qilganingiz uchun rahmat! 🙏"
    await safe_send(bot, item["finder_id"], finder_text)

    # Kanaldagi postni yangilash
    returned_text = channel_post_text(item, returned=True)
    try:
        if item["publish_mode"] in ("photo", "blur"):
            await bot.edit_message_caption(
                chat_id=CHANNEL_ID, message_id=item["channel_msg_id"], caption=returned_text, reply_markup=None
            )
        else:
            await bot.edit_message_text(
                returned_text,
                chat_id=CHANNEL_ID,
                message_id=item["channel_msg_id"],
                reply_markup=None,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
    except TelegramAPIError as error:
        logger.warning("Kanal posti yangilanmadi: %s", error)

    await _mark_done(callback, "✅ To'lov tasdiqlandi, ikki tomon bog'landi")
    await bot.send_message(
        ADMIN_GROUP_ID,
        f"💳 <b>Suyunchi o'tkazish kerak</b> | #{code}\n\n"
        f"Summa: <b>{money(share)} so'm</b>\n"
        f"Kimga: {user_link(item['finder_id'], item['finder_name'], item['finder_username'])}\n"
        f"Karta: <code>{escape(item['finder_card'] or 'kiritilmagan')}</code>",
    )
    await callback.answer("Bog'landi ✅")
