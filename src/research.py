from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

from .schemas import ApiUsage, ResearchBundle, ResearchResult


ROOT = Path(__file__).resolve().parents[1]

# Standard-processing reference prices as of 2026-10-06.
# These are estimates only; the OpenAI billing dashboard remains authoritative.
MODEL_PRICING_PER_MTOK = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
    "gpt-6.1-sol": {"input": 2.00, "cached_input": 0.10, "output": 10.00},
    "gpt-6-astra": {"input": 10.00, "cached_input": 1.00, "output": 50.00},
}
WEB_SEARCH_USD_PER_CALL = 0.01


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _research_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "research_date": {"type": "string"},
            "market": {"type": "string", "enum": ["US", "KOREA"]},
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event_key": {"type": "string"},
                        "title": {"type": "string"},
                        "market": {"type": "string", "enum": ["US", "KOREA", "CROSS-MARKET"]},
                        "category": {
                            "type": "string",
                            "enum": [
                                "Macro", "Rates", "FX", "Semiconductor", "AI",
                                "Corporate", "Earnings", "Policy", "Flows",
                                "Commodities", "Other"
                            ],
                        },
                        "event_status": {
                            "type": "string",
                            "enum": ["NEW", "FOLLOW-UP", "REPEAT", "NOISE"],
                        },
                        "summary": {"type": "string"},
                        "why_important": {"type": "string"},
                        "facts": {"type": "array", "items": {"type": "string"}},
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "url": {"type": "string"},
                                    "source_type": {
                                        "type": "string",
                                        "enum": ["PRIMARY", "TRUSTED_REPORTING", "OTHER"],
                                    },
                                },
                                "required": ["title", "url", "source_type"],
                                "additionalProperties": False,
                            },
                        },
                        "portfolio_links": {"type": "array", "items": {"type": "string"}},
                        "portfolio_relevance": {
                            "type": "string",
                            "enum": ["HIGH", "MEDIUM", "LOW", "NONE"],
                        },
                        "next_check": {"type": "string"},
                    },
                    "required": [
                        "event_key", "title", "market", "category", "event_status",
                        "summary", "why_important", "facts", "sources",
                        "portfolio_links", "portfolio_relevance", "next_check"
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["research_date", "market", "events"],
        "additionalProperties": False,
    }


def _usage_value(obj: object, name: str, default: int = 0) -> int:
    value = getattr(obj, name, default)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _build_usage(response: object, market: str, model: str) -> ApiUsage:
    usage = getattr(response, "usage", None)
    input_tokens = _usage_value(usage, "input_tokens") if usage else 0
    output_tokens = _usage_value(usage, "output_tokens") if usage else 0
    total_tokens = _usage_value(usage, "total_tokens") if usage else input_tokens + output_tokens

    cached_input_tokens = 0
    if usage:
        details = getattr(usage, "input_tokens_details", None)
        if details is not None:
            cached_input_tokens = _usage_value(details, "cached_tokens")

    web_search_calls = 0
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "web_search_call":
            web_search_calls += 1

    model_cost = None
    pricing = MODEL_PRICING_PER_MTOK.get(model)
    if pricing:
        uncached_input = max(input_tokens - cached_input_tokens, 0)
        model_cost = (
            uncached_input * pricing["input"] / 1_000_000
            + cached_input_tokens * pricing["cached_input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )

    search_cost = web_search_calls * WEB_SEARCH_USD_PER_CALL
    total_cost = (model_cost + search_cost) if model_cost is not None else None

    return ApiUsage(
        market=market,
        model=model,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        web_search_calls=web_search_calls,
        estimated_model_cost_usd=round(model_cost, 6) if model_cost is not None else None,
        estimated_web_search_cost_usd=round(search_cost, 6),
        estimated_total_cost_usd=round(total_cost, 6) if total_cost is not None else None,
        pricing_note=(
            "Estimate using 2026-10-06 Standard API list prices; web search assumed $0.01/call. "
            "Actual billing may differ by service tier, region, caching, or future price changes."
        ),
    )


def run_research(market: str, target_date: str) -> ResearchResult:
    if market not in {"US", "KOREA"}:
        raise ValueError("market must be US or KOREA")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    client = OpenAI(api_key=api_key)

    prompt_file = "research_us.md" if market == "US" else "research_korea.md"
    instructions = _load_prompt(prompt_file)
    user_input = (
        f"Research target date: {target_date}. "
        f"Return only market-moving events relevant to the {market} research scope. "
        "Use live web search. Prefer primary sources, and keep the list selective."
    )

    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        tools=[{
            "type": "web_search",
            "external_web_access": True,
            "search_context_size": "low",
        }],
        tool_choice="required",
        input=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_input},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": f"{market.lower()}_market_research",
                "strict": True,
                "schema": _research_schema(),
            }
        },
        include=["web_search_call.action.sources"],
    )

    data = json.loads(response.output_text)
    bundle = ResearchBundle.model_validate(data)
    usage = _build_usage(response, market, model)
    return ResearchResult(bundle=bundle, usage=usage)
