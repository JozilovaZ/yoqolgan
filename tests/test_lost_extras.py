""""Yo'qotdim" e'loniga qo'shimchalar: hujjat raqami (docnumber.py) va rasm o'xshashligi (visual.py)."""
import sqlite3
from datetime import date, timedelta
from io import BytesIO

import numpy as np
import pytest
from aiogram.methods import DeleteMessage
from aiogram.types import PhotoSize
from PIL import Image, ImageDraw

import database as db
import docnumber
from consent import OFFER_VERSION
from keyboards import BTN_LOST
import scheduler
import services
import verify
import visual
from tests.fakes import buttons, make_item

OWNER = 30
SKIP = "⏭ O'tkazib yuborish"
MRZ = ["P<UZBALIYEV<<VALI<<<<<<<<<<<<<<<<<<<<<<<<<<", "AA12345671UZB9005123M3001017<<<<<<<<<<<<<<04"]


@pytest.fixture(autouse=True)
async def owner_accepted_terms():
    await db.accept_terms(OWNER, OFFER_VERSION)


def vector(*values: float) -> bytes:
    data = np.array(values, dtype=np.float32)
    return (data / np.linalg.norm(data)).tobytes()


async def fill_lost_form(tg, category: str, description: str = "qora"):
    await tg.send(BTN_LOST, user_id=OWNER)
    await tg.press(f"lostsub:{category}", user_id=OWNER)
    await tg.press("reg:0", user_id=OWNER)  # Toshkent shahri
    await tg.send(SKIP, user_id=OWNER)
    await tg.press(f"day:{date.today().isoformat()}", user_id=OWNER)
    await tg.send(description, user_id=OWNER)


# ---------- hujjat raqami ----------

@pytest.mark.parametrize("text", ["AA1234567", "aa 123 45 67", "АА1234567", "AA-1234567", "AAl234567"])
def test_normalize_accepts_common_spellings(text):
    assert docnumber.normalize(text) == "AA1234567"


@pytest.mark.parametrize("text", ["1234567", "AA123456", "AAA1234567", "A11234567", ""])
def test_normalize_rejects_wrong_format(text):
    assert docnumber.normalize(text) is None


def test_numbers_in_text_reads_printed_and_mrz():
    assert docnumber.numbers_in_text(MRZ) == {"AA1234567"}  # tug'ilgan sana (UZB9005123) olinmaydi
    assert docnumber.numbers_in_text(["Pasport: AB 765432I"]) == {"AB7654321"}
    assert docnumber.masked("AA1234567") == "AA•••••67"


async def test_lost_passport_with_number_is_stored_as_fingerprint_only(tg, fresh_db):
    await fill_lost_form(tg, "passport")
    assert "Hujjat raqamini" in tg.last_text()

    await tg.send("12345", user_id=OWNER)
    assert "AA1234567" in tg.last_text()  # yo'riq: format noto'g'ri

    await tg.send("aa 1234567", user_id=OWNER)
    assert tg.sent(DeleteMessage)  # raqam chatdan o'chirildi
    assert "AA•••••67" in tg.last_text()
    await tg.press("lostform:save", user_id=OWNER)

    [report] = await db.list_user_lost_reports(OWNER)
    assert report["doc_hash"] == docnumber.fingerprint("AA1234567") and report["doc_hint"] == "AA•••••67"
    with sqlite3.connect(fresh_db) as con:
        dump = "\n".join(con.iterdump())
    assert "1234567" not in dump  # raqamning o'zi bazada yo'q


async def lost_passport(owner_id: int = OWNER, region: str = "Samarqand viloyati", **fields) -> dict:
    data = {"owner_id": owner_id, "category": "passport", "region": region,
            "lost_day": (date.today() - timedelta(days=200)).isoformat(),
            "doc_hash": docnumber.fingerprint("AA1234567"), "doc_hint": "AA•••••67"}
    data.update(fields)
    return await db.get_lost_report(await db.create_lost_report(data))


async def test_found_document_with_same_number_notifies_owner_once(tg):
    report = await lost_passport()  # boshqa viloyat, 200 kun oldin — baribir mos
    await lost_passport(owner_id=31, doc_hash=docnumber.fingerprint("AB0000000"))
    item = await make_item(category="passport", publish_mode="blur", ocr_text="\n".join(MRZ))

    await services.notify_document_owners(tg.bot, item["id"])
    [notice] = tg.to(OWNER)
    assert "Hujjatingiz topilgan" in notice.text and "AA•••••67" in notice.text
    assert f"claim:{item['id']}" in buttons(notice) and f"lostclose:{report['id']}" in buttons(notice)
    assert not tg.to(31)

    tg.calls.clear()
    await services.notify_document_owners(tg.bot, item["id"])
    assert not tg.to(OWNER)  # ikkinchi marta yuborilmaydi


async def test_ocr_finishing_after_publish_notifies(tg, monkeypatch):
    await lost_passport()
    item = await make_item(category="passport", publish_mode="blur")

    async def fake_document_text(bot, file_id):
        return MRZ

    monkeypatch.setattr(verify, "document_text", fake_document_text)
    await verify._read_and_save(tg.bot, item)
    assert "Hujjatingiz topilgan" in tg.texts(OWNER)[0]


async def test_pending_document_waits_for_publish(tg):
    await lost_passport()
    item = await make_item(category="passport", status="pending", ocr_text="\n".join(MRZ))
    await services.notify_document_owners(tg.bot, item["id"])
    assert not tg.to(OWNER)  # hali kanalda emas

    await services.publish_item(tg.bot, await db.get_item(item["id"]), "text")
    assert any("Hujjatingiz topilgan" in text for text in tg.texts(OWNER))


async def test_finder_is_not_notified_about_own_item(tg):
    await lost_passport(owner_id=20)  # make_item'dagi topuvchi
    item = await make_item(category="passport", ocr_text="\n".join(MRZ))
    await services.notify_document_owners(tg.bot, item["id"])
    assert not tg.to(20)


async def test_new_search_finds_document_already_in_channel(tg):
    item = await make_item(category="passport", publish_mode="blur", ocr_text="\n".join(MRZ))
    await fill_lost_form(tg, "passport")
    await tg.send("AA1234567", user_id=OWNER)
    await tg.press("lostform:save", user_id=OWNER)
    notice = [call for call in tg.to(OWNER) if "Hujjatingiz topilgan" in call.text]
    assert notice and f"claim:{item['id']}" in buttons(notice[0])


async def test_search_with_number_does_not_expire(tg):
    with_number = await lost_passport()
    without_number = await lost_passport(doc_hash=None, doc_hint=None)
    await scheduler.close_outdated_lost_reports(tg.bot)
    assert (await db.get_lost_report(with_number["id"]))["status"] == "active"
    assert (await db.get_lost_report(without_number["id"]))["status"] == "closed"


async def test_bank_card_does_not_ask_number_or_photo(tg):
    await fill_lost_form(tg, "bank_card")
    assert "tekshiring" in tg.last_text()


# ---------- rasm o'xshashligi ----------

def test_similarity_levels():
    a = vector(1, 0, 0)
    assert visual.similarity(a, a) == pytest.approx(1.0)
    assert visual.level(visual.similarity(a, vector(1, 0.2, 0))) == "high"
    assert visual.level(visual.similarity(a, vector(1, 0.9, 0))) == "medium"
    assert visual.level(visual.similarity(a, vector(0, 1, 0))) is None
    assert visual.similarity(a, None) is None


@pytest.fixture
def fake_embed(monkeypatch):
    """Rasm ID si -> barmoq izi (haqiqiy model o'rniga)."""
    vectors = {}

    async def embed(bot, file_id):
        return vectors.get(file_id)

    monkeypatch.setattr(visual, "embed", embed)
    return vectors


async def test_lost_photo_ranks_matches(tg, fake_embed):
    fake_embed.update(LOST=vector(1, 0, 0), RED=vector(1, 0.1, 0), BLUE=vector(0, 1, 0))
    red = await make_item(photo_id="RED", embedding=fake_embed["RED"])
    await make_item(photo_id="BLUE", embedding=fake_embed["BLUE"])
    await make_item(photo_id="OLD")  # eski e'lon, barmoq izi yo'q

    await fill_lost_form(tg, "phone")
    assert "rasmi bormi" in tg.last_text()
    await tg.send("salom", user_id=OWNER)
    assert "Rasm yuboring" in tg.last_text()
    await tg.send(None, user_id=OWNER, photo=[PhotoSize(file_id="LOST", file_unique_id="L", width=1, height=1)])
    assert "Rasm qo'shilgan" in tg.last_text()
    await tg.press("lostform:save", user_id=OWNER)

    [report] = await db.list_user_lost_reports(OWNER)
    assert report["photo_id"] == "LOST" and report["embedding"] == fake_embed["LOST"]
    matches = tg.to(OWNER)[-1]
    assert "eng o'xshashlari tepada" in matches.text
    assert buttons(matches)[0] == f"claim:{red['id']}"


async def test_new_item_notification_mentions_photo_similarity(tg, fake_embed):
    fake_embed.update(FOUND=vector(1, 0.1, 0))
    await db.create_lost_report({"owner_id": OWNER, "category": "phone", "region": "Toshkent shahri",
                                 "lost_day": date.today().isoformat(), "embedding": vector(1, 0, 0)})
    item = await make_item(status="pending", photo_id="FOUND")
    await services.publish_item(tg.bot, item, "photo")
    assert "juda o'xshaydi" in tg.texts(OWNER)[0]
    assert (await db.get_item(item["id"]))["embedding"] == fake_embed["FOUND"]


async def test_documents_get_no_embedding(tg, fake_embed):
    fake_embed.update(PHOTO=vector(1, 0, 0))
    item = await make_item(category="passport", status="pending")
    await services.publish_item(tg.bot, item, "text")
    assert (await db.get_item(item["id"]))["embedding"] is None


# ---------- haqiqiy model (sekin: pytest -m ocr) ----------

def drawing(color: str, shape: str, shift: int = 0) -> bytes:
    image = Image.new("RGB", (320, 320), "white")
    draw = ImageDraw.Draw(image)
    box = (60 + shift, 60 + shift, 260 + shift, 260 + shift)
    (draw.ellipse if shape == "circle" else draw.rectangle)(box, fill=color)
    result = BytesIO()
    image.save(result, format="JPEG")
    return result.getvalue()


@pytest.mark.ocr
def test_real_model_prefers_same_picture():
    original = visual.embed_image(drawing("red", "circle"))
    shifted = visual.embed_image(drawing("red", "circle", shift=20))
    other = visual.embed_image(drawing("blue", "square"))
    assert visual.similarity(original, shifted) > visual.similarity(original, other)
