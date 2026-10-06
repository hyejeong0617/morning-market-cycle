from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage

from .schemas import MorningBrief


def _portfolio_lines(brief: MorningBrief) -> str:
    if not brief.portfolio:
        return "- No directly linked portfolio items today."
    return "\n".join(
        f"- {item.asset} [{item.relevance}]: {item.reason}"
        for item in brief.portfolio
    )


def _question_lines(brief: MorningBrief) -> str:
    if not brief.questions:
        return "- No follow-up question."
    return "\n".join(f"- {q}" for q in brief.questions[:2])


def _plain_text(
    *,
    brief_date: str,
    us_market_date: str | None,
    korea_market_date: str | None,
    brief: MorningBrief,
    estimated_api_cost_usd: float | None,
) -> str:
    cost = f"${estimated_api_cost_usd:.4f}" if estimated_api_cost_usd is not None else "n/a"
    return f"""Morning Market Brief — {brief_date}
US market: {us_market_date or 'n/a'} | Korea market: {korea_market_date or 'n/a'}

TODAY IN ONE LINE
{brief.market_one_liner}

🇺🇸 OVERNIGHT US
{brief.us_one_liner}

🇰🇷 TODAY KOREA
{brief.korea_one_liner}

🔗 US → KOREA
Transmission: {brief.cross_market.transmission} ({brief.cross_market.confidence})
US signal: {brief.cross_market.us_signal}
Expected Korea response: {brief.cross_market.expected_korea_response}
Observed Korea response: {brief.cross_market.observed_korea_response}
Key difference: {brief.cross_market.key_difference}

💼 MY PORTFOLIO
{_portfolio_lines(brief)}

🔎 TODAY'S QUESTIONS
{_question_lines(brief)}

Estimated OpenAI API cost for this run: {cost}
"""


def _html_body(
    *,
    brief_date: str,
    us_market_date: str | None,
    korea_market_date: str | None,
    brief: MorningBrief,
    estimated_api_cost_usd: float | None,
) -> str:
    esc = html.escape
    cost = f"${estimated_api_cost_usd:.4f}" if estimated_api_cost_usd is not None else "n/a"
    portfolio = "".join(
        f"<li><strong>{esc(item.asset)}</strong> [{esc(item.relevance)}]: {esc(item.reason)}</li>"
        for item in brief.portfolio
    ) or "<li>No directly linked portfolio items today.</li>"
    questions = "".join(
        f"<li>{esc(q)}</li>" for q in brief.questions[:2]
    ) or "<li>No follow-up question.</li>"
    factors = "".join(
        f"<li>{esc(x)}</li>" for x in brief.cross_market.korea_specific_factors
    )

    return f"""<!doctype html>
<html><body style="font-family:Arial,sans-serif;max-width:720px;margin:auto;line-height:1.55;color:#222">
<h2>Morning Market Brief — {esc(brief_date)}</h2>
<p style="color:#666">US market: {esc(us_market_date or 'n/a')} · Korea market: {esc(korea_market_date or 'n/a')}</p>
<h3>오늘 시장 한 문장</h3><p><strong>{esc(brief.market_one_liner)}</strong></p>
<h3>🇺🇸 Overnight US</h3><p>{esc(brief.us_one_liner)}</p>
<h3>🇰🇷 Today Korea</h3><p>{esc(brief.korea_one_liner)}</p>
<h3>🔗 US → Korea</h3>
<p><strong>Transmission: {esc(brief.cross_market.transmission)}</strong> · Confidence: {esc(brief.cross_market.confidence)}</p>
<p><strong>US signal:</strong> {esc(brief.cross_market.us_signal)}</p>
<p><strong>Expected:</strong> {esc(brief.cross_market.expected_korea_response)}</p>
<p><strong>Observed:</strong> {esc(brief.cross_market.observed_korea_response)}</p>
{f'<ul>{factors}</ul>' if factors else ''}
<p><strong>Key difference:</strong> {esc(brief.cross_market.key_difference)}</p>
<h3>💼 My Portfolio</h3><ul>{portfolio}</ul>
<h3>🔎 Today's Questions</h3><ul>{questions}</ul>
<hr><p style="font-size:12px;color:#777">Estimated OpenAI API cost for this run: {esc(cost)}</p>
</body></html>"""


def send_morning_brief_email(
    *,
    brief_date: str,
    us_market_date: str | None,
    korea_market_date: str | None,
    brief: MorningBrief,
    estimated_api_cost_usd: float | None,
) -> dict:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "465"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    recipient = os.getenv("EMAIL_TO", "").strip()
    sender = os.getenv("EMAIL_FROM", "").strip() or username

    missing = [name for name, value in {
        "SMTP_USERNAME": username,
        "SMTP_PASSWORD": password,
        "EMAIL_TO": recipient,
    }.items() if not value]
    if missing:
        return {
            "status": "SKIPPED",
            "reason": f"Missing email configuration: {', '.join(missing)}",
        }

    msg = EmailMessage()
    msg["Subject"] = f"Morning Market Brief | {brief_date} | {brief.cross_market.transmission}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(_plain_text(
        brief_date=brief_date,
        us_market_date=us_market_date,
        korea_market_date=korea_market_date,
        brief=brief,
        estimated_api_cost_usd=estimated_api_cost_usd,
    ))
    msg.add_alternative(_html_body(
        brief_date=brief_date,
        us_market_date=us_market_date,
        korea_market_date=korea_market_date,
        brief=brief,
        estimated_api_cost_usd=estimated_api_cost_usd,
    ), subtype="html")

    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(username, password)
        smtp.send_message(msg)

    return {
        "status": "SENT",
        "recipient": recipient,
        "subject": msg["Subject"],
    }
