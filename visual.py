"""Rasm o'xshashligi: yo'qotgan odam yuborgan rasm va topilgan narsalar rasmi.

Har bir rasm MobileNetV3 (ImageNet) bilan 960 sonli "barmoq izi"ga aylantiriladi va bazada saqlanadi.
Ikki rasm o'xshashligi — barmoq izlari orasidagi kosinus (0..1). Bu aniq isbot emas (boshqa qora hamyon ham
o'xshash chiqadi), shuning uchun faqat tartiblash va "rasmi o'xshaydi" belgisi uchun ishlatiladi —
mos kelishni baribir kategoriya, viloyat va sana hal qiladi.
"""
import asyncio
import logging
import threading
from io import BytesIO

import numpy as np
from aiogram import Bot
from PIL import Image

logger = logging.getLogger(__name__)

# Taxminiy chegaralar — haqiqiy e'lonlar to'plangach moslash kerak. Model shaklga rangdan ko'ra ko'proq
# e'tibor beradi: bir xil shakldagi boshqa rangli narsa ham ~0.85 chiqishi mumkin
VERY_SIMILAR = 0.85
SIMILAR = 0.7

_model = None
_transforms = None
_model_lock = threading.Lock()


def get_model():
    """Modelni bir marta yuklaydi (~21 MB). Bot ishga tushganda fonda chaqiriladi."""
    global _model, _transforms
    with _model_lock:
        if _model is None:
            import torch
            from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

            weights = MobileNet_V3_Large_Weights.IMAGENET1K_V2
            model = mobilenet_v3_large(weights=weights).eval()
            model.classifier = torch.nn.Identity()  # sinf emas, xususiyatlar kerak
            _model, _transforms = model, weights.transforms()
    return _model, _transforms


def embed_image(data: bytes) -> bytes:
    """Rasm -> normallangan barmoq izi (float32 baytlar)."""
    import torch

    image = Image.open(BytesIO(data)).convert("RGB")
    model, transforms = get_model()
    with torch.no_grad():
        vector = model(transforms(image).unsqueeze(0))[0].numpy().astype(np.float32)
    vector /= np.linalg.norm(vector) or 1.0
    return vector.tobytes()


def similarity(a: bytes | None, b: bytes | None) -> float | None:
    if not a or not b:
        return None
    return float(np.dot(np.frombuffer(a, dtype=np.float32), np.frombuffer(b, dtype=np.float32)))


def level(score: float | None) -> str | None:
    """'high' | 'medium' | None — foydalanuvchiga ko'rsatish uchun."""
    if score is None:
        return None
    if score >= VERY_SIMILAR:
        return "high"
    return "medium" if score >= SIMILAR else None


async def embed(bot: Bot, file_id: str) -> bytes | None:
    """Telegram'dagi rasmning barmoq izi. Xato bo'lsa None — o'xshashlik shunchaki hisobga olinmaydi."""
    try:
        source = BytesIO()
        await bot.download(file_id, destination=source)
        return await asyncio.to_thread(embed_image, source.getvalue())
    except Exception as error:
        logger.warning("Rasm barmoq izi olinmadi: %s", error)
        return None
