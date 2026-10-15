"""Hujjat egasini avtomatik tekshirish.

Egasi ism-familiyasini va hujjat raqamining oxirgi 3 ta raqamini yozadi. OCR asl (xiralashtirilmagan)
rasmni o'qiydi va solishtiradi. Ism-familiya HAM raqam mos kelsagina tasdiqlanadi — raqamlar kanaldagi
rasmda xiralashtirilgan, shuning uchun ularni faqat haqiqiy egasi biladi.
Hech qachon avtomatik rad etilmaydi: mos kelmasa, admin qaror qiladi.
"""
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from aiogram import Bot

import database as db
from images import document_text

logger = logging.getLogger(__name__)

# Bir harf adashsa ham (OCR yoki imlo xatosi) mos deb hisoblaymiz
NAME_SIMILARITY = 0.8
# Pasport / ID karta / prava raqami: 2 harfli seriya + 7 raqam (AA1234567). MRZ'da undan keyin
# bitta nazorat raqami turadi (AA12345671UZB...). Oldidan harf turmasligi kerak:
# MRZ'dagi "UZB9005123" (tug'ilgan sana) hujjat raqami emas
DOCUMENT_NUMBER_RE = re.compile(r"(?<![A-Z])[A-Z]{2}\s?([0-9OIDL|]{7})(?=\d?(?:\D|$))")
CARD_NUMBER_RE = re.compile(r"(?<!\d)\d{16}(?!\d)")

CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}

# Raqamlar orasida OCR adashtiradigan harflar
DIGIT_LOOKALIKES = str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1", "|": "1"})


@dataclass
class Verdict:
    name_ok: bool
    number_ok: bool

    @property
    def approved(self) -> bool:
        return self.name_ok and self.number_ok

    def summary(self) -> str:
        mark = {True: "✅", False: "❌"}
        return f"🤖 Avtomatik tekshiruv: ism-familiya {mark[self.name_ok]}, raqam {mark[self.number_ok]}"


def _words(text: str) -> list[str]:
    text = "".join(CYRILLIC.get(char, char) for char in text.lower())
    text = re.sub(r"['ʻʼ‘’`]", "", text)  # O'ktam / Oʻktam / Oktam — bir xil
    return re.findall(r"[a-z]{3,}", text)


def _document_numbers(lines: list[str]) -> list[str]:
    """Faqat hujjat raqamlari: seriya + 7 raqam ("AA 1234567", MRZ boshi) yoki 16 xonali karta raqami.
    Sanalar va MRZ'dagi boshqa raqamlar olinmaydi — ular tasodifan mos kelib qolmasligi uchun."""
    numbers = []
    for line in lines:
        line = line.upper()
        for digits in DOCUMENT_NUMBER_RE.findall(line):
            digits = digits.translate(DIGIT_LOOKALIKES)
            if digits.isdigit():
                numbers.append(digits)
        numbers += CARD_NUMBER_RE.findall(re.sub(r"(?<=\d)[\s-]+(?=\d)", "", line))
    return numbers


def _similar(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= NAME_SIMILARITY


def check(proof: str, lines: list[str]) -> Verdict:
    # Ism: kamida 2 ta so'z (ism va familiya) hujjatda topilishi kerak
    document_words = {word for line in lines for word in _words(line.replace("<", " "))}
    owner_words = _words(re.sub(r"\d", " ", proof))
    matched = sum(any(_similar(word, other) for other in document_words) for word in set(owner_words))
    name_ok = matched >= 2

    # Raqam: egasi yozgan oxirgi 3 ta raqam hujjat raqamining oxiri bilan mos kelishi kerak
    digits = "".join(re.findall(r"\d", proof))
    number_ok = False
    if len(digits) >= 3:
        number_ok = any(number.endswith(digits[-3:]) for number in _document_numbers(lines))
    return Verdict(name_ok, number_ok)


async def verify_document_claim(bot: Bot, item: dict, proof: str) -> Verdict | None:
    """None — tekshirib bo'lmadi (OCR xatosi), admin qaror qiladi."""
    try:
        if item.get("ocr_text") is None:
            lines = await document_text(bot, item["photo_id"])
            # Keyingi murojaatlar uchun saqlab qo'yamiz — OCR sekin ishlaydi
            await db.update_item(item["id"], ocr_text="\n".join(lines))
        else:
            lines = item["ocr_text"].split("\n")
    except Exception as error:
        logger.warning("Hujjat o'qilmadi (#%s): %s", item["id"], error)
        return None
    verdict = check(proof, lines)
    logger.info("Hujjat tekshiruvi #%s: %s", item["id"], verdict)
    return verdict
