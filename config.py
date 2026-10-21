import os

from dotenv import load_dotenv

load_dotenv()


def _chat_id(value: str) -> int | str:
    """'-100123...' ko'rinishidagi IDni int ga, '@kanal' ni o'zicha qoldiradi."""
    value = value.strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value


BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin guruh: yangi e'lonlar, murojaatlar va to'lov cheklari shu yerga keladi
ADMIN_GROUP_ID = _chat_id(os.getenv("ADMIN_GROUP_ID", "0"))

# E'lonlar chiqadigan kanal (@kanal_nomi yoki -100...)
CHANNEL_ID = _chat_id(os.getenv("CHANNEL_ID", ""))
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "")
if not CHANNEL_LINK and isinstance(CHANNEL_ID, str) and CHANNEL_ID.startswith("@"):
    CHANNEL_LINK = f"https://t.me/{CHANNEL_ID[1:]}"

# Ixtiyoriy: ofertaning internetdagi havolasi (masalan, telegra.ph sahifa). Bo'sh bo'lsa — matn botning o'zida
OFFER_URL = os.getenv("OFFER_URL", "")

# Savollar uchun admin username (masalan: @admin)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")

# To'lov sozlamalari
SERVICE_FEE = int(os.getenv("SERVICE_FEE", "50000"))  # so'm
FINDER_SHARE = int(os.getenv("FINDER_SHARE", "50"))  # topuvchiga beriladigan foiz
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_OWNER = os.getenv("CARD_OWNER", "")

# Onlayn to'lov (Click/Payme): @BotFather -> Bot -> Payments dan olingan token.
# To'ldirilsa egasi bot ichida to'laydi va to'lov avtomatik tasdiqlanadi.
# Bo'sh bo'lsa — karta raqami + chek skrinshoti (admin tekshiradi).
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")

# true: hujjat egasining javobi OCR bilan tekshiriladi, mos kelsa admin'siz tasdiqlanadi
AUTO_VERIFY_DOCUMENTS = os.getenv("AUTO_VERIFY_DOCUMENTS", "true").lower() == "true"

# Eslatmalar (soatda): egasi tasdiqlangandan keyin to'lamasa — eslatma, keyin murojaat yopiladi
PAYMENT_REMIND_HOURS = int(os.getenv("PAYMENT_REMIND_HOURS", "24"))
PAYMENT_EXPIRE_HOURS = int(os.getenv("PAYMENT_EXPIRE_HOURS", "48"))
# Murojaat shuncha soat tekshirilmasa — admin guruhga eslatma
ADMIN_REMIND_HOURS = int(os.getenv("ADMIN_REMIND_HOURS", "3"))
# To'lovdan shuncha soat o'tib ikki tomondan "narsa topshirildimi?" deb so'raladi,
# yana shuncha soat egasi javob bermasa — admin guruhga xabar
HANDOVER_ASK_HOURS = int(os.getenv("HANDOVER_ASK_HOURS", "24"))
HANDOVER_ESCALATE_HOURS = int(os.getenv("HANDOVER_ESCALATE_HOURS", "48"))

# Yopilgan e'lon va murojaatlardagi shaxsiy ma'lumotlar (telefon, karta, isbot) shuncha kundan keyin o'chiriladi
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))
# To'lovdan keyin egasi va topuvchi shuncha kun bot orqali yozisha oladi
CHAT_DAYS = int(os.getenv("CHAT_DAYS", "14"))

# Baza zaxirasi: har kuni shu soatda (mahalliy vaqt) Telegram'ga fayl bo'lib yuboriladi.
# Qayerga: bo'sh bo'lsa — admin guruhga; "off" — o'chirilgan
_backup_chat = os.getenv("BACKUP_CHAT_ID", "").strip()
BACKUP_CHAT_ID = None if _backup_chat.lower() == "off" else (_chat_id(_backup_chat) if _backup_chat else ADMIN_GROUP_ID)
BACKUP_HOUR = int(os.getenv("BACKUP_HOUR", "3"))

# true: e'lon darhol kanalga chiqadi, admin keyin o'chira oladi
# false: avval admin tasdiqlaydi
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "true").lower() == "true"

DB_PATH = os.getenv("DB_PATH", "bot.db")

# Webhook (nginx bilan). Bo'sh bo'lsa — polling rejimi
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")  # masalan: https://bot.example.uz
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

# Instagram: kanalga chiqqan e'lonlar Instagram biznes akkauntiga ham joylanadi (Meta Graph API).
# Instagram rasmni faqat ochiq havola orqali oladi — shuning uchun WEBHOOK_URL (domen) ham kerak.
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "").strip()
INSTAGRAM_TOKEN = os.getenv("INSTAGRAM_TOKEN", "").strip()
INSTAGRAM_API_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v23.0")
INSTAGRAM_ENABLED = bool(INSTAGRAM_USER_ID and INSTAGRAM_TOKEN and WEBHOOK_URL)
# Instagram yuklab olishi uchun rasmlar vaqtincha shu papkada turadi (WEBHOOK_URL/media/... orqali)
MEDIA_DIR = os.getenv("MEDIA_DIR", os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "media"))
MEDIA_PATH = "/media"

# key: (nomi, hashtag, hujjatmi)
CATEGORIES = {
    "passport": ("🛂 Pasport", "pasport", True),
    "id_card": ("🪪 ID karta", "idkarta", True),
    "driver": ("🚗 Haydovchilik guvohnomasi", "prava", True),
    "bank_card": ("💳 Bank karta", "bankkarta", True),
    "document": ("📄 Boshqa hujjat", "hujjat", True),
    "phone": ("📱 Telefon", "telefon", False),
    "wallet": ("👛 Hamyon", "hamyon", False),
    "keys": ("🔑 Kalit", "kalit", False),
    "bag": ("🎒 Sumka", "sumka", False),
    "other": ("📦 Boshqa", "boshqa", False),
}

REGIONS = [
    "Toshkent shahri",
    "Toshkent viloyati",
    "Andijon viloyati",
    "Buxoro viloyati",
    "Farg'ona viloyati",
    "Jizzax viloyati",
    "Xorazm viloyati",
    "Namangan viloyati",
    "Navoiy viloyati",
    "Qashqadaryo viloyati",
    "Qoraqalpog'iston",
    "Samarqand viloyati",
    "Sirdaryo viloyati",
    "Surxondaryo viloyati",
]
