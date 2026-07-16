import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")

WEEKDAYS = [
    "월요일",
    "화요일",
    "수요일",
    "목요일",
    "금요일",
    "토요일",
    "일요일",
]

# 주요 24개국 및 지역
COUNTRY_ALIASES = {
    # 호주
    "AU": ("AU", "🇦🇺"),
    "AUS": ("AU", "🇦🇺"),
    "AUSTRALIA": ("AU", "🇦🇺"),

    # 브라질
    "BR": ("BR", "🇧🇷"),
    "BRA": ("BR", "🇧🇷"),
    "BRAZIL": ("BR", "🇧🇷"),

    # 캐나다
    "CA": ("CA", "🇨🇦"),
    "CAN": ("CA", "🇨🇦"),
    "CANADA": ("CA", "🇨🇦"),

    # 중국
    "CN": ("CN", "🇨🇳"),
    "CHN": ("CN", "🇨🇳"),
    "CHINA": ("CN", "🇨🇳"),

    # 유로존
    "EU": ("EU", "🇪🇺"),
    "EMU": ("EU", "🇪🇺"),
    "EURO ZONE": ("EU", "🇪🇺"),
    "EUROZONE": ("EU", "🇪🇺"),
    "EURO AREA": ("EU", "🇪🇺"),
    "EUROPEAN UNION": ("EU", "🇪🇺"),

    # 프랑스
    "FR": ("FR", "🇫🇷"),
    "FRA": ("FR", "🇫🇷"),
    "FRANCE": ("FR", "🇫🇷"),

    # 독일
    "DE": ("DE", "🇩🇪"),
    "DEU": ("DE", "🇩🇪"),
    "GERMANY": ("DE", "🇩🇪"),

    # 홍콩
    "HK": ("HK", "🇭🇰"),
    "HKG": ("HK", "🇭🇰"),
    "HONG KONG": ("HK", "🇭🇰"),

    # 인도
    "IN": ("IN", "🇮🇳"),
    "IND": ("IN", "🇮🇳"),
    "INDIA": ("IN", "🇮🇳"),

    # 인도네시아
    "ID": ("ID", "🇮🇩"),
    "IDN": ("ID", "🇮🇩"),
    "INDONESIA": ("ID", "🇮🇩"),

    # 이탈리아
    "IT": ("IT", "🇮🇹"),
    "ITA": ("IT", "🇮🇹"),
    "ITALY": ("IT", "🇮🇹"),

    # 일본
    "JP": ("JP", "🇯🇵"),
    "JPN": ("JP", "🇯🇵"),
    "JAPAN": ("JP", "🇯🇵"),

    # 한국
    "KR": ("KR", "🇰🇷"),
    "KOR": ("KR", "🇰🇷"),
    "SOUTH KOREA": ("KR", "🇰🇷"),
    "KOREA": ("KR", "🇰🇷"),
    "REPUBLIC OF KOREA": ("KR", "🇰🇷"),

    # 멕시코
    "MX": ("MX", "🇲🇽"),
    "MEX": ("MX", "🇲🇽"),
    "MEXICO": ("MX", "🇲🇽"),

    # 뉴질랜드
    "NZ": ("NZ", "🇳🇿"),
    "NZL": ("NZ", "🇳🇿"),
    "NEW ZEALAND": ("NZ", "🇳🇿"),

    # 포르투갈
    "PT": ("PT", "🇵🇹"),
    "PRT": ("PT", "🇵🇹"),
    "PORTUGAL": ("PT", "🇵🇹"),

    # 러시아
    "RU": ("RU", "🇷🇺"),
    "RUS": ("RU", "🇷🇺"),
    "RUSSIA": ("RU", "🇷🇺"),

    # 싱가포르
    "SG": ("SG", "🇸🇬"),
    "SGP": ("SG", "🇸🇬"),
    "SINGAPORE": ("SG", "🇸🇬"),

    # 남아프리카공화국
    "ZA": ("ZA", "🇿🇦"),
    "ZAF": ("ZA", "🇿🇦"),
    "SOUTH AFRICA": ("ZA", "🇿🇦"),

    # 스페인
    "ES": ("ES", "🇪🇸"),
    "ESP": ("ES", "🇪🇸"),
    "SPAIN": ("ES", "🇪🇸"),

    # 스위스
    "CH": ("CH", "🇨🇭"),
    "CHE": ("CH", "🇨🇭"),
    "SWITZERLAND": ("CH", "🇨🇭"),

    # 튀르키예
    "TR": ("TR", "🇹🇷"),
    "TUR": ("TR", "🇹🇷"),
    "TURKEY": ("TR", "🇹🇷"),
    "TÜRKIYE": ("TR", "🇹🇷"),
    "TURKIYE": ("TR", "🇹🇷"),

    # 영국
    "UK": ("UK", "🇬🇧"),
    "GB": ("UK", "🇬🇧"),
    "GBR": ("UK", "🇬🇧"),
    "UNITED KINGDOM": ("UK", "🇬🇧"),
    "GREAT BRITAIN": ("UK", "🇬🇧"),

    # 미국
    "US": ("US", "🇺🇸"),
    "USA": ("US", "🇺🇸"),
    "UNITED STATES": ("US", "🇺🇸"),
    "UNITED STATES OF AMERICA": ("US", "🇺🇸"),
}


def clean_text(value):
    if value is None:
        return "-"

    text = str(value).replace("\xa0", " ").strip()

    if not text or text.lower() in {"none", "null", "nan", "n/a"}:
        return "-"

    return text


def format_number(value):
    if value is None:
        return "-"

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

        return f"{value:.6f}".rstrip("0").rstrip(".")

    return clean_text(value)


def format_value(value, unit):
    result = format_number(value)

    if result == "-":
        return "-"

    unit_text = clean_text(unit)

    if unit_text == "-":
        return result

    # 값 자체에 단위가 이미 들어간 경우
    if unit_text in result:
        return result

    if unit_text in {"%", "K", "M", "B"}:
        return f"{result}{unit_text}"

    return f"{result} {unit_text}"


def parse_fmp_datetime(value):
    text = clean_text(value)

    if text == "-":
        raise ValueError("이벤트 시간이 없습니다.")

    text = text.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")

    # FMP 경제 캘린더 시간은 UTC 기준
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(KST)


def get_country(country_value):
    country_text = clean_text(country_value).upper()

    return COUNTRY_ALIASES.get(country_text)


def download_fmp_calendar(target_date):
    api_key = os.environ.get("FMP_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("FMP_API_KEY가 GitHub Secrets에 없습니다.")

    # 한국시간 하루는 UTC 기준 전날 15시부터 당일 15시 전까지이므로
    # 날짜 경계 누락 방지를 위해 전날부터 다음 날까지 넓게 조회합니다.
    from_date = target_date - timedelta(days=1)
    to_date = target_date + timedelta(days=1)

    query = urllib.parse.urlencode(
        {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "apikey": api_key,
        }
    )

    url = (
        "https://financialmodelingprep.com/stable/economic-calendar?"
        + query
    )

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "EconomicCalendarTelegramBot/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read().decode("utf-8")

    data = json.loads(body)

    if isinstance(data, dict):
        error_message = (
            data.get("Error Message")
            or data.get("error")
            or data.get("message")
        )

        if error_message:
            raise RuntimeError(f"FMP 응답 오류: {error_message}")

        # 일부 응답 형식은 결과가 배열 안에 들어갑니다.
        data = (
            data.get("economicCalendar")
            or data.get("data")
            or data.get("results")
            or []
        )

    if not isinstance(data, list):
        raise RuntimeError("FMP 경제 캘린더 응답 형식을 확인할 수 없습니다.")

    return data


def fetch_events_once(target_date):
    raw_events = download_fmp_calendar(target_date)
    events = []

    for item in raw_events:
        if not isinstance(item, dict):
            continue

        impact = clean_text(item.get("impact")).lower()

        # 중요도 높음만 허용
        if impact != "high":
            continue

        country_info = get_country(item.get("country"))

        # 주요 24개국 이외의 국가는 제외
        if not country_info:
            continue

        country_code, flag = country_info

        raw_time = item.get("date") or item.get("time")

        try:
            event_time = parse_fmp_datetime(raw_time)
        except Exception:
            continue

        # 한국시간 기준 오늘 일정만 허용
        if event_time.date() != target_date:
            continue

        title = (
            item.get("event")
            or item.get("name")
            or item.get("title")
            or "이름 없는 경제 이벤트"
        )

        unit = item.get("unit")

        actual = format_value(
            item.get("actual"),
            unit,
        )

        forecast = format_value(
            item.get("estimate")
            if item.get("estimate") is not None
            else item.get("forecast"),
            unit,
        )

        previous = format_value(
            item.get("previous")
            if item.get("previous") is not None
            else item.get("prev"),
            unit,
        )

        events.append(
            {
                "sort_time": event_time,
                "time": event_time.strftime("%H:%M"),
                "country": country_code,
                "flag": flag,
                "title": clean_text(title),
                "actual": actual,
                "forecast": forecast,
                "previous": previous,
            }
        )

    events.sort(key=lambda event: event["sort_time"])
    return events


def fetch_events_with_retry(target_date):
    errors = []

    for attempt in range(1, 4):
        try:
            return fetch_events_once(target_date)
        except Exception as exc:
            errors.append(f"{attempt}차: {exc}")

            if attempt < 3:
                time.sleep(attempt * 20)

    raise RuntimeError("\n".join(errors))


def make_messages(target_date, events):
    weekday = WEEKDAYS[target_date.weekday()]

    header = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📅 {target_date.year}년 {target_date.month}월 "
        f"{target_date.day}일 {weekday}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    if not events:
        return [
            header
            + "\n\n"
            + "오늘 예정된 <b>중요도 높음(★★★)</b> "
            + "경제 이벤트가 없습니다.\n\n"
            + "<i>자료: Financial Modeling Prep</i>"
        ]

    blocks = []

    for event in events:
        event_time = html.escape(event["time"])
        country = html.escape(event["country"])
        title = html.escape(event["title"])
        actual = html.escape(event["actual"])
        forecast = html.escape(event["forecast"])
        previous = html.escape(event["previous"])

        block = (
            f"<b>{event_time}　{country} {event['flag']}</b>\n"
            f"★★★　│　<b>{title}</b>\n"
            f"실제: <b>{actual}</b>　"
            f"예측: {forecast}　"
            f"이전: {previous}"
        )

        blocks.append(block)

    messages = []
    current = header

    for block in blocks:
        candidate = current + "\n\n" + block

        # 텔레그램 메시지 길이 제한 대비
        if len(candidate) > 3700:
            messages.append(
                current
                + "\n\n<i>자료: Financial Modeling Prep</i>"
            )

            current = (
                f"<b>📅 {target_date.year}년 "
                f"{target_date.month}월 {target_date.day}일 "
                f"일정 계속</b>\n\n{block}"
            )
        else:
            current = candidate

    if current:
        current += "\n\n<i>자료: Financial Modeling Prep</i>"
        messages.append(current)

    return messages


def telegram_send(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN이 없습니다.")

    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID가 없습니다.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError(f"텔레그램 전송 실패: {result}")


def wait_until_7():
    should_wait = (
        os.environ.get("WAIT_UNTIL_7", "false").strip().lower()
        == "true"
    )

    # 수동 테스트 실행은 기다리지 않음
    if not should_wait:
        return

    now = datetime.now(KST)
    target = datetime.combine(
        now.date(),
        dt_time(7, 0),
        tzinfo=KST,
    )

    if now < target:
        seconds = (target - now).total_seconds()
        print(f"한국시간 오전 7시까지 {int(seconds)}초 기다립니다.")
        time.sleep(seconds)


def main():
    wait_until_7()

    target_date = datetime.now(KST).date()

    try:
        events = fetch_events_with_retry(target_date)

        print(f"중요도 High 이벤트 수: {len(events)}")

        messages = make_messages(target_date, events)

        for message in messages:
            telegram_send(message)
            time.sleep(1)

        print("텔레그램 경제 캘린더 전송 완료")

    except Exception as exc:
        print(f"경제 캘린더 실행 실패: {exc}")

        safe_error = html.escape(str(exc))[:2500]

        try:
            telegram_send(
                "⚠️ <b>경제 캘린더 실행 실패</b>\n\n"
                f"{safe_error}\n\n"
                "GitHub Actions 실행 기록을 확인해주세요."
            )
        except Exception as telegram_error:
            print(f"오류 알림 전송 실패: {telegram_error}")

        raise


if __name__ == "__main__":
    main()
