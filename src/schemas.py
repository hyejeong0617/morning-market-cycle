from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


MarketScope = Literal["US", "KOREA", "CROSS-MARKET"]
EventStatus = Literal["NEW", "FOLLOW-UP", "REPEAT", "NOISE"]
PortfolioRelevance = Literal["HIGH", "MEDIUM", "LOW", "NONE"]


class SourceItem(BaseModel):
    title: str
    url: str
    source_type: Literal["PRIMARY", "TRUSTED_REPORTING", "OTHER"] = "OTHER"


class ResearchEvent(BaseModel):
    event_key: str = Field(description="Stable lowercase slug used for deduplication")
    title: str
    market: MarketScope
    category: Literal[
        "Macro", "Rates", "FX", "Semiconductor", "AI",
        "Corporate", "Earnings", "Policy", "Flows",
        "Commodities", "Other"
    ]
    event_status: EventStatus = "NEW"
    summary: str
    why_important: str
    facts: list[str]
    sources: list[SourceItem]
    portfolio_links: list[str] = []
    portfolio_relevance: PortfolioRelevance = "NONE"
    next_check: str = ""


class ResearchBundle(BaseModel):
    research_date: str
    market: Literal["US", "KOREA"]
    events: list[ResearchEvent]


class ApiUsage(BaseModel):
    market: Literal["US", "KOREA"]
    model: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    web_search_calls: int = 0
    estimated_model_cost_usd: float | None = None
    estimated_web_search_cost_usd: float | None = None
    estimated_total_cost_usd: float | None = None
    pricing_note: str = "Estimate only; verify against the OpenAI billing dashboard."


class ResearchResult(BaseModel):
    bundle: ResearchBundle
    usage: ApiUsage


class MarketQuote(BaseModel):
    symbol: str
    label: str
    market: Literal["US", "KOREA", "CROSS"]
    as_of: str | None = None
    close: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    status: Literal["OK", "MISSING", "ERROR"] = "OK"
    note: str = ""


class MarketSnapshot(BaseModel):
    generated_at: str
    quotes: list[MarketQuote]


class MvpRun(BaseModel):
    schema_version: Literal["mvp1-v2"] = "mvp1-v2"
    brief_date: str
    us_market_date: str | None
    korea_market_date: str | None
    market_snapshot: MarketSnapshot
    us_research: ResearchBundle
    korea_research: ResearchBundle
    api_usage: list[ApiUsage] = []
    estimated_api_cost_usd: float | None = None
    warnings: list[str] = []
