import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

import database as db
import images
from config import (
    ADMIN_GROUP_ID,
    BOT_TOKEN,
    CARD_NUMBER,
    CHANNEL_ID,
    WEB_PORT,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    WEBHOOK_URL,
)
from handlers import get_routers


def check_config() -> None:
    missing = [
        name
        for name, value in [
            ("BOT_TOKEN", BOT_TOKEN),
            ("ADMIN_GROUP_ID", ADMIN_GROUP_ID),
            ("CHANNEL_ID", CHANNEL_ID),
            ("CARD_NUMBER", CARD_NUMBER),
        ]
        if not value
    ]
    if "BOT_TOKEN" in missing:
        sys.exit(".env faylida BOT_TOKEN yo'q. README.md dagi ko'rsatmaga qarang.")
    if missing:
        logging.warning(".env da to'ldirilmagan: %s", ", ".join(missing))


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """Nginx orqasida ishlaydigan rejim: Telegram yangilanishlarni o'zi yuboradi."""
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    app = web.Application()
    app.router.add_get("/health", lambda request: web.Response(text="ok"))
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

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Asosiy menyu"),
            BotCommand(command="cancel", description="Bekor qilish"),
        ]
    )

    # OCR modelini fonda oldindan yuklab qo'yamiz (birinchi hujjat tez ishlashi uchun)
    preload = asyncio.create_task(asyncio.to_thread(images.get_reader))
    preload.add_done_callback(lambda task: task.exception() and logging.warning("OCR yuklanmadi: %s", task.exception()))

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
