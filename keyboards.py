import calendar
from datetime import date, datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CATEGORIES, REGIONS

BTN_FOUND = "📦 Narsa topdim"
BTN_LOST = "🔍 Narsa yo'qotdim"
BTN_MY_SEARCHES = "🔔 Qidiruvlarim"
BTN_RULES = "ℹ️ Qoidalar"
BTN_CANCEL = "❌ Bekor qilish"
BTN_SKIP = "⏭ O'tkazib yuborish"
BTN_MANUAL_ADDRESS = "✍️ Manzilni qo'lda kiritish"

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

MONTHS = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_FOUND), KeyboardButton(text=BTN_LOST)],
            [KeyboardButton(text=BTN_MY_SEARCHES), KeyboardButton(text=BTN_RULES)],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Hozir turgan joyimni yuborish", request_location=True)],
            [KeyboardButton(text=BTN_MANUAL_ADDRESS)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def regions_kb(allow_unknown: bool = False):
    builder = InlineKeyboardBuilder()
    for index, region in enumerate(REGIONS):
        builder.button(text=region, callback_data=f"reg:{index}")
    builder.adjust(2)
    if allow_unknown:
        builder.row(InlineKeyboardButton(text="🤷 Aniq bilmayman", callback_data="reg:any"))
    return builder.as_markup()


def _ignore(text: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data="cal:ignore")


def calendar_kb(year: int | None = None, month: int | None = None) -> InlineKeyboardMarkup:
    """Oylik kalendar. Kelajakdagi kunlarni tanlab bo'lmaydi."""
    today = date.today()
    year, month = year or today.year, month or today.month

    prev_month = date(year, month, 1) - timedelta(days=1)
    next_month = date(year, month, 28) + timedelta(days=4)
    is_current = (year, month) == (today.year, today.month)

    rows = [
        [
            InlineKeyboardButton(text="◀️", callback_data=f"cal:nav:{prev_month:%Y-%m}"),
            _ignore(f"{MONTHS[month - 1]} {year}"),
            _ignore("·") if is_current else InlineKeyboardButton(text="▶️", callback_data=f"cal:nav:{next_month:%Y-%m}"),
        ],
        [_ignore(name) for name in ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")],
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
            InlineKeyboardButton(text="Bugun", callback_data=f"day:{today.isoformat()}"),
            InlineKeyboardButton(text="Kecha", callback_data=f"day:{(today - timedelta(days=1)).isoformat()}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hours_kb(day: date):
    """Soatlar: 00:00 ... 23:00. Bugun bo'lsa, hali kelmagan soatlar chiqmaydi."""
    builder = InlineKeyboardBuilder()
    last_hour = datetime.now().hour if day == date.today() else 23
    for hour in range(last_hour + 1):
        builder.button(text=f"{hour:02d}:00", callback_data=f"hour:{hour}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="🤷 Aniq bilmayman", callback_data="hour:unknown"))
    return builder.as_markup()


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_SKIP)], [KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


def categories_kb(prefix: str):
    builder = InlineKeyboardBuilder()
    for key, (label, _, _) in CATEGORIES.items():
        builder.button(text=label, callback_data=f"{prefix}:{key}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_found_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yuborish", callback_data="found:send")
    builder.button(text="❌ Bekor qilish", callback_data="found:cancel")
    return builder.as_markup()


def channel_post_kb(bot_username: str, item_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🙋 Bu meniki", url=f"https://t.me/{bot_username}?start=claim_{item_id}")
    return builder.as_markup()


def lost_items_kb(items: list[dict], subscribe_category: str | None = None):
    from utils import item_code

    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=f"🙋 #{item_code(item['id'])} — {item['region']}, {item['found_date']}",
            callback_data=f"claim:{item['id']}",
        )
    if subscribe_category:
        builder.button(text="🔔 Topilsa xabar bering", callback_data=f"lostsub:{subscribe_category}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_lost_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Saqlash", callback_data="lostform:save")
    builder.button(text="❌ Bekor qilish", callback_data="lostform:cancel")
    return builder.as_markup()


def lost_match_kb(item_id: int, report_id: int, post_url: str = ""):
    builder = InlineKeyboardBuilder()
    builder.button(text="🙋 Bu meniki", callback_data=f"claim:{item_id}")
    if post_url:
        builder.button(text="👀 Kanalda ko'rish", url=post_url)
    builder.button(text="🔕 Qidiruvni to'xtatish", callback_data=f"lostclose:{report_id}")
    builder.adjust(1)
    return builder.as_markup()


def my_searches_kb(reports: list[dict]):
    from utils import lost_code

    builder = InlineKeyboardBuilder()
    for report in reports:
        builder.button(text=f"🔕 #{lost_code(report['id'])} — to'xtatish", callback_data=f"lostclose:{report['id']}")
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
