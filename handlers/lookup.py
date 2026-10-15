"""E'lon raqami bo'yicha tez qidiruv: botga "T0012" yozilsa yoki kanaldagi post forward qilinsa — o'sha e'lon ochiladi.

Router routerlar ro'yxatining oxirida turadi: tanilmagan matnga yo'l-yo'riq beradi.
"""
import re
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.types import LinkPreviewOptions, Message

import database as db
from i18n import t
from keyboards import lookup_kb, main_menu, my_searches_kb
from services import post_link
from utils import category_label, cut, item_code, location_text, lost_code, lost_report_text

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

# "T0012", "#T0012", "t12", "T-0012" (kirill "Т" ham)
ITEM_CODE_RE = re.compile(r"#?\s*[TtТт]\s*-?\s*(\d{1,7})")
LOST_CODE_RE = re.compile(r"#?\s*[Yy]\s*-?\s*(\d{1,7})")
# Kanaldagi post matnida: "🔎 TOPILDI | #T0012"
POST_CODE_RE = re.compile(r"#T(\d{4,7})\b")


async def show_item(message: Message, item_id: int, lang: str) -> None:
    item = await db.get_item(item_id)
    code = item_code(item_id)
    if item and item["finder_id"] == message.chat.id:
        await message.answer(
            t("lookup.own", lang, code=code, button=t("btn.my_items", lang)),
            reply_markup=lookup_kb(item_id, own=True, lang=lang),
        )
        return
    if not item or item["status"] not in ("published", "returned"):
        await message.answer(t("lookup.not_found", lang, code=code), reply_markup=main_menu(lang))
        return
    if item["status"] == "returned":
        await message.answer(t("lookup.returned", lang, code=code, category=category_label(item["category"], lang)))
        return

    lines = [
        f"🔎 <b>{category_label(item['category'], lang)}</b> | #{code}",
        location_text(item, lang=lang),
        f"📅 {escape(item['found_date'] or '')}",
    ]
    if item["description"]:
        lines.append(f"📝 {escape(cut(item['description'], 500))}")
    lines += ["", t("lookup.press", lang)]
    text = "\n".join(lines)
    keyboard = lookup_kb(item_id, post_url=post_link(item["channel_msg_id"]), lang=lang)
    if item["publish_mode"] == "photo":
        # Hujjatlarning aniq rasmi ko'rsatilmaydi — ular kanalda faqat xira holda turadi
        await message.answer_photo(item["photo_id"], caption=text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True))


async def show_lost_report(message: Message, report_id: int, lang: str) -> None:
    report = await db.get_lost_report(report_id)
    if not report or report["owner_id"] != message.chat.id or report["status"] != "active":
        await message.answer(t("lookup.search_not_found", lang, code=lost_code(report_id)))
        return
    await message.answer(
        t("lookup.search", lang) + lost_report_text(report, lang), reply_markup=my_searches_kb([report], lang)
    )


@router.message(StateFilter(None), F.forward_origin, F.text | F.caption)
async def forwarded_post(message: Message, lang: str):
    """Kanaldagi post botga forward qilingan."""
    match = POST_CODE_RE.search(message.text or message.caption)
    if not match:
        await _not_understood(message, lang)
        return
    await show_item(message, int(match.group(1)), lang)


@router.message(StateFilter(None), F.text.len() <= 20, F.text.func(lambda text: ITEM_CODE_RE.fullmatch(text.strip())))
async def item_code_typed(message: Message, lang: str):
    await show_item(message, int(ITEM_CODE_RE.fullmatch(message.text.strip()).group(1)), lang)


@router.message(StateFilter(None), F.text.len() <= 20, F.text.func(lambda text: LOST_CODE_RE.fullmatch(text.strip())))
async def lost_code_typed(message: Message, lang: str):
    await show_lost_report(message, int(LOST_CODE_RE.fullmatch(message.text.strip()).group(1)), lang)


@router.message(StateFilter(None), F.text)
async def not_understood(message: Message, lang: str):
    await _not_understood(message, lang)


async def _not_understood(message: Message, lang: str) -> None:
    await message.answer(t("lookup.not_understood", lang, button=t("btn.lost", lang)), reply_markup=main_menu(lang))
