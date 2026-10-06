from __future__ import annotations

import json
import os
from typing import Iterable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .schemas import EventScore, MorningBrief, ResearchEvent


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
DEFAULT_DATA_SOURCE_ID = "de2d05dd-6694-4cb0-b7d0-c65db73cb01a"


def _request(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(
        f"{NOTION_API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Notion API {exc.code}: {detail}") from exc


def _rich_text(value: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}


def _title(value: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def _select(value: str) -> dict:
    return {"select": {"name": value}}


def _multi_select(values: Iterable[str]) -> dict:
    return {"multi_select": [{"name": value} for value in values]}


def _date(value: str | None) -> dict:
    return {"date": {"start": value}} if value else {"date": None}


def _sources_text(event: ResearchEvent) -> str:
    return "\n".join(f"{s.title} — {s.url}" for s in event.sources)[:2000]


def _primary_source(event: ResearchEvent) -> str | None:
    primary = next((s.url for s in event.sources if s.source_type == "PRIMARY"), None)
    return primary or (event.sources[0].url if event.sources else None)


def _already_exists(token: str, data_source_id: str, event_key: str, brief_date: str) -> bool:
    payload = {
        "filter": {
            "and": [
                {"property": "Event Key", "rich_text": {"equals": event_key}},
                {"property": "Brief Date", "date": {"equals": brief_date}},
            ]
        },
        "page_size": 1,
    }
    result = _request("POST", f"/data_sources/{data_source_id}/query", token, payload)
    return bool(result.get("results"))


def _create_page(token: str, data_source_id: str, properties: dict) -> None:
    _request(
        "POST",
        "/pages",
        token,
        {"parent": {"type": "data_source_id", "data_source_id": data_source_id}, "properties": properties},
    )


def _local_event_properties(
    event: ResearchEvent,
    score: EventScore,
    brief_date: str,
    us_market_date: str | None,
    korea_market_date: str | None,
) -> dict:
    return {
        "Event": _title(event.title),
        "Brief Date": _date(brief_date),
        "US Market Date": _date(us_market_date),
        "Korea Market Date": _date(korea_market_date),
        "Market": _select(event.market),
        "Event Status": _select(event.event_status),
        "Category": _select(event.category),
        "Importance": {"number": score.total_score},
        "Portfolio Relevance": _select(event.portfolio_relevance),
        "Portfolio Links": _multi_select(event.portfolio_links),
        "Transmission": _select("N/A"),
        "Filter": _select("UNREVIEWED"),
        "Evidence Strength": {"number": score.evidence_strength},
        "Summary": _rich_text(event.summary),
        "Why Important": _rich_text(event.why_important),
        "Next Check": _rich_text(event.next_check),
        "Primary Source": {"url": _primary_source(event)},
        "Sources": _rich_text(_sources_text(event)),
        "Event Key": _rich_text(event.event_key),
    }


def _cross_market_properties(
    brief: MorningBrief,
    brief_date: str,
    us_market_date: str | None,
    korea_market_date: str | None,
) -> tuple[str, dict]:
    event_key = f"{brief_date}_us_korea_transmission"
    portfolio_links = list(dict.fromkeys(item.asset for item in brief.portfolio))
    relevance = "HIGH" if any(item.relevance == "HIGH" for item in brief.portfolio) else "MEDIUM"
    summary = brief.cross_market.key_difference
    why_important = (
        f"US signal: {brief.cross_market.us_signal} | "
        f"Observed Korea response: {brief.cross_market.observed_korea_response}"
    )
    next_check = " | ".join(brief.questions[:2])
    title = f"US→Korea transmission: {brief.cross_market.transmission}"

    properties = {
        "Event": _title(title),
        "Brief Date": _date(brief_date),
        "US Market Date": _date(us_market_date),
        "Korea Market Date": _date(korea_market_date),
        "Market": _select("CROSS-MARKET"),
        "Event Status": _select("NEW"),
        "Category": _select("Other"),
        "Importance": {"number": 10 if brief.cross_market.transmission != "UNCLEAR" else 7},
        "Portfolio Relevance": _select(relevance),
        "Portfolio Links": _multi_select(portfolio_links),
        "Transmission": _select(brief.cross_market.transmission),
        "Filter": _select("UNREVIEWED"),
        "Evidence Strength": {"number": 1 if brief.cross_market.confidence == "MEDIUM" else 2},
        "Summary": _rich_text(summary),
        "Why Important": _rich_text(why_important),
        "Next Check": _rich_text(next_check),
        "Primary Source": {"url": None},
        "Sources": _rich_text("Derived from the selected US and Korea events in this Morning Market Brief."),
        "Event Key": _rich_text(event_key),
    }
    return event_key, properties


def sync_market_inbox(
    *,
    brief_date: str,
    us_market_date: str | None,
    korea_market_date: str | None,
    selected_events: list[ResearchEvent],
    event_scores: list[EventScore],
    morning_brief: MorningBrief,
) -> dict:
    token = os.getenv("NOTION_TOKEN")
    data_source_id = os.getenv("NOTION_DATA_SOURCE_ID", DEFAULT_DATA_SOURCE_ID)
    if not token:
        return {"status": "SKIPPED", "reason": "NOTION_TOKEN is not set", "created": 0, "duplicates": 0}

    score_map = {score.event_key: score for score in event_scores}
    created = 0
    duplicates = 0

    for event in selected_events:
        score = score_map[event.event_key]
        if _already_exists(token, data_source_id, event.event_key, brief_date):
            duplicates += 1
            continue
        _create_page(
            token,
            data_source_id,
            _local_event_properties(event, score, brief_date, us_market_date, korea_market_date),
        )
        created += 1

    cross_key, cross_props = _cross_market_properties(
        morning_brief, brief_date, us_market_date, korea_market_date
    )
    if _already_exists(token, data_source_id, cross_key, brief_date):
        duplicates += 1
    else:
        _create_page(token, data_source_id, cross_props)
        created += 1

    return {
        "status": "OK",
        "created": created,
        "duplicates": duplicates,
        "data_source_id": data_source_id,
    }
