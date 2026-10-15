import logging
import re
from datetime import date, datetime, timezone
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import CATEGORIES
from geo import map_link
from keyboards import WEEKDAYS

logger = logging.getLogger(__name__)


def item_code(item_id: int) -> str:
    return f"T{item_id:04d}"


def lost_code(report_id: int) -> str:
    return f"Y{report_id:04d}"


def day_text(day: date) -> str:
    return f"{day:%d.%m.%Y} ({WEEKDAYS[day.weekday()]})"


ITEM_STATUSES = {
    "pending": "⏳ Tekshiruvda",
    "published": "📢 Kanalda",
    "returned": "✅ Egasiga qaytarildi",
    "removed": "🗑 O'chirilgan",
    "rejected": "❌ Rad etilgan",
}

CLAIM_STATUSES = {
    "checking": "⏳ Egasi tekshirilmoqda",
    "awaiting_payment": "💳 To'lov kutilmoqda",
    "payment_review": "🧾 Chek tekshirilmoqda",
    "completed": "✅ Yakunlangan",
    "rejected": "❌ Rad etilgan",
    "expired": "⌛ Muddati o'tgan",
}


def local_time(value: str | None) -> str:
    """Bazadagi UTC vaqt ("2026-10-15 09:30:00") -> mahalliy "15.10.2026 14:30"."""
    if not value:
        return "—"
    moment = datetime.fromisoformat(value).replace(tzinfo=timezone.utc).astimezone()
    return f"{moment:%d.%m.%Y %H:%M}"


def money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def cut(text: str | None, limit: int = 300) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def category_label(key: str) -> str:
    return CATEGORIES.get(key, CATEGORIES["other"])[0]


def is_document(key: str) -> bool:
    return CATEGORIES.get(key, CATEGORIES["other"])[2]


def user_link(user_id: int, name: str | None, username: str | None) -> str:
    link = f'<a href="tg://user?id={user_id}">{escape(name or "Foydalanuvchi")}</a>'
    if username:
        link += f" (@{escape(username)})"
    return link


def location_text(item: dict, limit: int = 250) -> str:
    """📍 manzil + xaritaga havola (lokatsiya bo'lsa)."""
    address = ", ".join(part for part in (item["region"], item["place"]) if part)
    text = f"📍 {escape(cut(address, limit) or 'Xaritada belgilangan')}"
    if item.get("latitude") is not None:
        text += f'\n🗺 <a href="{map_link(item["latitude"], item["longitude"])}">Xaritada ko\'rish</a>'
    return text


def channel_post_text(item: dict, returned: bool = False) -> str:
    code = item_code(item["id"])
    tag = CATEGORIES.get(item["category"], CATEGORIES["other"])[1]
    header = "✅ <b>EGASIGA QAYTARILDI</b>" if returned else "🔎 <b>TOPILDI</b>"
    hashtags = f"#{tag}"
    if item["region"]:
        # "Samarqand viloyati" -> #Samarqand
        hashtags += " #" + re.sub(r"\W", "", item["region"].split()[0])

    lines = [
        f"{header} | #{code}",
        "",
        f"<b>{category_label(item['category'])}</b>",
        location_text(item),
        f"📅 {escape(item['found_date'] or '')}",
    ]
    if item["description"]:
        lines.append(f"📝 {escape(cut(item['description'], 500))}")
    if not returned:
        lines += ["", "👇 Bu narsa sizniki bo'lsa, pastdagi tugmani bosing."]
    lines += ["", hashtags]
    return "\n".join(lines)


def item_details(item: dict) -> str:
    """Admin uchun e'lonning to'liq ma'lumotlari."""
    return "\n".join(
        [
            f"<b>{category_label(item['category'])}</b> | #{item_code(item['id'])}",
            location_text(item, 150),
            f"📅 {escape(item['found_date'] or '')}",
            f"📝 {escape(cut(item['description'], 200))}",
            "",
            f"👤 Topuvchi: {user_link(item['finder_id'], item['finder_name'], item['finder_username'])}",
            f"📞 {escape(item['finder_phone'] or '-')}",
            f"💳 {escape(item['finder_card'] or 'kiritilmagan')}",
        ]
    )


def lost_report_text(report: dict) -> str:
    """"Yo'qotdim" e'loni: egasining o'ziga ko'rsatish uchun."""
    header = f"<b>{category_label(report['category'])}</b>"
    if report.get("id"):
        header += f" | #{lost_code(report['id'])}"
    address = ", ".join(part for part in (report["region"], report["place"]) if part)
    lines = [
        header,
        f"📍 {escape(cut(address, 200) or 'aniq emas')}",
        f"📅 {day_text(date.fromisoformat(report['lost_day']))}",
    ]
    if report["description"]:
        lines.append(f"📝 {escape(cut(report['description'], 300))}")
    return "\n".join(lines)


def lost_match_text(item: dict, report: dict) -> str:
    """Yo'qotgan odamga: unga o'xshash narsa topilgani haqida xabar."""
    lines = [
        "🔔 <b>Siz qidirayotgan narsaga o'xshash narsa topildi!</b>",
        "",
        f"<b>{category_label(item['category'])}</b> | #{item_code(item['id'])}",
        location_text(item),
        f"📅 {escape(item['found_date'] or '')}",
    ]
    if item["description"]:
        lines.append(f"📝 {escape(cut(item['description'], 300))}")
    lines += [
        "",
        f"Qidiruvingiz: #{lost_code(report['id'])}",
        "Narsangiz bo'lsa, <b>«🙋 Bu meniki»</b> tugmasini bosing 👇",
    ]
    return "\n".join(lines)


async def safe_send(bot: Bot, chat_id: int | str, text: str, **kwargs) -> bool:
    """Foydalanuvchi botni bloklagan bo'lsa ham bot to'xtab qolmasligi uchun."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except TelegramAPIError as error:
        logger.warning("Xabar yuborilmadi (%s): %s", chat_id, error)
        return False
