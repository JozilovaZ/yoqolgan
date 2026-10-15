"""Foydalanuvchining to'liq yo'llari: "yo'qotdim" e'loni, hujjat egasini avtomatik tasdiqlash, onlayn to'lov."""
from datetime import date

import pytest

from aiogram.methods import AnswerPreCheckoutQuery, SendInvoice, SendPhoto
from aiogram.types import PreCheckoutQuery, SuccessfulPayment, User

import database as db
import services
from config import ADMIN_GROUP_ID
from consent import OFFER_VERSION
from keyboards import BTN_LOST
from tests.fakes import buttons, make_claim, make_item

FINDER, OWNER, STRANGER = 20, 30, 40


@pytest.fixture(autouse=True)
async def owner_accepted_terms():
    """Bu fayldagi yo'llar ofertaga rozi bo'lgan foydalanuvchi uchun (rozilikning o'zi — test_terms.py)."""
    await db.accept_terms(OWNER, OFFER_VERSION)


# ---------- "yo'qotdim" e'loni ----------

async def test_lost_report_shows_existing_matches(tg):
    item = await make_item()  # bugun Toshkentda topilgan telefon
    await tg.send(BTN_LOST, user_id=OWNER)
    await tg.press("lost:phone", user_id=OWNER)
    assert "lostsub:phone" in buttons(tg.to(OWNER)[-1])

    await tg.press("lostsub:phone", user_id=OWNER)
    await tg.press("reg:0", user_id=OWNER)  # Toshkent shahri
    await tg.send("Chilonzor", user_id=OWNER)
    await tg.press(f"day:{date.today().isoformat()}", user_id=OWNER)
    await tg.send("qora iPhone", user_id=OWNER)
    await tg.press("lostform:save", user_id=OWNER)

    reports = await db.list_user_lost_reports(OWNER)
    assert len(reports) == 1 and reports[0]["region"] == "Toshkent shahri" and reports[0]["description"] == "qora iPhone"
    assert "saqlandi" in tg.texts(OWNER)[0]
    assert f"claim:{item['id']}" in buttons(tg.to(OWNER)[-1])  # kanalda turgan mos e'lon darhol ko'rsatildi


async def test_new_item_notifies_lost_owner(tg):
    report_id = await db.create_lost_report({"owner_id": OWNER, "category": "phone", "region": "Toshkent shahri",
                                             "lost_day": date.today().isoformat()})
    await db.create_lost_report({"owner_id": 31, "category": "wallet", "lost_day": date.today().isoformat()})
    item = await make_item(status="pending")
    await services.publish_item(tg.bot, item, "photo")

    notice = tg.to(OWNER)[0]
    assert "o'xshash narsa topildi" in notice.text
    claim_button, post_url, close_button = buttons(notice)
    assert claim_button == f"claim:{item['id']}" and close_button == f"lostclose:{report_id}"
    assert post_url.startswith("https://t.me/test_kanal/")  # kanaldagi postga havola
    assert not tg.to(31)  # boshqa turdagi qidiruv

    await tg.press(f"lostclose:{report_id}", user_id=OWNER)
    assert (await db.get_lost_report(report_id))["status"] == "closed"


async def test_max_active_searches(tg):
    for _ in range(5):
        await db.create_lost_report({"owner_id": OWNER, "category": "phone", "lost_day": "2026-10-01"})
    await tg.press("lostsub:phone", user_id=OWNER)
    assert "5 ta faol qidiruv" in tg.texts(OWNER)[0]


# ---------- hujjat egasini avtomatik tekshirish ----------

async def claim_document(tg, proof: str):
    item = await make_item(category="passport", ocr_text="TOSHMATOV\nALISHER\nAA12345671UZB9005123M3001017<<02")
    await tg.send(f"/start claim_{item['id']}", user_id=OWNER)
    await tg.send(proof, user_id=OWNER)
    await tg.send("+998937654321", user_id=OWNER)
    return item, (await db.list_user_claims(OWNER))[0]


async def test_document_auto_approved(tg):
    item, claim = await claim_document(tg, "Toshmatov Alisher 567")
    assert claim["status"] == "awaiting_payment" and claim["approved_at"]
    admin = tg.to(ADMIN_GROUP_ID, SendPhoto)[0]
    assert "AVTOMATIK TASDIQLANDI" in admin.caption and buttons(admin) == [f"cl:undo:{claim['id']}"]
    assert any("mos keldi" in text for text in tg.texts(OWNER))
    assert any("8600 0000 0000 0000" in text for text in tg.texts(OWNER))  # karta orqali to'lov so'raldi

    await tg.press(f"cl:undo:{claim['id']}")  # admin bekor qiladi
    assert (await db.get_claim(claim["id"]))["status"] == "rejected"
    assert any("to'lov qilmang" in text for text in tg.texts(OWNER))


async def test_document_wrong_number_goes_to_admin(tg):
    item, claim = await claim_document(tg, "Toshmatov Alisher 123")
    assert claim["status"] == "checking"
    admin = tg.to(ADMIN_GROUP_ID, SendPhoto)[0]
    assert "EGASI MUROJAAT QILDI" in admin.caption and "ism-familiya ✅, raqam ❌" in admin.caption
    assert buttons(admin) == [f"cl:ok:{claim['id']}", f"cl:no:{claim['id']}"]


# ---------- onlayn to'lov (Click / Payme) ----------

async def test_online_payment(tg, monkeypatch):
    monkeypatch.setattr(services, "PAYMENT_PROVIDER_TOKEN", "TEST:token")
    item = await make_item()
    claim = await make_claim(item["id"])
    await db.approve_claim(claim["id"])
    await services.request_payment(tg.bot, claim, item)
    invoice = tg.to(OWNER, SendInvoice)[0]
    assert invoice.payload == f"claim:{claim['id']}" and invoice.prices[0].amount == 50000 * 100

    async def pre_checkout(user_id, amount=50000 * 100):
        tg.calls.clear()
        query = PreCheckoutQuery(id="q", from_user=User(id=user_id, is_bot=False, first_name="U"), currency="UZS",
                                 total_amount=amount, invoice_payload=invoice.payload)
        await tg.feed(pre_checkout_query=query)
        return [call for call in tg.calls if isinstance(call, AnswerPreCheckoutQuery)][0]

    assert not (await pre_checkout(STRANGER)).ok  # boshqa odam to'lay olmaydi
    assert not (await pre_checkout(OWNER, amount=100)).ok  # summa noto'g'ri
    assert (await pre_checkout(OWNER)).ok

    payment = SuccessfulPayment(currency="UZS", total_amount=50000 * 100, invoice_payload=invoice.payload,
                                telegram_payment_charge_id="tg-1", provider_payment_charge_id="click-777")
    await tg.send("", user_id=OWNER, successful_payment=payment)
    claim = await db.get_claim(claim["id"])
    assert claim["status"] == "completed" and claim["payment_charge_id"] == "click-777"
    assert (await db.get_item(item["id"]))["status"] == "returned"
    assert buttons(tg.to(OWNER)[0]) == [f"ho:o:yes:{claim['id']}", f"ho:o:no:{claim['id']}", f"chat:{claim['id']}"]
    assert "click-777" in tg.texts(ADMIN_GROUP_ID)[0]


async def test_payment_after_cancellation_asks_admin_to_refund(tg):
    item = await make_item()
    claim = await make_claim(item["id"], status="rejected")  # to'lov oynasi ochiq turganda admin bekor qilgan
    payment = SuccessfulPayment(currency="UZS", total_amount=50000 * 100, invoice_payload=f"claim:{claim['id']}",
                                telegram_payment_charge_id="tg-2", provider_payment_charge_id="payme-9")
    await tg.send("", user_id=OWNER, successful_payment=payment)
    assert "Pulni qaytarish kerak" in tg.texts(ADMIN_GROUP_ID)[0] and "payme-9" in tg.texts(ADMIN_GROUP_ID)[0]
    assert "qaytariladi" in tg.texts(OWNER)[0]
    assert (await db.get_item(item["id"]))["status"] == "published"  # e'lon yopilmadi
