import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from curl_cffi import requests


KST = ZoneInfo("Asia/Seoul")

# 인베스팅 경제 캘린더의 주요 24개국
COUNTRIES = {
    25: ("AU", "🇦🇺"),
    32: ("BR", "🇧🇷"),
    6: ("CA", "🇨🇦"),
    37: ("CN", "🇨🇳"),
    72: ("EU", "🇪🇺"),
    22: ("FR", "🇫🇷"),
    17: ("DE", "🇩🇪"),
    39: ("HK", "🇭🇰"),
    14: ("IN", "🇮🇳"),
    48: ("ID", "🇮🇩"),
    10: ("IT", "🇮🇹"),
    35: ("JP", "🇯🇵"),
    11: ("KR", "🇰🇷"),
    7: ("MX", "🇲🇽"),
    43: ("NZ", "🇳🇿"),
    38: ("PT", "🇵🇹"),
    56: ("RU", "🇷🇺"),
    36: ("SG", "🇸🇬"),
    110: ("ZA", "🇿🇦"),
    26: ("ES", "🇪🇸"),
    12: ("CH", "🇨🇭"),
    63: ("TR", "🇹🇷"),
    4: ("UK", "🇬🇧"),
    5: ("US", "🇺🇸"),
}

COUNTRY_NAME_MAP = {
    "호주": ("AU", "🇦🇺"),
    "브라질": ("BR", "🇧🇷"),
    "캐나다": ("CA", "🇨🇦"),
    "중국": ("CN", "🇨🇳"),
    "유로존": ("EU", "🇪🇺"),
    "프랑스": ("FR", "🇫🇷"),
    "독일": ("DE", "🇩🇪"),
    "홍콩": ("HK", "🇭🇰"),
    "인도": ("IN", "🇮🇳"),
    "인도네시아": ("ID", "🇮🇩"),
    "이탈리아": ("IT", "🇮🇹"),
    "일본": ("JP", "🇯🇵"),
    "대한민국": ("KR", "🇰🇷"),
    "한국": ("KR", "🇰🇷"),
    "멕시코": ("MX", "🇲🇽"),
    "뉴질랜드": ("NZ", "🇳🇿"),
    "포르투갈": ("PT", "🇵🇹"),
    "러시아": ("RU", "🇷🇺"),
    "싱가포르": ("SG", "🇸🇬"),
    "남아프리카 공화국": ("ZA", "🇿🇦"),
    "스페인": ("ES", "🇪🇸"),
    "스위스": ("CH", "🇨🇭"),
    "튀르키예": ("TR", "🇹🇷"),
    "터키": ("TR", "🇹🇷"),
    "영국": ("UK", "🇬🇧"),
    "미국": ("US", "🇺🇸"),
}

CURRENCY_MAP = {
    "AUD": ("AU", "🇦🇺"),
    "BRL": ("BR", "🇧🇷"),
    "CAD": ("CA", "🇨🇦"),
    "CNY": ("CN", "🇨🇳"),
    "EUR": ("EU", "🇪🇺"),
    "HKD": ("HK", "🇭🇰"),
    "INR": ("IN", "🇮🇳"),
    "IDR": ("ID", "🇮🇩"),
    "JPY": ("JP", "🇯🇵"),
    "KRW": ("KR", "🇰🇷"),
    "MXN": ("MX", "🇲🇽"),
    "NZD": ("NZ", "🇳🇿"),
    "RUB": ("RU", "🇷🇺"),
    "SGD": ("SG", "🇸🇬"),
    "ZAR": ("ZA", "🇿🇦"),
    "CHF": ("CH", "🇨🇭"),
    "TRY": ("TR", "🇹🇷"),
    "GBP": ("UK", "🇬🇧"),
    "USD": ("US", "🇺🇸"),
}

WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def clean_text(value):
    if value is None:
        return "-"
    text = str(value).replace("\xa0", " ").strip()
    return text if text else "-"


def get_session():
    session = requests.Session(impersonate="chrome")
    session.headers.update(
        {
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
        }
    )
    return session


def extract_access_token(page_text):
    patterns = [
        r'"accessToken"\s*:\s*"([^"]+)"',
        r'\\"accessToken\\"\s*:\s*\\"([^"\\]+)',
        r'accessToken[\'"]?\s*[:=]\s*[\'"]([^\'"]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, page_text)
        if match:
            return match.group(1)

    return None


def format_api_value(occurrence, key):
    if key not in occurrence or occurrence.get(key) is None:
        return "-"

    value = occurrence.get(key)
    unit = clean_text(occurrence.get("unit"))
    if unit == "-":
        unit = ""

    try:
        number = float(value)
        precision = int(occurrence.get("precision", 0))

        if precision > 0:
            result = f"{number:.{precision}f}"
        elif number.is_integer():
            result = str(int(number))
        else:
            result = str(number)

        return f"{result}{unit}"
    except (TypeError, ValueError):
        return f"{value}{unit}"


def fetch_modern_api(target_date):
    session = get_session()

    page = session.get(
        "https://kr.investing.com/economic-calendar/",
        timeout=40,
    )
    page.raise_for_status()

    token = extract_access_token(page.text)
    if not token:
        raise RuntimeError("인베스팅 페이지에서 접근 토큰을 찾지 못했습니다.")

    start_kst = datetime.combine(target_date, dt_time.min, tzinfo=KST)
    end_kst = datetime.combine(target_date, dt_time.max, tzinfo=KST)

    start_utc = start_kst.astimezone(timezone.utc)
    end_utc = end_kst.astimezone(timezone.utc)

    params = {
        "domain_id": 18,
        "limit": 500,
        "start_date": start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "end_date": end_utc.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "importance": "high",
        "country_ids": ",".join(str(x) for x in COUNTRIES.keys()),
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://kr.investing.com",
        "Referer": "https://kr.investing.com/economic-calendar/",
        "Accept": "application/json",
    }

    response = session.get(
        "https://endpoints.investing.com/"
        "pd-instruments/v1/calendars/economic/events/occurrences",
        params=params,
        headers=headers,
        timeout=40,
    )
    response.raise_for_status()

    data = response.json()
    events_by_id = {
        event.get("event_id"): event for event in data.get("events", [])
    }

    results = []

    for occurrence in data.get("occurrences", []):
        event = events_by_id.get(occurrence.get("event_id"))
        if not event:
            continue

        if str(event.get("importance", "")).lower() != "high":
            continue

        country_id = event.get("country_id")
        if country_id not in COUNTRIES:
            continue

        raw_time = occurrence.get("occurrence_time")
        if not raw_time:
            continue

        event_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        event_time_kst = event_time.astimezone(KST)

        if event_time_kst.date() != target_date:
            continue

        country_code, flag = COUNTRIES[country_id]

        title = (
            event.get("event_translated")
            or event.get("short_name")
            or event.get("long_name")
            or "이름 없는 일정"
        )

        reference_period = clean_text(occurrence.get("reference_period"))
        if reference_period != "-" and reference_period not in title:
            title = f"{title} ({reference_period})"

        results.append(
            {
                "sort_time": event_time_kst,
                "time": event_time_kst.strftime("%H:%M"),
                "country": country_code,
                "flag": flag,
                "title": clean_text(title),
                "actual": format_api_value(occurrence, "actual"),
                "forecast": format_api_value(occurrence, "forecast"),
                "previous": format_api_value(occurrence, "previous"),
            }
        )

    results.sort(key=lambda item: item["sort_time"])
    return results


def country_from_legacy(row, currency):
    country_id = (
        row.get("data-country")
        or row.get("data-country-id")
        or row.get("data-country_id")
    )

    try:
        country_id = int(country_id)
        if country_id in COUNTRIES:
            return COUNTRIES[country_id]
    except (TypeError, ValueError):
        pass

    flag_element = row.select_one("[title]")
    if flag_element:
        country_name = clean_text(flag_element.get("title"))
        if country_name in COUNTRY_NAME_MAP:
            return COUNTRY_NAME_MAP[country_name]

    return CURRENCY_MAP.get(currency, (currency[:2] or "--", "🌐"))


def fetch_legacy_api(target_date):
    session = get_session()
    calendar_url = "https://kr.investing.com/economic-calendar/"

    page = session.get(calendar_url, timeout=40)
    page.raise_for_status()

    payload = [
        ("dateFrom", target_date.strftime("%m/%d/%Y")),
        ("dateTo", target_date.strftime("%m/%d/%Y")),
        ("timeZone", "88"),
        ("timeFilter", "timeOnly"),
        ("currentTab", "custom"),
        ("submitFilters", "1"),
        ("limit_from", "0"),
        ("importance[]", "3"),
    ]

    for country_id in COUNTRIES:
        payload.append(("country[]", str(country_id)))

    response = session.post(
        "https://kr.investing.com/economic-calendar/"
        "Service/getCalendarFilteredData",
        data=payload,
        headers={
            "Referer": calendar_url,
            "Origin": "https://kr.investing.com",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        timeout=40,
    )
    response.raise_for_status()

    data = response.json()
    table_html = data.get("data")

    if not table_html:
        raise RuntimeError("구형 캘린더 응답에 일정 데이터가 없습니다.")

    soup = BeautifulSoup(table_html, "html.parser")
    results = []

    for row in soup.select("tr.js-event-item"):
        importance_count = len(
            row.select(
                ".grayFullBullishIcon, "
                ".fullBullishIcon, "
                "[class*='FullBullishIcon']"
            )
        )

        if importance_count and importance_count < 3:
            continue

        time_cell = row.select_one("td.time")
        event_cell = row.select_one("td.event")
        actual_cell = row.select_one("td.act")
        forecast_cell = row.select_one("td.fore")
        previous_cell = row.select_one("td.prev")
        currency_cell = row.select_one("td.flagCur")

        event_time_text = (
            clean_text(time_cell.get_text(" ", strip=True))
            if time_cell
            else "-"
        )
        title = (
            clean_text(event_cell.get_text(" ", strip=True))
            if event_cell
            else "이름 없는 일정"
        )
        currency = (
            clean_text(currency_cell.get_text(" ", strip=True))
            if currency_cell
            else "--"
        )

        country_code, flag = country_from_legacy(row, currency)

        sort_hour = 99
        sort_minute = 99
        match = re.search(r"(\d{1,2}):(\d{2})", event_time_text)
        if match:
            sort_hour = int(match.group(1))
            sort_minute = int(match.group(2))

        results.append(
            {
                "sort_time": (sort_hour, sort_minute),
                "time": event_time_text,
                "country": country_code,
                "flag": flag,
                "title": title,
                "actual": (
                    clean_text(actual_cell.get_text(" ", strip=True))
                    if actual_cell
                    else "-"
                ),
                "forecast": (
                    clean_text(forecast_cell.get_text(" ", strip=True))
                    if forecast_cell
                    else "-"
                ),
                "previous": (
                    clean_text(previous_cell.get_text(" ", strip=True))
                    if previous_cell
                    else "-"
                ),
            }
        )

    results.sort(key=lambda item: item["sort_time"])
    return results


def fetch_events_with_retry(target_date):
    errors = []

    for attempt in range(1, 4):
        try:
            events = fetch_modern_api(target_date)
            return events, "modern"
        except Exception as exc:
            errors.append(f"현행 API {attempt}차: {exc}")

        try:
            events = fetch_legacy_api(target_date)
            return events, "legacy"
        except Exception as exc:
            errors.append(f"구형 API {attempt}차: {exc}")

        if attempt < 3:
            time.sleep(attempt * 20)

    raise RuntimeError("\n".join(errors[-6:]))


def format_message(target_date, events):
    weekday = WEEKDAYS[target_date.weekday()]

    header = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📅 {target_date.year}년 {target_date.month}월 "
        f"{target_date.day}일 {weekday}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    if not events:
        return [
            header
            + "\n\n"
            + "오늘 예정된 <b>중요도 높음(★★★)</b> 경제 이벤트가 없습니다."
        ]

    blocks = []

    for event in events:
        title = html.escape(event["title"])
        event_time = html.escape(event["time"])
        country = html.escape(event["country"])
        actual = html.escape(event["actual"])
        forecast = html.escape(event["forecast"])
        previous = html.escape(event["previous"])

        block = (
            f"<b>{event_time}　{country} {event['flag']}</b>\n"
            f"★★★　│　<b>{title}</b>\n"
            f"실제: <b>{actual}</b>　 예측: {forecast}　 이전: {previous}"
        )
        blocks.append(block)

    messages = []
    current = header

    for block in blocks:
        candidate = current + "\n\n" + block

        if len(candidate) > 3800:
            messages.append(current)
            current = (
                f"<b>📅 {target_date.year}년 {target_date.month}월 "
                f"{target_date.day}일 일정 계속</b>\n\n{block}"
            )
        else:
            current = candidate

    if current:
        messages.append(current)

    return messages


def telegram_send(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")

    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID가 설정되지 않았습니다.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    request = urllib.request.Request(url, data=payload, method="POST")

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError(f"텔레그램 전송 실패: {result}")


def wait_until_7_if_needed():
    should_wait = os.environ.get("WAIT_UNTIL_7", "false").lower() == "true"

    if not should_wait:
        return

    now = datetime.now(KST)
    target = datetime.combine(now.date(), dt_time(7, 0), tzinfo=KST)

    if now < target:
        seconds = (target - now).total_seconds()
        print(f"오전 7시까지 {int(seconds)}초 기다립니다.")
        time.sleep(seconds)


def main():
    wait_until_7_if_needed()

    now = datetime.now(KST)
    target_date = now.date()

    try:
        events, source = fetch_events_with_retry(target_date)
        print(f"데이터 수집 방식: {source}")
        print(f"수집된 중요 이벤트 수: {len(events)}")

        messages = format_message(target_date, events)

        for message in messages:
            telegram_send(message)
            time.sleep(1)

        print("텔레그램 전송 완료")

    except Exception as exc:
        error_text = html.escape(str(exc))[:3000]

        try:
            telegram_send(
                "⚠️ <b>경제 캘린더 수집 실패</b>\n\n"
                f"{error_text}\n\n"
                "인베스팅 사이트 차단 또는 구조 변경 가능성이 있습니다. "
                "GitHub Actions 실행 기록을 확인해주세요."
            )
        except Exception as telegram_exc:
            print(f"오류 알림 전송도 실패했습니다: {telegram_exc}")

        raise


if __name__ == "__main__":
    main()
