FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Server vaqti O'zbekiston bo'yicha (kalendar va soatlar to'g'ri chiqishi uchun)
    TZ=Asia/Tashkent \
    DB_PATH=/app/data/bot.db \
    # EasyOCR modellari shu yerda saqlanadi (image ichiga oldindan yuklanadi)
    EASYOCR_MODULE_PATH=/opt/easyocr \
    # Rasm o'xshashligi modeli (visual.py) ham image ichiga oldindan yuklanadi
    TORCH_HOME=/opt/torch

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# torch — faqat CPU versiyasi (GPU versiyasi ~2.5 GB, bizga kerak emas)
RUN pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# OCR modelini build vaqtida yuklab qo'yamiz — konteyner har safar internetdan yuklamasligi uchun
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)"
RUN python -c "from torchvision.models import MobileNet_V3_Large_Weights as W, mobilenet_v3_large as m; m(weights=W.IMAGENET1K_V2)"

COPY . .

# Root bo'lmagan foydalanuvchi — xavfsizlik uchun
RUN useradd --create-home bot && mkdir -p /app/data && chown -R bot:bot /app/data
USER bot

CMD ["python", "main.py"]
