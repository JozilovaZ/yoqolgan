import calendar
from datetime import date, datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CATEGORIES, REGIONS
from i18n import category_label, months, region_label, t, variants, weekdays

# Asosiy (o'zbekcha) matnlar — testlar va eski kod uchun. Handlerlarda tugmalar barcha tillarda tekshiriladi:
# F.text.in_(BUTTONS["found"])
BTN_FOUND = t("btn.found")
BTN_LOST = t("btn.lost")
BTN_MY_SEARCHES = t("btn.my_searches")
BTN_MY_ITEMS = t("btn.my_items")
BTN_RULES = t("btn.rules")
BTN_CANCEL = t("btn.cancel")
BTN_SKIP = t("btn.skip")
BTN_MANUAL_ADDRESS = t("btn.manual_address")
BTN_CHAT_EXIT = t("btn.chat_exit")

BUTTONS = {
    name: variants(f"btn.{name}")
    for name in (
        "found", "lost", "my_searches", "my_items", "rules", "lang", "cancel", "skip", "manual_address", "chat_exit"
    )
}


def main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn.found", lang)), KeyboardButton(text=t("btn.lost", lang))],
            [KeyboardButton(text=t("btn.my_items", lang)), KeyboardButton(text=t("btn.my_searches", lang))],
            [KeyboardButton(text=t("btn.rules", lang)), KeyboardButton(text=t("btn.lang", lang))],
        ],
        resize_keyboard=True,
    )


def lang_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang:uz")
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru")
    return builder.as_markup()


def cancel_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t("btn.cancel", lang))]], resize_keyboard=True)


def chat_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t("btn.chat_exit", lang))]], resize_keyboard=True)


def chat_reply_kb(claim_id: int, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("kb.chat_reply", lang), callback_data=f"chat:{claim_id}")
    return builder.as_markup()


def location_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn.send_location", lang), request_location=True)],
            [KeyboardButton(text=t("btn.manual_address", lang))],
            [KeyboardButton(text=t("btn.cancel", lang))],
        ],
        resize_keyboard=True,
    )


def regions_kb(allow_unknown: bool = False, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    for index, region in enumerate(REGIONS):
        builder.button(text=region_label(region, lang), callback_data=f"reg:{index}")
    builder.adjust(2)
    if allow_unknown:
        builder.row(InlineKeyboardButton(text=t("kb.unknown", lang), callback_data="reg:any"))
    return builder.as_markup()


def _ignore(text: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data="cal:ignore")


def calendar_kb(year: int | None = None, month: int | None = None, lang: str = "uz") -> InlineKeyboardMarkup:
    """Oylik kalendar. Kelajakdagi kunlarni tanlab bo'lmaydi."""
    today = date.today()
    year, month = year or today.year, month or today.month

    prev_month = date(year, month, 1) - timedelta(days=1)
    next_month = date(year, month, 28) + timedelta(days=4)
    is_current = (year, month) == (today.year, today.month)

    rows = [
        [
            InlineKeyboardButton(text="◀️", callback_data=f"cal:nav:{prev_month:%Y-%m}"),
            _ignore(f"{months(lang)[month - 1]} {year}"),
            _ignore("·") if is_current else InlineKeyboardButton(text="▶️", callback_data=f"cal:nav:{next_month:%Y-%m}"),
        ],
        [_ignore(name) for name in weekdays(lang, short=True)],
    ]
    for week in calendar.monthcalendar(year, month):
        row = []
        for day_number in week:
            if day_number == 0:
                row.append(_ignore(" "))
                continue
            day = date(year, month, day_number)
            if day > today:
                row.append(_ignore("·"))
            else:
                label = f"[{day_number}]" if day == today else str(day_number)
                row.append(InlineKeyboardButton(text=label, callback_data=f"day:{day.isoformat()}"))
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(text=t("kb.today", lang), callback_data=f"day:{today.isoformat()}"),
            InlineKeyboardButton(
                text=t("kb.yesterday", lang), callback_data=f"day:{(today - timedelta(days=1)).isoformat()}"
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hours_kb(day: date, lang: str = "uz"):
    """Soatlar: 00:00 ... 23:00. Bugun bo'lsa, hali kelmagan soatlar chiqmaydi."""
    builder = InlineKeyboardBuilder()
    last_hour = datetime.now().hour if day == date.today() else 23
    for hour in range(last_hour + 1):
        builder.button(text=f"{hour:02d}:00", callback_data=f"hour:{hour}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text=t("kb.unknown", lang), callback_data="hour:unknown"))
    return builder.as_markup()


def phone_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn.send_phone", lang), request_contact=True)],
            [KeyboardButton(text=t("btn.cancel", lang))],
        ],
        resize_keyboard=True,
    )


def skip_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn.skip", lang))], [KeyboardButton(text=t("btn.cancel", lang))]],
        resize_keyboard=True,
    )


def categories_kb(prefix: str, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    for key in CATEGORIES:
        builder.button(text=category_label(key, lang), callback_data=f"{prefix}:{key}")
    builder.adjust(2)
    return builder.as_markup()


def terms_kb(action: str, offer_url: str = "", lang: str = "uz"):
    """action — rozilikdan keyin davom etadigan amal: found / claim_15 / lostsub_phone."""
    builder = InlineKeyboardBuilder()
    if offer_url:
        builder.button(text=t("kb.offer_text", lang), url=offer_url)
    else:
        builder.button(text=t("kb.offer_text", lang), callback_data="terms:read")
    builder.button(text=t("kb.agree", lang), callback_data=f"terms:ok:{action}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_found_kb(lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("kb.send", lang), callback_data="found:send")
    builder.button(text=t("kb.cancel", lang), callback_data="found:cancel")
    return builder.as_markup()


def channel_post_kb(bot_username: str, item_id: int):
    """Kanal posti — doim o'zbekcha."""
    builder = InlineKeyboardBuilder()
    builder.button(text=t("kb.claim"), url=f"https://t.me/{bot_username}?start=claim_{item_id}")
    return builder.as_markup()


def lost_items_kb(items: list[dict], subscribe_category: str | None = None, lang: str = "uz"):
    from utils import item_code

    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=f"🙋 #{item_code(item['id'])} — {region_label(item['region'], lang)}, {item['found_date']}",
            callback_data=f"claim:{item['id']}",
        )
    if subscribe_category:
        builder.button(text=t("kb.subscribe", lang), callback_data=f"lostsub:{subscribe_category}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_lost_kb(lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("kb.save", lang), callback_data="lostform:save")
    builder.button(text=t("kb.cancel", lang), callback_data="lostform:cancel")
    return builder.as_markup()


def lost_match_kb(item_id: int, report_id: int, post_url: str = "", lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("kb.claim", lang), callback_data=f"claim:{item_id}")
    if post_url:
        builder.button(text=t("kb.view_channel", lang), url=post_url)
    builder.button(text=t("kb.stop_search", lang), callback_data=f"lostclose:{report_id}")
    builder.adjust(1)
    return builder.as_markup()


def lookup_kb(item_id: int, post_url: str = "", own: bool = False, lang: str = "uz"):
    """E'lon raqami bo'yicha topilgan e'lon: "Bu meniki" (yoki o'z e'loni bo'lsa — boshqarish)."""
    builder = InlineKeyboardBuilder()
    if own:
        builder.button(text=t("kb.open_item", lang), callback_data=f"my:i:{item_id}")
    else:
        builder.button(text=t("kb.claim", lang), callback_data=f"claim:{item_id}")
        if post_url:
            builder.button(text=t("kb.view_channel", lang), url=post_url)
    builder.adjust(1)
    return builder.as_markup()


def my_searches_kb(reports: list[dict], lang: str = "uz"):
    from utils import lost_code

    builder = InlineKeyboardBuilder()
    for report in reports:
        builder.button(
            text=t("kb.stop_search_code", lang, code=lost_code(report["id"])), callback_data=f"lostclose:{report['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def handover_kb(claim_id: int, role: str, lang: str = "uz"):
    """role: "o" — egasi, "f" — topuvchi."""
    builder = InlineKeyboardBuilder()
    if role == "o":
        builder.button(text=t("kb.owner_yes", lang), callback_data=f"ho:o:yes:{claim_id}")
        builder.button(text=t("kb.owner_no", lang), callback_data=f"ho:o:no:{claim_id}")
    else:
        builder.button(text=t("kb.finder_yes", lang), callback_data=f"ho:f:yes:{claim_id}")
        builder.button(text=t("kb.finder_no", lang), callback_data=f"ho:f:no:{claim_id}")
    builder.button(text=t("kb.chat", lang), callback_data=f"chat:{claim_id}")
    builder.adjust(1)
    return builder.as_markup()


# ---------- Mening e'lonlarim ----------

def my_list_kb(items: list[dict], claims: list[dict]):
    from utils import item_code

    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"📦 #{item_code(item['id'])}", callback_data=f"my:i:{item['id']}")
    for claim in claims:
        builder.button(text=f"🙋 #{item_code(claim['item_id'])}", callback_data=f"my:c:{claim['id']}")
    builder.adjust(3)
    return builder.as_markup()


def my_item_kb(item: dict, deal: dict | None, confirm: str = "", lang: str = "uz"):
    """confirm: "ret" | "del" — shu amal uchun tasdiqlash tugmasi ko'rsatiladi."""
    builder = InlineKeyboardBuilder()
    item_id = item["id"]
    if item["status"] in ("pending", "published"):
        builder.button(text=t("kb.edit", lang), callback_data=f"my:edit:{item_id}")
    if item["status"] == "published":
        if confirm == "ret":
            builder.button(text=t("kb.returned_confirm", lang), callback_data=f"my:ret2:{item_id}")
        else:
            builder.button(text=t("kb.returned", lang), callback_data=f"my:ret:{item_id}")
    if item["status"] in ("pending", "published"):
        if confirm == "del":
            builder.button(text=t("kb.remove_confirm", lang), callback_data=f"my:del2:{item_id}")
        else:
            builder.button(text=t("kb.remove", lang), callback_data=f"my:del:{item_id}")
    if deal and deal["handover"] is None and not deal["finder_answer"]:
        builder.button(text=t("kb.finder_yes", lang), callback_data=f"ho:f:yes:{deal['id']}")
        builder.button(text=t("kb.finder_no", lang), callback_data=f"ho:f:no:{deal['id']}")
    if deal and deal["handover"] != "refunded":
        builder.button(text=t("kb.chat_owner", lang), callback_data=f"chat:{deal['id']}")
    builder.button(text=t("kb.back", lang), callback_data="my:list")
    builder.adjust(1)
    return builder.as_markup()


def my_claim_kb(claim: dict, online_payment: bool, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    if claim["status"] == "awaiting_payment":
        text = t("kb.pay_online" if online_payment else "kb.pay_card", lang)
        builder.button(text=text, callback_data=f"my:pay:{claim['id']}")
    if claim["status"] == "completed" and claim["handover"] is None and not claim["owner_answer"]:
        builder.button(text=t("kb.owner_yes", lang), callback_data=f"ho:o:yes:{claim['id']}")
        builder.button(text=t("kb.owner_no", lang), callback_data=f"ho:o:no:{claim['id']}")
    if claim["status"] == "completed" and claim["handover"] != "refunded":
        builder.button(text=t("kb.chat_finder", lang), callback_data=f"chat:{claim['id']}")
    builder.button(text=t("kb.back", lang), callback_data="my:list")
    builder.adjust(1)
    return builder.as_markup()


# ---------- admin tugmalari ----------

def moderation_kb(item_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Rasm bilan chiqarish", callback_data=f"mod:photo:{item_id}")
    builder.button(text="🌫 Xira rasm bilan (hujjat)", callback_data=f"mod:blur:{item_id}")
    builder.button(text="🙈 Rasmsiz chiqarish", callback_data=f"mod:text:{item_id}")
    builder.button(text="❌ Rad etish", callback_data=f"mod:reject:{item_id}")
    builder.adjust(1)
    return builder.as_markup()


def published_kb(item_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Kanaldan o'chirish", callback_data=f"mod:delete:{item_id}")
    return builder.as_markup()


def claim_review_kb(claim_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Egasi ekan", callback_data=f"cl:ok:{claim_id}")
    builder.button(text="❌ Rad etish", callback_data=f"cl:no:{claim_id}")
    builder.adjust(2)
    return builder.as_markup()


def claim_undo_kb(claim_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Bekor qilish (egasi emas)", callback_data=f"cl:undo:{claim_id}")
    return builder.as_markup()


def dispute_kb(claim_id: int, chat_messages: int = 0):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Topshirildi — suyunchiga ruxsat", callback_data=f"hd:ok:{claim_id}")
    builder.button(text="↩️ Pul qaytarildi — yopish", callback_data=f"hd:refund:{claim_id}")
    if chat_messages:
        builder.button(text=f"💬 Yozishmani ko'rish ({chat_messages})", callback_data=f"hc:{claim_id}")
    builder.adjust(1)
    return builder.as_markup()


def payout_kb(claim_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Suyunchi o'tkazildi", callback_data=f"po:one:{claim_id}")
    return builder.as_markup()


def payouts_list_kb(rows: list[dict]):
    from utils import item_code

    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=f"✅ #{item_code(row['id'])} o'tkazildi", callback_data=f"po:list:{row['claim_id']}")
    builder.adjust(2)
    return builder.as_markup()


def item_card_kb(item: dict, confirm_return: bool = False):
    builder = InlineKeyboardBuilder()
    if item["photo_id"]:
        builder.button(text="🖼 Rasmni ko'rish", callback_data=f"fi:photo:{item['id']}")
    if item["status"] == "published":
        builder.button(text="🗑 Kanaldan o'chirish", callback_data=f"mod:delete:{item['id']}")
        if confirm_return:
            builder.button(text="⚠️ Ha, qaytarildi deb yopish", callback_data=f"fi:ret2:{item['id']}")
        else:
            builder.button(text="✅ Qaytarildi deb belgilash", callback_data=f"fi:ret:{item['id']}")
    elif item["status"] == "pending":
        builder.button(text="✅ Rasm bilan chiqarish", callback_data=f"mod:photo:{item['id']}")
        builder.button(text="🌫 Xira rasm bilan", callback_data=f"mod:blur:{item['id']}")
        builder.button(text="🙈 Rasmsiz chiqarish", callback_data=f"mod:text:{item['id']}")
        builder.button(text="❌ Rad etish", callback_data=f"mod:reject:{item['id']}")
    builder.button(text="👤 Topuvchi", callback_data=f"fi:user:{item['finder_id']}")
    builder.adjust(1)
    return builder.as_markup()


def user_card_kb(user_id: int, banned: bool):
    builder = InlineKeyboardBuilder()
    if banned:
        builder.button(text="✅ Blokdan chiqarish", callback_data=f"ban:off:{user_id}")
    else:
        builder.button(text="⛔ Bloklash", callback_data=f"ban:on:{user_id}")
    return builder.as_markup()


def stats_kb(active: str):
    builder = InlineKeyboardBuilder()
    for period, title in (("today", "Bugun"), ("week", "7 kun"), ("month", "30 kun"), ("all", "Jami")):
        builder.button(text=f"• {title} •" if period == active else title, callback_data=f"st:{period}")
    builder.button(text="📈 Grafik", callback_data="st:chart")
    builder.button(text="🔄 Yangilash", callback_data=f"st:{active}")
    builder.adjust(4, 2)
    return builder.as_markup()


def broadcast_kb(message_id: int, count: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📣 Ha, {count} kishiga yuborish", callback_data=f"bc:go:{message_id}")
    builder.button(text="❌ Bekor qilish", callback_data="bc:no")
    builder.adjust(1)
    return builder.as_markup()


def payment_review_kb(claim_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ To'lov tushdi", callback_data=f"pay:ok:{claim_id}")
    builder.button(text="❌ To'lov topilmadi", callback_data=f"pay:no:{claim_id}")
    builder.adjust(2)
    return builder.as_markup()
