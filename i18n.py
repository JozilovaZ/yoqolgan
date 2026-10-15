"""Foydalanuvchi tili: o'zbekcha (asosiy) va ruscha. Matnlar locales/uz.py va locales/ru.py da.

Admin guruh va kanal postlari doim o'zbekcha.
"""
import database as db
from config import CATEGORIES, REGIONS
from locales import ru, uz

LOCALES = {"uz": uz, "ru": ru}
DEFAULT_LANG = "uz"


def _locale(lang: str):
    return LOCALES.get(lang, uz)


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    text = _locale(lang).TEXTS.get(key) or uz.TEXTS[key]
    return text.format(**kwargs) if kwargs else text


def variants(key: str) -> list[str]:
    """Tugma matni barcha tillarda — F.text.in_(variants("btn.found"))."""
    return list(dict.fromkeys(locale.TEXTS[key] for locale in LOCALES.values()))


def guess_lang(language_code: str | None) -> str:
    """Telegram ilovasi tili bo'yicha (birinchi marta kirganda)."""
    return "ru" if (language_code or "").lower().startswith("ru") else DEFAULT_LANG


async def user_lang(user_id: int) -> str:
    """Boshqa foydalanuvchiga xabar yuborishdan oldin uning tilini bilish uchun."""
    return await db.get_lang(user_id) or DEFAULT_LANG


def category_label(key: str, lang: str = DEFAULT_LANG) -> str:
    if lang == "ru":
        return ru.CATEGORIES.get(key, ru.CATEGORIES["other"])
    return CATEGORIES.get(key, CATEGORIES["other"])[0]


def region_label(region: str, lang: str = DEFAULT_LANG) -> str:
    """Bazada viloyat o'zbekcha saqlanadi, foydalanuvchiga uning tilida ko'rsatiladi."""
    if lang == "ru" and region in REGIONS:
        return ru.REGIONS[REGIONS.index(region)]
    return region


def weekdays(lang: str, short: bool = False) -> list[str]:
    return _locale(lang).WEEKDAYS_SHORT if short else _locale(lang).WEEKDAYS


def months(lang: str) -> list[str]:
    return _locale(lang).MONTHS
