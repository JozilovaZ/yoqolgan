from aiogram import Bot
from aiogram.types import BufferedInputFile, LinkPreviewOptions

import database as db
from config import CHANNEL_ID, CHANNEL_LINK
from images import blurred_photo
from keyboards import channel_post_kb
from utils import channel_post_text, is_document

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
    return post.message_id


def post_link(message_id: int) -> str:
    return f"{CHANNEL_LINK}/{message_id}" if CHANNEL_LINK else ""
