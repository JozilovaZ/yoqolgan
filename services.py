import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile, LinkPreviewOptions

import database as db
from config import CHANNEL_ID, CHANNEL_LINK
from images import blurred_photo
from keyboards import channel_post_kb, lost_match_kb
from matching import is_match
from utils import channel_post_text, is_document, lost_match_text, safe_send

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
