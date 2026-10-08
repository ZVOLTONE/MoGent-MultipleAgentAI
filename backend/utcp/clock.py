"""Current-time tool (local, no network).

Gives agents a reliable "now" so they can reason about data recency and avoid
time confusion (e.g. stating a 2025 figure is "current"). Returns WIB (UTC+7)
plus ISO/UTC for completeness.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

_MONTHS_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
              "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
_DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def now_info() -> dict:
    now_wib = datetime.now(WIB)
    now_utc = datetime.now(timezone.utc)
    tanggal = (f"{_DAYS_ID[now_wib.weekday()]}, {now_wib.day} "
               f"{_MONTHS_ID[now_wib.month]} {now_wib.year}")
    return {
        "now_wib": now_wib.isoformat(timespec="seconds"),
        "now_utc": now_utc.isoformat(timespec="seconds"),
        "date_wib": now_wib.strftime("%Y-%m-%d"),
        "time_wib": now_wib.strftime("%H:%M:%S"),
        "tanggal_id": tanggal,
        "year": now_wib.year,
        "timezone": "WIB (UTC+7)",
    }
