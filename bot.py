import os
import json
import html
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


# ─────────────────────────────────────
# 기본 설정
# ─────────────────────────────────────

KST = ZoneInfo("Asia/Seoul")

PARSE_API_URL = (
    "https://api.parse.bot/scraper/"
    "e9336453-2dcd-48ab-9665-5232efe69319/"
    "get_calendar"
)


# ─────────────────────────────────────
# 인베스팅 주요 24개 국가
# ─────────────────────────────────────

COUNTRY_IDS = [
    110,  # 남아프리카공화국
    17,   # 독일
    29,   # 아르헨티나
    25,   # 호주
    32,   # 브라질
    6,    # 캐나다
    37,   # 중국
    36,   # 싱가포르
    26,   # 스페인
    5,    # 미국
    22,   # 프랑스
    39,   # 홍콩
    14,   # 인도
    48,   # 인도네시아
    10,   # 이탈리아
    35,   # 일본
    7,    # 멕시코
    43,   # 뉴질랜드
    38,   # 포르투갈
    4,    # 영국
    12,   # 스위스
    72,   # 유로존
    11,   # 대한민국
    63,   # 튀르키예
]


# ─────────────────────────────────────
# 국가 ID → 국가 코드·국기
# ─────────────────────────────────────

COUNTRY_INFO = {
    110: ("ZA", "🇿🇦"),
    17: ("DE", "🇩🇪"),
    29: ("AR", "🇦🇷"),
    25: ("AU", "🇦🇺"),
    32: ("BR", "🇧🇷"),
    6: ("CA", "🇨🇦"),
    37: ("CN", "🇨🇳"),
    36: ("SG", "🇸🇬"),
    26: ("ES", "🇪🇸"),
    5: ("US", "🇺🇸"),
    22: ("FR", "🇫🇷"),
    39: ("HK", "🇭🇰"),
    14: ("IN", "🇮🇳"),
    48: ("ID", "🇮🇩"),
    10: ("IT", "🇮🇹"),
    35: ("JP", "🇯🇵"),
    7: ("MX", "🇲🇽"),
    43: ("NZ", "🇳🇿"),
    38: ("PT", "🇵🇹"),
    4: ("UK", "🇬🇧"),
    12: ("CH", "🇨🇭"),
    72: ("EU", "🇪🇺"),
    11: ("KR", "🇰🇷"),
    63: ("TR", "🇹🇷"),
}


WEEKDAYS_KO = [
    "월요일",
    "화요일",
    "수요일",
    "목요일",
    "금요일",
    "토요일",
    "일요일",
]


# 모바일에서 줄바꿈되지 않도록 짧게 설정
DIVIDER = "━━━━━━━━━━━━"


# ─────────────────────────────────────
# GitHub Secrets 확인
# ─────────────────────────────────────

def get_required_env(name):
    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(
            f"{name}가 GitHub Secrets에 등록되어 있지 않습니다."
        )

    return value


# ─────────────────────────────────────
# 오전 7시까지 기다리기
# ─────────────────────────────────────

def wait_until_7_kst():
    should_wait = (
        os.environ.get("WAIT_UNTIL_7", "false").lower() == "true"
    )

    if not should_wait:
        return

    now = datetime.now(KST)

    target = now.replace(
        hour=7,
        minute=0,
        second=0,
        microsecond=0,
    )

    if now < target:
        seconds = int((target - now).total_seconds())

        print(
            f"한국시간 오전 7시까지 {seconds}초 기다립니다."
        )

        time.sleep(seconds)


# ─────────────────────────────────────
# UTC 시간을 한국시간으로 변환
# ─────────────────────────────────────

def parse_utc_time(value):
    if not value:
        raise ValueError("경제일정 시간이 비어 있습니다.")

    value = str(value).strip()

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(KST)


# ─────────────────────────────────────
# Parse.bot 경제캘린더 가져오기
# ─────────────────────────────────────

def download_calendar(target_date, parse_api_key):
    start_date = target_date - timedelta(days=1)
    end_date = target_date

    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "domain_id": "18",
        "importance": "high",
        "country_ids": ",".join(
            str(country_id) for country_id in COUNTRY_IDS
        ),
    }

    url = (
        PARSE_API_URL
        + "?"
        + urllib.parse.urlencode(params)
    )

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "X-API-Key": parse_api_key,
            "Accept": "application/json",
            "User-Agent": "EconomicCalendarTelegramBot/1.0",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=90,
        ) as response:
            body = response.read().decode("utf-8")

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Parse.bot HTTP 오류: "
            f"{error.code} {error_body[:300]}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Parse.bot 접속 오류: {error.reason}"
        ) from error

    try:
        result = json.loads(body)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Parse.bot 응답이 올바른 JSON 형식이 아닙니다."
        ) from error

    if not isinstance(result, dict):
        raise RuntimeError(
            "Parse.bot 응답 형식이 예상과 다릅니다."
        )

    if result.get("status") != "success":
        raise RuntimeError(
            "Parse.bot 호출 실패: "
            + str(result)[:500]
        )

    payload = result.get("data", {})

    if isinstance(payload, dict):
        raw_events = payload.get("data", [])

    elif isinstance(payload, list):
        raw_events = payload

    else:
        raw_events = []

    if not isinstance(raw_events, list):
        raise RuntimeError(
            "Parse.bot 경제캘린더 데이터 형식이 예상과 다릅니다."
        )

    selected_events = []
    seen = set()

    for event in raw_events:
        if not isinstance(event, dict):
            continue

        importance = str(
            event.get("importance", "")
        ).lower()

        if importance != "high":
            continue

        try:
            event_time_kst = parse_utc_time(
                event.get("time")
            )

        except Exception:
            continue

        if event_time_kst.date() != target_date:
            continue

        duplicate_key = (
            event.get("occurrence_id"),
            event.get("event_id"),
            event_time_kst.isoformat(),
        )

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)

        copied_event = dict(event)
        copied_event["_kst_time"] = event_time_kst

        selected_events.append(copied_event)

    selected_events.sort(
        key=lambda event: (
            event["_kst_time"],
            int(event.get("country_id") or 0),
            str(event.get("event_name") or ""),
        )
    )

    print(
        f"Parse.bot 원본 {len(raw_events)}건, "
        f"한국시간 오늘 High 일정 "
        f"{len(selected_events)}건"
    )

    return selected_events


# ─────────────────────────────────────
# 날짜 제목 만들기
# ─────────────────────────────────────

def make_header(target_date):
    weekday = WEEKDAYS_KO[target_date.weekday()]

    return (
        f"{DIVIDER}\n"
        f"📅 <b>{target_date.year}년 "
        f"{target_date.month}월 "
        f"{target_date.day}일 "
        f"{weekday}</b>\n"
        f"{DIVIDER}"
    )


# ─────────────────────────────────────
# 개별 일정 표시
# ─────────────────────────────────────

def make_event_block(event):
    event_time = event["_kst_time"].strftime("%H:%M")

    country_id = int(
        event.get("country_id") or 0
    )

    country_code, flag = COUNTRY_INFO.get(
        country_id,
        (
            str(event.get("currency") or "??"),
            "🌐",
        ),
    )

    title = (
        event.get("event_name")
        or event.get("long_name")
        or "경제지표 발표"
    )

    title = html.escape(
        str(title).strip()
    )

    return (
        f"<b>{event_time}  "
        f"{country_code} {flag}</b>\n"
        f"<b>{title}</b>"
    )


# ─────────────────────────────────────
# 텔레그램 전체 메시지 만들기
# 하단 기준 및 링크는 표시하지 않음
# ─────────────────────────────────────

def make_messages(target_date, events):
    header = make_header(target_date)

    if not events:
        return [
            header
            + "\n\n"
            + "오늘 예정된 <b>중요도 High</b> "
            + "경제 이벤트가 없습니다."
        ]

    blocks = [
        make_event_block(event)
        for event in events
    ]

    messages = []
    current = header

    for block in blocks:
        candidate = (
            current
            + "\n\n"
            + block
        )

        if len(candidate) > 3900:
            messages.append(current)

            current = (
                header
                + "\n\n"
                + block
            )

        else:
            current = candidate

    messages.append(current)

    return messages


# ─────────────────────────────────────
# 텔레그램 메시지 전송
# ─────────────────────────────────────

def telegram_send(bot_token, chat_id, message):
    url = (
        f"https://api.telegram.org/"
        f"bot{bot_token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json"
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            body = response.read().decode("utf-8")

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"텔레그램 HTTP 오류: "
            f"{error.code} {error_body[:300]}"
        ) from error

    try:
        result = json.loads(body)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "텔레그램 응답이 올바른 JSON 형식이 아닙니다."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(
            "텔레그램 전송 실패: "
            + str(result)[:500]
        )


# ─────────────────────────────────────
# 오류 알림 보내기
# ─────────────────────────────────────

def send_error_message(
    bot_token,
    chat_id,
    error,
):
    safe_error = html.escape(
        str(error)[:1000]
    )

    message = (
        "⚠️ <b>경제캘린더 알림 오류</b>\n\n"
        f"{safe_error}\n\n"
        "오늘 일정이 없다는 뜻이 아니라, "
        "데이터를 가져오지 못했다는 뜻입니다."
    )

    telegram_send(
        bot_token,
        chat_id,
        message,
    )


# ─────────────────────────────────────
# 실행
# ─────────────────────────────────────

def main():
    bot_token = get_required_env(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = get_required_env(
        "TELEGRAM_CHAT_ID"
    )

    parse_api_key = get_required_env(
        "PARSE_API_KEY"
    )

    try:
        wait_until_7_kst()

        target_date = datetime.now(KST).date()

        events = download_calendar(
            target_date=target_date,
            parse_api_key=parse_api_key,
        )

        messages = make_messages(
            target_date,
            events,
        )

        for message in messages:
            telegram_send(
                bot_token,
                chat_id,
                message,
            )

            time.sleep(1)

        print(
            f"{target_date.isoformat()} "
            f"경제캘린더 {len(events)}건 전송 완료"
        )

    except Exception as error:
        print(f"오류 발생: {error}")

        try:
            send_error_message(
                bot_token,
                chat_id,
                error,
            )

        except Exception as telegram_error:
            print(
                "오류 메시지 전송도 실패: "
                + str(telegram_error)
            )

        raise


if __name__ == "__main__":
    main()
