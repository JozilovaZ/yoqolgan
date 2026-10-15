"""Narsa qo'lga tekkanini tasdiqlash: egasi va topuvchining javoblari, admin nizolarni hal qiladi.

Suyunchi faqat egasi "narsamni oldim" degandan (yoki admin tasdiqlagandan) keyin o'tkaziladi.
"""
from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

import database as db
from config import ADMIN_GROUP_ID, ADMIN_USERNAME
from i18n import t, user_lang
from keyboards import handover_kb
from services import report_dispute, request_payout
from utils import category_label, item_code, safe_send, user_link

router = Router()

CLOSED = ("confirmed", "refunded")


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
