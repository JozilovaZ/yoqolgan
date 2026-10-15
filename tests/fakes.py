"""Soxta Telegram: bot haqiqiy aiogram Dispatcher orqali ishlaydi, lekin so'rovlar Telegram'ga ketmaydi —
yozib olinadi va testda tekshiriladi."""
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    AnswerCallbackQuery,
    CopyMessage,
    GetMe,
    SendDocument,
    SendInvoice,
    SendMessage,
    SendPhoto,
)
from aiogram.types import CallbackQuery, Chat, Message, MessageId, Update, User

import database as db
from alerts import on_error
from config import ADMIN_GROUP_ID
from handlers import get_routers
from middlewares import BanMiddleware

ADMIN = 10  # admin guruh a'zosi
BOT_ID = 1

_dispatcher: Dispatcher | None = None


def dispatcher() -> Dispatcher:
    """Routerlar modul darajasida — ularni faqat bir marta ulash mumkin, shuning uchun bitta Dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher()
        _dispatcher.include_routers(*get_routers())
        _dispatcher.errors.register(on_error)
        for observer in (_dispatcher.message, _dispatcher.callback_query, _dispatcher.pre_checkout_query):
            observer.outer_middleware(BanMiddleware())
    return _dispatcher


class FakeSession(BaseSession):
    def __init__(self, telegram: "Telegram"):
        super().__init__()
        self.telegram = telegram

    async def make_request(self, bot, method, timeout=None):
        tg = self.telegram
        tg.calls.append(method)
        tg.counter += 1
        chat_id = getattr(method, "chat_id", None)
        if chat_id in tg.blocked:
            raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
        if isinstance(method, GetMe):
            return User(id=BOT_ID, is_bot=True, first_name="Izla", username="izla_bot")
        if isinstance(method, CopyMessage):
            return MessageId(message_id=tg.counter)
        if isinstance(method, (SendMessage, SendPhoto, SendDocument, SendInvoice)):
            chat = Chat(id=chat_id, type="supergroup" if chat_id < 0 else "private")
            return Message(
                message_id=tg.counter, date=datetime.now(), chat=chat, text=getattr(method, "text", None)
            ).as_(bot)
        return True

    async def stream_content(self, *args, **kwargs):
        yield b""

    async def close(self):
        pass


class Telegram:
    """Test uchun: xabar yuborish / tugma bosish va bot nima javob berganini tekshirish."""

    def __init__(self):
        self.calls: list = []
        self.counter = 1000
        self.blocked: set[int] = set()  # botni bloklagan foydalanuvchilar
        self.bot = Bot("123:test", session=FakeSession(self), default=DefaultBotProperties(parse_mode="HTML"))
        self.dp = dispatcher()
        self.dp.fsm.storage = MemoryStorage()  # oldingi testdagi suhbat holati (FSM) o'tib ketmasin
        self._update_id = 0

    # ---------- foydalanuvchi harakatlari ----------

    def message(self, text: str, user_id: int = ADMIN, chat_id: int | None = None, reply_to=None,
                message_id: int = 1, **extra) -> Message:
        chat_id = chat_id if chat_id is not None else (ADMIN_GROUP_ID if user_id == ADMIN else user_id)
        return Message(
            message_id=message_id,
            date=datetime.now(),
            chat=Chat(id=chat_id, type="supergroup" if chat_id < 0 else "private"),
            from_user=User(id=user_id, is_bot=False, first_name=f"User{user_id}", username=f"user{user_id}"),
            text=text,
            reply_to_message=reply_to,
            **extra,
        )

    async def send(self, text: str, user_id: int = ADMIN, chat_id: int | None = None, reply_to=None, **extra):
        """Botga xabar (yoki buyruq). Oldingi yozuvlar tozalanadi."""
        self.calls.clear()
        await self.feed(message=self.message(text, user_id, chat_id, reply_to, **extra))

    async def press(self, data: str, user_id: int = ADMIN, chat_id: int | None = None, text: str = "xabar"):
        """Inline tugma bosish. Oldingi yozuvlar tozalanadi."""
        self.calls.clear()
        chat_id = chat_id if chat_id is not None else (ADMIN_GROUP_ID if user_id == ADMIN else user_id)
        message = Message(
            message_id=55,
            date=datetime.now(),
            chat=Chat(id=chat_id, type="supergroup" if chat_id < 0 else "private"),
            from_user=User(id=BOT_ID, is_bot=True, first_name="Izla"),
            text=text,
        )
        callback = CallbackQuery(
            id=str(self._update_id),
            chat_instance="test",
            data=data,
            message=message,
            from_user=User(id=user_id, is_bot=False, first_name=f"User{user_id}"),
        )
        await self.feed(callback_query=callback)

    async def feed(self, **event):
        """Istalgan update: feed(pre_checkout_query=...), feed(message=...)."""
        self._update_id += 1
        await self.dp.feed_update(self.bot, Update(update_id=self._update_id, **event))

    # ---------- bot nima qildi ----------

    def sent(self, kind=SendMessage) -> list:
        return [call for call in self.calls if isinstance(call, kind)]

    def to(self, chat_id: int, kind=SendMessage) -> list:
        return [call for call in self.sent(kind) if call.chat_id == chat_id]

    def texts(self, chat_id: int) -> list[str]:
        return [call.text for call in self.to(chat_id)]

    def last_text(self) -> str:
        return self.sent()[-1].text

    def alerts(self) -> list[str]:
        return [call.text for call in self.calls if isinstance(call, AnswerCallbackQuery) and call.show_alert]

    def edits(self) -> list[str]:
        return [call.text for call in self.calls if type(call).__name__ == "EditMessageText"]

    @property
    def admin(self) -> list[str]:
        return self.texts(ADMIN_GROUP_ID)


def buttons(call) -> list[str]:
    """Xabardagi inline tugmalarning callback_data (yoki url) ro'yxati."""
    markup = getattr(call, "reply_markup", None)
    if not markup:
        return []
    return [button.callback_data or button.url for row in markup.inline_keyboard for button in row]


async def make_item(**fields) -> dict:
    """Kanalga chiqqan e'lon (sukut bo'yicha telefon, Toshkent)."""
    data = {
        "finder_id": 20, "finder_name": "Topuvchi", "finder_username": "topuvchi", "finder_phone": "+998901234567",
        "finder_card": "8600 1111 2222 3333", "category": "phone", "photo_id": "PHOTO", "region": "Toshkent",
        "place": "Chilonzor", "found_date": f"{datetime.now():%d.%m.%Y} (Payshanba)", "description": "qora",
        "status": "published", "channel_msg_id": 7, "publish_mode": "photo",
    }
    data.update(fields)
    return await db.get_item(await db.create_item(data))


async def make_claim(item_id: int, **fields) -> dict:
    data = {"item_id": item_id, "owner_id": 30, "owner_name": "Egasi", "owner_username": "egasi",
            "owner_phone": "+998937654321", "proof": "qora iPhone"}
    data.update(fields)
    return await db.get_claim(await db.create_claim(data))
