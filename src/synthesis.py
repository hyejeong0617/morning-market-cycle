from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

from .research import build_usage
from .schemas import ApiUsage, MarketSnapshot, MorningBrief, ResearchEvent

ROOT = Path(__file__).resolve().parents[1]


def _brief_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "market_one_liner": {"type": "string"},
            "us_one_liner": {"type": "string"},
            "korea_one_liner": {"type": "string"},
            "cross_market": {
                "type": "object",
                "properties": {
                    "us_signal": {"type": "string"},
                    "expected_korea_response": {"type": "string"},
                    "observed_korea_response": {"type": "string"},
                    "korea_specific_factors": {"type": "array", "items": {"type": "string"}},
                    "transmission": {"type": "string", "enum": ["YES", "PARTIAL", "NO", "UNCLEAR", "N/A"]},
                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "key_difference": {"type": "string"}
                },
                "required": ["us_signal", "expected_korea_response", "observed_korea_response", "korea_specific_factors", "transmission", "confidence", "key_difference"],
                "additionalProperties": False
            },
            "portfolio": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset": {"type": "string"},
                        "relevance": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "reason": {"type": "string"}
                    },
                    "required": ["asset", "relevance", "reason"],
                    "additionalProperties": False
                }
            },
            "questions": {"type": "array", "items": {"type": "string"}, "maxItems": 2}
        },
        "required": ["market_one_liner", "us_one_liner", "korea_one_liner", "cross_market", "portfolio", "questions"],
        "additionalProperties": False
    }


def run_synthesis(brief_date: str, us_market_date: str | None, korea_market_date: str | None, snapshot: MarketSnapshot, selected_events: list[ResearchEvent]) -> tuple[MorningBrief, ApiUsage]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    client = OpenAI(api_key=api_key)
    instructions = (ROOT / "prompts" / "synthesis.md").read_text(encoding="utf-8")
    payload = {
        "brief_date": brief_date,
        "us_market_date": us_market_date,
        "korea_market_date": korea_market_date,
        "market_snapshot": snapshot.model_dump(mode="json"),
        "selected_events": [e.model_dump(mode="json") for e in selected_events],
    }
    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        input=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        text={"format": {"type": "json_schema", "name": "morning_market_brief", "strict": True, "schema": _brief_schema()}},
    )
    brief = MorningBrief.model_validate(json.loads(response.output_text))
    usage = build_usage(response, "SYNTHESIS", model)
    return brief, usage
