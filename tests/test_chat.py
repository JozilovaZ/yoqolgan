"""To'lovdan keyin egasi va topuvchi bot orqali yozishadi (handlers/chat.py)."""
from aiogram.methods import CopyMessage, SendMessage
from aiogram.types import PhotoSize

import database as db
from keyboards import BTN_CHAT_EXIT
from services import complete_claim
from tests.fakes import ADMIN, buttons, make_claim, make_item

FINDER, OWNER, STRANGER = 20, 30, 40


async def paid_claim(tg) -> int:
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    await complete_claim(tg.bot, await db.get_claim(claim["id"]), item)
    return claim["id"]


async def test_owner_writes_finder_replies(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"chat:{claim_id}", user_id=OWNER)
    assert "topuvchiga bot orqali yetkaziladi" in tg.last_text()

    await tg.send("Ertaga soat 10 da Chilonzor metrosida bo'lamanmi?", user_id=OWNER)
    relayed = tg.to(FINDER)[0]
    assert "Narsa egasi" in relayed.text and "Chilonzor metrosida" in relayed.text
    assert buttons(relayed) == [f"chat:{claim_id}"]

    await tg.press(f"chat:{claim_id}", user_id=FINDER)
    await tg.send("Kelishdik", user_id=FINDER)
    assert "Topuvchi" in tg.texts(OWNER)[0] and "Kelishdik" in tg.texts(OWNER)[0]
    assert [row["sender_id"] for row in await db.list_chat_messages(claim_id)] == [OWNER, FINDER]


async def test_photo_is_copied_with_header(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"chat:{claim_id}", user_id=OWNER)
    await tg.send(None, user_id=OWNER, photo=[PhotoSize(file_id="P", file_unique_id="P", width=1, height=1)],
                  caption="mana chek")
    copy = tg.sent(CopyMessage)[0]
    assert copy.chat_id == FINDER and "Narsa egasi" in copy.caption and "mana chek" in copy.caption
    assert (await db.list_chat_messages(claim_id))[0]["kind"] == "photo"


async def test_exit_chat(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"chat:{claim_id}", user_id=OWNER)
    await tg.send(BTN_CHAT_EXIT, user_id=OWNER)
    assert "Chatdan chiqdingiz" in tg.last_text()
    await tg.send("salom", user_id=OWNER)
    assert not tg.to(FINDER)  # endi yetkazilmaydi


async def test_stranger_and_unpaid_cannot_chat(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"chat:{claim_id}", user_id=STRANGER)
    assert tg.alerts()

    item = await make_item()
    unpaid = await make_claim(item["id"])
    await tg.press(f"chat:{unpaid['id']}", user_id=OWNER)
    assert tg.alerts()


async def test_chat_closes_after_refund(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"chat:{claim_id}", user_id=OWNER)
    await db.update_claim(claim_id, handover="refunded")
    await tg.send("salom", user_id=OWNER)
    assert "yozishma yopilgan" in tg.last_text() and not tg.to(FINDER)


async def test_chat_closes_after_days(tg):
    claim_id = await paid_claim(tg)
    await db.update_claim(claim_id, completed_at="2020-01-01 00:00:00")
    await tg.press(f"chat:{claim_id}", user_id=OWNER)
    assert tg.alerts()


async def test_blocked_recipient(tg):
    claim_id = await paid_claim(tg)
    tg.blocked.add(FINDER)
    await tg.press(f"chat:{claim_id}", user_id=OWNER)
    await tg.send("salom", user_id=OWNER)
    assert "yetkazilmadi" in tg.last_text()
    assert await db.list_chat_messages(claim_id) == []


async def test_admin_sees_transcript_in_dispute(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"chat:{claim_id}", user_id=OWNER)
    await tg.send("Qayerdasiz?", user_id=OWNER)
    await tg.press(f"ho:o:no:{claim_id}", user_id=OWNER)

    dispute = [call for call in tg.to(-1001) if "NIZO" in call.text][0]
    assert "1 ta xabar" in dispute.text and f"hc:{claim_id}" in buttons(dispute)

    await tg.press(f"hc:{claim_id}", user_id=ADMIN)
    assert "Qayerdasiz?" in tg.sent(SendMessage)[0].text and "Egasi" in tg.sent(SendMessage)[0].text

    await tg.press(f"hc:{claim_id}", user_id=OWNER)  # admin guruhdan tashqarida — ishlamaydi
    assert not tg.sent(SendMessage)
