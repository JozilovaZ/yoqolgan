"""Narsa yo'qotgan odam uchun bo'lim: qidiruv va "topilsa xabar bering" e'loni."""
from datetime import date

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import database as db
import visual
from config import CATEGORIES, CHANNEL_LINK, REGIONS
from docnumber import NUMBERED_DOCUMENTS, fingerprint, masked, normalize
from i18n import region_label, t
from keyboards import (
    BUTTONS,
    calendar_kb,
    cancel_kb,
    categories_kb,
    confirm_lost_kb,
    lost_items_kb,
    main_menu,
    my_searches_kb,
    regions_kb,
    skip_kb,
)
from consent import require_terms
from matching import is_match
from services import match_report_documents
from utils import category_label, day_text, is_document, lost_code, lost_report_text

from .claim import start_claim

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

# Bir odamda bir vaqtda ko'pi bilan shuncha faol qidiruv bo'ladi
MAX_ACTIVE_SEARCHES = 5


class LostForm(StatesGroup):
    region = State()
    place = State()
    lost_date = State()
    description = State()
    doc_number = State()  # faqat pasport, ID karta, prava
    photo = State()  # faqat hujjat bo'lmagan narsalar
    confirm = State()


@router.message(StateFilter(None), F.text.in_(BUTTONS["lost"]))
async def lost(message: Message, lang: str):
    text = t("lost.intro", lang)
    if CHANNEL_LINK:
        text += t("lost.channel", lang, link=CHANNEL_LINK)
    text += t("lost.choose", lang)
    await message.answer(text, reply_markup=categories_kb("lost", lang))


@router.callback_query(F.data.startswith("lost:"))
async def lost_category(callback: CallbackQuery, lang: str):
    category = callback.data.split(":", 1)[1]
    if category not in CATEGORIES:
        await callback.answer()
        return
    items = await db.list_published(category)
    await callback.answer()
    text = t("lost.list" if items else "lost.empty", lang, category=category_label(category, lang))
    await callback.message.answer(text, reply_markup=lost_items_kb(items, subscribe_category=category, lang=lang))


@router.callback_query(F.data.startswith("claim:"))
async def claim_from_list(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.answer()
    await state.clear()
    await start_claim(callback.message, state, int(callback.data.split(":")[1]), callback.from_user, lang)


# ---------- "Topilsa xabar bering" e'loni ----------

@router.callback_query(F.data.startswith("lostsub:"))
async def start_lost_report(callback: CallbackQuery, state: FSMContext, lang: str):
    category = callback.data.split(":", 1)[1]
    await callback.answer()
    if category not in CATEGORIES:
        return
    await begin_lost_report(callback.message, state, callback.from_user.id, category, lang)


async def begin_lost_report(message: Message, state: FSMContext, user_id: int, category: str, lang: str):
    """"Topilsa xabar bering" tugmasidan yoki ofertaga rozilikdan keyin chaqiriladi."""
    if len(await db.list_user_lost_reports(user_id)) >= MAX_ACTIVE_SEARCHES:
        await message.answer(
            t("lost.max_searches", lang, max=MAX_ACTIVE_SEARCHES, button=t("btn.my_searches", lang))
        )
        return
    if not await require_terms(message, user_id, f"lostsub_{category}", lang):
        return

    await state.clear()
    await state.update_data(category=category)
    await state.set_state(LostForm.region)
    await message.answer(
        t("lost.report_intro", lang, category=category_label(category, lang)), reply_markup=cancel_kb(lang)
    )
    await message.answer(t("lost.q_region", lang), reply_markup=regions_kb(allow_unknown=True, lang=lang))


@router.callback_query(LostForm.region, F.data.startswith("reg:"))
async def got_region(callback: CallbackQuery, state: FSMContext, lang: str):
    value = callback.data.split(":")[1]
    region = "" if value == "any" else REGIONS[int(value)]
    await state.update_data(region=region)
    await state.set_state(LostForm.place)
    await callback.answer()
    shown = region_label(region, lang) or t("lost.region_unknown", lang)
    await callback.message.edit_text(t("lost.region_chosen", lang, region=shown))
    await callback.message.answer(t("lost.q_place", lang), reply_markup=skip_kb(lang))


@router.message(LostForm.region)
async def region_required(message: Message, lang: str):
    await message.answer(t("common.region_required", lang))


@router.message(LostForm.place, F.text)
async def got_place(message: Message, state: FSMContext, lang: str):
    place = "" if message.text in BUTTONS["skip"] else message.text.strip()
    if len(place) > 200:
        await message.answer(t("common.too_long", lang, limit=200))
        return
    await state.update_data(place=place)
    await state.set_state(LostForm.lost_date)
    await message.answer("👌", reply_markup=cancel_kb(lang))
    await message.answer(t("lost.q_date", lang), reply_markup=calendar_kb(lang=lang))


@router.callback_query(LostForm.lost_date, F.data.startswith("cal:nav:"))
async def calendar_navigate(callback: CallbackQuery, lang: str):
    year, month = map(int, callback.data.split(":")[2].split("-"))
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(year, month, lang))


@router.callback_query(LostForm.lost_date, F.data.startswith("day:"))
async def got_date(callback: CallbackQuery, state: FSMContext, lang: str):
    day = date.fromisoformat(callback.data.split(":", 1)[1])
    if day > date.today():
        await callback.answer(t("common.future_day", lang), show_alert=True)
        return
    await state.update_data(lost_day=day.isoformat())
    await state.set_state(LostForm.description)
    await callback.answer()
    await callback.message.edit_text(t("lost.date_chosen", lang, date=day_text(day, lang)))
    await callback.message.answer(t("lost.q_description", lang), reply_markup=skip_kb(lang))


@router.message(LostForm.lost_date)
async def date_required(message: Message, lang: str):
    await message.answer(t("common.date_required", lang))


@router.message(LostForm.description, F.text)
async def got_description(message: Message, state: FSMContext, lang: str):
    description = "" if message.text in BUTTONS["skip"] else message.text.strip()
    if len(description) > 500:
        await message.answer(t("common.too_long_500", lang))
        return
    await state.update_data(description=description)
    category = (await state.get_data())["category"]
    if category in NUMBERED_DOCUMENTS:
        await state.set_state(LostForm.doc_number)
        await message.answer(t("lost.q_doc_number", lang), reply_markup=skip_kb(lang))
    elif not is_document(category):
        await state.set_state(LostForm.photo)
        await message.answer(t("lost.q_photo", lang), reply_markup=skip_kb(lang))
    else:
        await show_confirm(message, state, lang)


@router.message(LostForm.doc_number, F.text)
async def got_doc_number(message: Message, state: FSMContext, lang: str):
    if message.text not in BUTTONS["skip"]:
        number = normalize(message.text)
        if not number:
            await message.answer(t("lost.bad_doc_number", lang))
            return
        # Raqamning o'zi saqlanmaydi — faqat izi va "AA•••••67" ko'rinishi
        await state.update_data(doc_hash=fingerprint(number), doc_hint=masked(number))
        try:
            await message.delete()  # chatda ham ochiq turmasin
        except TelegramAPIError:
            pass
    await show_confirm(message, state, lang)


@router.message(LostForm.doc_number)
async def doc_number_required(message: Message, lang: str):
    await message.answer(t("lost.bad_doc_number", lang))


@router.message(LostForm.photo, F.photo)
async def got_photo(message: Message, state: FSMContext, lang: str):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await show_confirm(message, state, lang)


@router.message(LostForm.photo, F.text.in_(BUTTONS["skip"]))
async def skip_photo(message: Message, state: FSMContext, lang: str):
    await show_confirm(message, state, lang)


@router.message(LostForm.photo)
async def photo_required(message: Message, lang: str):
    await message.answer(t("lost.photo_required", lang))


async def show_confirm(message: Message, state: FSMContext, lang: str):
    await state.set_state(LostForm.confirm)
    data = await state.get_data()
    await message.answer(t("common.almost_ready", lang), reply_markup=ReplyKeyboardRemove())
    await message.answer(
        t("common.check_header", lang) + lost_report_text(data, lang), reply_markup=confirm_lost_kb(lang)
    )


@router.callback_query(LostForm.confirm, F.data == "lostform:cancel")
async def lost_cancel(callback: CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await callback.answer(t("common.cancelled_toast", lang))
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t("common.post_cancelled", lang), reply_markup=main_menu(lang))


@router.callback_query(LostForm.confirm, F.data == "lostform:save")
async def lost_save(callback: CallbackQuery, state: FSMContext, bot: Bot, lang: str):
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    user = callback.from_user
    photo_id = data.get("photo_id")
    embedding = await visual.embed(bot, photo_id) if photo_id else None

    report_id = await db.create_lost_report(
        {
            "owner_id": user.id,
            "owner_name": user.full_name,
            "owner_username": user.username,
            "category": data["category"],
            "region": data["region"],
            "place": data["place"],
            "lost_day": data["lost_day"],
            "description": data["description"],
            "doc_hash": data.get("doc_hash"),
            "doc_hint": data.get("doc_hint"),
            "photo_id": photo_id,
            "embedding": embedding,
        }
    )
    report = await db.get_lost_report(report_id)

    await callback.message.answer(
        t("lost.saved", lang, code=lost_code(report_id), button=t("btn.my_searches", lang)),
        reply_markup=main_menu(lang),
    )

    # Kanalda allaqachon turgan, raqami aynan mos hujjat
    await match_report_documents(bot, report)

    # Kanalda allaqachon turgan mos e'lonlar. Rasm yuborilgan bo'lsa — eng o'xshashlari tepada
    matches = [item for item in await db.list_published(report["category"], limit=50) if is_match(report, item)]
    text_key = "lost.matches_now"
    if embedding and any(item["embedding"] for item in matches):
        matches.sort(key=lambda item: visual.similarity(embedding, item["embedding"]) or 0.0, reverse=True)
        text_key = "lost.matches_by_photo"
    if matches:
        await callback.message.answer(
            t(text_key, lang, count=len(matches)), reply_markup=lost_items_kb(matches[:10], lang=lang)
        )


# ---------- Qidiruvlarim ----------

@router.message(StateFilter(None), F.text.in_(BUTTONS["my_searches"]))
async def my_searches(message: Message, lang: str):
    reports = await db.list_user_lost_reports(message.from_user.id)
    if not reports:
        await message.answer(t("lost.no_searches", lang, button=t("btn.lost", lang)))
        return
    text = t("lost.my_searches", lang) + "\n\n".join(lost_report_text(report, lang) for report in reports)
    text += t("lost.my_searches_footer", lang)
    await message.answer(text, reply_markup=my_searches_kb(reports, lang))


@router.callback_query(F.data.startswith("lostclose:"))
async def close_search(callback: CallbackQuery, lang: str):
    report = await db.get_lost_report(int(callback.data.split(":")[1]))
    if not report or report["owner_id"] != callback.from_user.id or report["status"] != "active":
        await callback.answer(t("lost.already_stopped", lang), show_alert=True)
        return
    await db.update_lost_report(report["id"], status="closed")
    await callback.answer(t("lost.stopped_toast", lang))
    await callback.message.answer(t("lost.stopped", lang, code=lost_code(report["id"])))
