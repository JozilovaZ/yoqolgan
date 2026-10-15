"""Yo'qotilgan va topilgan narsalarni moslashtirish (matching.py)."""
import pytest

from matching import found_day, is_match, region_key

REPORT = {"category": "phone", "owner_id": 1, "region": "Samarqand viloyati", "lost_day": "2026-10-10"}
ITEM = {"category": "phone", "finder_id": 2, "region": "Samarqand", "found_date": "11.10.2026 (Shanba), soat 14:00"}


@pytest.mark.parametrize(
    "item_changes, report_changes, expected",
    [
        ({}, {}, True),
        ({"region": "Toshkent"}, {}, False),  # boshqa viloyat
        ({"found_date": "01.10.2026 (Payshanba)"}, {}, False),  # yo'qotilishidan oldin topilgan
        ({"found_date": "09.10.2026 (Juma)"}, {}, True),  # 1 kun zaxira — sanani adashtirishi mumkin
        ({"found_date": "20.12.2026 (Yakshanba)"}, {}, False),  # 60 kundan keyin
        ({"category": "wallet"}, {}, False),
        ({"finder_id": 1}, {}, False),  # o'zi topgan narsasi
        ({"region": ""}, {}, True),  # topilgan joy viloyati noma'lum
        ({"region": "Toshkent"}, {"region": ""}, True),  # egasi viloyatni bilmaydi
        ({"region": "Самарқанд"}, {}, True),  # kirillcha — noma'lum deb hisoblanadi
    ],
)
def test_is_match(item_changes, report_changes, expected):
    assert is_match({**REPORT, **report_changes}, {**ITEM, **item_changes}) is expected


def test_region_key_ignores_apostrophes_and_suffix():
    assert region_key("Qoraqalpogʻiston") == region_key("Qoraqalpog'iston") == "qoraqalpogiston"
    assert region_key("Farg'ona viloyati") == region_key("Fargʻona") == "fargona"
    assert region_key("") == region_key(None) == ""


def test_found_day_parses_date_prefix():
    assert found_day({"found_date": "05.03.2026 (Payshanba), soat 09:00 atrofida"}).isoformat() == "2026-03-05"
    assert found_day({"found_date": ""}) is None
