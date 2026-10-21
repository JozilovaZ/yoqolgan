"""Kanalga chiqqan e'lonlarni Instagram biznes akkauntiga joylash (Meta Graph API).

Instagram rasmni fayl sifatida qabul qilmaydi — faqat ochiq havola orqali o'zi yuklab oladi.
Shuning uchun rasm vaqtincha MEDIA_DIR ga yoziladi va WEBHOOK_URL/media/<tasodifiy nom>.jpg orqali beriladi
(main.py dagi web server), joylangandan keyin o'chiriladi.

E'lon kanalga chiqqach navbatga qo'yiladi (ig_status = 'queued'). Navbat darhol fonda, keyin esa har
15 daqiqada (scheduler) qayta ko'riladi — Instagram vaqtincha ishlamasa yoki kunlik limit tugasa keyinroq joylanadi.

Eslatma: Graph API orqali Instagram postini o'chirib bo'lmaydi. Kanaldan o'chirilgan e'lonning Instagram
havolasi admin guruhga yuboriladi — qo'lda o'chiriladi.
"""
import asyncio
import logging
import os
import re
import secrets
from html import escape
from io import BytesIO

import aiohttp
from aiogram import Bot
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import database as db
from config import (
    ADMIN_GROUP_ID,
    CATEGORIES,
    INSTAGRAM_API_VERSION,
    INSTAGRAM_ENABLED,
    INSTAGRAM_TOKEN,
    INSTAGRAM_USER_ID,
    MEDIA_DIR,
    MEDIA_PATH,
    WEBHOOK_URL,
)
from utils import cut, item_code, safe_send

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
CAPTION_LIMIT = 2200
# Instagram qabul qiladigan nisbat (eni / bo'yi): 4:5 dan 1.91:1 gacha
MIN_RATIO, MAX_RATIO = 4 / 5, 1.91
# Shu kodlar — vaqtincha limit (kunlik post limiti, so'rovlar ko'pligi): urinish hisoblanmaydi, keyinroq qaytadan
RATE_LIMIT_CODES = {4, 9, 17, 32, 613}
MEDIA_NAME = re.compile(r"^[A-Za-z0-9_-]{20,}\.jpg$")

_lock = asyncio.Lock()
_tasks: set[asyncio.Task] = set()


class InstagramError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


# ---------- rasm ----------

def fit_ratio(data: bytes) -> bytes:
    """Instagram nisbatiga moslaydi: yetmagan joy rasmning o'zining xiralashgan nusxasi bilan to'ldiriladi."""
    image = Image.open(BytesIO(data)).convert("RGB")
    image.thumbnail((1440, 1440))
    width, height = image.size
    ratio = width / height
    if ratio < MIN_RATIO:
        size = (round(height * MIN_RATIO), height)
    elif ratio > MAX_RATIO:
        size = (width, round(width / MAX_RATIO))
    else:
        size = None
    if size:
        background = image.resize(size).filter(ImageFilter.GaussianBlur(radius=max(size) / 25))
        background.paste(image, ((size[0] - width) // 2, (size[1] - height) // 2))
        image = background
    result = BytesIO()
    image.save(result, format="JPEG", quality=90)
    return result.getvalue()


def text_card(item: dict) -> bytes:
    """Rasmsiz e'lon uchun oddiy kartochka (Instagram'ga rasmsiz post joylab bo'lmaydi)."""
    image = Image.new("RGB", (1080, 1080), (24, 64, 120))
    draw = ImageDraw.Draw(image)
    category = CATEGORIES.get(item["category"], CATEGORIES["other"])[0].split(" ", 1)[-1]  # emojisiz
    lines = [
        ("TOPILDI", 110),
        (category, 72),
        (item["region"] or "", 52),
        (f"#{item_code(item['id'])}", 64),
    ]
    y = 260
    for text, size in lines:
        if not text:
            continue
        font = ImageFont.load_default(size=size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text(((1080 - (right - left)) / 2, y - top), text, font=font, fill="white")
        y += (bottom - top) + 70
    result = BytesIO()
    image.save(result, format="JPEG", quality=90)
    return result.getvalue()


async def _download(bot: Bot, file_id: str) -> bytes:
    source = BytesIO()
    await bot.download(file_id, destination=source)
    return source.getvalue()


async def post_image(bot: Bot, item: dict) -> bytes:
    """Kanalda qanday chiqqan bo'lsa shunday rasm. Xiralashtirilgan rasm topilmasa — asl rasm emas, kartochka."""
    file_id = item["ig_photo_id"] or (item["photo_id"] if item["publish_mode"] == "photo" else None)
    if not file_id:
        return await asyncio.to_thread(text_card, item)
    return await asyncio.to_thread(fit_ratio, await _download(bot, file_id))


# ---------- matn ----------

def caption(item: dict, bot_username: str) -> str:
    """Instagram'da HTML ishlamaydi va havolalar bosilmaydi — oddiy matn, botga e'lon raqami bilan yo'naltiramiz."""
    code = item_code(item["id"])
    name, tag, _ = CATEGORIES.get(item["category"], CATEGORIES["other"])
    hashtags = [f"#{tag}", "#topildi", "#yoqolgan", "#izla"]
    if item["region"]:
        hashtags.append("#" + re.sub(r"\W", "", item["region"].split()[0]))
    lines = [f"🔎 TOPILDI | {code}", "", name]
    address = ", ".join(part for part in (item["region"], item["place"]) if part)
    if address:
        lines.append(f"📍 {cut(address, 250)}")
    if item["found_date"]:
        lines.append(f"📅 {item['found_date']}")
    if item["description"]:
        lines.append(f"📝 {cut(item['description'], 500)}")
    lines += [
        "",
        f"👉 Bu narsa sizniki bo'lsa: Telegram'da @{bot_username} botiga {code} deb yozing.",
        "",
        " ".join(hashtags),
    ]
    return cut("\n".join(lines), CAPTION_LIMIT)


# ---------- Graph API ----------

async def _graph(method: str, path: str, **params) -> dict:
    url = f"https://graph.facebook.com/{INSTAGRAM_API_VERSION}/{path}"
    params["access_token"] = INSTAGRAM_TOKEN
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        async with session.request(method, url, data=params if method == "POST" else None,
                                   params=params if method == "GET" else None) as response:
            data = await response.json(content_type=None)
    if "error" in data:
        error = data["error"]
        raise InstagramError(error.get("error_user_msg") or error.get("message", "noma'lum xato"), error.get("code"))
    return data


async def _wait_container(container_id: str) -> None:
    """Rasm odatda darhol tayyor bo'ladi, lekin ba'zan Meta bir necha soniya ishlaydi."""
    for _ in range(10):
        status = (await _graph("GET", container_id, fields="status_code")).get("status_code")
        if status in (None, "FINISHED"):
            return
        if status in ("ERROR", "EXPIRED"):
            raise InstagramError(f"rasm qabul qilinmadi ({status})")
        await asyncio.sleep(3)
    raise InstagramError("rasm tayyor bo'lishi kutib turildi, lekin tugamadi")


async def publish(bot: Bot, item: dict) -> tuple[str, str]:
    """E'lonni Instagram'ga joylaydi. Qaytaradi: (media_id, permalink)."""
    me = await bot.me()
    image = await post_image(bot, item)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    name = f"{secrets.token_urlsafe(24)}.jpg"  # taxmin qilib bo'lmaydigan nom
    path = os.path.join(MEDIA_DIR, name)
    with open(path, "wb") as file:
        file.write(image)
    try:
        container = await _graph(
            "POST",
            f"{INSTAGRAM_USER_ID}/media",
            image_url=f"{WEBHOOK_URL}{MEDIA_PATH}/{name}",
            caption=caption(item, me.username),
        )
        await _wait_container(container["id"])
        media = await _graph("POST", f"{INSTAGRAM_USER_ID}/media_publish", creation_id=container["id"])
    finally:
        os.remove(path)
    try:
        permalink = (await _graph("GET", media["id"], fields="permalink")).get("permalink", "")
    except InstagramError:
        permalink = ""  # post joylandi, faqat havolasi olinmadi
    return media["id"], permalink


# ---------- navbat ----------

async def enqueue(bot: Bot, item_id: int, photo_id: str | None) -> None:
    """E'lon kanalga chiqdi — Instagram navbatiga qo'yiladi va fonda joylanadi."""
    if not INSTAGRAM_ENABLED:
        return
    await db.update_item(item_id, ig_status="queued", ig_photo_id=photo_id)
    task = asyncio.create_task(process_queue(bot))
    _tasks.add(task)  # havola saqlanadi, aks holda GC tugamagan vazifani o'chirib yuborishi mumkin
    task.add_done_callback(_tasks.discard)


async def process_queue(bot: Bot) -> None:
    """Navbatdagi e'lonlarni joylaydi. Bir vaqtda faqat bitta — bitta e'lon ikki marta joylanmasin."""
    if not INSTAGRAM_ENABLED:
        return
    async with _lock:
        for item in await db.list_instagram_queue():
            if item["status"] != "published":
                await db.update_item(item["id"], ig_status="skipped")  # navbatda turganda yopildi
                continue
            try:
                media_id, permalink = await publish(bot, item)
            except InstagramError as error:
                if error.code in RATE_LIMIT_CODES:
                    logger.warning("Instagram limiti: %s — keyinroq qayta uriniladi", error)
                    return
                await _failed(bot, item, str(error))
                continue
            except Exception as error:  # tarmoq xatosi, rasm buzuq va h.k.
                logger.exception("Instagram'ga joylanmadi: #%s", item["id"])
                await _failed(bot, item, f"{type(error).__name__}: {error}")
                continue
            await db.update_item(
                item["id"], ig_status="posted", ig_media_id=media_id, ig_permalink=permalink, ig_error=None
            )
            logger.info("#%s Instagram'ga joylandi: %s", item["id"], permalink or media_id)


async def _failed(bot: Bot, item: dict, error: str) -> None:
    attempts = item["ig_attempts"] + 1
    if attempts < MAX_ATTEMPTS:
        await db.update_item(item["id"], ig_attempts=attempts, ig_error=error)
        logger.warning("#%s Instagram'ga joylanmadi (%d-urinish): %s", item["id"], attempts, error)
        return
    await db.update_item(item["id"], ig_status="failed", ig_attempts=attempts, ig_error=error)
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        f"📷 #{item_code(item['id'])} Instagram'ga joylanmadi ({attempts} marta urinildi).\n"
        f"Sabab: {cut(error, 300)}\n\n"
        "Token muddati tugagan yoki akkaunt sozlamalari o'zgargan bo'lishi mumkin (DEPLOY.md, Instagram bo'limi).",
        parse_mode=None,
    )


def removal_note(item: dict) -> str:
    """Kanaldan o'chirilgan e'lon Instagram'da qoladi — admin qo'lda o'chirishi uchun eslatma."""
    if item.get("ig_status") == "posted":
        return f"\n📷 Instagram'dagi postni qo'lda o'chiring: {escape(item['ig_permalink'] or item['ig_media_id'])}"
    return ""


async def serve_media(request):
    """WEBHOOK_URL/media/<nom>.jpg — Instagram rasmni shu yerdan yuklab oladi."""
    from aiohttp import web

    name = request.match_info["name"]
    path = os.path.join(MEDIA_DIR, name)
    if not MEDIA_NAME.match(name) or not os.path.isfile(path):
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Content-Type": "image/jpeg", "Cache-Control": "no-store"})
