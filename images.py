"""Hujjat rasmlaridagi shaxsiy ma'lumotlarni yashirish.

Pasport / ID karta / prava uchun:
1. Rasm 4 xil burchakda tekshiriladi, yuz eng aniq topilgan burchak tanlanadi (teskari rasm ham to'g'rilanadi).
2. Yuz rasmi xiralashtiriladi.
3. OCR (EasyOCR) bilan matn o'qiladi: raqamli yozuvlar (karta raqami, sanalar, MRZ qatori) xiralashtiriladi.
Biror bosqich ishlamasa — xavfsizlik uchun butun rasm xiralashtiriladi.
"""
import asyncio
import logging
import re
import threading
from io import BytesIO

import cv2
import numpy as np
from aiogram import Bot
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Ikki xil aniqlagich — biri o'tkazib yuborgan yuzni ikkinchisi topishi mumkin
FACE_CASCADES = [
    cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml"),
    cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"),
]

LABEL_PARTIAL = "Yuz va raqamlar yashirilgan"
LABEL_FULL = "Shaxsiy ma'lumotlar yashirilgan"

_reader = None
_reader_lock = threading.Lock()

Box = tuple[int, int, int, int]  # x, y, w, h


def get_reader():
    """EasyOCR modelini bir marta yuklaydi (~10 soniya). Bot ishga tushganda fonda chaqiriladi."""
    global _reader
    with _reader_lock:
        if _reader is None:
            import easyocr

            _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


# ---------- yuz ----------

def _find_faces(image: Image.Image) -> list[Box]:
    gray = cv2.equalizeHist(cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY))
    min_side = int(min(image.size) * 0.08)  # juda mayda "yuz"lar — odatda fon naqshi
    faces = []
    for cascade in FACE_CASCADES:
        found = cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=6, minSize=(min_side, min_side))
        faces += [tuple(map(int, face)) for face in found]
    return faces


def _upright_with_faces(image: Image.Image) -> tuple[Image.Image, list[Box]]:
    """Rasmni 0/90/180/270 gradusga burib, eng katta yuz topilgan holatini qaytaradi."""
    best_image, best_faces, best_size = image, [], 0
    for angle in (0, 90, 180, 270):
        rotated = image.rotate(angle, expand=True) if angle else image
        faces = _find_faces(rotated)
        if faces:
            size = max(w for _, _, w, _ in faces)
            if size > best_size:
                best_image, best_faces, best_size = rotated, faces, size
    # Asosiy portret va unga yaqin o'lchamdagilar (masalan, pasportdagi kichik nusxa-rasm)
    faces = [face for face in best_faces if face[2] >= best_size * 0.3]
    return best_image, faces


# ---------- raqamlar ----------

def _find_numbers(image: Image.Image) -> list[Box]:
    """Ichida kamida 3 ta raqam bor yoki MRZ ('<<') qatori bo'lgan yozuvlar joylashuvi."""
    # Tezlik uchun OCR kichikroq nusxada ishlaydi, natija asl o'lchamga qaytariladi
    scale = min(1.0, 960 / max(image.size))
    small = image.resize((int(image.width * scale), int(image.height * scale))) if scale < 1 else image
    results = get_reader().readtext(np.array(small))
    boxes = []
    for points, text, _confidence in results:
        if len(re.findall(r"\d", text)) >= 3 or "<<" in text:
            xs = [int(p[0] / scale) for p in points]
            ys = [int(p[1] / scale) for p in points]
            boxes.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
    return boxes


# ---------- chizish ----------

def _blur_box(image: Image.Image, box: Box, pad_w: float, pad_h: float) -> None:
    x, y, w, h = box
    width, height = image.size
    area = (
        max(0, int(x - w * pad_w)),
        max(0, int(y - h * pad_h)),
        min(width, int(x + w + w * pad_w)),
        min(height, int(y + h + h * pad_h)),
    )
    region = image.crop(area)
    # Kichraytirib-kattalashtirish (piksel) + blur — qaytarib tiklab bo'lmaydi
    small = region.resize((max(1, region.width // 10), max(1, region.height // 10)))
    region = small.resize(region.size).filter(ImageFilter.GaussianBlur(radius=max(4, min(w, h) / 3)))
    image.paste(region, area)


def _add_label(image: Image.Image, label: str) -> None:
    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default(size=max(16, width // 28))
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = right - left, bottom - top
    band_h = text_h * 2
    draw.rectangle((0, height - band_h, width, height), fill=(0, 0, 0, 170))
    draw.text(((width - text_w) / 2, height - band_h + (band_h - text_h) / 2 - top), label, font=font, fill="white")


def _blur_all(image: Image.Image) -> Image.Image:
    image = image.filter(ImageFilter.GaussianBlur(radius=max(image.size) / 30))
    _add_label(image, LABEL_FULL)
    return image


def hide_personal_data(data: bytes, faces_only: bool) -> bytes:
    """faces_only=True: yuz va raqamlar xiralashadi (pasport, ID karta, prava).
    faces_only=False: butun rasm xiralashadi (bank karta va h.k.)."""
    image = Image.open(BytesIO(data)).convert("RGB")
    image.thumbnail((1280, 1280))

    if not faces_only:
        image = _blur_all(image)
    else:
        try:
            image, faces = _upright_with_faces(image)
            if not faces:
                raise ValueError("yuz topilmadi")
            numbers = _find_numbers(image)
            logger.info("Yashirildi: %d ta yuz, %d ta raqamli yozuv", len(faces), len(numbers))
            for face in faces:
                _blur_box(image, face, pad_w=0.5, pad_h=0.6)
            for box in numbers:
                _blur_box(image, box, pad_w=0.08, pad_h=0.25)
            _add_label(image, LABEL_PARTIAL)
        except Exception as error:
            logger.warning("Qisman yashirib bo'lmadi (%s) — butun rasm xiralashtirildi", error)
            image = _blur_all(image)

    result = BytesIO()
    image.save(result, format="JPEG", quality=88)
    return result.getvalue()


async def blurred_photo(bot: Bot, file_id: str, faces_only: bool) -> bytes:
    source = BytesIO()
    await bot.download(file_id, destination=source)
    # OCR og'ir ish — bot boshqa foydalanuvchilarga javob berishda davom etishi uchun alohida oqimda
    return await asyncio.to_thread(hide_personal_data, source.getvalue(), faces_only)
