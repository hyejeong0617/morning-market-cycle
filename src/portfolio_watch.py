from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schemas import MorningBrief, PortfolioWatch, PortfolioWatchItem


NOTION_API = "https://api.notion.com/v1"


def _plain_text(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    parts = prop.get("title") or prop.get("rich_text") or []
    return "".join(x.get("plain_text", "") for x in parts).strip()


def _number(prop: dict[str, Any] | None) -> float | None:
    if not prop:
        return None
    value = prop.get("number")
    return float(value) if value is not None else None


def _select(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    value = prop.get("select")
    return (value or {}).get("name", "")


def _relation_ids(prop: dict[str, Any] | None) -> list[str]:
    if not prop:
        return []
    return [x.get("id", "") for x in prop.get("relation", []) if x.get("id")]


def _query_data_source(token: str, data_source_id: str) -> list[dict[str, Any]]:
    url = f"{NOTION_API}/data_sources/{data_source_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": os.getenv("NOTION_API_VERSION", "2025-09-03"),
        "Content-Type": "application/json",
    }
    results: list[dict[str, Any]] = []
    payload: dict[str, Any] = {"page_size": 100}

    while True:
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
    return results


def _impact_for_group(asset_group: str, brief: MorningBrief) -> str:
    key = asset_group.lower().replace(" ", "")
    aliases: dict[str, tuple[str, ...]] = {
        "s&p500": ("s&p500", "sp500", "미국s&p500"),
        "nasdaq100": ("nasdaq", "나스닥"),
        "usdividendetf": ("미국배당다우존스", "배당다우존스"),
        "coveredcalletf": ("커버드콜", "coveredcall"),
        "tiger200": ("tiger200", "tiger 200", "코스피200"),
        "samsungelectronics": ("삼성전자", "samsung"),
        "cash": ("현금", "cash"),
    }
    terms = aliases.get(key, (asset_group.lower(),))

    for impact in brief.portfolio:
        name = impact.asset.lower()
        if key == "usdividendetf" and ("커버드콜" in name or "covered" in name):
            continue
        if any(term in name for term in terms):
            return impact.reason
    return ""


def _signal_reason(
    *, asset_group: str, signal: str, current: float | None, target: float | None,
    min_weight: float | None, max_weight: float | None, decision_status: str,
) -> str:
    parts: list[str] = []
    if current is not None and target is not None:
        parts.append(f"현재 {current:.1f}% / 목표 {target:.1f}%")
    if signal == "INCREASE BIAS":
        parts.append("전략상 목표 하단보다 낮아 향후 신규자금 배분 우선순위를 높게 유지")
    elif signal == "REDUCE BIAS":
        parts.append("전략상 목표 상단을 넘어 추가매수보다 비중 정상화가 우선")
    elif signal == "EXIT PLAN":
        parts.append("기존 Exit 계획 유지; 당일 뉴스만으로 전략을 되돌리지 않음")
    else:
        parts.append("현재 전략 허용 범위 안에서 유지")
    if decision_status:
        parts.append(f"Weekly status: {decision_status}")
    return ". ".join(parts) + "."


def build_private_portfolio_watch(brief: MorningBrief) -> PortfolioWatch | None:
    """Build a private daily strategic-bias summary from Notion.

    This object is for email rendering only. The caller must not persist it into the
    public Daily JSON or Markdown output.
    """
    token = os.getenv("NOTION_TOKEN", "").strip()
    strategy_id = os.getenv("NOTION_STRATEGY_DATA_SOURCE_ID", "").strip()
    holdings_id = os.getenv("NOTION_HOLDINGS_DATA_SOURCE_ID", "").strip()
    if not token or not strategy_id or not holdings_id:
        return None

    try:
        holdings_rows = _query_data_source(token, holdings_id)
        strategy_rows = _query_data_source(token, strategy_id)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    market_values: dict[str, float] = {}
    total_market_value = 0.0
    for row in holdings_rows:
        props = row.get("properties", {})
        value = _number(props.get("Market Value")) or 0.0
        row_id = row.get("id", "")
        if row_id:
            market_values[row_id] = value
        total_market_value += value

    if total_market_value <= 0:
        return None

    candidates: list[tuple[float, PortfolioWatchItem, bool]] = []
    review_flag = False

    for row in strategy_rows:
        props = row.get("properties", {})
        asset_group = _plain_text(props.get("Asset Group"))
        if not asset_group:
            continue
        role = _select(props.get("Role"))
        decision_status = _select(props.get("Decision Status"))
        target = _number(props.get("Target Weight %"))
        min_weight = _number(props.get("Min Weight %"))
        max_weight = _number(props.get("Max Weight %"))
        relation_ids = _relation_ids(props.get("Holdings"))
        current_value = sum(market_values.get(row_id, 0.0) for row_id in relation_ids)
        current_weight = current_value / total_market_value * 100.0
        market_note = _impact_for_group(asset_group, brief)

        if role == "Exit" or decision_status == "EXIT ON RECOVERY" or (target == 0 and current_weight > 0):
            signal = "EXIT PLAN"
            priority = 4.0
        elif max_weight is not None and current_weight > max_weight:
            signal = "REDUCE BIAS"
            priority = 3.0
        elif min_weight is not None and current_weight < min_weight:
            signal = "INCREASE BIAS"
            priority = 2.0
        else:
            signal = "HOLD"
            priority = 0.5

        if asset_group.lower() == "cash":
            priority -= 0.75
        if market_note:
            priority += 0.75
        if decision_status == "REVIEW" and market_note:
            review_flag = True

        if signal == "HOLD" and not market_note:
            continue

        item = PortfolioWatchItem(
            asset_group=asset_group,
            signal=signal,
            current_weight_pct=round(current_weight, 2),
            target_weight_pct=target,
            reason=_signal_reason(
                asset_group=asset_group,
                signal=signal,
                current=current_weight,
                target=target,
                min_weight=min_weight,
                max_weight=max_weight,
                decision_status=decision_status,
            ),
            market_note=market_note,
        )
        candidates.append((priority, item, bool(market_note)))

    candidates.sort(key=lambda x: (x[0], x[2]), reverse=True)
    signals = [item for _, item, _ in candidates[:3]]
    if not signals:
        return PortfolioWatch(signals=[])

    status = "WEEKLY REVIEW NEEDED" if review_flag else "STRATEGY UNCHANGED"
    return PortfolioWatch(status=status, signals=signals)
