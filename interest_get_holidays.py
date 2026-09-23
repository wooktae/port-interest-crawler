"""Common helper module that queries whether a given date is a market holiday.

It calls the Nager.Date API to fetch public holidays per country and is used for KRX/US market holiday determination.
Because it includes external API requests, there is a network impact when the calling validation/collection scripts run.
"""

import requests
from datetime import datetime, date

HOLIDAY_API_BASE = "https://date.nager.at/api/v3/PublicHolidays"

# Cache (minimize API calls)
_cache = {}


def _fetch_holidays(year: int, country_code: str):
    key = (country_code, year)

    if key in _cache:
        return _cache[key]

    url = f"{HOLIDAY_API_BASE}/{year}/{country_code}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    holidays = {
        datetime.strptime(r["date"], "%Y-%m-%d").date()
        for r in resp.json()
    }

    _cache[key] = holidays
    return holidays


def is_holiday(target_date: date, market: str) -> bool:
    """
    market:
      - "KR"
      - "US"
    """

    # Weekend
    if target_date.weekday() >= 5:
        return True

    # Public holiday
    holidays = _fetch_holidays(target_date.year, market)

    return target_date in holidays
