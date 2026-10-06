from __future__ import annotations

from typing import Any

from .schemas import EventScore, MorningBrief, ResearchEvent


def build_learning_signal(
    *,
    event_scores: list[EventScore],
    selected_events: list[ResearchEvent],
    brief: MorningBrief,
) -> dict[str, Any]:
    """Return a conservative, deterministic learning signal.

    This is intentionally not a replacement for Daily Market Filter. It only
    decides whether the day is worth a manual filter review.
    """
    selected_keys = {e.event_key for e in selected_events}
    selected_scores = [s for s in event_scores if s.event_key in selected_keys]

    reasons: list[str] = []
    strength = "NONE"

    # 1) A meaningful cross-market divergence plus portfolio relevance is
    # especially useful for the user's learning objective.
    portfolio_relevant = any(
        item.relevance in {"HIGH", "MEDIUM"} for item in brief.portfolio
    )
    if (
        brief.cross_market.transmission in {"NO", "PARTIAL", "UNCLEAR"}
        and portfolio_relevant
        and brief.cross_market.confidence in {"HIGH", "MEDIUM"}
    ):
        reasons.append(
            f"US→Korea 전달이 {brief.cross_market.transmission}이고 보유자산 연결이 있어 추가 검토 가치가 있음"
        )
        strength = "HIGH"

    # 2) High-scoring events that combine portfolio relevance and learning value.
    strong_events = [
        score for score in selected_scores
        if score.total_score >= 10
        and score.portfolio_relevance_score >= 2
        and score.learning_value >= 2
    ]
    if strong_events:
        top = max(strong_events, key=lambda x: x.total_score)
        reasons.append(
            f"보유자산 연관성과 학습가치가 함께 높은 사건이 있음: {top.title} (score {top.total_score}/12)"
        )
        if strength == "NONE":
            strength = "MEDIUM"

    # 3) Very strong evidence/impact event even if portfolio link is indirect.
    exceptional = [
        score for score in selected_scores
        if score.total_score >= 11 and score.evidence_strength >= 1
    ]
    if exceptional:
        top = max(exceptional, key=lambda x: x.total_score)
        marker = f"시장·거시 학습가치가 높은 핵심 사건: {top.title} (score {top.total_score}/12)"
        if marker not in reasons:
            reasons.append(marker)
        if strength == "NONE":
            strength = "MEDIUM"

    signal = bool(reasons)
    suggested_question = brief.questions[0] if signal and brief.questions else None

    return {
        "signal": signal,
        "strength": strength,
        "reasons": reasons[:3],
        "suggested_question": suggested_question,
        "action": (
            "Daily Market Filter 실행 권장"
            if signal
            else "오늘은 이메일 확인으로 충분; Daily Market Filter 생략 권장"
        ),
        "rule_version": "learning-signal-v1",
    }
