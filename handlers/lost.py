"""Narsa yo'qotgan odam uchun bo'lim: qidiruv va "topilsa xabar bering" e'loni."""
from datetime import date

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import database as db
from config import CATEGORIES, CHANNEL_LINK, REGIONS
from keyboards import (
    BTN_LOST,
    BTN_MY_SEARCHES,
    BTN_SKIP,
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
from matching import is_match
from utils import category_label, day_text, lost_code, lost_report_text

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
    confirm = State()


@router.message(StateFilter(None), F.text == BTN_LOST)
async def lost(message: Message):
    text = "🔍 <b>Narsangizni yo'qotdingizmi?</b>\n\n"
    if CHANNEL_LINK:
        text += f"Barcha topilgan narsalar kanalimizda: {CHANNEL_LINK}\n\n"
    text += (
        "Quyida turini tanlang — oxirgi topilganlarni ko'rsataman. "
        "Topilmagan bo'lsa, e'lon qoldirasiz va o'xshash narsa topilishi bilan sizga xabar beraman 👇"
    )
    await message.answer(text, reply_markup=categories_kb("lost"))


@router.callback_query(F.data.startswith("lost:"))
async def lost_category(callback: CallbackQuery):
    category = callback.data.split(":", 1)[1]
    if category not in CATEGORIES:
        await callback.answer()
        return
    items = await db.list_published(category)
    await callback.answer()
    if items:
        text = (
            f"{category_label(category)} — oxirgi topilganlar.\n"
            "Batafsil ko'rish uchun kanalda e'lon raqamini qidiring.\n"
            "Narsangiz bo'lsa, ustiga bosing 👇\n\n"
            "Ro'yxatda yo'qmi? <b>«🔔 Topilsa xabar bering»</b> tugmasini bosing."
        )
    else:
        text = (
            f"{category_label(category)} bo'yicha hozircha e'lon yo'q 😔\n\n"
            "<b>«🔔 Topilsa xabar bering»</b> tugmasini bosing — o'xshash narsa topilishi bilan sizga darhol yozaman."
        )
    await callback.message.answer(text, reply_markup=lost_items_kb(items, subscribe_category=category))


@router.callback_query(F.data.startswith("claim:"))
async def claim_from_list(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await start_claim(callback.message, state, int(callback.data.split(":")[1]), callback.from_user)


# ---------- "Topilsa xabar bering" e'loni ----------

@router.callback_query(F.data.startswith("lostsub:"))
async def start_lost_report(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    await callback.answer()
    if category not in CATEGORIES:
        return
    if len(await db.list_user_lost_reports(callback.from_user.id)) >= MAX_ACTIVE_SEARCHES:
        await callback.message.answer(
            f"Sizda allaqachon {MAX_ACTIVE_SEARCHES} ta faol qidiruv bor.\n"
            f"Keraksizlarini <b>«{BTN_MY_SEARCHES}»</b> bo'limida to'xtatib, keyin yangisini qo'shing."
        )
        return

    await state.clear()
    await state.update_data(category=category)
    await state.set_state(LostForm.region)
    await callback.message.answer(
        f"🔔 <b>{category_label(category)}</b> uchun e'lon qoldiramiz.\n"
        "🔒 U kanalga chiqmaydi — faqat mos narsa topilganda sizga xabar berish uchun kerak.",
        reply_markup=cancel_kb(),
    )
    await callback.message.answer(
        "1/4. 🗺 <b>Qaysi viloyatda yo'qotdingiz?</b>", reply_markup=regions_kb(allow_unknown=True)
    )


@router.callback_query(LostForm.region, F.data.startswith("reg:"))
async def got_region(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[1]
    region = "" if value == "any" else REGIONS[int(value)]
    await state.update_data(region=region)
    await state.set_state(LostForm.place)
    await callback.answer()
    await callback.message.edit_text(f"1/4. 🗺 Viloyat: <b>{region or 'aniq bilmayman'}</b>")
    await callback.message.answer(
        "2/4. 📍 <b>Taxminan qayerda yo'qotdingiz?</b> (ixtiyoriy)\n"
        "<i>Masalan: Chilonzor tumani, 45-avtobusda, «Novza» metrosi atrofida</i>",
        reply_markup=skip_kb(),
    )


@router.message(LostForm.region)
async def region_required(message: Message):
    await message.answer("Iltimos, yuqoridagi ro'yxatdan <b>viloyatni tanlang</b> 👆")


@router.message(LostForm.place, F.text)
async def got_place(message: Message, state: FSMContext):
    place = "" if message.text == BTN_SKIP else message.text.strip()
    if len(place) > 200:
        await message.answer("Juda uzun. Iltimos, qisqaroq yozing (200 belgigacha).")
        return
    await state.update_data(place=place)
    await state.set_state(LostForm.lost_date)
    await message.answer("👌", reply_markup=cancel_kb())
    await message.answer(
        "3/4. 📅 <b>Qaysi kuni yo'qotdingiz?</b> Taxminiy kunni tanlang:\n"
        "<i>◀️ tugmasi bilan oldingi oylarga o'tish mumkin</i>",
        reply_markup=calendar_kb(),
    )


@router.callback_query(LostForm.lost_date, F.data.startswith("cal:nav:"))
async def calendar_navigate(callback: CallbackQuery):
    year, month = map(int, callback.data.split(":")[2].split("-"))
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(year, month))


@router.callback_query(LostForm.lost_date, F.data.startswith("day:"))
async def got_date(callback: CallbackQuery, state: FSMContext):
    day = date.fromisoformat(callback.data.split(":", 1)[1])
    if day > date.today():
        await callback.answer("Kelajakdagi kunni tanlab bo'lmaydi", show_alert=True)
        return
    await state.update_data(lost_day=day.isoformat())
    await state.set_state(LostForm.description)
    await callback.answer()
    await callback.message.edit_text(f"3/4. 📅 Sana: <b>{day_text(day)}</b>")
    await callback.message.answer(
        "4/4. 📝 <b>Narsangizni qisqacha tasvirlang</b> (ixtiyoriy)\n"
        "<i>Rangi, markasi, o'ziga xos belgilari. Bu matn hech qayerda e'lon qilinmaydi.</i>",
        reply_markup=skip_kb(),
    )


@router.message(LostForm.lost_date)
async def date_required(message: Message):
    await message.answer("Iltimos, yuqoridagi <b>kalendardan</b> kunni tanlang 👆")


@router.message(LostForm.description, F.text)
async def got_description(message: Message, state: FSMContext):
    description = "" if message.text == BTN_SKIP else message.text.strip()
    if len(description) > 500:
        await message.answer("Juda uzun. Iltimos, 500 belgigacha yozing.")
        return
    await state.update_data(description=description)
    await state.set_state(LostForm.confirm)
    data = await state.get_data()
    await message.answer("Deyarli tayyor ✅", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "📋 <b>E'loningizni tekshiring:</b>\n\n" + lost_report_text(data), reply_markup=confirm_lost_kb()
    )


@router.callback_query(LostForm.confirm, F.data == "lostform:cancel")
async def lost_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Bekor qilindi")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("E'lon bekor qilindi. Asosiy menyu 👇", reply_markup=main_menu())


@router.callback_query(LostForm.confirm, F.data == "lostform:save")
async def lost_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    user = callback.from_user

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
        }
    )
    report = await db.get_lost_report(report_id)

    await callback.message.answer(
        f"✅ E'loningiz saqlandi: <b>#{lost_code(report_id)}</b>\n\n"
        "🔔 O'xshash narsa topilishi bilan sizga darhol xabar beraman.\n"
        f"Qidiruvni <b>«{BTN_MY_SEARCHES}»</b> bo'limida to'xtatishingiz mumkin.",
        reply_markup=main_menu(),
    )

    # Kanalda allaqachon turgan mos e'lonlar
    matches = [item for item in await db.list_published(report["category"], limit=50) if is_match(report, item)]
    if matches:
        await callback.message.answer(
            f"👀 Hozirning o'zida <b>{len(matches)}</b> ta o'xshash e'lon bor. Narsangiz bo'lsa, ustiga bosing 👇",
            reply_markup=lost_items_kb(matches[:10]),
        )


# ---------- Qidiruvlarim ----------

@router.message(StateFilter(None), F.text == BTN_MY_SEARCHES)
async def my_searches(message: Message):
    reports = await db.list_user_lost_reports(message.from_user.id)
    if not reports:
        await message.answer(
            "Sizda faol qidiruv yo'q.\n\n"
            f"Biror narsangiz yo'qolgan bo'lsa, <b>«{BTN_LOST}»</b> bo'limida e'lon qoldiring — "
            "o'xshash narsa topilishi bilan sizga xabar beraman 🔔"
        )
        return
    text = "🔔 <b>Faol qidiruvlaringiz:</b>\n\n" + "\n\n".join(lost_report_text(report) for report in reports)
    text += "\n\nNarsangiz topilgan bo'lsa, qidiruvni to'xtating 👇"
    await message.answer(text, reply_markup=my_searches_kb(reports))


@router.callback_query(F.data.startswith("lostclose:"))
async def close_search(callback: CallbackQuery):
    report = await db.get_lost_report(int(callback.data.split(":")[1]))
    if not report or report["owner_id"] != callback.from_user.id or report["status"] != "active":
        await callback.answer("Bu qidiruv allaqachon to'xtatilgan", show_alert=True)
        return
    await db.update_lost_report(report["id"], status="closed")
    await callback.answer("Qidiruv to'xtatildi")
    await callback.message.answer(f"🔕 #{lost_code(report['id'])} qidiruvi to'xtatildi.")
