"""«Mening e'lonlarim» (handlers/mine.py): ro'yxat, tahrirlash, yopish, murojaat holati."""
from aiogram.methods import DeleteMessage, EditMessageCaption, SendInvoice

import database as db
from keyboards import BTN_MY_ITEMS
from services import complete_claim
from tests.fakes import buttons, make_claim, make_item

FINDER, OWNER, STRANGER = 20, 30, 40
ADMIN_GROUP = -1001


async def test_empty_list(tg):
    await tg.send(BTN_MY_ITEMS, user_id=STRANGER)
    assert "hali e'lon yoki murojaat yo'q" in tg.last_text()


async def test_list_shows_items_and_claims(tg):
    item = await make_item()
    other = await make_item(finder_id=99, category="wallet")
    claim = await make_claim(other["id"], owner_id=FINDER)

    await tg.send(BTN_MY_ITEMS, user_id=FINDER)
    answer = tg.sent()[-1]
    assert f"#T{item['id']:04d}" in answer.text and "Kanalda" in answer.text
    assert "Murojaatlarim" in answer.text and "Egasi tekshirilmoqda" in answer.text
    assert buttons(answer) == [f"my:i:{item['id']}", f"my:c:{claim['id']}"]


async def test_stranger_cannot_open_or_close(tg):
    item = await make_item()
    for data in (f"my:i:{item['id']}", f"my:del2:{item['id']}", f"my:ret2:{item['id']}", f"my:edit:{item['id']}"):
        await tg.press(data, user_id=STRANGER)
        assert tg.alerts()
    assert (await db.get_item(item["id"]))["status"] == "published"


async def test_item_card_buttons(tg):
    item = await make_item()
    await tg.press(f"my:i:{item['id']}", user_id=FINDER)
    card = tg.calls[-1]
    assert "Kanalda" in card.text and "https://t.me/test_kanal/7" in card.text
    assert buttons(card) == [f"my:edit:{item['id']}", f"my:ret:{item['id']}", f"my:del:{item['id']}", "my:list"]


async def test_remove_needs_confirmation(tg):
    item = await make_item()
    await tg.press(f"my:del:{item['id']}", user_id=FINDER)
    assert f"my:del2:{item['id']}" in buttons(tg.calls[-1])
    assert (await db.get_item(item["id"]))["status"] == "published"

    await tg.press(f"my:del2:{item['id']}", user_id=FINDER)
    assert (await db.get_item(item["id"]))["status"] == "removed"
    assert [call.message_id for call in tg.sent(DeleteMessage)] == [7]
    assert "o'zi olib tashladi" in tg.admin[0]
    card = [call for call in tg.calls if type(call).__name__ == "EditMessageText"][-1]
    assert buttons(card) == ["my:list"]  # yopilgan e'londa faqat "orqaga"


async def test_mark_returned_updates_channel(tg):
    item = await make_item()
    await tg.press(f"my:ret2:{item['id']}", user_id=FINDER)
    assert (await db.get_item(item["id"]))["status"] == "returned"
    edit = tg.sent(EditMessageCaption)[0]
    assert "EGASIGA QAYTARILDI" in edit.caption and edit.reply_markup is None
    assert "o'zi qaytarganini" in tg.admin[0]


async def test_cannot_close_with_open_claim(tg):
    item = await make_item()
    await make_claim(item["id"], status="payment_review")
    await tg.press(f"my:del2:{item['id']}", user_id=FINDER)
    assert "murojaat ko'rib chiqilmoqda" in tg.alerts()[0]
    assert (await db.get_item(item["id"]))["status"] == "published" and not tg.sent(DeleteMessage)


async def test_edit_description_refreshes_post(tg):
    item = await make_item(description="qora")
    await tg.press(f"my:edit:{item['id']}", user_id=FINDER)
    await tg.send("qora, chap burchagi singan", user_id=FINDER)

    assert (await db.get_item(item["id"]))["description"] == "qora, chap burchagi singan"
    edit = tg.sent(EditMessageCaption)[0]
    assert "chap burchagi singan" in edit.caption
    assert buttons(edit) == [f"https://t.me/izla_bot?start=claim_{item['id']}"]  # "Bu meniki" qoladi
    assert "Eski: <i>qora</i>" in tg.admin[0]


async def test_edit_too_long(tg):
    item = await make_item(description="qora")
    await tg.press(f"my:edit:{item['id']}", user_id=FINDER)
    await tg.send("x" * 501, user_id=FINDER)
    assert "juda uzun" in tg.last_text()
    assert (await db.get_item(item["id"]))["description"] == "qora"


async def test_finder_sees_payout_status(tg):
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    await complete_claim(tg.bot, await db.get_claim(claim["id"]), item)

    await tg.press(f"my:i:{item['id']}", user_id=FINDER)
    card = tg.calls[-1]
    assert "egasi narsani olganini tasdiqlagach" in card.text
    assert f"ho:f:yes:{claim['id']}" in buttons(card)

    await db.update_claim(claim["id"], handover="confirmed")
    await db.mark_payout(claim["id"])
    await tg.press(f"my:i:{item['id']}", user_id=FINDER)
    assert "✅ o'tkazilgan" in tg.calls[-1].text


async def test_owner_claim_card_and_pay_again(tg):
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])

    await tg.press(f"my:c:{claim['id']}", user_id=OWNER)
    card = tg.calls[-1]
    assert "To'lov kutilmoqda" in card.text and buttons(card) == [f"my:pay:{claim['id']}", "my:list"]

    await tg.press(f"my:pay:{claim['id']}", user_id=OWNER)
    assert "8600 0000 0000 0000" in tg.texts(OWNER)[0]
    assert not tg.sent(SendInvoice)

    await tg.press(f"my:pay:{claim['id']}", user_id=STRANGER)
    assert tg.alerts()


async def test_owner_sees_finder_contact_after_payment(tg):
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    await complete_claim(tg.bot, await db.get_claim(claim["id"]), item)

    await tg.press(f"my:c:{claim['id']}", user_id=OWNER)
    card = tg.calls[-1]
    assert "+998901234567" in card.text and "topshirilishi kutilmoqda" in card.text
    assert buttons(card)[:3] == [f"hoqr:{claim['id']}", f"ho:o:yes:{claim['id']}", f"ho:o:no:{claim['id']}"]


async def test_back_to_list(tg):
    item = await make_item()
    await tg.press("my:list", user_id=FINDER)
    assert f"my:i:{item['id']}" in buttons(tg.calls[-1])
