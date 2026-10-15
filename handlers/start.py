from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import database as db
from config import ADMIN_USERNAME, FINDER_SHARE, SERVICE_FEE
from keyboards import BTN_CANCEL, BTN_RULES, main_menu
from utils import money

from .claim import start_claim

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

WELCOME = (
    "Assalomu alaykum, {name}! 👋\n\n"
    "Bu bot <b>yo'qolgan narsalarni egasiga qaytarishga</b> yordam beradi.\n\n"
    "📦 Biror narsa topdingizmi? — <b>«Narsa topdim»</b>\n"
    "🔍 Biror narsangizni yo'qotdingizmi? — <b>«Narsa yo'qotdim»</b>"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    await db.save_user(message.from_user.id, message.from_user.full_name, message.from_user.username)

    # Kanaldagi "Bu meniki" tugmasidan kelgan bo'lsa: /start claim_15
    if command.args and command.args.startswith("claim_") and command.args[6:].isdigit():
        await start_claim(message, state, int(command.args[6:]), message.from_user)
        return

    await message.answer(WELCOME.format(name=message.from_user.first_name), reply_markup=main_menu())


@router.message(StateFilter("*"), Command("cancel"))
@router.message(StateFilter("*"), F.text == BTN_CANCEL)
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi. Asosiy menyu 👇", reply_markup=main_menu())


@router.message(StateFilter(None), F.text == BTN_RULES)
async def rules(message: Message):
    text = (
        "ℹ️ <b>Bot qanday ishlaydi?</b>\n\n"
        "1️⃣ Narsa topgan odam bot orqali e'lon beradi.\n"
        "2️⃣ Admin tekshiradi va e'lon kanalga chiqadi.\n"
        "3️⃣ Egasi kanalda narsasini ko'rib, <b>«Bu meniki»</b> tugmasini bosadi.\n"
        "4️⃣ Egalikni isbotlash uchun narsa haqida savollarga javob beradi.\n"
        "5️⃣ Xizmat haqi to'lanadi va bot ikki tomonni bog'lab beradi.\n\n"
        "🔔 Narsangiz hali topilmagan bo'lsa, <b>«Narsa yo'qotdim»</b> bo'limida e'lon qoldiring — "
        "o'xshash narsa topilishi bilan bot sizga xabar beradi.\n\n"
        f"💰 Xizmat haqi: <b>{money(SERVICE_FEE)} so'm</b>\n"
        f"🎁 Shundan <b>{FINDER_SHARE}%</b> narsani topgan insonga suyunchi sifatida beriladi.\n\n"
        "🔐 Pasport va boshqa hujjatlardagi shaxsiy ma'lumotlar kanalda e'lon qilinmaydi."
    )
    if ADMIN_USERNAME:
        text += f"\n\n❓ Savollar uchun: {ADMIN_USERNAME}"
    await message.answer(text)
