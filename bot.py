import html
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")

CALENDAR_URL = (
    "https://nfs.faireconomy.media/"
    "ff_calendar_thisweek.json"
)

WEEKDAYS = [
    "월요일",
    "화요일",
    "수요일",
    "목요일",
    "금요일",
    "토요일",
    "일요일",
]

CURRENCIES = {
    "USD": ("US", "🇺🇸"),
    "GBP": ("UK", "🇬🇧"),
    "EUR": ("EU", "🇪🇺"),
    "JPY": ("JP", "🇯🇵"),
    "CAD": ("CA", "🇨🇦"),
    "AUD": ("AU", "🇦🇺"),
    "NZD": ("NZ", "🇳🇿"),
    "CHF": ("CH", "🇨🇭"),
    "CNY": ("CN", "🇨🇳"),
}

# 자주 나오는 경제지표를 한글로 표시하기 위한 사전
TITLE_TRANSLATIONS = {
    "GDP m/m": "GDP (MoM)",
    "GDP q/q": "GDP (QoQ)",
    "GDP y/y": "GDP (YoY)",
    "Retail Sales m/m": "소매판매 (MoM)",
    "Core Retail Sales m/m": "근원 소매판매 (MoM)",
    "Unemployment Claims": "신규 실업수당청구건수",
    "Unemployment Rate": "실업률",
    "Non-Farm Employment Change": "비농업 고용지수",
    "ADP Non-Farm Employment Change": "ADP 비농업 고용지수",
    "CPI m/m": "소비자물가지수 (MoM)",
    "CPI y/y": "소비자물가지수 (YoY)",
    "Core CPI m/m": "근원 소비자물가지수 (MoM)",
    "Core CPI y/y": "근원 소비자물가지수 (YoY)",
    "PPI m/m": "생산자물가지수 (MoM)",
    "Core PPI m/m": "근원 생산자물가지수 (MoM)",
    "Federal Funds Rate": "미국 기준금리 결정",
    "Official Bank Rate": "영국 기준금리 결정",
    "Main Refinancing Rate": "유럽 기준금리 결정",
    "BOC Overnight Rate": "캐나다 기준금리 결정",
    "Overnight Rate": "캐나다 기준금리 결정",
    "Cash Rate": "호주 기준금리 결정",
    "Philly Fed Manufacturing Index": "필라델피아 연은 제조업활동지수",
    "ISM Manufacturing PMI": "ISM 제조업 구매관리자지수",
    "ISM Services PMI": "ISM 서비스업 구매관리자지수",
    "Flash Manufacturing PMI": "제조업 구매관리자지수 잠정치",
    "Flash Services PMI": "서비스업 구매관리자지수 잠정치",
    "Consumer Confidence": "소비자신뢰지수",
    "Trade Balance": "무역수지",
    "Industrial Production m/m": "산업생산 (MoM)",
    "Manufacturing Production m/m": "제조업 생산 (MoM)",
    "Crude Oil Inventories": "원유재고",
}


def clean_text(value):
    if value is None:
        return "-"

    text = str(value).replace("\xa0", " ").strip()

    if not text:
        return "-"

    return text


def translate_title(title):
    title = clean_text(title)

    if title in TITLE_TRANSLATIONS:
        return TITLE_TRANSLATIONS[title]

    return title


def parse_event_time(value):
    if not value:
        raise ValueError("이벤트 시간이 없습니다.")

    event_time = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    return event_time.astimezone(KST)


def download_calendar():
    request = urllib.request.Request(
        CALENDAR_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 EconomicCalendarBot/1.0",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=45,
    ) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    if not isinstance(result, list):
        raise RuntimeError(
            "경제 캘린더 응답 형식이 올바르지 않습니다."
        )

    return result


def fetch_events_once(target_date):
    raw_events = download_calendar()
    events = []

    for item in raw_events:
        if not isinstance(item, dict):
            continue

        # 중요도 High만 표시
        impact = clean_text(
            item.get("impact")
        ).lower()

        if impact != "high":
            continue

        currency = clean_text(
            item.get("country")
        ).upper()

        if currency not in CURRENCIES:
            continue

        try:
            event_time = parse_event_time(
                item.get("date")
            )
        except Exception:
            continue

        # 한국시간 기준 오늘 이벤트만 선택
        if event_time.date() != target_date:
            continue

        country_code, flag = CURRENCIES[currency]

        actual = clean_text(
            item.get("actual")
        )
        forecast = clean_text(
            item.get("forecast")
        )
        previous = clean_text(
            item.get("previous")
        )

        events.append(
            {
                "sort_time": event_time,
                "time": event_time.strftime("%H:%M"),
                "country": country_code,
                "currency": currency,
                "flag": flag,
                "title": translate_title(
                    item.get("title")
                ),
                "actual": actual,
                "forecast": forecast,
                "previous": previous,
            }
        )

    events.sort(
        key=lambda event: event["sort_time"]
    )

    return events


def fetch_events_with_retry(target_date):
    errors = []

    for attempt in range(1, 4):
        try:
            return fetch_events_once(target_date)
        except Exception as exc:
            errors.append(
                f"{attempt}차: {exc}"
            )

            if attempt < 3:
                time.sleep(attempt * 20)

    raise RuntimeError("\n".join(errors))


def make_messages(target_date, events):
    weekday = WEEKDAYS[
        target_date.weekday()
    ]

    header = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📅 {target_date.year}년 "
        f"{target_date.month}월 "
        f"{target_date.day}일 {weekday}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    if not events:
        message = (
            header
            + "\n\n"
            + "오늘 예정된 <b>중요도 높음(★★★)</b> "
            + "경제 이벤트가 없습니다.\n\n"
            + "<i>기준: 주요 9개 통화권·High 이벤트</i>"
        )

        return [message]

    blocks = []

    for event in events:
        event_time = html.escape(
            event["time"]
        )
        country = html.escape(
            event["country"]
        )
        title = html.escape(
            event["title"]
        )
        actual = html.escape(
            event["actual"]
        )
        forecast = html.escape(
            event["forecast"]
        )
        previous = html.escape(
            event["previous"]
        )

        block = (
            f"<b>{event_time}　"
            f"{country} {event['flag']}</b>\n"
            f"★★★　│　<b>{title}</b>\n"
            f"실제: <b>{actual}</b>　"
            f"예측: {forecast}　"
            f"이전: {previous}"
        )

        blocks.append(block)

    messages = []
    current = header

    for block in blocks:
        candidate = (
            current
            + "\n\n"
            + block
        )

        # 텔레그램 메시지 길이 제한 대비
        if len(candidate) > 3700:
            current += (
                "\n\n"
                "<i>기준: 주요 9개 통화권·"
                "High 이벤트</i>"
            )
            messages.append(current)

            current = (
                f"<b>📅 {target_date.year}년 "
                f"{target_date.month}월 "
                f"{target_date.day}일 "
                f"일정 계속</b>\n\n"
                f"{block}"
            )
        else:
            current = candidate

    current += (
        "\n\n"
        "<i>기준: 주요 9개 통화권·"
        "High 이벤트</i>"
    )
    messages.append(current)

    return messages


def telegram_send(message):
    bot_token = os.environ.get(
        "TELEGRAM_BOT_TOKEN",
        "",
    ).strip()

    chat_id = os.environ.get(
        "TELEGRAM_CHAT_ID",
        "",
    ).strip()

    if not bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN이 없습니다."
        )

    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID가 없습니다."
        )

    url = (
        f"https://api.telegram.org/"
        f"bot{bot_token}/sendMessage"
    )

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

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    if not result.get("ok"):
        raise RuntimeError(
            f"텔레그램 전송 실패: {result}"
        )


def wait_until_7():
    should_wait = (
        os.environ.get(
            "WAIT_UNTIL_7",
            "false",
        ).strip().lower()
        == "true"
    )

    # 수동 테스트는 기다리지 않음
    if not should_wait:
        return

    now = datetime.now(KST)

    target = datetime.combine(
        now.date(),
        dt_time(7, 0),
        tzinfo=KST,
    )

    if now < target:
        seconds = (
            target - now
        ).total_seconds()

        print(
            f"오전 7시까지 "
            f"{int(seconds)}초 기다립니다."
        )

        time.sleep(seconds)


def main():
    wait_until_7()

    target_date = datetime.now(
        KST
    ).date()

    try:
        events = fetch_events_with_retry(
            target_date
        )

        print(
            f"오늘 High 이벤트 수: "
            f"{len(events)}"
        )

        messages = make_messages(
            target_date,
            events,
        )

        for message in messages:
            telegram_send(message)
            time.sleep(1)

        print(
            "텔레그램 경제 캘린더 전송 완료"
        )

    except Exception as exc:
        print(
            f"경제 캘린더 실행 실패: {exc}"
        )

        safe_error = html.escape(
            str(exc)
        )[:2500]

        try:
            telegram_send(
                "⚠️ <b>경제 캘린더 실행 실패</b>\n\n"
                f"{safe_error}\n\n"
                "GitHub Actions 실행 기록을 "
                "확인해주세요."
            )
        except Exception as telegram_error:
            print(
                "오류 알림 전송도 실패: "
                f"{telegram_error}"
            )

        raise


if __name__ == "__main__":
    main()
