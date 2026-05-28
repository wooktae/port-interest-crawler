"""시장 휴일 여부를 조회하는 공통 보조 모듈이다.

Nager.Date API를 호출해 국가별 공휴일을 가져오고, KRX/US 시장 휴일 판정에 사용된다.
외부 API 요청이 포함되므로 호출하는 validation/수집 스크립트 실행 시 네트워크 영향이 있다.
"""

import requests
from datetime import datetime, date

HOLIDAY_API_BASE = "https://date.nager.at/api/v3/PublicHolidays"

# 캐시 (API 호출 최소화)
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

    # 주말
    if target_date.weekday() >= 5:
        return True

    # 공휴일
    holidays = _fetch_holidays(target_date.year, market)

    return target_date in holidays
