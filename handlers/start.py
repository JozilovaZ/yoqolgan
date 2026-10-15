from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import ADMIN_USERNAME, DATA_RETENTION_DAYS, FINDER_SHARE, SERVICE_FEE
from i18n import LOCALES, t
from keyboards import BUTTONS, lang_kb, main_menu
from utils import money

from .claim import start_claim

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject, lang: str):
    await state.clear()
    user = message.from_user
    first_time = await db.get_lang(user.id) is None
    await db.save_user(user.id, user.full_name, user.username)
    if first_time:
        await db.set_lang(user.id, lang)  # Telegram ilovasi tili bo'yicha taxmin — keyin o'zgartirsa bo'ladi

    # Kanaldagi "Bu meniki" tugmasidan kelgan bo'lsa: /start claim_15
    if command.args and command.args.startswith("claim_") and command.args[6:].isdigit():
        await start_claim(message, state, int(command.args[6:]), user, lang)
        return

    await message.answer(t("start.welcome", lang, name=user.first_name), reply_markup=main_menu(lang))
    if first_time:
        await message.answer(t("lang.choose", lang), reply_markup=lang_kb())


@router.message(StateFilter(None), Command("lang"))
@router.message(StateFilter(None), F.text.in_(BUTTONS["lang"]))
async def choose_lang(message: Message, lang: str):
    await message.answer(t("lang.choose", lang), reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    if lang not in LOCALES:
        await callback.answer()
        return
    await db.set_lang(callback.from_user.id, lang)
    await callback.answer(t("lang.set", lang))
    await callback.message.edit_text(t("lang.set", lang))
    await callback.message.answer(
        t("start.welcome", lang, name=callback.from_user.first_name), reply_markup=main_menu(lang)
    )


@router.message(StateFilter("*"), Command("cancel"))
@router.message(StateFilter("*"), F.text.in_(BUTTONS["cancel"]))
async def cancel(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(t("common.cancelled", lang), reply_markup=main_menu(lang))


@router.message(StateFilter(None), F.text.in_(BUTTONS["rules"]))
async def rules(message: Message, lang: str):
    text = t("rules.text", lang, fee=money(SERVICE_FEE), share=FINDER_SHARE, days=DATA_RETENTION_DAYS)
    if ADMIN_USERNAME:
        text += t("rules.questions", lang, admin=ADMIN_USERNAME)
    await message.answer(text)
