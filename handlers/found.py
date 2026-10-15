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
from keyboards import (
    BTN_FOUND,
    BTN_MANUAL_ADDRESS,
    BTN_SKIP,
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
from verify import prepare_document
from utils import category_label, cut, day_text, is_document, item_code, item_details, location_text, money

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

PHONE_RE = re.compile(r"^\+?\d{9,13}$")
PRIVATE_NOTE = "🔒 <i>faqat adminga ko'rinadi</i>"


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


@router.message(StateFilter(None), F.text == BTN_FOUND)
async def start_found(message: Message, state: FSMContext):
    await state.set_state(FoundForm.category)
    await message.answer(
        "Rahmat, siz yaxshi ish qilyapsiz! 🙌\nBir nechta savolga javob bering.",
        reply_markup=cancel_kb(),
    )
    await message.answer("1/8. <b>Nima topdingiz?</b> Turini tanlang:", reply_markup=categories_kb("fcat"))


@router.callback_query(FoundForm.category, F.data.startswith("fcat:"))
async def got_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    if category not in CATEGORIES:
        await callback.answer()
        return
    await state.update_data(category=category)
    await state.set_state(FoundForm.photo)
    await callback.answer()
    await callback.message.edit_text(f"1/8. Tanlandi: <b>{category_label(category)}</b>")

    text = "2/8. 📸 <b>Topilgan narsaning rasmini yuboring.</b>"
    if is_document(category):
        text += (
            "\n\n🔐 Kanalga rasm <b>xiralashtirilgan</b> holda chiqadi — ism va raqamlar o'qilmaydi. "
            "Aniq rasmni faqat admin ko'radi va u orqali haqiqiy egasini tekshiradi."
        )
    await callback.message.answer(text)


# ---------- rasm ----------

@router.message(FoundForm.photo, F.photo)
async def got_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(FoundForm.location)
    await message.answer(
        "3/8. 📍 <b>Qayerda topdingiz? Lokatsiyani yuboring.</b>\n\n"
        "• Hozir o'sha joyda bo'lsangiz — pastdagi tugmani bosing.\n"
        "• Boshqa joyda bo'lsangiz — 📎 (skrepka) → <b>Joylashuv</b> → xaritadan joyni belgilang.\n"
        "• Yoki <b>«Manzilni qo'lda kiritish»</b> tugmasini bosing.",
        reply_markup=location_kb(),
    )


@router.message(FoundForm.photo)
async def photo_required(message: Message):
    await message.answer("Iltimos, narsaning <b>rasmini</b> yuboring 📸")


# ---------- joylashuv ----------

@router.message(FoundForm.location, F.location)
async def got_location(message: Message, state: FSMContext):
    lat, lon = message.location.latitude, message.location.longitude
    wait = await message.answer("⏳ Manzil aniqlanmoqda...")
    region, place = await reverse_geocode(lat, lon)
    await wait.delete()

    await state.update_data(region=region, place=place, latitude=lat, longitude=lon)
    address = ", ".join(part for part in (region, place) if part) or "Xaritada belgilangan joy"
    await message.answer(f"✅ Manzil: <b>{escape(address)}</b>")
    await _ask_landmark(message, state)


@router.message(FoundForm.location, F.text == BTN_MANUAL_ADDRESS)
async def manual_address(message: Message, state: FSMContext):
    await state.set_state(FoundForm.manual_region)
    await message.answer("✍️ Qo'lda kiritamiz.", reply_markup=cancel_kb())
    await message.answer("3/8. 🗺 <b>Qaysi viloyatda topdingiz?</b>", reply_markup=regions_kb())


@router.message(FoundForm.location, F.text)
async def got_location_text(message: Message, state: FSMContext):
    """Tugmani bosmasdan to'g'ridan-to'g'ri manzil yozib yuborsa ham qabul qilamiz."""
    if len(message.text) > 200:
        await message.answer("Juda uzun. Iltimos, qisqaroq yozing (200 belgigacha).")
        return
    await state.update_data(region="", place=message.text.strip(), latitude=None, longitude=None)
    await _ask_landmark(message, state)


@router.message(FoundForm.location)
async def location_required(message: Message):
    await message.answer("Iltimos, <b>lokatsiya</b> yuboring yoki <b>«Manzilni qo'lda kiritish»</b> tugmasini bosing 📍")


@router.callback_query(FoundForm.manual_region, F.data.startswith("reg:"))
async def got_manual_region(callback: CallbackQuery, state: FSMContext):
    region = REGIONS[int(callback.data.split(":")[1])]
    await state.update_data(region=region, latitude=None, longitude=None)
    await state.set_state(FoundForm.manual_place)
    await callback.answer()
    await callback.message.edit_text(f"3/8. 🗺 Viloyat: <b>{region}</b>")
    await callback.message.answer(
        "📍 <b>Tuman, ko'cha yoki mo'ljalni yozing:</b>\n"
        "<i>Masalan: Chilonzor tumani, Bunyodkor ko'chasi, «Novza» metrosi yonida</i>"
    )


@router.message(FoundForm.manual_region)
async def region_required(message: Message):
    await message.answer("Iltimos, yuqoridagi ro'yxatdan <b>viloyatni tanlang</b> 👆")


@router.message(FoundForm.manual_place, F.text)
async def got_manual_place(message: Message, state: FSMContext):
    if len(message.text) > 200:
        await message.answer("Juda uzun. Iltimos, qisqaroq yozing (200 belgigacha).")
        return
    await state.update_data(place=message.text.strip())
    await _ask_date(message, state)  # mo'ljal shu yerda yozildi — alohida so'ramaymiz


async def _ask_landmark(message: Message, state: FSMContext):
    await state.set_state(FoundForm.landmark)
    await message.answer(
        "4/8. 🏠 <b>Aniq mo'ljal</b> (ixtiyoriy)\n"
        "<i>Masalan: «Novza» metrosi chiqishida, avtobus bekatida</i>",
        reply_markup=skip_kb(),
    )


@router.message(FoundForm.landmark, F.text)
async def got_landmark(message: Message, state: FSMContext):
    if message.text != BTN_SKIP:
        if len(message.text) > 150:
            await message.answer("Juda uzun. Iltimos, qisqaroq yozing (150 belgigacha).")
            return
        data = await state.get_data()
        place = ", ".join(part for part in (data["place"], message.text.strip()) if part)
        await state.update_data(place=place)
    await _ask_date(message, state)


async def _ask_date(message: Message, state: FSMContext):
    await state.set_state(FoundForm.found_date)
    await message.answer("👌", reply_markup=cancel_kb())
    await message.answer(
        "5/8. 📅 <b>Qaysi kuni topdingiz?</b> Kalendardan tanlang:\n"
        "<i>◀️ tugmasi bilan oldingi oylarga o'tish mumkin</i>",
        reply_markup=calendar_kb(),
    )


# ---------- sana (kalendar) va soat ----------

@router.callback_query(F.data == "cal:ignore")
async def calendar_ignore(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(FoundForm.found_date, F.data.startswith("cal:nav:"))
async def calendar_navigate(callback: CallbackQuery):
    year, month = map(int, callback.data.split(":")[2].split("-"))
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(year, month))


@router.callback_query(FoundForm.found_date, F.data.startswith("day:"))
async def got_date(callback: CallbackQuery, state: FSMContext):
    day = date.fromisoformat(callback.data.split(":", 1)[1])
    if day > date.today():
        await callback.answer("Kelajakdagi kunni tanlab bo'lmaydi", show_alert=True)
        return
    value = day_text(day)
    await state.update_data(found_date=value, found_day=day.isoformat())
    await state.set_state(FoundForm.found_time)
    await callback.answer()
    await callback.message.edit_text(
        f"5/8. 📅 Sana: <b>{value}</b>\n\n🕐 <b>Soat nechada topdingiz?</b> Taxminiy vaqtni tanlang:",
        reply_markup=hours_kb(day),
    )


@router.message(FoundForm.found_date)
async def date_required(message: Message):
    await message.answer("Iltimos, yuqoridagi <b>kalendardan</b> kunni tanlang 👆")


@router.callback_query(FoundForm.found_time, F.data.startswith("hour:"))
async def got_time(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    data = await state.get_data()
    found_date = data["found_date"]
    if value != "unknown":
        found_date += f", soat {int(value):02d}:00 atrofida"
    await state.update_data(found_date=found_date)
    await state.set_state(FoundForm.description)
    await callback.answer()
    await callback.message.edit_text(f"5/8. 📅 Topilgan vaqt: <b>{found_date}</b>")

    text = (
        "6/8. 📝 <b>Qisqacha izoh yozing.</b>\n"
        "Bu matn kanalda chiqadi: rangi, holati va h.k."
    )
    if is_document(data["category"]):
        text += (
            "\n\n⚠️ <b>Hujjatdagi ism-familiya, raqam va boshqa shaxsiy ma'lumotlarni YOZMANG!</b> "
            "Masalan: «Ko'k muqovali pasport, ichida bank karta bor»."
        )
    await callback.message.answer(text, reply_markup=skip_kb())


@router.message(FoundForm.found_time)
async def time_required(message: Message):
    await message.answer("Iltimos, yuqoridagi tugmalardan <b>soatni</b> tanlang 👆")


# ---------- izoh, telefon, karta ----------

@router.message(FoundForm.description, F.text)
async def got_description(message: Message, state: FSMContext):
    description = "" if message.text == BTN_SKIP else message.text.strip()
    if len(description) > 500:
        await message.answer("Izoh juda uzun. Iltimos, 500 belgigacha yozing.")
        return
    await state.update_data(description=description)
    await state.set_state(FoundForm.phone)
    await message.answer(
        "7/8. 📞 <b>Telefon raqamingizni yuboring.</b>\n\n"
        "🔒 Raqamingiz <b>kanalda chiqmaydi</b> — uni faqat admin ko'radi. "
        "Egasi topilib, to'lov qilgandan keyingina unga beriladi.",
        reply_markup=phone_kb(),
    )


@router.message(FoundForm.phone, F.contact)
async def got_contact(message: Message, state: FSMContext):
    await _save_phone(message, state, message.contact.phone_number)


@router.message(FoundForm.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    phone = message.text.replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        await message.answer("Raqam noto'g'ri. Tugmani bosing yoki +998901234567 ko'rinishida yozing.")
        return
    await _save_phone(message, state, phone)


async def _save_phone(message: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    await state.set_state(FoundForm.card)
    await message.answer(
        "8/8. 💳 <b>Suyunchi uchun karta raqamingiz</b>\n\n"
        f"Egasi topilsa, xizmat haqining <b>{FINDER_SHARE}%</b> qismi "
        f"(<b>{money(SERVICE_FEE * FINDER_SHARE // 100)} so'm</b>) kartangizga o'tkaziladi.\n"
        "🔒 Karta raqami ham faqat adminga ko'rinadi.\n\n"
        "16 xonali karta raqamini yozing yoki o'tkazib yuboring.",
        reply_markup=skip_kb(),
    )


@router.message(FoundForm.card, F.text)
async def got_card(message: Message, state: FSMContext):
    if message.text == BTN_SKIP:
        card = ""
    else:
        card = message.text.replace(" ", "")
        if not (card.isdigit() and len(card) == 16):
            await message.answer("Karta raqami 16 ta raqamdan iborat bo'lishi kerak. Qaytadan yozing:")
            return
        card = " ".join(card[i : i + 4] for i in range(0, 16, 4))

    await state.update_data(card=card)
    await state.set_state(FoundForm.confirm)
    data = await state.get_data()

    summary = (
        "📋 <b>E'loningizni tekshiring:</b>\n\n"
        f"<b>{category_label(data['category'])}</b>\n"
        f"{location_text(data, 200)}\n"
        f"📅 {escape(data['found_date'])}\n"
        f"📝 {escape(cut(data['description'], 350)) or '—'}\n\n"
        f"📞 {escape(data['phone'])} — {PRIVATE_NOTE}\n"
        f"💳 {card or '—'}"
    )
    if card:
        summary += f" — {PRIVATE_NOTE}"
    await message.answer("Deyarli tayyor ✅", reply_markup=ReplyKeyboardRemove())
    await message.answer_photo(data["photo_id"], caption=summary, reply_markup=confirm_found_kb())


@router.callback_query(FoundForm.confirm, F.data == "found:cancel")
async def found_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Bekor qilindi")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("E'lon bekor qilindi. Asosiy menyu 👇", reply_markup=main_menu())


@router.callback_query(FoundForm.confirm, F.data == "found:send")
async def found_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
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
            wait = await callback.message.answer("⏳ Rasmdagi shaxsiy ma'lumotlar yashirilmoqda, biroz kuting...")
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
        link = post_link(message_id)
        text = f"✅ E'loningiz kanalga chiqdi! Raqami: <b>#{code}</b>\n"
        if link:
            text += f"👉 {link}\n"
        text += "\nEgasi topilsa, sizga darhol xabar beramiz. Rahmat! 🙏"
    else:
        text = (
            f"✅ E'loningiz qabul qilindi! Raqami: <b>#{code}</b>\n\n"
            "Admin tekshirgandan so'ng kanalga chiqadi. Egasi topilsa, sizga xabar beramiz. Rahmat! 🙏"
        )
    await callback.message.answer(text, reply_markup=main_menu())

    # Hujjatni hozirdan o'qib qo'yamiz — egasi murojaat qilganda tekshiruv bir zumda bo'ladi
    prepare_document(bot, item)
