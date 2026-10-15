"""Narsa qo'lga tekkanini tasdiqlash: egasi va topuvchining javoblari, admin nizolarni hal qiladi.

Suyunchi faqat egasi "narsamni oldim" degandan (yoki admin tasdiqlagandan) keyin o'tkaziladi.
"""
from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

import database as db
from config import ADMIN_GROUP_ID, ADMIN_USERNAME
from keyboards import handover_kb
from services import report_dispute, request_payout
from utils import category_label, item_code, safe_send, user_link

router = Router()

CLOSED = ("confirmed", "refunded")


async def _confirm(bot: Bot, claim: dict, item: dict, note: str) -> None:
    await db.update_claim(claim["id"], handover="confirmed")
    await safe_send(
        bot,
        item["finder_id"],
        f"🎉 #{item_code(item['id'])}: narsa egasiga topshirilgani tasdiqlandi. "
        "Suyunchingiz tez orada o'tkaziladi. Rahmat! 🙏",
    )
    await request_payout(bot, claim, item, note)


@router.callback_query(F.data.startswith("ho:"))
async def handover_answer(callback: CallbackQuery, bot: Bot):
    _, role, answer, claim_id = callback.data.split(":")
    claim = await db.get_claim(int(claim_id))
    item = claim and await db.get_item(claim["item_id"])
    expected_user = claim and (claim["owner_id"] if role == "o" else item["finder_id"])
    if not claim or claim["status"] != "completed" or callback.from_user.id != expected_user:
        await callback.answer("Bu so'rov endi amalda emas", show_alert=True)
        return
    if claim["handover"] in CLOSED:
        await callback.answer("Bu murojaat allaqachon yopilgan ✅", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await db.update_claim(claim["id"], **{"owner_answer" if role == "o" else "finder_answer": answer})
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    code = item_code(item["id"])

    if role == "o" and answer == "yes":
        await callback.message.answer(
            "🎉 Ajoyib! Narsangiz qo'lingizga tekkanidan xursandmiz.\nBotimizdan foydalanganingiz uchun rahmat! 🙏"
        )
        note = "✅ <b>Egasi narsani olganini tasdiqladi</b>"
        if claim["handover"] == "disputed":
            note += " — nizo hal bo'ldi"
        await _confirm(bot, claim, item, note)

    elif role == "f" and answer == "yes":
        await callback.message.answer(
            "Rahmat! 🙏 Egasi ham narsani olganini tasdiqlagach, suyunchingiz o'tkaziladi."
        )
        if not claim["owner_answer"]:
            await safe_send(
                bot,
                claim["owner_id"],
                f"📦 Topuvchi #{code} — {category_label(item['category'])} narsani sizga topshirganini aytdi.\n"
                "Narsangizni olgan bo'lsangiz, tasdiqlang 👇",
                reply_markup=handover_kb(claim["id"], "o"),
            )

    else:  # "no" — nizo
        if role == "o":
            text = (
                "😔 Tushunarli. Admin siz bilan bog'lanib, yordam beradi.\n\n"
                f"Topuvchi: {user_link(item['finder_id'], item['finder_name'], item['finder_username'])} "
                f"📞 <b>{escape(item['finder_phone'] or '')}</b>\n\n"
                "Narsani olsangiz, pastdagi tugmani bosing 👇"
            )
            reason = "Egasi topuvchi bilan bog'lana olmayotganini aytdi."
        else:
            text = (
                "Tushunarli, admin xabardor qilindi.\n"
                "Egasi bog'lanib, narsani topshirsangiz — pastdagi tugmani bosing 👇"
            )
            reason = "Topuvchi egasi kelmagani / bog'lanmaganini aytdi."
        if ADMIN_USERNAME:
            text += f"\n\nSavollar uchun: {ADMIN_USERNAME}"
        await callback.message.answer(text, reply_markup=handover_kb(claim["id"], role))
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
        await safe_send(bot, claim["owner_id"], f"✅ #{code}: admin narsa sizga topshirilganini tasdiqladi. Rahmat! 🙏")
        await _confirm(bot, claim, item, f"✅ <b>Admin narsa topshirilganini tasdiqladi</b> — <i>{who}</i>")
    else:
        await db.update_claim(claim["id"], handover="refunded")
        await callback.message.edit_text(
            callback.message.html_text + f"\n\n↩️ Pul qaytarildi, murojaat yopildi — <i>{who}</i>", reply_markup=None
        )
        await safe_send(
            bot, claim["owner_id"], f"↩️ #{code} bo'yicha to'lovingiz qaytarildi. Noqulaylik uchun uzr so'raymiz."
        )
        text = f"#{code} bo'yicha kelishuv bekor qilindi — narsa egasiga topshirilmagani uchun suyunchi berilmaydi."
        if ADMIN_USERNAME:
            text += f"\nSavollar uchun: {ADMIN_USERNAME}"
        await safe_send(bot, item["finder_id"], text)
    await callback.answer("Saqlandi ✅")
