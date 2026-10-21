"""Narsa qo'lga tekkanini tasdiqlash: egasi va topuvchining javoblari, admin nizolarni hal qiladi.

Suyunchi faqat egasi "narsamni oldim" degandan (yoki admin tasdiqlagandan) keyin o'tkaziladi.
"""
import asyncio
import hmac
import re
import secrets
from html import escape
from io import BytesIO

import qrcode
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import database as db
from config import ADMIN_GROUP_ID, ADMIN_USERNAME
from i18n import t, user_lang
from keyboards import handover_kb
from services import report_dispute, request_payout
from utils import category_label, item_code, safe_send, user_link

router = Router()

CLOSED = ("confirmed", "refunded")
MAX_CODE_ATTEMPTS = 5
CODE_RE = re.compile(r"\d{6}")


async def _confirm(bot: Bot, claim: dict, item: dict, note: str) -> None:
    await db.update_claim(claim["id"], handover="confirmed")
    await safe_send(
        bot, item["finder_id"], t("ho.finder_confirmed", await user_lang(item["finder_id"]), code=item_code(item["id"]))
    )
    await request_payout(bot, claim, item, note)


@router.callback_query(F.data.startswith("ho:"))
async def handover_answer(callback: CallbackQuery, bot: Bot, lang: str):
    _, role, answer, claim_id = callback.data.split(":")
    claim = await db.get_claim(int(claim_id))
    item = claim and await db.get_item(claim["item_id"])
    expected_user = claim and (claim["owner_id"] if role == "o" else item["finder_id"])
    if not claim or claim["status"] != "completed" or callback.from_user.id != expected_user:
        await callback.answer(t("ho.not_active", lang), show_alert=True)
        return
    if claim["handover"] in CLOSED:
        await callback.answer(t("ho.already_closed", lang), show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await db.update_claim(claim["id"], **{"owner_answer" if role == "o" else "finder_answer": answer})
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    code = item_code(item["id"])

    if role == "o" and answer == "yes":
        await callback.message.answer(t("ho.owner_yes", lang))
        note = "✅ <b>Egasi narsani olganini tasdiqladi</b>"
        if claim["handover"] == "disputed":
            note += " — nizo hal bo'ldi"
        await _confirm(bot, claim, item, note)

    elif role == "f" and answer == "yes":
        await callback.message.answer(t("ho.finder_yes", lang))
        if not claim["owner_answer"]:
            owner_lang = await user_lang(claim["owner_id"])
            await safe_send(
                bot,
                claim["owner_id"],
                t("ho.ask_owner", owner_lang, code=code, category=category_label(item["category"], owner_lang)),
                reply_markup=handover_kb(claim["id"], "o", owner_lang),
            )

    else:  # "no" — nizo
        if role == "o":
            text = t(
                "ho.owner_no",
                lang,
                finder=user_link(item["finder_id"], item["finder_name"], item["finder_username"]),
                phone=escape(item["finder_phone"] or ""),
            )
            reason = "Egasi topuvchi bilan bog'lana olmayotganini aytdi."
        else:
            text = t("ho.finder_no", lang)
            reason = "Topuvchi egasi kelmagani / bog'lanmaganini aytdi."
        if ADMIN_USERNAME:
            text += "\n\n" + t("common.questions", lang, admin=ADMIN_USERNAME)
        await callback.message.answer(text, reply_markup=handover_kb(claim["id"], role, lang))
        if claim["handover"] != "disputed":  # admin bir marta xabardor qilinadi
            await db.update_claim(claim["id"], handover="disputed")
            await report_dispute(bot, claim["id"], reason)


# ---------- QR-kod bilan tasdiqlash ----------
# Egasi QR-kodni ko'rsatadi, topuvchi skanerlaydi (yoki 6 xonali kodni yozadi) — ikki tomon uchrashgani
# va egasi narsani olgani bir harakatda tasdiqlanadi. QR ko'rsatish = "Narsamni oldim" tugmasi.

def _qr_png(url: str) -> bytes:
    result = BytesIO()
    qrcode.make(url, box_size=10, border=4).save(result, format="PNG")
    return result.getvalue()


@router.callback_query(F.data.startswith("hoqr:"))
async def show_qr(callback: CallbackQuery, bot: Bot, lang: str):
    claim = await db.get_claim(int(callback.data.split(":")[1]))
    if not claim or claim["status"] != "completed" or callback.from_user.id != claim["owner_id"]:
        await callback.answer(t("ho.not_active", lang), show_alert=True)
        return
    if claim["handover"] in CLOSED:
        await callback.answer(t("ho.already_closed", lang), show_alert=True)
        return
    token, code = claim["handover_token"], claim["handover_code"]
    if not token:
        token = secrets.token_urlsafe(12)  # taxmin qilib bo'lmaydi
        code = f"{secrets.randbelow(10**6):06d}"
        await db.update_claim(claim["id"], handover_token=token, handover_code=code)
    me = await bot.me()
    image = await asyncio.to_thread(_qr_png, f"https://t.me/{me.username}?start=ho_{token}")
    await callback.answer()
    await callback.message.answer_photo(
        BufferedInputFile(image, filename="qr.png"),
        caption=t("ho.qr_caption", lang, item=item_code(claim["item_id"]), code=f"{code[:3]} {code[3:]}"),
        protect_content=True,  # forward qilib yoki saqlab bo'lmaydi — faqat ekrandan ko'rsatiladi
    )


async def _confirm_by_owner_code(bot: Bot, claim: dict, item: dict, how: str) -> None:
    await db.update_claim(claim["id"], owner_answer="yes", finder_answer="yes")
    note = f"📲 <b>Topshirish {how} bilan tasdiqlandi</b>"
    if claim["handover"] == "disputed":
        note += " — nizo hal bo'ldi"
    await _confirm(bot, claim, item, note)
    owner_lang = await user_lang(claim["owner_id"])
    await safe_send(bot, claim["owner_id"], t("ho.qr_owner_done", owner_lang, code=item_code(item["id"])))


async def confirm_by_qr(message: Message, token: str, lang: str) -> None:
    """Topuvchi QR-kodni skanerladi: /start ho_<token>."""
    claim = await db.get_claim_by_handover_token(token) if token else None
    if not claim or claim["status"] != "completed":
        await message.answer(t("ho.qr_invalid", lang))
        return
    if claim["handover"] in CLOSED:
        await message.answer(t("ho.already_closed", lang))
        return
    item = await db.get_item(claim["item_id"])
    if message.from_user.id == claim["owner_id"]:
        await message.answer(t("ho.qr_own", lang))
        return
    if message.from_user.id != item["finder_id"]:
        await message.answer(t("ho.qr_not_finder", lang))
        return
    await _confirm_by_owner_code(message.bot, claim, item, "QR-kod")


async def code_claims(message: Message) -> dict | bool:
    """Filtr: 6 xonali raqam va yozgan odam — egasi QR-kod olgan, hali topshirilmagan narsaning topuvchisi.
    Boshqa hollarda xabar keyingi routerlarga o'tadi (masalan, e'lon raqami qidiruvi)."""
    if not message.text or not CODE_RE.fullmatch(message.text.strip()):
        return False
    claims = await db.list_finder_code_handovers(message.from_user.id)
    return {"code_claims": claims} if claims else False


@router.message(StateFilter(None), F.chat.type == ChatType.PRIVATE, code_claims)
async def handover_code(message: Message, bot: Bot, lang: str, code_claims: list[dict]):
    code = message.text.strip()
    active = [claim for claim in code_claims if claim["handover_code_attempts"] < MAX_CODE_ATTEMPTS]
    if not active:
        await message.answer(t("ho.code_locked", lang))
        return
    for claim in active:
        if hmac.compare_digest(claim["handover_code"], code):
            await _confirm_by_owner_code(bot, claim, await db.get_item(claim["item_id"]), "6 xonali kod")
            return

    # Noto'g'ri — urinishlar cheklangan, aks holda topuvchi kodni tanlab topishi mumkin
    left = 0
    for claim in active:
        attempts = claim["handover_code_attempts"] + 1
        await db.update_claim(claim["id"], handover_code_attempts=attempts)
        left = max(left, MAX_CODE_ATTEMPTS - attempts)
        if attempts == MAX_CODE_ATTEMPTS:
            await safe_send(
                bot,
                ADMIN_GROUP_ID,
                f"🔒 #{item_code(claim['item_id'])}, murojaat №{claim['id']}: topuvchi topshirish kodini "
                f"{MAX_CODE_ATTEMPTS} marta noto'g'ri kiritdi — kod bloklandi (QR-kod ishlayveradi).",
            )
    await message.answer(t("ho.code_wrong", lang, left=left) if left else t("ho.code_locked", lang))


# ---------- admin: nizoni hal qilish ----------

@router.callback_query(F.data.startswith("hd:"), F.message.chat.id == ADMIN_GROUP_ID)
async def resolve_dispute(callback: CallbackQuery, bot: Bot):
    _, action, claim_id = callback.data.split(":")
    claim = await db.get_claim(int(claim_id))
    if not claim or claim["status"] != "completed" or claim["handover"] in CLOSED:
        await callback.answer("Bu murojaat allaqachon hal qilingan", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return
    item = await db.get_item(claim["item_id"])
    code = item_code(item["id"])
    who = escape(callback.from_user.full_name)

    if action == "ok":
        await callback.message.edit_text(
            callback.message.html_text + f"\n\n✅ Topshirildi deb belgilandi — <i>{who}</i>", reply_markup=None
        )
        await safe_send(bot, claim["owner_id"], t("ho.admin_ok_owner", await user_lang(claim["owner_id"]), code=code))
        await _confirm(bot, claim, item, f"✅ <b>Admin narsa topshirilganini tasdiqladi</b> — <i>{who}</i>")
    else:
        await db.update_claim(claim["id"], handover="refunded")
        await callback.message.edit_text(
            callback.message.html_text + f"\n\n↩️ Pul qaytarildi, murojaat yopildi — <i>{who}</i>", reply_markup=None
        )
        await safe_send(bot, claim["owner_id"], t("ho.refund_owner", await user_lang(claim["owner_id"]), code=code))
        finder_lang = await user_lang(item["finder_id"])
        text = t("ho.refund_finder", finder_lang, code=code)
        if ADMIN_USERNAME:
            text += "\n" + t("common.questions", finder_lang, admin=ADMIN_USERNAME)
        await safe_send(bot, item["finder_id"], text)
    await callback.answer("Saqlandi ✅")
