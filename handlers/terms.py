"""Oferta: /oferta buyrug'i, "Oferta matni" va "Roziman" tugmalari."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import CATEGORIES
from consent import OFFER_VERSION, offer_pages

from .claim import start_claim
from .found import start_found
from .lost import begin_lost_report

router = Router()


async def _send_offer(message: Message) -> None:
    for page in offer_pages():
        await message.answer(page)


@router.message(Command("oferta"), F.chat.type == "private")
async def cmd_offer(message: Message):
    await _send_offer(message)


@router.callback_query(F.data == "terms:read")
async def read_offer(callback: CallbackQuery):
    await callback.answer()
    await _send_offer(callback.message)


@router.callback_query(F.data.startswith("terms:ok:"))
async def accept_terms(callback: CallbackQuery, state: FSMContext):
    """Rozilik saqlanadi va foydalanuvchi to'xtagan joyidan davom etadi."""
    action = callback.data.split(":", 2)[2]
    await db.accept_terms(callback.from_user.id, OFFER_VERSION)
    await callback.answer("Rahmat! ✅")
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()

    message, user = callback.message, callback.from_user
    if action == "found":
        await start_found(message, state)
    elif action.startswith("claim_") and action[6:].isdigit():
        await start_claim(message, state, int(action[6:]), user)
    elif action.startswith("lostsub_") and action[8:] in CATEGORIES:
        await begin_lost_report(message, state, user.id, action[8:])
