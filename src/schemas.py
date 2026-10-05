from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


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
    schema_version: Literal["mvp1-v1"] = "mvp1-v1"
    brief_date: str
    us_market_date: str | None
    korea_market_date: str | None
    market_snapshot: MarketSnapshot
    us_research: ResearchBundle
    korea_research: ResearchBundle
    warnings: list[str] = []
