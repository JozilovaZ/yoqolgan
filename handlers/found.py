"""Narsa topgan odam e'lon beradigan bo'lim."""
import logging
import re
from datetime import date
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import database as db
from config import ADMIN_GROUP_ID, AUTO_PUBLISH, CATEGORIES, FINDER_SHARE, REGIONS, SERVICE_FEE
from geo import reverse_geocode
from i18n import region_label, t
from keyboards import (
    BUTTONS,
    cancel_kb,
    categories_kb,
    confirm_found_kb,
    calendar_kb,
    hours_kb,
    location_kb,
    main_menu,
    moderation_kb,
    phone_kb,
    published_kb,
    regions_kb,
    skip_kb,
)
from services import default_mode, post_link, publish_item
from consent import require_terms
from verify import prepare_document
from utils import category_label, cut, day_text, is_document, item_code, item_details, location_text, money

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

PHONE_RE = re.compile(r"^\+?\d{9,13}$")


class FoundForm(StatesGroup):
    category = State()
    photo = State()
    location = State()
    manual_region = State()
    manual_place = State()
    landmark = State()
    found_date = State()
    found_time = State()
    description = State()
    phone = State()
    card = State()
    confirm = State()


@router.message(StateFilter(None), F.text.in_(BUTTONS["found"]))
async def found_button(message: Message, state: FSMContext, lang: str):
    await start_found(message, state, lang)


async def start_found(message: Message, state: FSMContext, lang: str):
    # message.chat.id — shaxsiy chatda foydalanuvchi ID si (rozilikdan keyin message botniki bo'ladi)
    if not await require_terms(message, message.chat.id, "found", lang):
        return
    await state.set_state(FoundForm.category)
    await message.answer(t("found.thanks", lang), reply_markup=cancel_kb(lang))
    await message.answer(t("found.q_category", lang), reply_markup=categories_kb("fcat", lang))


@router.callback_query(FoundForm.category, F.data.startswith("fcat:"))
async def got_category(callback: CallbackQuery, state: FSMContext, lang: str):
    category = callback.data.split(":", 1)[1]
    if category not in CATEGORIES:
        await callback.answer()
        return
    await state.update_data(category=category)
    await state.set_state(FoundForm.photo)
    await callback.answer()
    await callback.message.edit_text(t("found.category_chosen", lang, category=category_label(category, lang)))

    text = t("found.q_photo", lang)
    if is_document(category):
        text += t("found.photo_doc_note", lang)
    await callback.message.answer(text)


# ---------- rasm ----------

@router.message(FoundForm.photo, F.photo)
async def got_photo(message: Message, state: FSMContext, lang: str):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(FoundForm.location)
    await message.answer(t("found.q_location", lang), reply_markup=location_kb(lang))


@router.message(FoundForm.photo)
async def photo_required(message: Message, lang: str):
    await message.answer(t("found.photo_required", lang))


# ---------- joylashuv ----------

@router.message(FoundForm.location, F.location)
async def got_location(message: Message, state: FSMContext, lang: str):
    lat, lon = message.location.latitude, message.location.longitude
    wait = await message.answer(t("found.locating", lang))
    region, place = await reverse_geocode(lat, lon)
    await wait.delete()

    await state.update_data(region=region, place=place, latitude=lat, longitude=lon)
    address = ", ".join(part for part in (region_label(region, lang), place) if part) or t("found.map_point", lang)
    await message.answer(t("found.address", lang, address=escape(address)))
    await _ask_landmark(message, state, lang)


@router.message(FoundForm.location, F.text.in_(BUTTONS["manual_address"]))
async def manual_address(message: Message, state: FSMContext, lang: str):
    await state.set_state(FoundForm.manual_region)
    await message.answer(t("found.manual", lang), reply_markup=cancel_kb(lang))
    await message.answer(t("found.q_region", lang), reply_markup=regions_kb(lang=lang))


@router.message(FoundForm.location, F.text)
async def got_location_text(message: Message, state: FSMContext, lang: str):
    """Tugmani bosmasdan to'g'ridan-to'g'ri manzil yozib yuborsa ham qabul qilamiz."""
    if len(message.text) > 200:
        await message.answer(t("common.too_long", lang, limit=200))
        return
    await state.update_data(region="", place=message.text.strip(), latitude=None, longitude=None)
    await _ask_landmark(message, state, lang)


@router.message(FoundForm.location)
async def location_required(message: Message, lang: str):
    await message.answer(t("found.location_required", lang))


@router.callback_query(FoundForm.manual_region, F.data.startswith("reg:"))
async def got_manual_region(callback: CallbackQuery, state: FSMContext, lang: str):
    region = REGIONS[int(callback.data.split(":")[1])]
    await state.update_data(region=region, latitude=None, longitude=None)
    await state.set_state(FoundForm.manual_place)
    await callback.answer()
    await callback.message.edit_text(t("found.region_chosen", lang, region=region_label(region, lang)))
    await callback.message.answer(t("found.q_place", lang))


@router.message(FoundForm.manual_region)
async def region_required(message: Message, lang: str):
    await message.answer(t("common.region_required", lang))


@router.message(FoundForm.manual_place, F.text)
async def got_manual_place(message: Message, state: FSMContext, lang: str):
    if len(message.text) > 200:
        await message.answer(t("common.too_long", lang, limit=200))
        return
    await state.update_data(place=message.text.strip())
    await _ask_date(message, state, lang)  # mo'ljal shu yerda yozildi — alohida so'ramaymiz


async def _ask_landmark(message: Message, state: FSMContext, lang: str):
    await state.set_state(FoundForm.landmark)
    await message.answer(t("found.q_landmark", lang), reply_markup=skip_kb(lang))


@router.message(FoundForm.landmark, F.text)
async def got_landmark(message: Message, state: FSMContext, lang: str):
    if message.text not in BUTTONS["skip"]:
        if len(message.text) > 150:
            await message.answer(t("common.too_long", lang, limit=150))
            return
        data = await state.get_data()
        place = ", ".join(part for part in (data["place"], message.text.strip()) if part)
        await state.update_data(place=place)
    await _ask_date(message, state, lang)


async def _ask_date(message: Message, state: FSMContext, lang: str):
    await state.set_state(FoundForm.found_date)
    await message.answer("👌", reply_markup=cancel_kb(lang))
    await message.answer(t("found.q_date", lang), reply_markup=calendar_kb(lang=lang))


# ---------- sana (kalendar) va soat ----------

@router.callback_query(F.data == "cal:ignore")
async def calendar_ignore(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(FoundForm.found_date, F.data.startswith("cal:nav:"))
async def calendar_navigate(callback: CallbackQuery, lang: str):
    year, month = map(int, callback.data.split(":")[2].split("-"))
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(year, month, lang))


@router.callback_query(FoundForm.found_date, F.data.startswith("day:"))
async def got_date(callback: CallbackQuery, state: FSMContext, lang: str):
    day = date.fromisoformat(callback.data.split(":", 1)[1])
    if day > date.today():
        await callback.answer(t("common.future_day", lang), show_alert=True)
        return
    # Bazaga va kanalga o'zbekcha yoziladi, foydalanuvchiga o'z tilida ko'rsatiladi
    await state.update_data(found_date=day_text(day), found_date_shown=day_text(day, lang), found_day=day.isoformat())
    await state.set_state(FoundForm.found_time)
    await callback.answer()
    await callback.message.edit_text(t("found.q_time", lang, date=day_text(day, lang)), reply_markup=hours_kb(day, lang))


@router.message(FoundForm.found_date)
async def date_required(message: Message, lang: str):
    await message.answer(t("common.date_required", lang))


@router.callback_query(FoundForm.found_time, F.data.startswith("hour:"))
async def got_time(callback: CallbackQuery, state: FSMContext, lang: str):
    value = callback.data.split(":", 1)[1]
    data = await state.get_data()
    found_date, shown = data["found_date"], data["found_date_shown"]
    if value != "unknown":
        hour = f"{int(value):02d}"
        found_date += t("time.at_hour", hour=hour)
        shown += t("time.at_hour", lang, hour=hour)
    await state.update_data(found_date=found_date, found_date_shown=shown)
    await state.set_state(FoundForm.description)
    await callback.answer()
    await callback.message.edit_text(t("found.time_chosen", lang, when=shown))

    text = t("found.q_description", lang)
    if is_document(data["category"]):
        text += t("found.doc_warning", lang)
    await callback.message.answer(text, reply_markup=skip_kb(lang))


@router.message(FoundForm.found_time)
async def time_required(message: Message, lang: str):
    await message.answer(t("found.time_required", lang))


# ---------- izoh, telefon, karta ----------

@router.message(FoundForm.description, F.text)
async def got_description(message: Message, state: FSMContext, lang: str):
    description = "" if message.text in BUTTONS["skip"] else message.text.strip()
    if len(description) > 500:
        await message.answer(t("common.description_too_long", lang))
        return
    await state.update_data(description=description)
    await state.set_state(FoundForm.phone)
    await message.answer(t("found.q_phone", lang), reply_markup=phone_kb(lang))


@router.message(FoundForm.phone, F.contact)
async def got_contact(message: Message, state: FSMContext, lang: str):
    await _save_phone(message, state, message.contact.phone_number, lang)


@router.message(FoundForm.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext, lang: str):
    phone = message.text.replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        await message.answer(t("common.phone_invalid", lang))
        return
    await _save_phone(message, state, phone, lang)


async def _save_phone(message: Message, state: FSMContext, phone: str, lang: str):
    await state.update_data(phone=phone)
    await state.set_state(FoundForm.card)
    await message.answer(
        t("found.q_card", lang, share=FINDER_SHARE, amount=money(SERVICE_FEE * FINDER_SHARE // 100)),
        reply_markup=skip_kb(lang),
    )


@router.message(FoundForm.card, F.text)
async def got_card(message: Message, state: FSMContext, lang: str):
    if message.text in BUTTONS["skip"]:
        card = ""
    else:
        card = message.text.replace(" ", "")
        if not (card.isdigit() and len(card) == 16):
            await message.answer(t("found.card_invalid", lang))
            return
        card = " ".join(card[i : i + 4] for i in range(0, 16, 4))

    await state.update_data(card=card)
    await state.set_state(FoundForm.confirm)
    data = await state.get_data()

    private = t("found.private", lang)
    summary = t("common.check_header", lang) + t(
        "found.summary",
        lang,
        category=category_label(data["category"], lang),
        location=location_text(data, 200, lang),
        date=escape(data["found_date_shown"]),
        description=escape(cut(data["description"], 350)) or "—",
        phone=escape(data["phone"]),
        private=private,
        card=card or "—",
    )
    if card:
        summary += f" — {private}"
    await message.answer(t("common.almost_ready", lang), reply_markup=ReplyKeyboardRemove())
    await message.answer_photo(data["photo_id"], caption=summary, reply_markup=confirm_found_kb(lang))


@router.callback_query(FoundForm.confirm, F.data == "found:cancel")
async def found_cancel(callback: CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await callback.answer(t("common.cancelled_toast", lang))
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t("common.post_cancelled", lang), reply_markup=main_menu(lang))


@router.callback_query(FoundForm.confirm, F.data == "found:send")
async def found_send(callback: CallbackQuery, state: FSMContext, bot: Bot, lang: str):
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    user = callback.from_user

    item_id = await db.create_item(
        {
            "finder_id": user.id,
            "finder_name": user.full_name,
            "finder_username": user.username,
            "finder_phone": data["phone"],
            "finder_card": data["card"],
            "category": data["category"],
            "photo_id": data["photo_id"],
            "region": data["region"],
            "place": data["place"],
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "found_date": data["found_date"],
            "description": data["description"],
        }
    )
    item = await db.get_item(item_id)
    code = item_code(item_id)

    # Avtomatik chiqarish: hujjatlar rasmsiz, qolganlari rasm bilan
    message_id = None
    publish_error = ""
    if AUTO_PUBLISH:
        wait = None
        if is_document(item["category"]):
            wait = await callback.message.answer(t("found.blurring", lang))
        try:
            message_id = await publish_item(bot, item, default_mode(item))
        except Exception as error:  # Telegram xatosi yoki rasmni qayta ishlashdagi xato
            logger.error("Kanalga avtomatik chiqmadi: %s", error)
            publish_error = str(error)
        if wait:
            await wait.delete()

    if message_id:
        caption = "📢 <b>YANGI E'LON KANALGA CHIQDI</b>\n\n" + item_details(item)
        keyboard = published_kb(item_id)
    else:
        caption = "🆕 <b>YANGI E'LON — tekshiring</b>\n\n" + item_details(item)
        if publish_error:
            caption += f"\n\n⚠️ Avtomatik chiqmadi: {escape(cut(publish_error, 120))}"
        if is_document(item["category"]):
            caption += "\n\n⚠️ <b>Hujjat!</b> Xira rasm bilan chiqarish tavsiya etiladi."
        keyboard = moderation_kb(item_id)
    try:
        await bot.send_photo(ADMIN_GROUP_ID, item["photo_id"], caption=caption, reply_markup=keyboard)
    except TelegramAPIError as error:
        logger.error("Admin guruhga yuborilmadi: %s", error)

    if message_id:
        text = t("found.published", lang, code=code)
        link = post_link(message_id)
        if link:
            text += f"👉 {link}\n"
        text += t("found.published_footer", lang)
    else:
        text = t("found.accepted", lang, code=code)
    await callback.message.answer(text, reply_markup=main_menu(lang))

    # Hujjatni hozirdan o'qib qo'yamiz — egasi murojaat qilganda tekshiruv bir zumda bo'ladi
    prepare_document(bot, item)
