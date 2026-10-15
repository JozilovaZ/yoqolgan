"""Ikki til (i18n.py, locales/): lug'atlar to'liqligi va ruscha foydalanuvchi yo'li."""
import string

from aiogram.methods import SendMessage
from aiogram.types import User

import database as db
from config import CATEGORIES, REGIONS
from consent import offer_pages
from i18n import guess_lang, t
from locales import ru, uz
from services import complete_claim
from tests.fakes import buttons, make_claim, make_item

USER, FINDER, OWNER = 40, 20, 30


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_same_keys_and_placeholders():
    assert set(uz.TEXTS) == set(ru.TEXTS)
    for key in uz.TEXTS:
        assert _fields(uz.TEXTS[key]) == _fields(ru.TEXTS[key]), key


def test_lists_match_config():
    assert set(ru.CATEGORIES) == set(CATEGORIES)
    assert len(ru.REGIONS) == len(REGIONS)
    for locale in (uz, ru):
        assert len(locale.WEEKDAYS) == len(locale.WEEKDAYS_SHORT) == 7 and len(locale.MONTHS) == 12


def test_offer_renders_in_both_languages():
    for lang in ("uz", "ru"):
        pages = offer_pages(lang)
        assert pages and all(len(page) <= 4096 for page in pages)
    assert "ПУБЛИЧНАЯ ОФЕРТА" in offer_pages("ru")[0]


def test_guess_lang():
    assert guess_lang("ru") == guess_lang("ru-RU") == "ru"
    assert guess_lang("uz") == guess_lang(None) == guess_lang("en") == "uz"


async def test_first_start_uses_telegram_language(tg):
    message = tg.message("/start", user_id=USER)
    message = message.model_copy(
        update={"from_user": User(id=USER, is_bot=False, first_name="Ivan", language_code="ru")}
    )
    tg.calls.clear()
    await tg.feed(message=message)
    assert "Здравствуйте" in tg.sent()[0].text
    assert buttons(tg.sent()[1]) == ["lang:uz", "lang:ru"]  # birinchi marta tilni almashtirish taklif qilinadi
    assert await db.get_lang(USER) == "ru"

    await tg.send("/start", user_id=USER)  # ikkinchi marta — saqlangan til, tanlov qayta chiqmaydi
    assert len(tg.sent()) == 1 and "Здравствуйте" in tg.last_text()


async def test_switch_language(tg):
    await db.set_lang(USER, "ru")
    await tg.press("lang:uz", user_id=USER)
    assert await db.get_lang(USER) == "uz"
    assert "Assalomu alaykum" in tg.last_text()
    menu = tg.sent()[-1].reply_markup.keyboard
    assert menu[0][0].text == t("btn.found", "uz")


async def test_russian_buttons_work(tg):
    await db.set_lang(USER, "ru")
    await tg.send(t("btn.found", "ru"), user_id=USER)
    assert "условия использования" in tg.last_text()  # oferta — ruscha
    await tg.send(t("btn.my_items", "ru"), user_id=USER)
    assert "нет объявлений" in tg.last_text()
    await tg.send(t("btn.lang", "ru"), user_id=USER)
    assert buttons(tg.sent()[0]) == ["lang:uz", "lang:ru"]


async def test_russian_region_and_category_labels(tg):
    await db.set_lang(USER, "ru")
    item = await make_item(region="Toshkent shahri", category="wallet")
    await tg.send(f"T{item['id']}", user_id=USER)
    caption = tg.calls[-1].caption
    assert "Кошелёк" in caption and "г. Ташкент" in caption and "Это моё" in caption


async def test_each_side_gets_own_language(tg):
    await db.set_lang(OWNER, "ru")
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    tg.calls.clear()
    await complete_claim(tg.bot, await db.get_claim(claim["id"]), item)
    assert "Оплата подтверждена" in tg.texts(OWNER)[0]
    assert "egasi topildi" in tg.texts(FINDER)[0]
    assert "Bot orqali yozish" in tg.to(FINDER)[0].reply_markup.inline_keyboard[2][0].text
    assert "Написать через бота" in tg.to(OWNER)[0].reply_markup.inline_keyboard[2][0].text
    assert any("Ikki tomon bog'landi" in text for text in tg.admin)  # admin guruh — o'zbekcha


async def test_chat_header_in_recipient_language(tg):
    await db.set_lang(FINDER, "ru")
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    await complete_claim(tg.bot, await db.get_claim(claim["id"]), item)
    await tg.press(f"chat:{claim['id']}", user_id=OWNER)
    await tg.send("Salom", user_id=OWNER)
    relayed = [call for call in tg.sent(SendMessage) if call.chat_id == FINDER][0]
    assert "Владелец вещи" in relayed.text and "Salom" in relayed.text
