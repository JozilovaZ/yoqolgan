import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat

import database as db
import images
import instagram
from config import (
    ADMIN_GROUP_ID,
    BOT_TOKEN,
    CARD_NUMBER,
    PAYMENT_PROVIDER_TOKEN,
    CHANNEL_ID,
    INSTAGRAM_ENABLED,
    INSTAGRAM_TOKEN,
    MEDIA_PATH,
    WEB_PORT,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    WEBHOOK_URL,
)
from alerts import on_error
from handlers import get_routers
from middlewares import BanMiddleware, LangMiddleware
from utils import safe_send
from scheduler import run_scheduler


ADMIN_COMMANDS = [
    BotCommand(command="help", description="Admin panel: barcha buyruqlar"),
    BotCommand(command="find", description="Qidirish: T0012, m15, telefon, @username"),
    BotCommand(command="stats", description="Statistika"),
    BotCommand(command="payouts", description="O'tkazilmagan suyunchilar"),
    BotCommand(command="export", description="Bazani Excel faylga"),
    BotCommand(command="pending", description="Kanalga chiqmagan e'lonlar"),
    BotCommand(command="backup", description="Bazaning zaxira nusxasi"),
    BotCommand(command="ban", description="Bloklash: /ban @username sabab"),
    BotCommand(command="unban", description="Blokdan chiqarish"),
    BotCommand(command="broadcast", description="Xabarga reply qilib — barchaga yuborish"),
]


def check_config() -> None:
    missing = [
        name
        for name, value in [
            ("BOT_TOKEN", BOT_TOKEN),
            ("ADMIN_GROUP_ID", ADMIN_GROUP_ID),
            ("CHANNEL_ID", CHANNEL_ID),
            ("CARD_NUMBER", CARD_NUMBER or PAYMENT_PROVIDER_TOKEN),
        ]
        if not value
    ]
    if "BOT_TOKEN" in missing:
        sys.exit(".env faylida BOT_TOKEN yo'q. README.md dagi ko'rsatmaga qarang.")
    if missing:
        logging.warning(".env da to'ldirilmagan: %s", ", ".join(missing))
    if INSTAGRAM_TOKEN and not INSTAGRAM_ENABLED:
        logging.warning("Instagram o'chiq: INSTAGRAM_USER_ID va WEBHOOK_URL (domen) ham kerak")


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """Nginx orqasida ishlaydigan rejim: Telegram yangilanishlarni o'zi yuboradi."""
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    app = web.Application()
    app.router.add_get("/health", lambda request: web.Response(text="ok"))
    app.router.add_get(MEDIA_PATH + "/{name}", instagram.serve_media)  # Instagram rasmni shu yerdan oladi
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET or None).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", WEB_PORT).start()

    await bot.set_webhook(
        f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )
    logging.info("Bot ishga tushdi (webhook): %s%s", WEBHOOK_URL, WEBHOOK_PATH)
    await asyncio.Event().wait()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    check_config()
    await db.init_db()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(*get_routers())
    dp.errors.register(on_error)  # kutilmagan xato — admin guruhga xabar
    for observer in (dp.message, dp.callback_query, dp.pre_checkout_query):
        observer.outer_middleware(BanMiddleware())
        observer.outer_middleware(LangMiddleware())

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Asosiy menyu"),
            BotCommand(command="cancel", description="Bekor qilish"),
            BotCommand(command="lang", description="Tilni o'zgartirish / Язык"),
            BotCommand(command="oferta", description="Foydalanish shartlari"),
        ]
    )
    # Telegram ilovasi ruscha bo'lganlarga
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="cancel", description="Отмена"),
            BotCommand(command="lang", description="Сменить язык / Til"),
            BotCommand(command="oferta", description="Условия использования"),
        ],
        language_code="ru",
    )
    # Admin guruhda "/" bosilganda chiqadigan buyruqlar
    if ADMIN_GROUP_ID:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=ADMIN_GROUP_ID))
        except TelegramAPIError as error:
            logging.warning("Admin guruh buyruqlari o'rnatilmadi: %s", error)

    # OCR modelini fonda oldindan yuklab qo'yamiz (birinchi hujjat tez ishlashi uchun)
    preload = asyncio.create_task(asyncio.to_thread(images.get_reader))
    preload.add_done_callback(lambda task: task.exception() and logging.warning("OCR yuklanmadi: %s", task.exception()))

    await safe_send(bot, ADMIN_GROUP_ID, "🟢 Bot ishga tushdi")

    # Eslatmalar, muddati o'tganlarni yopish, eski shaxsiy ma'lumotlarni tozalash
    scheduler = asyncio.create_task(run_scheduler(bot))  # noqa: F841 — havola saqlanadi, aks holda GC o'chiradi

    if WEBHOOK_URL:
        await run_webhook(bot, dp)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Bot ishga tushdi (polling)")
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
