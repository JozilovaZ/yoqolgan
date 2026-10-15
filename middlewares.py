"""Bloklangan foydalanuvchilarning har qanday amalini to'xtatish."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, TelegramObject

import database as db
from config import ADMIN_GROUP_ID

BANNED_TEXT = "⛔ Siz botdan foydalanishdan cheklangansiz."


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        # Admin guruhdagi amallar tekshirilmaydi
        if not user or (chat and chat.id == ADMIN_GROUP_ID) or not await db.is_banned(user.id):
            return await handler(event, data)

        if isinstance(event, Message) and event.chat.type == ChatType.PRIVATE:
            await event.answer(BANNED_TEXT)
        elif isinstance(event, CallbackQuery):
            await event.answer(BANNED_TEXT, show_alert=True)
        elif isinstance(event, PreCheckoutQuery):
            await event.answer(ok=False, error_message=BANNED_TEXT)
        return None
