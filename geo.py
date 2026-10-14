"""Lokatsiyadan manzil nomini aniqlash (OpenStreetMap Nominatim, bepul)."""
import logging

import aiohttp

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "IzlaBot/1.0 (telegram @qaytar_izla_bot)"}


async def reverse_geocode(lat: float, lon: float) -> tuple[str, str]:
    """(viloyat/shahar, aniq joy) qaytaradi. Xato bo'lsa — bo'sh qatorlar."""
    params = {"format": "jsonv2", "lat": lat, "lon": lon, "accept-language": "uz", "zoom": 17}
    try:
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
            async with session.get(NOMINATIM_URL, params=params) as response:
                data = await response.json()
    except Exception as error:  # internet yo'q, server javob bermadi va h.k.
        logger.warning("Manzil aniqlanmadi: %s", error)
        return "", ""

    address = data.get("address", {})
    region = address.get("state") or address.get("city") or address.get("town") or ""

    parts: list[str] = []
    for key in ("city", "town", "village", "county", "district", "suburb", "road"):
        value = address.get(key)
        if value and value != region and value not in parts:
            parts.append(value)
    return region, ", ".join(parts[:3])


def map_link(lat: float, lon: float) -> str:
    return f"https://maps.google.com/?q={lat},{lon}"
