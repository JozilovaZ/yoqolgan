"""Yo'qotilgan narsalarni topilgan narsalar bilan moslashtirish."""
import re
from datetime import date, timedelta

# Narsa yo'qotilgan kundan keyin shuncha kun ichida topilgan bo'lsa — mos deb hisoblaymiz
MATCH_DAYS = 60


def region_key(region: str | None) -> str:
    """"Samarqand viloyati", "Samarqand" -> "samarqand". Lotinda bo'lmasa — bo'sh (noma'lum)."""
    words = (region or "").split()
    return re.sub(r"[^a-z]", "", words[0].lower()) if words else ""


def found_day(item: dict) -> date | None:
    """Item'dagi "15.10.2026 (Payshanba), soat ..." matnidan sanani ajratadi."""
    match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", item.get("found_date") or "")
    if not match:
        return None
    day, month, year = map(int, match.groups())
    return date(year, month, day)


def is_match(report: dict, item: dict) -> bool:
    if report["category"] != item["category"] or report["owner_id"] == item["finder_id"]:
        return False

    # Viloyat ikkalasida ham ma'lum bo'lsa — bir xil bo'lishi kerak
    lost_region, found_region = region_key(report["region"]), region_key(item["region"])
    if lost_region and found_region and lost_region != found_region:
        return False

    day = found_day(item)
    if day and report["lost_day"]:
        lost = date.fromisoformat(report["lost_day"])
        # 1 kun zaxira: odam sanani biroz adashtirishi mumkin
        if not lost - timedelta(days=1) <= day <= lost + timedelta(days=MATCH_DAYS):
            return False
    return True
