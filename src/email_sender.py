from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage
from typing import Any

from .schemas import MorningBrief


def _event_value(event: Any, field: str, default: str = "") -> str:
    if isinstance(event, dict):
        value = event.get(field, default)
    else:
        value = getattr(event, field, default)
    return str(value) if value is not None else default


def _more_headline_events(all_events: list[Any], selected_event_keys: list[str], limit: int = 5) -> list[Any]:
    selected = set(selected_event_keys)
    return [e for e in all_events if _event_value(e, "event_key") not in selected][:limit]


def _portfolio_lines(brief: MorningBrief) -> str:
    if not brief.portfolio:
        return "- 오늘 직접 연결된 보유자산 없음"
    return "\n".join(f"- {x.asset} [{x.relevance}]: {x.reason}" for x in brief.portfolio)


def _question_lines(brief: MorningBrief) -> str:
    if not brief.questions:
        return "- 추가 관찰 질문 없음"
    return "\n".join(f"- {q}" for q in brief.questions[:2])


def _headline_lines(events: list[Any]) -> str:
    if not events:
        return "- 추가 헤드라인 없음"
    return "\n".join(
        f"- [{_event_value(e, 'market', 'OTHER')}] {_event_value(e, 'title', '제목 없음')}"
        for e in events
    )


def _weekend_text(brief: MorningBrief) -> str:
    if not brief.weekend_watch:
        return ""
    return "\n🗓️ WEEKEND WATCH\n" + "\n".join(f"- {x}" for x in brief.weekend_watch) + "\n"


def _learning_signal_text(learning_signal: dict[str, Any]) -> str:
    if not learning_signal.get("signal"):
        return "🧭 LEARNING SIGNAL\nNO SIGNAL\n오늘은 이메일 확인으로 충분; Daily Market Filter 생략 권장"
    reasons = "\n".join(f"- {x}" for x in learning_signal.get("reasons", []))
    question = learning_signal.get("suggested_question")
    question_line = f"\n추천 질문: {question}" if question else ""
    return (
        f"🧭 LEARNING SIGNAL\nSIGNAL [{learning_signal.get('strength', 'MEDIUM')}]\n"
        f"{reasons}{question_line}\nDaily Market Filter 실행 권장"
    )


def _plain_text(
    *, brief_date: str, us_market_date: str | None, korea_market_date: str | None,
    brief: MorningBrief, more_headlines: list[Any], learning_signal: dict[str, Any],
    estimated_api_cost_usd: float | None,
) -> str:
    cost = f"${estimated_api_cost_usd:.4f}" if estimated_api_cost_usd is not None else "n/a"
    return f"""Morning Market Brief — {brief_date}
미국시장 기준일: {us_market_date or 'n/a'} | 한국시장 기준일: {korea_market_date or 'n/a'}

{_learning_signal_text(learning_signal)}

오늘 시장 한 문장
{brief.market_one_liner}

🇺🇸 미국시장
{brief.us_one_liner}
{_weekend_text(brief)}
🇰🇷 한국시장
{brief.korea_one_liner}

🔗 US → KOREA
Transmission: {brief.cross_market.transmission} ({brief.cross_market.confidence})
미국 신호: {brief.cross_market.us_signal}
예상 한국 반응: {brief.cross_market.expected_korea_response}
실제 한국 반응: {brief.cross_market.observed_korea_response}
핵심 차이: {brief.cross_market.key_difference}

💼 내 포트폴리오
{_portfolio_lines(brief)}

📰 MORE HEADLINES
{_headline_lines(more_headlines)}

🔎 오늘의 관찰 질문
{_question_lines(brief)}

예상 OpenAI API 비용: {cost}
"""


def _html_body(
    *, brief_date: str, us_market_date: str | None, korea_market_date: str | None,
    brief: MorningBrief, more_headlines: list[Any], learning_signal: dict[str, Any],
    estimated_api_cost_usd: float | None,
) -> str:
    esc = html.escape
    cost = f"${estimated_api_cost_usd:.4f}" if estimated_api_cost_usd is not None else "n/a"
    portfolio = "".join(f"<li><strong>{esc(x.asset)}</strong> [{esc(x.relevance)}]: {esc(x.reason)}</li>" for x in brief.portfolio) or "<li>오늘 직접 연결된 보유자산 없음</li>"
    questions = "".join(f"<li>{esc(q)}</li>" for q in brief.questions[:2]) or "<li>추가 관찰 질문 없음</li>"
    factors = "".join(f"<li>{esc(x)}</li>" for x in brief.cross_market.korea_specific_factors)
    headlines = "".join(
        f"<li><strong>{esc(_event_value(e, 'market', 'OTHER'))}</strong> · {esc(_event_value(e, 'title', '제목 없음'))}</li>"
        for e in more_headlines
    ) or "<li>추가 헤드라인 없음</li>"
    weekend = ""
    if brief.weekend_watch:
        items = "".join(f"<li>{esc(x)}</li>" for x in brief.weekend_watch)
        weekend = f"<h3>🗓️ Weekend Watch</h3><ul>{items}</ul>"

    if learning_signal.get("signal"):
        reasons = "".join(f"<li>{esc(x)}</li>" for x in learning_signal.get("reasons", []))
        question = learning_signal.get("suggested_question")
        question_html = f"<p><strong>추천 질문:</strong> {esc(question)}</p>" if question else ""
        signal_html = (
            f"<div style='padding:14px;border:1px solid #999;border-radius:8px'>"
            f"<h3>🧭 Learning Signal — SIGNAL [{esc(learning_signal.get('strength', 'MEDIUM'))}]</h3>"
            f"<ul>{reasons}</ul>{question_html}<p><strong>Daily Market Filter 실행 권장</strong></p></div>"
        )
    else:
        signal_html = (
            "<div style='padding:14px;border:1px solid #ccc;border-radius:8px'>"
            "<h3>🧭 Learning Signal — NO SIGNAL</h3>"
            "<p>오늘은 이메일 확인으로 충분; Daily Market Filter 생략 권장</p></div>"
        )

    return f"""<!doctype html>
<html><body style="font-family:Arial,sans-serif;max-width:720px;margin:auto;line-height:1.55;color:#222">
<h2>Morning Market Brief — {esc(brief_date)}</h2>
<p style="color:#666">미국시장 기준일: {esc(us_market_date or 'n/a')} · 한국시장 기준일: {esc(korea_market_date or 'n/a')}</p>
{signal_html}
<h3>오늘 시장 한 문장</h3><p><strong>{esc(brief.market_one_liner)}</strong></p>
<h3>🇺🇸 미국시장</h3><p>{esc(brief.us_one_liner)}</p>
{weekend}
<h3>🇰🇷 한국시장</h3><p>{esc(brief.korea_one_liner)}</p>
<h3>🔗 US → Korea</h3>
<p><strong>Transmission: {esc(brief.cross_market.transmission)}</strong> · Confidence: {esc(brief.cross_market.confidence)}</p>
<p><strong>미국 신호:</strong> {esc(brief.cross_market.us_signal)}</p>
<p><strong>예상 한국 반응:</strong> {esc(brief.cross_market.expected_korea_response)}</p>
<p><strong>실제 한국 반응:</strong> {esc(brief.cross_market.observed_korea_response)}</p>
{f'<ul>{factors}</ul>' if factors else ''}
<p><strong>핵심 차이:</strong> {esc(brief.cross_market.key_difference)}</p>
<h3>💼 내 포트폴리오</h3><ul>{portfolio}</ul>
<h3>📰 More Headlines</h3><ul>{headlines}</ul>
<h3>🔎 오늘의 관찰 질문</h3><ul>{questions}</ul>
<hr><p style="font-size:12px;color:#777">예상 OpenAI API 비용: {esc(cost)}</p>
</body></html>"""


def _send_via_smtp(*, host: str, port: int, username: str, password: str, msg: EmailMessage) -> None:
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(msg)
        return
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(msg)


def send_morning_brief_email(
    *, brief_date: str, us_market_date: str | None, korea_market_date: str | None,
    brief: MorningBrief, all_events: list[Any], selected_event_keys: list[str],
    learning_signal: dict[str, Any], estimated_api_cost_usd: float | None,
) -> dict:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
    recipient = os.getenv("EMAIL_TO", "").strip()
    sender = os.getenv("EMAIL_FROM", "").strip() or username

    missing = [name for name, value in {"SMTP_USERNAME": username, "SMTP_PASSWORD": password, "EMAIL_TO": recipient}.items() if not value]
    if missing:
        return {"status": "SKIPPED", "reason": f"Missing email configuration: {', '.join(missing)}"}

    more_headlines = _more_headline_events(all_events, selected_event_keys, limit=5)
    signal_label = "SIGNAL" if learning_signal.get("signal") else "NO SIGNAL"
    msg = EmailMessage()
    msg["Subject"] = f"Morning Market Brief | {brief_date} | {signal_label}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(_plain_text(
        brief_date=brief_date, us_market_date=us_market_date, korea_market_date=korea_market_date,
        brief=brief, more_headlines=more_headlines, learning_signal=learning_signal,
        estimated_api_cost_usd=estimated_api_cost_usd,
    ))
    msg.add_alternative(_html_body(
        brief_date=brief_date, us_market_date=us_market_date, korea_market_date=korea_market_date,
        brief=brief, more_headlines=more_headlines, learning_signal=learning_signal,
        estimated_api_cost_usd=estimated_api_cost_usd,
    ), subtype="html")

    _send_via_smtp(host=host, port=port, username=username, password=password, msg=msg)
    return {
        "status": "SENT", "recipient": recipient, "subject": msg["Subject"],
        "smtp_host": host, "smtp_port": port, "more_headlines_count": len(more_headlines),
        "weekend_watch_count": len(brief.weekend_watch), "learning_signal": signal_label,
    }
