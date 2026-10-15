"""To'lovdan keyin egasi va topuvchi bot orqali yozishadi: xabarlar ikkinchi tomonga yetkaziladi va bazada
saqlanadi (nizo bo'lsa admin ko'radi)."""
import logging
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReactionTypeEmoji

import database as db
from config import ADMIN_GROUP_ID, ADMIN_USERNAME, CHAT_DAYS
from i18n import t, user_lang
from keyboards import BUTTONS, chat_kb, chat_reply_kb, main_menu
from utils import category_label, cut, item_code, local_time

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

# Izoh (caption) bilan yuboriladigan turlar — sarlavha izohga qo'shiladi
CAPTIONED = {"photo", "video", "document", "voice", "audio", "animation"}
# Izohsiz turlar — sarlavha alohida xabar bilan
PLAIN = {"location", "venue", "sticker", "video_note", "contact"}
KIND_LABELS = {
    "photo": "📷 rasm", "video": "🎬 video", "document": "📎 fayl", "voice": "🎤 ovozli xabar",
    "audio": "🎵 audio", "animation": "🎞 GIF", "location": "📍 lokatsiya", "venue": "📍 manzil",
    "sticker": "🙂 stiker", "video_note": "⏺ video xabar", "contact": "👤 kontakt",
}
TELEGRAM_LIMIT = 4000


class ChatForm(StatesGroup):
    active = State()


async def _open_chat(claim_id: int, user_id: int) -> tuple[dict, dict, str] | None:
    """(murojaat, e'lon, rol) — foydalanuvchi bu murojaat ishtirokchisi va yozishma hali ochiq bo'lsa."""
    claim = await db.get_claim(claim_id)
    if not claim or claim["status"] != "completed" or claim["handover"] == "refunded":
        return None
    item = await db.get_item(claim["item_id"])
    if user_id == claim["owner_id"]:
        role = "o"
    elif user_id == item["finder_id"]:
        role = "f"
    else:
        return None
    completed = datetime.fromisoformat(claim["completed_at"] or claim["created_at"]).replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - completed > timedelta(days=CHAT_DAYS):
        return None
    return claim, item, role


@router.callback_query(F.data.startswith("chat:"))
async def start_chat(callback: CallbackQuery, state: FSMContext, lang: str):
    opened = await _open_chat(int(callback.data.split(":")[1]), callback.from_user.id)
    if not opened:
        await callback.answer(t("chat.closed", lang), show_alert=True)
        return
    claim, item, role = opened
    await callback.answer()
    await state.set_state(ChatForm.active)
    await state.update_data(claim_id=claim["id"])
    await callback.message.answer(
        t(
            "chat.started",
            lang,
            code=item_code(item["id"]),
            category=category_label(item["category"], lang),
            other=t("chat.to_finder" if role == "o" else "chat.to_owner", lang),
            button=t("btn.chat_exit", lang),
        ),
        reply_markup=chat_kb(lang),
    )


@router.message(ChatForm.active, F.text.in_(BUTTONS["chat_exit"]))
async def exit_chat(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(t("chat.exited", lang), reply_markup=main_menu(lang))


@router.message(ChatForm.active)
async def relay(message: Message, state: FSMContext, bot: Bot, lang: str):
    claim_id = (await state.get_data())["claim_id"]
    opened = await _open_chat(claim_id, message.from_user.id)
    if not opened:
        await state.clear()
        await message.answer(t("chat.closed_menu", lang), reply_markup=main_menu(lang))
        return
    claim, item, role = opened
    kind = message.content_type
    if kind != "text" and kind not in CAPTIONED and kind not in PLAIN:
        await message.answer(t("chat.unsupported", lang))
        return

    recipient = item["finder_id"] if role == "o" else claim["owner_id"]
    recipient_lang = await user_lang(recipient)
    sender_name = t("chat.from_owner" if role == "o" else "chat.from_finder", recipient_lang)
    header = f"💬 <b>#{item_code(item['id'])}</b> · {sender_name}:"
    text = message.text or message.caption or ""
    keyboard = chat_reply_kb(claim["id"], recipient_lang)
    try:
        if kind == "text":
            await bot.send_message(recipient, f"{header}\n{escape(text)}", reply_markup=keyboard)
        elif kind in CAPTIONED:
            caption = f"{header}\n{escape(cut(text, 900))}" if text else header
            await bot.copy_message(recipient, message.chat.id, message.message_id, caption=caption, reply_markup=keyboard)
        else:
            await bot.send_message(recipient, header)
            await bot.copy_message(recipient, message.chat.id, message.message_id, reply_markup=keyboard)
    except TelegramAPIError as error:
        logger.warning("Chat xabari yetkazilmadi (%s): %s", recipient, error)
        text = t("chat.not_delivered", lang)
        text += t("chat.write_admin", lang, admin=ADMIN_USERNAME) if ADMIN_USERNAME else "."
        await message.answer(text)
        return

    await db.add_chat_message(claim["id"], message.from_user.id, kind, text)
    try:
        await message.react([ReactionTypeEmoji(emoji="👌")])  # yetkazildi
    except TelegramAPIError:
        pass


# ---------- admin: nizoda yozishmani ko'rish ----------

def transcript(messages: list[dict], claim: dict) -> list[str]:
    """Yozishma matni, Telegram xabar chegarasiga bo'lingan."""
    pages, current = [], f"💬 <b>Yozishma</b> | murojaat №{claim['id']}, #{item_code(claim['item_id'])}\n"
    for row in messages:
        who = "Egasi" if row["sender_id"] == claim["owner_id"] else "Topuvchi"
        body = escape(row["text"] or "")
        if row["kind"] != "text":
            body = f"<i>[{KIND_LABELS.get(row['kind'], row['kind'])}]</i> {body}".strip()
        line = f"\n<b>{who}</b> · {local_time(row['created_at'])}\n{body}\n"
        if len(current) + len(line) > TELEGRAM_LIMIT:
            pages.append(current)
            current = ""
        current += line
    pages.append(current)
    return pages


@router.callback_query(F.data.startswith("hc:"), F.message.chat.id == ADMIN_GROUP_ID)
async def show_transcript(callback: CallbackQuery):
    claim = await db.get_claim(int(callback.data.split(":")[1]))
    messages = claim and await db.list_chat_messages(claim["id"])
    if not messages:
        await callback.answer("Yozishma yo'q (yoki saqlash muddati tugagan)", show_alert=True)
        return
    await callback.answer()
    for page in transcript(messages, claim):
        await callback.message.answer(page)
