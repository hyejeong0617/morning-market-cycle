from __future__ import annotations

from datetime import date, timedelta


def _previous_weekday(day: date) -> date:
    day = day - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def detect_session_status(brief_date: str, us_market_date: str | None, korea_market_date: str | None) -> dict:
    """Infer whether each market produced the session expected for this weekday.

    This is intentionally data-driven and lightweight: it compares the latest
    completed regular-session dates from market data with the dates expected for
    a Germany-morning brief. It does not attempt to maintain a holiday calendar.
    """
    today = date.fromisoformat(brief_date)
    expected_us = _previous_weekday(today).isoformat()
    expected_korea = today.isoformat() if today.weekday() < 5 else _previous_weekday(today + timedelta(days=1)).isoformat()

    def classify(actual: str | None, expected: str) -> str:
        if actual is None:
            return "UNKNOWN"
        if actual == expected:
            return "NEW_SESSION"
        if actual < expected:
            return "NO_NEW_SESSION"
        return "UNKNOWN"

    us_status = classify(us_market_date, expected_us)
    korea_status = classify(korea_market_date, expected_korea)
    return {
        "expected_us_market_date": expected_us,
        "expected_korea_market_date": expected_korea,
        "us_status": us_status,
        "korea_status": korea_status,
        "both_closed": us_status == "NO_NEW_SESSION" and korea_status == "NO_NEW_SESSION",
        "is_monday": today.weekday() == 0,
    }
