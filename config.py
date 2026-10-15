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

# true: e'lon darhol kanalga chiqadi, admin keyin o'chira oladi
# false: avval admin tasdiqlaydi
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "true").lower() == "true"

DB_PATH = os.getenv("DB_PATH", "bot.db")

# Webhook (nginx bilan). Bo'sh bo'lsa — polling rejimi
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")  # masalan: https://bot.example.uz
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

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
