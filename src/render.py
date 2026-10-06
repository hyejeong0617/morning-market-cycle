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
        f"> US market: {us_market_date or 'N/A'} · Korea market: {korea_market_date or 'N/A'}",
        "",
        "## 오늘 시장 한 문장",
        brief.market_one_liner,
        "",
        "## 🇺🇸 Overnight US",
        brief.us_one_liner,
        "",
        "## 🇰🇷 Today's Korea",
        brief.korea_one_liner,
        "",
        "## 🔗 US → Korea",
        f"**Transmission: {brief.cross_market.transmission} ({brief.cross_market.confidence})**",
        "",
        brief.cross_market.key_difference,
        "",
        f"- US signal: {brief.cross_market.us_signal}",
        f"- Expected Korea response: {brief.cross_market.expected_korea_response}",
        f"- Observed Korea response: {brief.cross_market.observed_korea_response}",
    ]

    if brief.cross_market.korea_specific_factors:
        lines += ["", "### Korea-specific factors"]
        lines += [f"- {item}" for item in brief.cross_market.korea_specific_factors]

    lines += ["", "## 💼 My Portfolio"]
    for item in brief.portfolio:
        lines.append(f"- **{item.asset} — {item.relevance}**: {item.reason}")

    lines += ["", "## 오늘의 관찰 질문"]
    for question in brief.questions[:2]:
        lines.append(f"- {question}")

    if estimated_api_cost_usd is not None:
        lines += ["", "---", f"Estimated OpenAI API cost: **${estimated_api_cost_usd:.6f}**"]

    return "\n".join(lines).strip() + "\n"
