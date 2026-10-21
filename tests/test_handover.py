"""Narsa qo'lga tekkanini tasdiqlash (handlers/handover.py): suyunchi faqat egasi "oldim" degach."""
import sqlite3

from aiogram.methods import SendPhoto

import database as db
import scheduler
from services import complete_claim
from tests.fakes import ADMIN, buttons, make_claim, make_item

FINDER, OWNER, STRANGER = 20, 30, 40


async def paid_claim(tg) -> int:
    item = await make_item(category="wallet")
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    tg.calls.clear()
    await complete_claim(tg.bot, await db.get_claim(claim["id"]), item)
    return claim["id"]


async def test_after_payment_buttons_but_no_payout_yet(tg):
    claim_id = await paid_claim(tg)
    assert buttons(tg.to(OWNER)[0]) == [f"hoqr:{claim_id}", f"ho:o:yes:{claim_id}", f"ho:o:no:{claim_id}", f"chat:{claim_id}"]
    assert buttons(tg.to(FINDER)[0]) == [f"ho:f:yes:{claim_id}", f"ho:f:no:{claim_id}", f"chat:{claim_id}"]
    assert "Ikki tomon bog'landi" in tg.admin[0] and "Suyunchi o'tkazish kerak" not in tg.admin[0]
    assert await db.list_unpaid_payouts() == [] and not await db.mark_payout(claim_id)


async def test_stranger_cannot_answer(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"ho:o:yes:{claim_id}", user_id=STRANGER)
    assert tg.alerts() and (await db.get_claim(claim_id))["handover"] is None


async def test_finder_then_owner_confirms(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"ho:f:yes:{claim_id}", user_id=FINDER)
    assert buttons(tg.to(OWNER)[0]) == [f"hoqr:{claim_id}", f"ho:o:yes:{claim_id}", f"ho:o:no:{claim_id}", f"chat:{claim_id}"]  # egasidan so'raldi
    assert not tg.admin

    await tg.press(f"ho:o:yes:{claim_id}", user_id=OWNER)
    assert (await db.get_claim(claim_id))["handover"] == "confirmed"
    payout = tg.to(-1001)[0]
    assert "Suyunchi o'tkazish kerak" in payout.text and buttons(payout) == [f"po:one:{claim_id}"]
    assert [row["claim_id"] for row in await db.list_unpaid_payouts()] == [claim_id]

    await tg.press(f"ho:o:no:{claim_id}", user_id=OWNER)  # keyin "muammo" — e'tiborsiz
    assert tg.alerts() and (await db.get_claim(claim_id))["handover"] == "confirmed"


async def test_dispute_reported_once_and_admin_resolves(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"ho:o:no:{claim_id}", user_id=OWNER)
    dispute = tg.to(-1001)[0]
    assert "NIZO" in dispute.text and "+998901234567" in dispute.text and "+998937654321" in dispute.text
    assert buttons(dispute) == [f"hd:ok:{claim_id}", f"hd:refund:{claim_id}"]
    assert "+998901234567" in tg.texts(OWNER)[0]  # egasiga topuvchi raqami yana beriladi

    await tg.press(f"ho:f:no:{claim_id}", user_id=FINDER)
    assert not tg.admin  # admin bir marta xabardor qilinadi

    await tg.press(f"hd:ok:{claim_id}", user_id=OWNER)  # admin guruhdan tashqarida — ishlamaydi
    assert (await db.get_claim(claim_id))["handover"] == "disputed"
    await tg.press(f"hd:ok:{claim_id}", user_id=ADMIN)
    assert (await db.get_claim(claim_id))["handover"] == "confirmed"
    assert any("Suyunchi o'tkazish kerak" in text for text in tg.admin)


async def test_owner_resolves_dispute_himself(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"ho:f:no:{claim_id}", user_id=FINDER)
    await tg.press(f"ho:o:yes:{claim_id}", user_id=OWNER)
    assert "nizo hal bo'ldi" in tg.admin[0]


async def test_refund_excludes_payout_and_income(tg):
    claim_id = await paid_claim(tg)
    paid_before = (await db.get_period_stats("all"))["paid"]
    await tg.press(f"ho:o:no:{claim_id}", user_id=OWNER)
    await tg.press(f"hd:refund:{claim_id}", user_id=ADMIN)
    assert (await db.get_claim(claim_id))["handover"] == "refunded"
    assert not await db.mark_payout(claim_id)
    assert (await db.get_period_stats("all"))["paid"] == paid_before - 1
    assert any("qaytarildi" in text for text in tg.texts(OWNER)) and tg.texts(FINDER)


async def test_scheduler_asks_silent_side_then_escalates(tg, fresh_db):
    claim_id = await paid_claim(tg)
    await db.update_claim(claim_id, finder_answer="yes")
    tg.calls.clear()
    await scheduler.ask_handover(tg.bot)
    assert not tg.calls  # hali 24 soat o'tmagan

    with sqlite3.connect(fresh_db) as con:
        con.execute("UPDATE claims SET completed_at = datetime('now', '-25 hours') WHERE id = ?", (claim_id,))
    await scheduler.ask_handover(tg.bot)
    assert len(tg.to(OWNER)) == 1 and not tg.to(FINDER)  # topuvchi javob bergan — undan so'ralmaydi
    tg.calls.clear()
    await scheduler.ask_handover(tg.bot)
    await scheduler.escalate_handover(tg.bot)
    assert not tg.calls

    with sqlite3.connect(fresh_db) as con:
        con.execute("UPDATE claims SET handover_asked_at = datetime('now', '-49 hours') WHERE id = ?", (claim_id,))
    await scheduler.escalate_handover(tg.bot)
    assert "72 soatdan beri" in tg.admin[0]
    tg.calls.clear()
    await scheduler.escalate_handover(tg.bot)
    assert not tg.calls


# ---------- QR-kod bilan tasdiqlash ----------

def read_qr(call) -> str:
    """Bot yuborgan QR rasmdan havolani o'qiydi (OpenCV)."""
    import cv2
    import numpy as np

    image = cv2.imdecode(np.frombuffer(call.photo.data, dtype=np.uint8), cv2.IMREAD_COLOR)
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    return text


async def owner_qr(tg, claim_id: int) -> tuple[str, str]:
    """Egasi QR-kodni ochadi. Qaytaradi: (/start argumenti, 6 xonali kod)."""
    await tg.press(f"hoqr:{claim_id}", user_id=OWNER)
    [photo] = tg.to(OWNER, SendPhoto)
    assert photo.protect_content
    url = read_qr(photo)
    assert url.startswith("https://t.me/izla_bot?start=ho_")
    claim = await db.get_claim(claim_id)
    assert f"{claim['handover_code'][:3]} {claim['handover_code'][3:]}" in photo.caption
    return url.split("start=")[1], claim["handover_code"]


async def test_finder_scans_owner_qr(tg):
    claim_id = await paid_claim(tg)
    start_arg, _ = await owner_qr(tg, claim_id)
    again, _ = await owner_qr(tg, claim_id)
    assert again == start_arg  # qayta bosilsa — o'sha kod

    await tg.send(f"/start {start_arg}", user_id=STRANGER)
    assert "boshqa topshirish uchun" in tg.texts(STRANGER)[0]
    await tg.send(f"/start {start_arg}", user_id=OWNER)
    assert "sizning QR-kodingiz" in tg.texts(OWNER)[0]
    assert (await db.get_claim(claim_id))["handover"] is None

    await tg.send(f"/start {start_arg}", user_id=FINDER)
    claim = await db.get_claim(claim_id)
    assert claim["handover"] == "confirmed" and claim["owner_answer"] == claim["finder_answer"] == "yes"
    assert "topshirilgani tasdiqlandi" in tg.texts(FINDER)[0]
    assert "QR-kodingizni tasdiqladi" in tg.texts(OWNER)[0]
    assert "QR-kod bilan tasdiqlandi" in tg.admin[0] and "Suyunchi o'tkazish kerak" in tg.admin[0]

    await tg.send(f"/start {start_arg}", user_id=FINDER)
    assert "allaqachon yopilgan" in tg.texts(FINDER)[0] and not tg.admin  # ikkinchi suyunchi so'rovi yo'q


async def test_finder_types_six_digit_code(tg):
    claim_id = await paid_claim(tg)
    await tg.send("123456", user_id=FINDER)
    assert "Tushunmadim" in tg.texts(FINDER)[0]  # egasi hali QR ochmagan — oddiy matn

    _, code = await owner_qr(tg, claim_id)
    await tg.send(f" {code} ", user_id=FINDER)
    assert (await db.get_claim(claim_id))["handover"] == "confirmed"
    assert "6 xonali kod bilan tasdiqlandi" in tg.admin[0]


async def test_wrong_codes_lock_after_limit(tg):
    claim_id = await paid_claim(tg)
    start_arg, code = await owner_qr(tg, claim_id)
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    for left in range(4, 0, -1):
        await tg.send(wrong, user_id=FINDER)
        assert f"<b>{left}</b> ta urinish" in tg.texts(FINDER)[0]
    await tg.send(wrong, user_id=FINDER)
    assert "bloklandi" in tg.texts(FINDER)[0] and "5 marta noto'g'ri" in tg.admin[0]

    await tg.send(code, user_id=FINDER)  # endi to'g'ri kod ham qabul qilinmaydi
    assert "bloklandi" in tg.texts(FINDER)[0] and (await db.get_claim(claim_id))["handover"] is None

    await tg.send(f"/start {start_arg}", user_id=FINDER)  # QR esa ishlaydi
    assert (await db.get_claim(claim_id))["handover"] == "confirmed"


async def test_qr_only_for_owner_of_paid_claim(tg):
    claim_id = await paid_claim(tg)
    await tg.press(f"hoqr:{claim_id}", user_id=FINDER)
    assert tg.alerts() and not tg.sent(SendPhoto)
    await tg.send("/start ho_notatoken", user_id=FINDER)
    assert "endi amalda emas" in tg.texts(FINDER)[0]
