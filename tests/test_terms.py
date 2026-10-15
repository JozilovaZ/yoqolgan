"""Ommaviy oferta (consent.py, handlers/terms.py): rozilik so'raladi va foydalanuvchi to'xtagan joyidan davom etadi."""
import re

import consent
import database as db
from aiogram.methods import SendPhoto
from consent import OFFER_VERSION, offer_pages
from keyboards import BTN_FOUND
from tests.fakes import buttons, make_item

USER = 30


async def test_found_asks_terms_then_continues(tg):
    await tg.send(BTN_FOUND, user_id=USER)
    ask = tg.to(USER)[0]
    assert "foydalanish shartlari" in ask.text and buttons(ask) == ["terms:read", "terms:ok:found"]

    await tg.press("terms:ok:found", user_id=USER)
    assert await db.has_accepted_terms(USER, OFFER_VERSION)
    assert any("Nima topdingiz" in text for text in tg.texts(USER))  # e'lon berish darhol boshlandi

    await tg.send("/cancel", user_id=USER)
    await tg.send(BTN_FOUND, user_id=USER)  # ikkinchi marta so'ralmaydi
    assert "Rahmat, siz yaxshi ish" in tg.texts(USER)[0]


async def test_claim_from_channel_continues_after_terms(tg):
    item = await make_item()
    await tg.send(f"/start claim_{item['id']}", user_id=USER)
    assert buttons(tg.to(USER)[0])[-1] == f"terms:ok:claim_{item['id']}"
    assert not await db.list_user_claims(USER)

    await tg.press(f"terms:ok:claim_{item['id']}", user_id=USER)
    assert any("Egalikni isbotlang" in text for text in tg.texts(USER))


async def test_lost_search_continues_after_terms(tg):
    await tg.press("lostsub:wallet", user_id=USER)
    assert buttons(tg.to(USER)[0])[-1] == "terms:ok:lostsub_wallet"
    await tg.press("terms:ok:lostsub_wallet", user_id=USER)
    assert any("Qaysi viloyatda yo'qotdingiz" in text for text in tg.texts(USER))


async def test_new_offer_version_asks_again(tg, monkeypatch):
    await db.accept_terms(USER, OFFER_VERSION)
    monkeypatch.setattr(consent, "OFFER_VERSION", "2099-01-01")  # oferta yangilandi
    await tg.send(BTN_FOUND, user_id=USER)
    assert "foydalanish shartlari" in tg.texts(USER)[0]


async def test_offer_text(tg):
    pages = offer_pages()
    text = "\n".join(pages)
    assert all(len(page) <= 4096 for page in pages)
    assert "50 000 so'm" in text and "25 000 so'm" in text and "50%" in text  # .env dagi qiymatlar
    assert not re.search(r"\{\w+\}", text), "to'ldirilmay qolgan {o'zgaruvchi}"
    assert "<b>4. Xizmat haqi va to'lov</b>" in text

    await tg.send("/oferta", user_id=USER)
    assert len(tg.texts(USER)) == len(pages)
    await tg.press("terms:read", user_id=USER)
    assert len(tg.texts(USER)) == len(pages)


async def test_offer_url_used_when_set(tg, monkeypatch):
    monkeypatch.setattr(consent, "OFFER_URL", "https://telegra.ph/izla-oferta")
    await tg.send(BTN_FOUND, user_id=USER)
    assert buttons(tg.to(USER)[0]) == ["https://telegra.ph/izla-oferta", "terms:ok:found"]
    assert not tg.sent(SendPhoto)
