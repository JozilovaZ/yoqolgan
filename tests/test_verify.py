"""Hujjat egasini OCR bilan tekshirish (verify.py)."""
import asyncio
import time
from io import BytesIO

import pytest

import database as db
import verify
from tests.fakes import make_item
from verify import check

PASSPORT = [
    "O'ZBEKISTON RESPUBLIKASI", "PASPORT", "Familiyasi / Surname", "TOSHMATOV",
    "Ismi / Given names", "ALISHER", "AA 1234567", "12.05.1990",
    "P<UZBTOSHMATOV<<ALISHER<<<<<<<<<<<<<<<<<<<<<",
    "AA12345671UZB9005123M3001017<<<<<<<<<<<<<<02",
]


@pytest.mark.parametrize(
    "proof, lines, name_ok, number_ok",
    [
        ("Toshmatov Alisher 567", PASSPORT, True, True),
        ("Тошматов Алишер, 567", PASSPORT, True, True),  # kirillcha
        ("toshmatov alisher, raqami AA1234567", PASSPORT, True, True),
        ("Toshmatov Alisher 123", PASSPORT, True, False),  # MRZ'dagi tug'ilgan sana "...123" bilan tugaydi
        ("Karimov Bobur 567", PASSPORT, False, True),
        ("Alisher 567", PASSPORT, False, True),  # familiyasiz
        ("Toshmatov Alisher", PASSPORT, True, False),  # raqamsiz
        ("Toshmatov Alisher 990", PASSPORT, True, False),  # tug'ilgan yil — hujjat raqami emas
        ("Toshmatov Alisher 567", ["TOSHMATOV ALISHER", "AA 12345G7"], True, False),
        ("Toshmatov Alisher 560", ["TOSHMATOV", "ALlSHER", "AA 123456O"], True, True),  # OCR: O -> 0
        ("ALISHER TOSHMATOV 9012", ["ALISHER TOSHMATOV", "8600 1234 5678 9012"], True, True),  # bank karta
    ],
)
def test_check(proof, lines, name_ok, number_ok):
    verdict = check(proof, lines)
    assert (verdict.name_ok, verdict.number_ok) == (name_ok, number_ok)
    assert verdict.approved is (name_ok and number_ok)


@pytest.fixture
def slow_ocr(monkeypatch):
    """OCR o'rniga: `delay` soniya kutib, PASSPORT matnini qaytaradi. calls — necha marta chaqirilgani."""
    state = {"calls": 0, "delay": 0.2}

    async def fake_document_text(bot, file_id):
        state["calls"] += 1
        await asyncio.sleep(state["delay"])
        return PASSPORT

    monkeypatch.setattr(verify, "document_text", fake_document_text)
    return state


async def test_prepared_ocr_is_reused(slow_ocr):
    """E'lon berilganda fonda boshlangan OCR'ni murojaat kutadi — hujjat ikki marta o'qilmaydi."""
    item = await make_item(category="passport")
    verify.prepare_document(None, item)
    verdict = await verify.verify_document_claim(None, item, "Toshmatov Alisher 567")
    assert verdict.approved and slow_ocr["calls"] == 1

    # Keyingi murojaat — bazadagi natijadan, bir zumda
    item = await db.get_item(item["id"])
    started = time.monotonic()
    assert (await verify.verify_document_claim(None, item, "Toshmatov Alisher 567")).approved
    assert time.monotonic() - started < 0.1 and slow_ocr["calls"] == 1


async def test_slow_ocr_goes_to_admin_but_finishes_in_background(slow_ocr, monkeypatch):
    monkeypatch.setattr(verify, "MAX_WAIT_SECONDS", 0.1)
    slow_ocr["delay"] = 0.4
    item = await make_item(category="passport")
    assert await verify.verify_document_claim(None, item, "Toshmatov Alisher 567") is None  # -> admin
    await asyncio.sleep(0.5)
    assert (await db.get_item(item["id"]))["ocr_text"]  # natija keyingi murojaatlar uchun saqlandi


def test_prepare_skips_non_documents(slow_ocr):
    verify.prepare_document(None, {"id": 1, "category": "phone", "ocr_text": None})
    assert not verify._running


@pytest.mark.ocr
def test_real_ocr_on_synthetic_passport():
    """Haqiqiy EasyOCR: chizilgan pasport namunasi, to'g'ri va 180° ag'darilgan holda."""
    from PIL import Image, ImageDraw, ImageFont

    from images import read_document_text

    image = Image.new("RGB", (1000, 640), (225, 235, 245))
    draw = ImageDraw.Draw(image)
    font, mono = ImageFont.load_default(size=34), ImageFont.load_default(size=30)
    for y, text in [(40, "O'ZBEKISTON RESPUBLIKASI"), (150, "TOSHMATOV"), (250, "ALISHER"), (320, "12.05.1990")]:
        draw.text((380, y), text, fill="black", font=font)
    draw.text((30, 500), "P<UZBTOSHMATOV<<ALISHER<<<<<<<<<<<<<<<<", fill="black", font=mono)
    draw.text((30, 560), "AA12345671UZB9005123M3001017<<<<<<<<<02", fill="black", font=mono)

    for angle in (0, 180):
        buffer = BytesIO()
        image.rotate(angle, expand=True).save(buffer, format="JPEG")
        lines = read_document_text(buffer.getvalue())
        assert check("Toshmatov Alisher 567", lines).approved, (angle, lines)
        assert not check("Toshmatov Alisher 123", lines).approved
