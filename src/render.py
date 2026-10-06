from __future__ import annotations

from .schemas import MorningBrief


def render_morning_brief_markdown(
    brief_date: str,
    us_market_date: str | None,
    korea_market_date: str | None,
    brief: MorningBrief,
    estimated_api_cost_usd: float | None = None,
) -> str:
    lines: list[str] = [
        f"# Morning Market Brief — {brief_date}",
        "",
        f"> 미국시장 기준일: {us_market_date or 'N/A'} · 한국시장 기준일: {korea_market_date or 'N/A'}",
        "",
        "## 오늘 시장 한 문장",
        brief.market_one_liner,
        "",
        "## 🇺🇸 미국시장",
        brief.us_one_liner,
    ]

    if brief.weekend_watch:
        lines += ["", "## 🗓️ Weekend Watch"]
        lines += [f"- {item}" for item in brief.weekend_watch]

    lines += [
        "",
        "## 🇰🇷 한국시장",
        brief.korea_one_liner,
        "",
        "## 🔗 US → Korea",
        f"**Transmission: {brief.cross_market.transmission} ({brief.cross_market.confidence})**",
        "",
        brief.cross_market.key_difference,
        "",
        f"- 미국 신호: {brief.cross_market.us_signal}",
        f"- 예상 한국 반응: {brief.cross_market.expected_korea_response}",
        f"- 실제 한국 반응: {brief.cross_market.observed_korea_response}",
    ]

    if brief.cross_market.korea_specific_factors:
        lines += ["", "### 한국 고유 변수"]
        lines += [f"- {item}" for item in brief.cross_market.korea_specific_factors]

    lines += ["", "## 💼 내 포트폴리오"]
    for item in brief.portfolio:
        lines.append(f"- **{item.asset} — {item.relevance}**: {item.reason}")

    lines += ["", "## 오늘의 관찰 질문"]
    for question in brief.questions[:2]:
        lines.append(f"- {question}")

    if estimated_api_cost_usd is not None:
        lines += ["", "---", f"예상 OpenAI API 비용: **${estimated_api_cost_usd:.6f}**"]

    return "\n".join(lines).strip() + "\n"
