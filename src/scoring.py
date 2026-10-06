from __future__ import annotations

from collections import OrderedDict

from .schemas import EventScore, ResearchEvent


PORTFOLIO_SCORE = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}

CATEGORY_MARKET_IMPACT = {
    "Macro": 3,
    "Rates": 3,
    "FX": 3,
    "Semiconductor": 3,
    "AI": 2,
    "Earnings": 2,
    "Policy": 3,
    "Flows": 3,
    "Commodities": 2,
    "Corporate": 1,
    "Other": 1,
}

CATEGORY_MACRO = {
    "Macro": 2,
    "Rates": 2,
    "FX": 2,
    "Policy": 2,
    "Flows": 1,
    "Semiconductor": 1,
    "AI": 1,
    "Earnings": 1,
    "Commodities": 1,
    "Corporate": 0,
    "Other": 0,
}

LEARNING_CATEGORIES = {"Macro", "Rates", "FX", "Semiconductor", "AI", "Flows", "Policy"}


def evidence_strength(event: ResearchEvent) -> int:
    source_types = {s.source_type for s in event.sources}
    if "PRIMARY" in source_types:
        return 2
    if "TRUSTED_REPORTING" in source_types:
        return 1
    return 0


def learning_value(event: ResearchEvent) -> int:
    score = 0
    if event.category in LEARNING_CATEGORIES:
        score += 1
    if event.portfolio_relevance in {"HIGH", "MEDIUM"} or event.market == "CROSS-MARKET":
        score += 1
    return min(score, 2)


def score_event(event: ResearchEvent) -> EventScore:
    market_impact = CATEGORY_MARKET_IMPACT.get(event.category, 1)
    if event.event_status == "NOISE":
        market_impact = 0
    elif event.event_status == "REPEAT":
        market_impact = max(market_impact - 1, 0)

    portfolio = PORTFOLIO_SCORE[event.portfolio_relevance]
    macro = CATEGORY_MACRO.get(event.category, 0)
    evidence = evidence_strength(event)
    learning = learning_value(event)
    total = market_impact + portfolio + macro + evidence + learning

    include = total >= 9
    reason = (
        f"impact={market_impact}, portfolio={portfolio}, macro={macro}, "
        f"evidence={evidence}, learning={learning}"
    )

    return EventScore(
        event_key=event.event_key,
        market=event.market,
        title=event.title,
        market_impact=market_impact,
        portfolio_relevance_score=portfolio,
        macro_importance=macro,
        evidence_strength=evidence,
        learning_value=learning,
        total_score=total,
        include_in_brief=include,
        reason=reason,
    )


def deduplicate_events(events: list[ResearchEvent]) -> list[ResearchEvent]:
    # MVP2 deterministic deduplication: exact event_key wins. Keep the stronger-evidence version.
    by_key: OrderedDict[str, ResearchEvent] = OrderedDict()
    for event in events:
        existing = by_key.get(event.event_key)
        if existing is None or evidence_strength(event) > evidence_strength(existing):
            by_key[event.event_key] = event
    return list(by_key.values())


def score_and_select(events: list[ResearchEvent], max_events: int = 5) -> tuple[list[EventScore], list[ResearchEvent]]:
    unique = deduplicate_events(events)
    scored = [(event, score_event(event)) for event in unique]
    scored.sort(key=lambda pair: pair[1].total_score, reverse=True)

    selected = [event for event, score in scored if score.include_in_brief][:max_events]
    # Ensure the brief is not empty in quiet markets; keep up to 3 highest-scoring events.
    if not selected:
        selected = [event for event, _ in scored[:3]]

    return [score for _, score in scored], selected
