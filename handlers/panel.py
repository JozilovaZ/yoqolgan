"""Admin panel (faqat admin guruhda): qidirish, bloklash, xabar tarqatish, suyunchilar, statistika, Excel."""
import asyncio
import logging
import re
from datetime import date
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, LinkPreviewOptions, Message

import database as db
from config import ADMIN_GROUP_ID, FINDER_SHARE, SERVICE_FEE
from export import build_export
from keyboards import broadcast_kb, item_card_kb, payouts_list_kb, user_card_kb
from services import mark_post_returned, post_link
from utils import (
    CLAIM_STATUSES,
    ITEM_STATUSES,
    category_label,
    item_code,
    item_details,
    local_time,
    lost_code,
    lost_report_text,
    money,
    safe_send,
    user_link,
)

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.id == ADMIN_GROUP_ID)
router.callback_query.filter(F.message.chat.id == ADMIN_GROUP_ID)

FINDER_REWARD = SERVICE_FEE * FINDER_SHARE // 100
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

HELP = (
    "🛠 <b>Admin panel</b>\n\n"
    "🔎 <b>/find</b> — qidirish:\n"
    "   <code>/find T0012</code> — e'lon\n"
    "   <code>/find m15</code> — murojaat №15\n"
    "   <code>/find Y0003</code> — yo'qotdim qidiruvi\n"
    "   <code>/find +998901234567</code> — telefon bo'yicha\n"
    "   <code>/find @username</code> yoki <code>/find 123456789</code> — foydalanuvchi\n\n"
    "📊 <b>/stats</b> — statistika\n"
    "💸 <b>/payouts</b> — o'tkazilmagan suyunchilar\n"
    "📁 <b>/export</b> — bazani Excel faylga\n"
    "⏳ <b>/pending</b> — kanalga chiqmagan e'lonlar\n\n"
    "⛔ <b>/ban</b> @username [sabab] — bloklash\n"
    "✅ <b>/unban</b> @username — blokdan chiqarish\n"
    "📣 <b>/broadcast</b> — xabarga <i>javob (reply)</i> qilib yozing: shu xabar barcha foydalanuvchilarga yuboriladi"
)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP)


# ---------- qidirish ----------

def _item_card(item: dict, claims: list[dict]) -> str:
    lines = [
        f"📦 <b>#{item_code(item['id'])}</b> — {ITEM_STATUSES.get(item['status'], item['status'])}",
        f"🕐 Berilgan: {local_time(item['created_at'])} · Yopilgan: {local_time(item['closed_at'])}",
    ]
    if item["channel_msg_id"] and item["status"] in ("published", "returned") and post_link(item["channel_msg_id"]):
        lines.append(f"🔗 {post_link(item['channel_msg_id'])}")
    lines += ["", item_details(item), ""]
    if claims:
        lines.append("🙋 <b>Murojaatlar:</b>")
        for claim in claims:
            line = (
                f"• №{claim['id']} — {user_link(claim['owner_id'], claim['owner_name'], claim['owner_username'])} — "
                f"{CLAIM_STATUSES.get(claim['status'], claim['status'])}"
            )
            if claim["status"] == "completed":
                line += " · 💸 suyunchi o'tkazildi" if claim["payout_at"] else " · 💸 suyunchi <b>o'tkazilmagan</b>"
            lines.append(line)
    else:
        lines.append("🙋 Murojaat yo'q")
    return "\n".join(lines)


async def _send_item_card(message: Message, item_id: int) -> None:
    item = await db.get_item(item_id)
    if not item:
        await message.answer(f"#{item_code(item_id)} e'loni topilmadi.")
        return
    await message.answer(
        _item_card(item, await db.list_item_claims(item_id)),
        reply_markup=item_card_kb(item),
        link_preview_options=NO_PREVIEW,
    )


async def _send_user_card(message: Message, user_id: int) -> bool:
    user = await db.get_user(user_id)
    items = await db.list_user_items(user_id)
    claims = await db.list_user_claims(user_id)
    reports = await db.list_user_lost_reports(user_id)
    if not (user or items or claims):
        return False

    banned = bool(user and user["banned"])
    lines = [
        f"👤 {user_link(user_id, user and user['full_name'], user and user['username'])}",
        f"ID: <code>{user_id}</code> · Qo'shilgan: {local_time(user and user['created_at'])}",
    ]
    if banned:
        lines.append("⛔ <b>BLOKLANGAN</b>")
    lines += ["", f"📦 <b>E'lonlari</b> (oxirgi {len(items)} ta):" if items else "📦 E'lon bermagan"]
    lines += [
        f"• #{item_code(i['id'])} {category_label(i['category'])} — {ITEM_STATUSES.get(i['status'], i['status'])}"
        for i in items
    ]
    lines += ["", f"🙋 <b>Murojaatlari</b> (oxirgi {len(claims)} ta):" if claims else "🙋 Murojaat qilmagan"]
    lines += [
        f"• №{c['id']} → #{item_code(c['item_id'])} — {CLAIM_STATUSES.get(c['status'], c['status'])}" for c in claims
    ]
    if reports:
        lines += ["", "🔔 <b>Faol qidiruvlari:</b>"]
        lines += [f"• #{lost_code(r['id'])} {category_label(r['category'])}" for r in reports]
    lines += ["", "Batafsil: <code>/find T0012</code>, <code>/find m15</code>"]
    await message.answer("\n".join(lines), reply_markup=user_card_kb(user_id, banned))
    return True


async def _send_phone_results(message: Message, digits: str) -> bool:
    items = await db.find_items_by_phone(digits)
    claims = await db.find_claims_by_phone(digits)
    if not (items or claims):
        return False
    lines = [f"📞 <b>...{digits[-4:]}</b> raqami bo'yicha:"]
    if items:
        lines += ["", "📦 <b>Topuvchi sifatida:</b>"]
        lines += [
            f"• #{item_code(i['id'])} {category_label(i['category'])} — {ITEM_STATUSES.get(i['status'], i['status'])} — "
            f"{user_link(i['finder_id'], i['finder_name'], i['finder_username'])}"
            for i in items
        ]
    if claims:
        lines += ["", "🙋 <b>Egasi sifatida:</b>"]
        lines += [
            f"• №{c['id']} → #{item_code(c['item_id'])} — {CLAIM_STATUSES.get(c['status'], c['status'])} — "
            f"{user_link(c['owner_id'], c['owner_name'], c['owner_username'])}"
            for c in claims
        ]
    await message.answer("\n".join(lines))
    return True


@router.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject):
    query = (command.args or "").strip().lstrip("#№").strip()
    if not query:
        await message.answer(HELP)
        return
    upper = query.upper()

    if match := re.fullmatch(r"T?(\d{1,6})", upper):
        await _send_item_card(message, int(match.group(1)))
    elif match := re.fullmatch(r"M(\d+)", upper):
        claim = await db.get_claim(int(match.group(1)))
        if claim:
            await _send_item_card(message, claim["item_id"])
        else:
            await message.answer(f"Murojaat №{match.group(1)} topilmadi.")
    elif match := re.fullmatch(r"Y(\d+)", upper):
        report = await db.get_lost_report(int(match.group(1)))
        if not report:
            await message.answer(f"#{lost_code(int(match.group(1)))} qidiruvi topilmadi.")
            return
        status = "🔔 Faol" if report["status"] == "active" else "Yopilgan"
        await message.answer(
            f"{lost_report_text(report)}\n\nHolati: {status} · Berilgan: {local_time(report['created_at'])}\n"
            f"👤 {user_link(report['owner_id'], report['owner_name'], report['owner_username'])}",
            reply_markup=user_card_kb(report["owner_id"], await db.is_banned(report["owner_id"])),
        )
    elif query.startswith("@"):
        user = await db.find_user_by_username(query)
        if not user or not await _send_user_card(message, user["user_id"]):
            await message.answer(f"{escape(query)} topilmadi.")
    else:
        digits = re.sub(r"\D", "", query)
        if len(digits) < 7:
            await message.answer("Tushunmadim 🤔\n\n" + HELP)
            return
        # Uzun raqam: foydalanuvchi ID si ham, telefon ham bo'lishi mumkin — ikkalasini qidiramiz
        found = not query.startswith("+") and await _send_user_card(message, int(digits))
        found = await _send_phone_results(message, digits[-9:]) or found
        if not found:
            await message.answer(f"<code>{escape(query)}</code> bo'yicha hech narsa topilmadi.")


@router.callback_query(F.data.startswith("fi:photo:"))
async def show_photo(callback: CallbackQuery):
    item = await db.get_item(int(callback.data.split(":")[2]))
    if not item or not item["photo_id"]:
        await callback.answer("Rasm o'chirilgan (saqlash muddati tugagan)", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer_photo(item["photo_id"], caption=f"#{item_code(item['id'])}")


@router.callback_query(F.data.startswith("fi:user:"))
async def show_user(callback: CallbackQuery):
    await callback.answer()
    if not await _send_user_card(callback.message, int(callback.data.split(":")[2])):
        await callback.message.answer("Foydalanuvchi topilmadi.")


@router.callback_query(F.data.startswith("fi:ret:"))
async def ask_mark_returned(callback: CallbackQuery):
    item = await db.get_item(int(callback.data.split(":")[2]))
    if not item or item["status"] != "published":
        await callback.answer("Bu e'lon kanalda emas", show_alert=True)
        return
    await callback.answer("Yana bir bor bosing — tasdiqlash uchun")
    await callback.message.edit_reply_markup(reply_markup=item_card_kb(item, confirm_return=True))


@router.callback_query(F.data.startswith("fi:ret2:"))
async def mark_returned(callback: CallbackQuery, bot: Bot):
    """Narsa bot tashqarisida egasiga qaytarilgan (to'lovsiz) — e'lon yopiladi."""
    item = await db.get_item(int(callback.data.split(":")[2]))
    if not item or item["status"] != "published":
        await callback.answer("Bu e'lon kanalda emas", show_alert=True)
        return
    code = item_code(item["id"])
    await db.close_item(item["id"], "returned")
    await mark_post_returned(bot, item)
    closed = await db.close_open_claims(item["id"])
    for claim in closed:
        await safe_send(
            bot,
            claim["owner_id"],
            f"😔 #{code} e'loni yopildi — narsa egasiga qaytarilgan.\n"
            "Agar to'lov qilib qo'ygan bo'lsangiz, admin bilan bog'laning.",
        )
    await safe_send(bot, item["finder_id"], f"✅ #{code} e'loningiz yopildi — narsa egasiga qaytarildi. Rahmat! 🙏")

    note = f"\n\n✅ Qaytarildi deb belgilandi — <i>{escape(callback.from_user.full_name)}</i>"
    paid = [claim for claim in closed if claim["status"] == "payment_review"]
    if paid:
        note += "\n⚠️ Chek yuborgan murojaatlar yopildi, pulni qaytarish kerak: " + ", ".join(
            f"№{claim['id']}" for claim in paid
        )
    await callback.message.edit_text(
        callback.message.html_text + note,
        reply_markup=item_card_kb(await db.get_item(item["id"])),
        link_preview_options=NO_PREVIEW,
    )
    await callback.answer("Yopildi ✅")


# ---------- bloklash ----------

async def _resolve_user(value: str) -> int | None:
    if value.startswith("@"):
        user = await db.find_user_by_username(value)
        return user["user_id"] if user else None
    return int(value) if value.isdigit() else None


async def _set_banned(bot: Bot, user_id: int, banned: bool, reason: str = "") -> None:
    await db.set_banned(user_id, banned)
    if banned:
        text = "⛔ Siz botdan foydalanishdan cheklandingiz."
        if reason:
            text += f"\nSabab: {escape(reason)}"
    else:
        text = "✅ Cheklov olib tashlandi. Botdan yana foydalanishingiz mumkin: /start"
    await safe_send(bot, user_id, text)
    logger.info("Foydalanuvchi %s: banned=%s", user_id, banned)


@router.message(Command("ban", "unban"))
async def cmd_ban(message: Message, command: CommandObject, bot: Bot):
    banned = command.command == "ban"
    args = (command.args or "").split(maxsplit=1)
    if not args:
        await message.answer(f"Masalan: <code>/{command.command} @username</code> yoki <code>/{command.command} 123456789</code>")
        return
    user_id = await _resolve_user(args[0])
    if not user_id:
        await message.answer(
            f"{escape(args[0])} topilmadi. Foydalanuvchi botga /start bosmagan bo'lishi mumkin — ID bilan urinib ko'ring "
            "(<code>/find</code> orqali bilish mumkin)."
        )
        return
    if user_id == message.from_user.id:
        await message.answer("O'zingizni bloklay olmaysiz 🙂")
        return
    await _set_banned(bot, user_id, banned, args[1] if len(args) > 1 else "")
    user = await db.get_user(user_id)
    who = user_link(user_id, user["full_name"], user["username"])
    await message.answer(f"⛔ {who} bloklandi." if banned else f"✅ {who} blokdan chiqarildi.")


@router.callback_query(F.data.startswith("ban:"))
async def ban_button(callback: CallbackQuery, bot: Bot):
    _, action, user_id = callback.data.split(":")
    banned = action == "on"
    if int(user_id) == callback.from_user.id:
        await callback.answer("O'zingizni bloklay olmaysiz", show_alert=True)
        return
    await _set_banned(bot, int(user_id), banned)
    await callback.message.edit_reply_markup(reply_markup=user_card_kb(int(user_id), banned))
    await callback.answer("Bloklandi ⛔" if banned else "Blokdan chiqarildi ✅")


# ---------- xabar tarqatish ----------

_broadcast_task: asyncio.Task | None = None


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    target = message.reply_to_message
    if not target:
        await message.answer(
            "📣 Avval guruhga yubormoqchi bo'lgan xabarni yozing (matn, rasm, video — farqi yo'q), "
            "keyin unga <b>javob (reply)</b> qilib <code>/broadcast</code> deb yozing."
        )
        return
    users = await db.list_broadcast_users()
    await target.reply(
        f"📣 Shu xabar <b>{len(users)}</b> ta foydalanuvchiga yuboriladi. Tasdiqlaysizmi?",
        reply_markup=broadcast_kb(target.message_id, len(users)),
    )


@router.callback_query(F.data == "bc:no")
async def broadcast_cancel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("❌ Xabar tarqatish bekor qilindi.")


@router.callback_query(F.data.startswith("bc:go:"))
async def broadcast_start(callback: CallbackQuery, bot: Bot):
    global _broadcast_task
    if _broadcast_task and not _broadcast_task.done():
        await callback.answer("Hozir boshqa xabar yuborilmoqda, tugashini kuting", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(f"⏳ Yuborilmoqda... — <i>{escape(callback.from_user.full_name)}</i>")
    _broadcast_task = asyncio.create_task(_broadcast(bot, int(callback.data.split(":")[2]), callback.message))


async def _copy(bot: Bot, user_id: int, message_id: int) -> bool:
    try:
        await bot.copy_message(user_id, ADMIN_GROUP_ID, message_id)
        return True
    except TelegramRetryAfter as error:  # Telegram "sekinroq" desa — kutib, bir marta qayta urinamiz
        await asyncio.sleep(error.retry_after)
        return await _copy(bot, user_id, message_id) if error.retry_after < 60 else False
    except TelegramAPIError:  # botni bloklagan yoki akkaunti o'chgan
        return False


async def _broadcast(bot: Bot, message_id: int, status: Message) -> None:
    sent = failed = 0
    try:
        for user_id in await db.list_broadcast_users():
            if await _copy(bot, user_id, message_id):
                sent += 1
            else:
                failed += 1
            await asyncio.sleep(0.05)  # Telegram limiti: sekundiga ~30 ta xabar
    except Exception:
        logger.exception("Xabar tarqatish to'xtadi")
    finally:
        try:
            await status.edit_text(
                f"📣 <b>Xabar tarqatish tugadi</b>\n\n✅ Yetkazildi: {sent}\n❌ Yetmadi: {failed} "
                "<i>(botni bloklagan yoki akkaunti o'chgan)</i>"
            )
        except TelegramAPIError:
            pass


# ---------- suyunchilar ----------

def _payouts_text(rows: list[dict]) -> str:
    if not rows:
        return "✅ Barcha suyunchilar o'tkazilgan."
    lines = [
        f"💸 <b>O'tkazilmagan suyunchilar: {len(rows)} ta, jami {money(FINDER_REWARD * len(rows))} so'm</b>",
        "",
    ]
    for row in rows[:20]:
        lines.append(
            f"• #{item_code(row['id'])} — {user_link(row['finder_id'], row['finder_name'], row['finder_username'])}\n"
            f"   💳 <code>{escape(row['finder_card'] or 'kiritilmagan')}</code> — {money(FINDER_REWARD)} so'm"
        )
    if len(rows) > 20:
        lines.append(f"\n... va yana {len(rows) - 20} ta")
    lines.append("\nO'tkazgach, tugmani bosing 👇")
    return "\n".join(lines)


@router.message(Command("payouts"))
async def cmd_payouts(message: Message):
    rows = await db.list_unpaid_payouts()
    await message.answer(_payouts_text(rows), reply_markup=payouts_list_kb(rows[:20]) if rows else None)


@router.callback_query(F.data.startswith("po:"))
async def payout_done(callback: CallbackQuery, bot: Bot):
    _, source, claim_id = callback.data.split(":")
    if not await db.mark_payout(int(claim_id)):
        await callback.answer("Bu suyunchi allaqachon o'tkazilgan deb belgilangan", show_alert=True)
        return
    claim = await db.get_claim(int(claim_id))
    item = await db.get_item(claim["item_id"])
    await safe_send(
        bot,
        item["finder_id"],
        f"🎁 #{item_code(item['id'])} uchun suyunchingiz (<b>{money(FINDER_REWARD)} so'm</b>) o'tkazildi.\n"
        "Yaxshiligingiz uchun rahmat! 🙏",
    )
    if source == "list":
        rows = await db.list_unpaid_payouts()
        await callback.message.edit_text(_payouts_text(rows), reply_markup=payouts_list_kb(rows[:20]) if rows else None)
    else:
        await callback.message.edit_text(
            callback.message.html_text + f"\n\n✅ Suyunchi o'tkazildi — <i>{escape(callback.from_user.full_name)}</i>",
            reply_markup=None,
        )
    await callback.answer("Belgilandi ✅")


# ---------- statistika va eksport ----------

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    lines = ["📊 <b>Statistika</b>", ""]
    for period, title in (("today", "Bugun"), ("week", "7 kun"), ("month", "30 kun"), ("all", "Jami")):
        s = await db.get_period_stats(period)
        income = s["paid"] * SERVICE_FEE
        lines += [
            f"<b>{title}</b>",
            f"📦 E'lonlar: {s['items']} · 🙋 Murojaatlar: {s['claims']} · ✅ Qaytarildi: {s['returned']}",
            f"💰 Tushum: {money(income)} so'm (sof: {money(income - s['paid'] * FINDER_REWARD)})",
            f"👥 Yangi foydalanuvchilar: {s['users']} · 🔔 Qidiruvlar: {s['lost_reports']}",
            "",
        ]

    now = await db.get_stats()
    lines += [
        "<b>Hozir</b>",
        f"📢 Kanalda: {now['published']} · ⏳ Tekshiruvda: {now['pending']}",
        f"🙋 Admin javobini kutmoqda: {now['waiting_claims']} · 💳 To'lov kutilmoqda: {now['awaiting_payment']}",
        f"💸 O'tkazilmagan suyunchi: {now['unpaid_payouts']} ta ({money(now['unpaid_payouts'] * FINDER_REWARD)} so'm)",
        f"🔔 Faol qidiruvlar: {now['lost_active']}",
        f"👥 Foydalanuvchilar: {now['users']} · ⛔ Bloklangan: {now['banned']}",
    ]

    categories = await db.top_values("category")
    if categories:
        lines += ["", "<b>30 kunda eng ko'p topilganlar:</b>"]
        lines += [f"{category_label(row['value'])} — {row['count']}" for row in categories]
    regions = await db.top_values("region")
    if regions:
        lines += ["", "<b>Hududlar:</b>"]
        lines += [f"📍 {escape(row['value'])} — {row['count']}" for row in regions]
    await message.answer("\n".join(lines))


@router.message(Command("export"))
async def cmd_export(message: Message):
    wait = await message.answer("⏳ Fayl tayyorlanmoqda...")
    try:
        data = await build_export()
    except Exception as error:
        logger.exception("Eksport xatosi")
        await wait.edit_text(f"❌ Fayl tayyorlanmadi: {escape(str(error))}")
        return
    await wait.delete()
    await message.answer_document(
        BufferedInputFile(data, filename=f"izla-{date.today():%Y-%m-%d}.xlsx"),
        caption="📁 Baza: e'lonlar, murojaatlar, qidiruvlar, foydalanuvchilar.\n"
        "⚠️ Faylda telefon va karta raqamlari bor — guruhdan tashqariga yubormang.",
    )
