from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

from .schemas import ResearchBundle


ROOT = Path(__file__).resolve().parents[1]


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _research_schema() -> dict:
    # Keep this schema intentionally compact for MVP 1.
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


def run_research(market: str, target_date: str) -> ResearchBundle:
    if market not in {"US", "KOREA"}:
        raise ValueError("market must be US or KOREA")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
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
        tools=[{"type": "web_search", "external_web_access": True}],
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
    return ResearchBundle.model_validate(data)
