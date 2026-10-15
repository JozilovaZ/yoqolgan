"""Narsa egasi murojaat qiladigan va to'lov chekini yuboradigan bo'lim."""
import logging
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, User

import database as db
from config import ADMIN_GROUP_ID, AUTO_VERIFY_DOCUMENTS, PAYMENT_PROVIDER_TOKEN
from i18n import t
from keyboards import cancel_kb, claim_review_kb, claim_undo_kb, main_menu, payment_review_kb, phone_kb
from consent import require_terms
from services import request_payment
from verify import verify_document_claim
from utils import category_label, cut, is_document, item_code, item_details, user_link

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

PHONE_RE = re.compile(r"^\+?\d{9,13}$")


class ClaimForm(StatesGroup):
    proof = State()
    phone = State()


async def start_claim(message: Message, state: FSMContext, item_id: int, user: User, lang: str):
    """Kanaldagi "Bu meniki" tugmasi yoki qidiruv ro'yxatidan chaqiriladi."""
    item = await db.get_item(item_id)
    if not item or item["status"] != "published":
        await message.answer(t("claim.not_available", lang), reply_markup=main_menu(lang))
        return
    if item["finder_id"] == user.id:
        await message.answer(t("claim.own", lang), reply_markup=main_menu(lang))
        return

    open_claim = await db.get_open_claim(user.id, item_id)
    if open_claim:
        if open_claim["status"] == "awaiting_payment":
            if PAYMENT_PROVIDER_TOKEN:
                # To'lov oynasini qaytadan yuboramiz
                await request_payment(message.bot, open_claim, item)
                return
            text = t("claim.already_approved", lang)
        else:
            text = t("claim.in_review", lang)
        await message.answer(text, reply_markup=main_menu(lang))
        return

    if not await require_terms(message, user.id, f"claim_{item_id}", lang):
        return

    await state.set_state(ClaimForm.proof)
    await state.update_data(item_id=item_id)

    question = t("claim.q_proof_doc" if is_document(item["category"]) else "claim.q_proof_item", lang)
    await message.answer(
        t("claim.intro", lang, code=item_code(item_id), category=category_label(item["category"], lang)) + question,
        reply_markup=cancel_kb(lang),
    )


@router.message(ClaimForm.proof, F.text)
async def got_proof(message: Message, state: FSMContext, lang: str):
    if len(message.text) > 500:
        await message.answer(t("common.too_long_500", lang))
        return
    await state.update_data(proof=message.text.strip())
    await state.set_state(ClaimForm.phone)
    await message.answer(t("claim.q_phone", lang), reply_markup=phone_kb(lang))


@router.message(ClaimForm.phone, F.contact)
async def got_contact(message: Message, state: FSMContext, bot: Bot, lang: str):
    await _finish_claim(message, state, bot, message.contact.phone_number, lang)


@router.message(ClaimForm.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext, bot: Bot, lang: str):
    phone = message.text.replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        await message.answer(t("common.phone_invalid", lang))
        return
    await _finish_claim(message, state, bot, phone, lang)


async def _finish_claim(message: Message, state: FSMContext, bot: Bot, phone: str, lang: str):
    data = await state.get_data()
    await state.clear()
    user = message.from_user

    item = await db.get_item(data["item_id"])
    if not item or item["status"] != "published":
        await message.answer(t("claim.inactive", lang), reply_markup=main_menu(lang))
        return

    claim_id = await db.create_claim(
        {
            "item_id": item["id"],
            "owner_id": user.id,
            "owner_name": user.full_name,
            "owner_username": user.username,
            "owner_phone": phone,
            "proof": data["proof"],
        }
    )

    # Hujjat bo'lsa — avval OCR bilan o'zimiz tekshiramiz
    verdict = None
    if AUTO_VERIFY_DOCUMENTS and is_document(item["category"]):
        wait = await message.answer(t("claim.verifying", lang))
        verdict = await verify_document_claim(bot, item, data["proof"])
        await wait.delete()

    details = (
        f"{item_details(item)}\n\n"
        f"━━━━━━━━━━\n"
        f"👤 Egasi: {user_link(user.id, user.full_name, user.username)}\n"
        f"📞 {escape(phone)}\n"
        f"🔐 Isboti: <i>{escape(cut(data['proof'], 300))}</i>"
    )
    if verdict:
        details += f"\n\n{verdict.summary()}"

    approved = verdict is not None and verdict.approved
    if approved:
        await db.approve_claim(claim_id)
        caption = (
            f"🤖 <b>AVTOMATIK TASDIQLANDI</b> | murojaat №{claim_id}\n\n{details}\n\n"
            "Egasidan to'lov so'raldi. Xato bo'lsa, to'lovdan oldin bekor qiling 👇"
        )
        keyboard = claim_undo_kb(claim_id)
    else:
        caption = (
            f"🙋 <b>EGASI MUROJAAT QILDI</b> | murojaat №{claim_id}\n\n{details}\n\n"
            "Rasm bilan solishtiring va qaror qiling 👇"
        )
        keyboard = claim_review_kb(claim_id)
    try:
        await bot.send_photo(ADMIN_GROUP_ID, item["photo_id"], caption=caption, reply_markup=keyboard)
    except TelegramAPIError as error:
        logger.error("Admin guruhga yuborilmadi: %s", error)

    if approved:
        await message.answer(t("claim.auto_ok", lang), reply_markup=main_menu(lang))
        await request_payment(bot, await db.get_claim(claim_id), item)
        return

    await message.answer(t("claim.sent", lang), reply_markup=main_menu(lang))


@router.message(StateFilter(None), F.photo)
async def got_receipt(message: Message, bot: Bot, lang: str):
    """To'lov cheki (skrinshot). Holat DB da saqlanadi, shuning uchun bot qayta ishga tushsa ham ishlaydi."""
    claim = await db.get_claim_awaiting_payment(message.from_user.id)
    if not claim:
        await message.answer(t("claim.unknown_photo", lang), reply_markup=main_menu(lang))
        return

    item = await db.get_item(claim["item_id"])
    if item["status"] != "published":
        await db.update_claim(claim["id"], status="rejected")
        await message.answer(t("claim.receipt_item_gone", lang, code=item_code(item["id"])), reply_markup=main_menu(lang))
        return

    photo_id = message.photo[-1].file_id
    await db.save_receipt(claim["id"], photo_id)

    caption = (
        f"💸 <b>TO'LOV CHEKI</b> | murojaat №{claim['id']}\n\n"
        f"E'lon: <b>#{item_code(item['id'])}</b> — {category_label(item['category'])}\n"
        f"👤 To'lovchi: {user_link(claim['owner_id'], claim['owner_name'], claim['owner_username'])}\n"
        f"📞 {escape(claim['owner_phone'] or '')}\n\n"
        "Kartaga pul tushganini tekshiring 👇"
    )
    try:
        await bot.send_photo(ADMIN_GROUP_ID, photo_id, caption=caption, reply_markup=payment_review_kb(claim["id"]))
    except TelegramAPIError as error:
        logger.error("Admin guruhga yuborilmadi: %s", error)

    await message.answer(t("claim.receipt_ok", lang))
