"""Instagram'ga joylash (instagram.py): rasm nisbati, izoh, navbat, xatolar va limit."""
import asyncio
import os
from io import BytesIO

import pytest
from aiohttp.test_utils import make_mocked_request
from aiohttp import web
from PIL import Image

import database as db
import instagram
from config import ADMIN_GROUP_ID
from services import publish_item
from tests.fakes import make_item


def jpeg(width: int, height: int) -> bytes:
    result = BytesIO()
    Image.new("RGB", (width, height), "red").save(result, format="JPEG")
    return result.getvalue()


def size(data: bytes) -> tuple[int, int]:
    return Image.open(BytesIO(data)).size


class FakeGraph:
    """Meta Graph API o'rniga: so'rovlarni yozib oladi, kerak bo'lsa xato beradi."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.error: instagram.InstagramError | None = None
        self.files_seen: list[bool] = []  # container yaratilganda rasm fayli serverda turganmidi

    async def __call__(self, method: str, path: str, **params) -> dict:
        self.calls.append((method, path, params))
        if path.endswith("/media"):
            if self.error:
                raise self.error
            name = params["image_url"].rsplit("/", 1)[1]
            self.files_seen.append(os.path.isfile(os.path.join(instagram.MEDIA_DIR, name)))
            return {"id": "C1"}
        if path.endswith("/media_publish"):
            return {"id": "M1"}
        if path == "C1":
            return {"status_code": "FINISHED"}
        return {"permalink": "https://www.instagram.com/p/abc/"}

    def published(self) -> list[dict]:
        return [params for _, path, params in self.calls if path.endswith("/media")]


@pytest.fixture
def graph(monkeypatch, tmp_path):
    fake = FakeGraph()
    downloads = []

    async def download(bot, file_id):
        downloads.append(file_id)
        return jpeg(600, 1000)

    monkeypatch.setattr(instagram, "INSTAGRAM_ENABLED", True)
    monkeypatch.setattr(instagram, "INSTAGRAM_USER_ID", "1784")
    monkeypatch.setattr(instagram, "WEBHOOK_URL", "https://bot.izla.uz")
    monkeypatch.setattr(instagram, "MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setattr(instagram, "_graph", fake)
    monkeypatch.setattr(instagram, "_download", download)
    fake.downloads = downloads
    return fake


async def wait_tasks():
    await asyncio.gather(*instagram._tasks)


# ---------- rasm va matn ----------

def test_fit_ratio_pads_tall_and_wide_images():
    width, height = size(instagram.fit_ratio(jpeg(600, 1000)))
    assert height == 1000 and abs(width / height - 0.8) < 0.01
    width, height = size(instagram.fit_ratio(jpeg(1400, 400)))
    assert width == 1400 and abs(width / height - 1.91) < 0.01
    assert size(instagram.fit_ratio(jpeg(800, 800))) == (800, 800)


async def test_text_card_and_caption():
    item = await make_item(publish_mode="text", description="qora <b>iPhone</b>")
    assert size(instagram.text_card(item)) == (1080, 1080)
    text = instagram.caption(item, "izla_bot")
    assert "T0001" in text and "@izla_bot" in text and "#telefon" in text and "#Toshkent" in text
    assert "<b>iPhone</b>" in text  # HTML yo'q — matn o'zicha


# ---------- navbat ----------

async def test_published_item_goes_to_instagram(tg, graph):
    item = await make_item(status="pending", publish_mode=None)
    await publish_item(tg.bot, item, "photo")
    await wait_tasks()

    item = await db.get_item(item["id"])
    assert item["ig_status"] == "posted" and item["ig_media_id"] == "M1"
    assert item["ig_permalink"] == "https://www.instagram.com/p/abc/"
    [params] = graph.published()
    assert params["image_url"].startswith("https://bot.izla.uz/media/")
    assert graph.files_seen == [True] and not os.listdir(instagram.MEDIA_DIR)  # joylangach o'chirildi
    assert graph.downloads == ["PHOTO"]

    await instagram.process_queue(tg.bot)
    assert len(graph.published()) == 1  # ikkinchi marta joylanmaydi


async def test_disabled_does_nothing(tg, graph, monkeypatch):
    monkeypatch.setattr(instagram, "INSTAGRAM_ENABLED", False)
    item = await make_item(status="pending", publish_mode=None)
    await publish_item(tg.bot, item, "photo")
    assert (await db.get_item(item["id"]))["ig_status"] is None and not graph.calls


async def test_blurred_document_never_uses_original_photo(tg, graph):
    """Kanaldagi xira rasm ID si yo'q bo'lsa — asl hujjat rasmi emas, kartochka joylanadi."""
    item = await make_item(category="passport", publish_mode="blur", ig_status="queued")
    await instagram.process_queue(tg.bot)
    assert not graph.downloads and (await db.get_item(item["id"]))["ig_status"] == "posted"

    item = await make_item(category="passport", publish_mode="blur", ig_status="queued", ig_photo_id="BLURRED")
    await instagram.process_queue(tg.bot)
    assert graph.downloads == ["BLURRED"]


async def test_closed_item_is_skipped(tg, graph):
    item = await make_item(ig_status="queued")
    await db.close_item(item["id"], "removed")
    await instagram.process_queue(tg.bot)
    assert (await db.get_item(item["id"]))["ig_status"] == "skipped" and not graph.calls


async def test_rate_limit_waits_without_counting(tg, graph):
    first = await make_item(ig_status="queued")
    second = await make_item(ig_status="queued")
    graph.error = instagram.InstagramError("Application request limit reached", code=9)
    await instagram.process_queue(tg.bot)
    for item_id in (first["id"], second["id"]):
        item = await db.get_item(item_id)
        assert item["ig_status"] == "queued" and item["ig_attempts"] == 0
    assert len(graph.published()) == 1  # limitdan keyin qolganlari urinilmaydi

    graph.error = None
    await instagram.process_queue(tg.bot)
    assert (await db.get_item(second["id"]))["ig_status"] == "posted"


async def test_errors_retry_then_alert_admin(tg, graph):
    item = await make_item(ig_status="queued")
    graph.error = instagram.InstagramError("Invalid OAuth access token", code=190)
    for _ in range(instagram.MAX_ATTEMPTS - 1):
        await instagram.process_queue(tg.bot)
    assert (await db.get_item(item["id"]))["ig_status"] == "queued" and not tg.admin

    await instagram.process_queue(tg.bot)
    item = await db.get_item(item["id"])
    assert item["ig_status"] == "failed" and "OAuth" in item["ig_error"]
    assert "Invalid OAuth access token" in tg.admin[0]
    assert not os.listdir(instagram.MEDIA_DIR)  # xatoda ham rasm o'chirildi


async def test_admin_delete_mentions_instagram_post(tg):
    item = await make_item(ig_status="posted", ig_media_id="M1", ig_permalink="https://www.instagram.com/p/abc/")
    await tg.press(f"mod:delete:{item['id']}", chat_id=ADMIN_GROUP_ID)
    edited = [call for call in tg.calls if type(call).__name__ == "EditMessageCaption"]
    assert "instagram.com/p/abc" in edited[0].caption


# ---------- rasmni berish ----------

async def test_serve_media_only_known_files(graph):
    os.makedirs(instagram.MEDIA_DIR)
    name = "A" * 32 + ".jpg"
    with open(os.path.join(instagram.MEDIA_DIR, name), "wb") as file:
        file.write(jpeg(10, 10))

    def request(file_name):
        return make_mocked_request("GET", f"/media/{file_name}", match_info={"name": file_name})

    assert isinstance(await instagram.serve_media(request(name)), web.FileResponse)
    for bad in ("B" * 32 + ".jpg", "..%2Fbot.db", "short.jpg"):
        with pytest.raises(web.HTTPNotFound):
            await instagram.serve_media(request(bad))
