import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, LabeledPrice, LinkPreviewOptions

import database as db
from config import (
    ADMIN_GROUP_ID,
    ADMIN_USERNAME,
    CARD_NUMBER,
    CARD_OWNER,
    CHANNEL_ID,
    CHANNEL_LINK,
    FINDER_SHARE,
    PAYMENT_EXPIRE_HOURS,
    PAYMENT_PROVIDER_TOKEN,
    SERVICE_FEE,
)
from images import blurred_photo
from keyboards import channel_post_kb, lost_match_kb, payout_kb
from matching import is_match
from utils import (
    category_label,
    channel_post_text,
    is_document,
    item_code,
    lost_match_text,
    money,
    safe_send,
    user_link,
)

logger = logging.getLogger(__name__)

# Bu hujjatlarda faqat yuz rasmi xiralashadi, qolganlarida (bank karta va h.k.) — butun rasm
FACE_BLUR_CATEGORIES = {"passport", "id_card", "driver"}


def default_mode(item: dict) -> str:
    """Hujjatlar xira rasm bilan, qolganlari oddiy rasm bilan chiqadi."""
    return "blur" if is_document(item["category"]) else "photo"


async def publish_item(bot: Bot, item: dict, mode: str) -> int:
    """E'lonni kanalga chiqaradi.

    mode: 'photo' — rasm bilan, 'blur' — xiralashtirilgan rasm bilan, 'text' — rasmsiz.
    Xato bo'lsa TelegramAPIError ko'taradi (masalan, bot kanalda admin emas).
    """
    me = await bot.me()
    text = channel_post_text(item)
    keyboard = channel_post_kb(me.username, item["id"])
    if mode == "photo":
        post = await bot.send_photo(CHANNEL_ID, item["photo_id"], caption=text, reply_markup=keyboard)
    elif mode == "blur":
        faces_only = item["category"] in FACE_BLUR_CATEGORIES
        photo = BufferedInputFile(await blurred_photo(bot, item["photo_id"], faces_only), filename="photo.jpg")
        post = await bot.send_photo(CHANNEL_ID, photo, caption=text, reply_markup=keyboard)
    else:
        post = await bot.send_message(
            CHANNEL_ID, text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    await db.update_item(item["id"], status="published", publish_mode=mode, channel_msg_id=post.message_id)
    try:
        await notify_lost_owners(bot, item, post.message_id)
    except Exception as error:  # xabar yuborilmasa ham e'lon kanalda qoladi
        logger.error("Yo'qotganlarga xabar yuborilmadi: %s", error)
    return post.message_id


async def notify_lost_owners(bot: Bot, item: dict, message_id: int) -> None:
    """Yangi e'longa mos keladigan "yo'qotdim" e'lonlari egalariga xabar beradi."""
    notified: set[int] = set()
    for report in await db.list_active_lost_reports(item["category"]):
        if report["owner_id"] in notified or not is_match(report, item):
            continue
        notified.add(report["owner_id"])
        await safe_send(
            bot,
            report["owner_id"],
            lost_match_text(item, report),
            reply_markup=lost_match_kb(item["id"], report["id"], post_link(message_id)),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    if notified:
        logger.info("#%s: %d ta yo'qotganga xabar berildi", item["id"], len(notified))


def post_link(message_id: int) -> str:
    return f"{CHANNEL_LINK}/{message_id}" if CHANNEL_LINK else ""


# ---------- to'lov ----------

async def request_payment(bot: Bot, claim: dict, item: dict, intro: str = "") -> None:
    """Egasi tasdiqlangach to'lov so'raladi: onlayn (Click/Payme) yoki karta + chek.

    intro — boshidagi matn (sukut bo'yicha tabrik; eslatmada boshqacha).
    """
    code = item_code(item["id"])
    intro = intro or (
        f"🎉 <b>Tabriklaymiz!</b> #{code} — {category_label(item['category'])} sizniki ekanligi tasdiqlandi.\n\n"
    )
    text = (
        intro + f"Topuvchi bilan bog'lanish uchun xizmat haqini to'lang: <b>{money(SERVICE_FEE)} so'm</b>\n"
        f"🎁 Shundan {FINDER_SHARE}% narsangizni topgan insonga suyunchi sifatida beriladi.\n"
        f"⏳ To'lov uchun {PAYMENT_EXPIRE_HOURS} soat vaqt bor, keyin murojaat yopiladi.\n\n"
    )
    if PAYMENT_PROVIDER_TOKEN:
        try:
            await bot.send_invoice(
                claim["owner_id"],
                title=f"Xizmat haqi #{code}",
                description=f"{category_label(item['category'])} topgan inson bilan bog'lanish",
                payload=f"claim:{claim['id']}",
                provider_token=PAYMENT_PROVIDER_TOKEN,
                currency="UZS",
                prices=[LabeledPrice(label="Xizmat haqi", amount=SERVICE_FEE * 100)],  # tiyinda
            )
            await safe_send(
                bot,
                claim["owner_id"],
                text + "💳 Yuqoridagi <b>«To'lash»</b> tugmasini bosing — to'lov tushishi bilan "
                "topuvchining kontaktini darhol yuboraman.",
            )
            return
        except TelegramAPIError as error:
            logger.error("Invoice yuborilmadi, karta orqali to'lovga o'tildi: %s", error)

    await safe_send(
        bot,
        claim["owner_id"],
        text + f"💳 Karta: <code>{escape(CARD_NUMBER)}</code>\n"
        f"👤 {escape(CARD_OWNER)}\n\n"
        "📸 To'lovdan so'ng <b>chek skrinshotini shu yerga yuboring.</b>",
    )


async def mark_post_returned(bot: Bot, item: dict) -> None:
    """Kanaldagi post "✅ EGASIGA QAYTARILDI" ga o'zgaradi, "Bu meniki" tugmasi olib tashlanadi."""
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


async def complete_claim(bot: Bot, claim: dict, item: dict, charge_id: str = "") -> None:
    """To'lov tasdiqlangach: ikki tomonga kontakt, kanal posti yangilanadi, adminga suyunchi eslatmasi.

    charge_id — onlayn to'lov bo'lsa, to'lov tizimidagi ID si.
    """
    code = item_code(item["id"])
    await db.update_claim(claim["id"], status="completed")
    await db.close_item(item["id"], "returned")
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

    await mark_post_returned(bot, item)

    admin_text = ""
    if charge_id:
        admin_text = (
            f"💳 <b>Onlayn to'lov qabul qilindi</b> | murojaat №{claim['id']}\n"
            f"To'lov ID: <code>{escape(charge_id)}</code>\nIkki tomon avtomatik bog'landi ✅\n\n"
        )
    admin_text += (
        f"💸 <b>Suyunchi o'tkazish kerak</b> | #{code}\n\n"
        f"Summa: <b>{money(share)} so'm</b>\n"
        f"Kimga: {user_link(item['finder_id'], item['finder_name'], item['finder_username'])}\n"
        f"Karta: <code>{escape(item['finder_card'] or 'kiritilmagan')}</code>"
    )
    await safe_send(bot, ADMIN_GROUP_ID, admin_text, reply_markup=payout_kb(claim["id"]))
