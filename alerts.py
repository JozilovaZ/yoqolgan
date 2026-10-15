"""Kutilmagan xatolar haqida admin guruhga xabar. Bir xil xato 30 daqiqada bir martadan ko'p yuborilmaydi."""
import logging
import os
import time
import traceback
from html import escape

from aiogram import Bot
from aiogram.types import CallbackQuery, ErrorEvent, Message

from config import ADMIN_GROUP_ID
from i18n import t, user_lang
from utils import cut, safe_send

logger = logging.getLogger(__name__)

THROTTLE_SECONDS = 30 * 60

# xato kaliti -> oxirgi yuborilgan vaqt
_last_sent: dict[str, float] = {}


async def report_error(bot: Bot, where: str, error: BaseException) -> None:
    key = f"{where.split(',')[0]}|{type(error).__name__}|{str(error)[:100]}"
    now = time.monotonic()
    if key in _last_sent and now - _last_sent[key] < THROTTLE_SECONDS:
        return
    _last_sent[key] = now

    frames = traceback.extract_tb(error.__traceback__) if error.__traceback__ else []
    # Bizning koddagi oxirgi qator (kutubxonalar ichidagisi emas)
    ours = [frame for frame in frames if "site-packages" not in frame.filename] or frames
    location = f"{os.path.basename(ours[-1].filename)}:{ours[-1].lineno}" if ours else "?"
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        "🐞 <b>Botda xato</b>\n\n"
        f"📍 {escape(where)}\n"
        f"❗ <code>{escape(type(error).__name__)}: {escape(cut(str(error), 300))}</code>\n"
        f"📄 {escape(location)}\n\n"
        "Batafsil: <code>docker compose logs bot</code>\n"
        "<i>Bir xil xato 30 daqiqada bir marta yuboriladi.</i>",
    )


async def on_error(event: ErrorEvent, bot: Bot) -> None:
    """Dispatcher: handler ichida ushlanmagan har qanday xato."""
    logger.error("Update ishlovida xato: %s", event.exception, exc_info=event.exception)
    update = event.update
    user = getattr(update.event, "from_user", None)
    where = update.event_type + (f", foydalanuvchi {user.id}" if user else "")
    await report_error(bot, where, event.exception)

    # Foydalanuvchi javobsiz qolmasin
    try:
        text = t("common.error", await user_lang(user.id) if user else "uz")
        if isinstance(update.event, Message) and update.event.chat.type == "private":
            await update.event.answer(text)
        elif isinstance(update.event, CallbackQuery):
            await update.event.answer(text, show_alert=True)
    except Exception:  # xato haqidagi xabar yangi xato chiqarmasin (masalan, baza ishlamasa)
        pass
