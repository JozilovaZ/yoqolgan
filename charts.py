"""Statistika grafigi (PNG): kunlar kesimida berilgan va qaytarilgan e'lonlar."""
from datetime import date
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 640
LEFT, RIGHT, TOP, BOTTOM = 70, 30, 110, 70

BACKGROUND = "#FFFFFF"
GRID = "#E6E9EF"
AXIS_TEXT = "#6B7280"
TITLE = "#111827"
ITEMS_COLOR = "#3B82F6"  # e'lonlar
RETURNED_COLOR = "#10B981"  # qaytarilganlar


def _nice_max(value: int) -> int:
    """Y o'qi uchun chiroyli yuqori chegara: 4 ga bo'linadigan (to'r chiziqlari butun son bo'lishi uchun)."""
    value = max(value, 4)
    return value + (-value % 4)


def daily_chart(rows: list[dict], title: str) -> bytes:
    """rows: [{"day": "2026-10-15", "items": 3, "returned": 1}, ...]"""
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=18)
    small = ImageFont.load_default(size=15)
    big = ImageFont.load_default(size=28)

    draw.text((LEFT, 28), title, font=big, fill=TITLE)
    total_items = sum(row["items"] for row in rows)
    total_returned = sum(row["returned"] for row in rows)
    legend_x = LEFT
    for color, label in ((ITEMS_COLOR, f"E'lonlar: {total_items}"), (RETURNED_COLOR, f"Qaytarildi: {total_returned}")):
        draw.rounded_rectangle((legend_x, 74, legend_x + 16, 90), radius=3, fill=color)
        draw.text((legend_x + 24, 72), label, font=font, fill=TITLE)
        legend_x += 24 + draw.textlength(label, font=font) + 36

    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    top_value = _nice_max(max([row["items"] for row in rows] + [row["returned"] for row in rows] + [0]))

    # To'r chiziqlari va Y o'qi raqamlari
    for step in range(5):
        value = top_value * step // 4
        y = TOP + plot_h - plot_h * step / 4
        draw.line((LEFT, y, WIDTH - RIGHT, y), fill=GRID, width=1)
        text = str(value)
        draw.text((LEFT - 12 - draw.textlength(text, font=small), y - 9), text, font=small, fill=AXIS_TEXT)

    # Ustunlar: har kunda ikkita (e'lonlar va qaytarilganlar)
    slot = plot_w / max(len(rows), 1)
    bar = max(min(slot * 0.36, 22), 2)
    label_every = max(1, round(len(rows) / 10))
    for index, row in enumerate(rows):
        center = LEFT + slot * index + slot / 2
        for offset, value, color in ((-bar / 2, row["items"], ITEMS_COLOR), (bar / 2, row["returned"], RETURNED_COLOR)):
            if value:
                height = plot_h * value / top_value
                x = center + offset
                draw.rounded_rectangle(
                    (x - bar / 2 + 1, TOP + plot_h - height, x + bar / 2 - 1, TOP + plot_h), radius=3, fill=color
                )
        # X o'qi: har bir nechta kunda sana (oxirgi kun doim ko'rsatiladi)
        if (len(rows) - 1 - index) % label_every == 0:
            label = f"{date.fromisoformat(row['day']):%d.%m}"
            draw.text((center - draw.textlength(label, font=small) / 2, TOP + plot_h + 12), label,
                      font=small, fill=AXIS_TEXT)

    result = BytesIO()
    image.save(result, format="PNG", optimize=True)
    return result.getvalue()
