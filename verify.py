"""Hujjat egasini avtomatik tekshirish.

Egasi ism-familiyasini va hujjat raqamining oxirgi 3 ta raqamini yozadi. OCR asl (xiralashtirilmagan)
rasmni o'qiydi va solishtiradi. Ism-familiya HAM raqam mos kelsagina tasdiqlanadi — raqamlar kanaldagi
rasmda xiralashtirilgan, shuning uchun ularni faqat haqiqiy egasi biladi.
Hech qachon avtomatik rad etilmaydi: mos kelmasa, admin qaror qiladi.
"""
import asyncio
import logging
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher

from aiogram import Bot

import database as db
from config import AUTO_VERIFY_DOCUMENTS
from docnumber import numbers_in_text
from images import document_text
from services import notify_document_owners
from utils import is_document

logger = logging.getLogger(__name__)

# Egasi natijani ko'pi bilan shuncha kutadi, keyin murojaat adminga o'tadi
MAX_WAIT_SECONDS = 20

# Hozir o'qilayotgan hujjatlar: item_id -> OCR vazifasi
_running: dict[int, asyncio.Task] = {}

# Bir harf adashsa ham (OCR yoki imlo xatosi) mos deb hisoblaymiz
NAME_SIMILARITY = 0.8
CARD_NUMBER_RE = re.compile(r"(?<!\d)\d{16}(?!\d)")

CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}


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
        numbers += [number[2:] for number in numbers_in_text([line])]  # seriyasiz, faqat 7 ta raqam
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


async def _read_and_save(bot: Bot, item: dict) -> list[str]:
    started = time.monotonic()
    lines = await document_text(bot, item["photo_id"])
    await db.update_item(item["id"], ocr_text="\n".join(lines))
    logger.info("Hujjat o'qildi (#%s): %.1f s", item["id"], time.monotonic() - started)
    try:
        await notify_document_owners(bot, item["id"])  # raqami mos "yo'qotdim" e'lonlari
    except Exception as error:
        logger.error("Hujjat egalariga xabar yuborilmadi (#%s): %s", item["id"], error)
    return lines


def _ocr_task(bot: Bot, item: dict) -> asyncio.Task:
    """Bitta e'lon uchun OCR faqat bir marta ishlaydi — ikkinchi so'rov o'sha natijani kutadi."""
    task = _running.get(item["id"])
    if task is None:
        task = asyncio.create_task(_read_and_save(bot, item))
        _running[item["id"]] = task
        task.add_done_callback(lambda _: _running.pop(item["id"], None))
    return task


def prepare_document(bot: Bot, item: dict) -> None:
    """E'lon berilishi bilan hujjatni fonda o'qib qo'yadi — egasi murojaat qilganda natija tayyor turadi."""
    if not AUTO_VERIFY_DOCUMENTS or not is_document(item["category"]) or item.get("ocr_text") is not None:
        return
    task = _ocr_task(bot, item)
    task.add_done_callback(
        lambda done: done.exception() and logger.warning("Hujjat o'qilmadi (#%s): %s", item["id"], done.exception())
    )


async def verify_document_claim(bot: Bot, item: dict, proof: str) -> Verdict | None:
    """None — tekshirib bo'lmadi (OCR xatosi yoki juda uzoq davom etdi), admin qaror qiladi."""
    if item.get("ocr_text") is not None:
        lines = item["ocr_text"].split("\n")
    else:
        try:
            # shield: vaqt tugasa ham OCR fonda davom etadi va natija keyingi murojaatlar uchun saqlanadi
            lines = await asyncio.wait_for(asyncio.shield(_ocr_task(bot, item)), timeout=MAX_WAIT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("Hujjat %s s ichida o'qilmadi (#%s) — admin tekshiradi", MAX_WAIT_SECONDS, item["id"])
            return None
        except Exception as error:
            logger.warning("Hujjat o'qilmadi (#%s): %s", item["id"], error)
            return None
    verdict = check(proof, lines)
    logger.info("Hujjat tekshiruvi #%s: %s", item["id"], verdict)
    return verdict
