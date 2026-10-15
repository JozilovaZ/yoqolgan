"""Bloklangan foydalanuvchilarning har qanday amalini to'xtatish va foydalanuvchi tilini aniqlash."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, TelegramObject

import database as db
from config import ADMIN_GROUP_ID
from i18n import guess_lang, t, user_lang


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

        text = t("common.banned", await user_lang(user.id))
        if isinstance(event, Message) and event.chat.type == ChatType.PRIVATE:
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, PreCheckoutQuery):
            await event.answer(ok=False, error_message=text)
        return None


class LangMiddleware(BaseMiddleware):
    """Handlerlarga `lang` beriladi: saqlangan til yoki (hali tanlanmagan bo'lsa) Telegram ilovasi tili."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        data["lang"] = (await db.get_lang(user.id) or guess_lang(user.language_code)) if user else "uz"
        return await handler(event, data)
