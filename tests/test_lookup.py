"""E'lon raqami bo'yicha tez qidiruv (handlers/lookup.py)."""
from datetime import datetime

import pytest
from aiogram.methods import SendPhoto
from aiogram.types import Chat, MessageOriginChannel

import database as db
from consent import OFFER_VERSION
from tests.fakes import buttons, make_item

FINDER, USER = 20, 40


@pytest.mark.parametrize("text", ["T{:04d}", "#T{:04d}", "t{}", " T-{:04d} ", "Т{:04d}"])  # oxirgisi kirillcha
async def test_code_opens_item(tg, text):
    item = await make_item()
    await tg.send(text.format(item["id"]), user_id=USER)
    answer = tg.sent(SendPhoto)[0]
    assert f"#T{item['id']:04d}" in answer.caption
    assert buttons(answer) == [f"claim:{item['id']}", "https://t.me/test_kanal/7"]


async def test_document_photo_not_shown(tg):
    item = await make_item(category="passport", publish_mode="blur")
    await tg.send(f"T{item['id']}", user_id=USER)
    assert not tg.sent(SendPhoto)
    assert f"claim:{item['id']}" in buttons(tg.sent()[0])


async def test_claim_button_starts_claim(tg):
    item = await make_item()
    await db.accept_terms(USER, OFFER_VERSION)
    await tg.send(f"T{item['id']}", user_id=USER)
    await tg.press(f"claim:{item['id']}", user_id=USER)
    assert "Egalikni isbotlang" in tg.last_text()


async def test_own_item(tg):
    item = await make_item()
    await tg.send(f"T{item['id']}", user_id=FINDER)
    assert "o'zingiz bergan" in tg.last_text() and buttons(tg.sent()[0]) == [f"my:i:{item['id']}"]


@pytest.mark.parametrize("status", ["pending", "removed", "rejected"])
async def test_hidden_items_not_found(tg, status):
    item = await make_item(status=status)
    await tg.send(f"T{item['id']}", user_id=USER)
    assert "topilmadi" in tg.last_text()


async def test_returned_and_missing(tg):
    item = await make_item(status="returned")
    await tg.send(f"T{item['id']}", user_id=USER)
    assert "allaqachon qaytarilgan" in tg.last_text()
    await tg.send("T9999", user_id=USER)
    assert "topilmadi" in tg.last_text()


async def test_forwarded_channel_post(tg):
    item = await make_item()
    origin = MessageOriginChannel(date=datetime.now(), chat=Chat(id=-1002, type="channel"), message_id=7)
    await tg.send(f"🔎 TOPILDI | #T{item['id']:04d}\n\nTelefon", user_id=USER, forward_origin=origin)
    assert f"claim:{item['id']}" in buttons(tg.sent(SendPhoto)[0])


async def test_lost_code_only_for_owner(tg):
    report_id = await db.create_lost_report(
        {"owner_id": USER, "category": "phone", "region": "", "place": "", "lost_day": "2026-10-01", "description": ""}
    )
    await tg.send(f"Y{report_id:04d}", user_id=USER)
    assert "Qidiruvingiz" in tg.last_text() and buttons(tg.sent()[0]) == [f"lostclose:{report_id}"]
    await tg.send(f"Y{report_id:04d}", user_id=FINDER)
    assert "topilmadi" in tg.last_text()


async def test_unknown_text_gets_hint(tg):
    await tg.send("salom, telefonimni yo'qotdim", user_id=USER)
    assert "Tushunmadim" in tg.last_text() and "T0012" in tg.last_text()


async def test_code_not_caught_inside_form(tg):
    """Forma to'ldirilayotganda (masalan, izoh) "T12" e'lon raqami deb tushunilmaydi."""
    item = await make_item(description="qora")
    await tg.press(f"my:edit:{item['id']}", user_id=FINDER)
    await tg.send("T12", user_id=FINDER)
    assert (await db.get_item(item["id"]))["description"] == "T12"
