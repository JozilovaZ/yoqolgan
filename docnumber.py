"""Hujjat raqami (pasport, ID karta, prava): "AA1234567" — 2 harfli seriya + 7 raqam.

Yo'qotgan odam raqamini yozib qo'yadi, topilgan hujjatdagi raqamni OCR o'qiydi — mos kelsa, egasiga darhol xabar.
Raqam bazada ochiq saqlanmaydi: faqat HMAC izi (DOC_HASH_SECRET kaliti bilan). Baza o'g'irlansa ham
kalitsiz raqamlarni tiklab bo'lmaydi.
"""
import hashlib
import hmac
import re

from config import DOC_HASH_SECRET

# Raqami so'raladigan hujjatlar (bank kartaning to'liq raqamini so'ramaymiz)
NUMBERED_DOCUMENTS = {"passport", "id_card", "driver"}

# Oldidan harf turmasligi kerak: MRZ'dagi "UZB9005123" (tug'ilgan sana) hujjat raqami emas.
# MRZ'da raqamdan keyin bitta nazorat raqami turadi (AA12345671UZB...)
DOCUMENT_NUMBER_RE = re.compile(r"(?<![A-Z])([A-Z]{2})\s?([0-9OIDL|]{7})(?=\d?(?:\D|$))")

# Raqamlar orasida OCR adashtiradigan harflar
DIGIT_LOOKALIKES = str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1", "|": "1"})
# Kirill klaviaturada yozilgan seriya: "АА" -> "AA"
CYRILLIC_LETTERS = str.maketrans("АВЕКМНОРСТХУ", "ABEKMHOPCTXY")


def normalize(text: str) -> str | None:
    """Foydalanuvchi yozgan raqam: "aa 123-45-67", "АА1234567" -> "AA1234567". Noto'g'ri bo'lsa None."""
    text = re.sub(r"[\s\-.№#]", "", text.upper().translate(CYRILLIC_LETTERS))
    if len(text) != 9:
        return None
    number = text[:2] + text[2:].translate(DIGIT_LOOKALIKES)
    return number if re.fullmatch(r"[A-Z]{2}\d{7}", number) else None


def numbers_in_text(lines: list[str]) -> set[str]:
    """OCR o'qigan yozuvlardagi hujjat raqamlari ("AA1234567")."""
    numbers = set()
    for line in lines:
        for series, digits in DOCUMENT_NUMBER_RE.findall(line.upper()):
            digits = digits.translate(DIGIT_LOOKALIKES)
            if digits.isdigit():
                numbers.add(series + digits)
    return numbers


def fingerprint(number: str) -> str:
    return hmac.new(DOC_HASH_SECRET.encode(), number.encode(), hashlib.sha256).hexdigest()


def masked(number: str) -> str:
    """Foydalanuvchiga ko'rsatish uchun: "AA•••••67"."""
    return f"{number[:2]}•••••{number[-2:]}"
