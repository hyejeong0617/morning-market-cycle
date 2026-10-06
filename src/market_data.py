from __future__ import annotations

from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

from .schemas import MarketQuote, MarketSnapshot


TICKERS = {
    "^GSPC": ("S&P 500", "US"),
    "^IXIC": ("Nasdaq Composite", "US"),
    "^SOX": ("PHLX Semiconductor", "US"),
    "^VIX": ("VIX", "US"),
    "^TNX": ("US 10Y yield proxy", "US"),
    "^KS11": ("KOSPI", "KOREA"),
    "^KQ11": ("KOSDAQ", "KOREA"),
    "005930.KS": ("Samsung Electronics", "KOREA"),
    "000660.KS": ("SK Hynix", "KOREA"),
    "KRW=X": ("USD/KRW", "CROSS"),
}

US_DATE_ANCHOR = "^GSPC"
US_DATE_FALLBACK = {"^GSPC", "^IXIC", "^SOX", "^TNX"}
KOREA_DATE_ANCHOR = "^KS11"
KOREA_DATE_FALLBACK = {"^KS11", "^KQ11", "005930.KS", "000660.KS"}


def _quote(symbol: str, label: str, market: str) -> MarketQuote:
    try:
        hist = yf.download(
            symbol,
            period="7d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if hist is None or hist.empty or len(hist) < 1:
            return MarketQuote(
                symbol=symbol, label=label, market=market,
                status="MISSING", note="No daily data returned."
            )

        close_col = hist["Close"]
        if hasattr(close_col, "columns"):
            close_col = close_col.iloc[:, 0]
        close_col = close_col.dropna()

        if close_col.empty:
            return MarketQuote(
                symbol=symbol, label=label, market=market,
                status="MISSING", note="Close series is empty."
            )

        last = float(close_col.iloc[-1])
        prev = float(close_col.iloc[-2]) if len(close_col) >= 2 else None
        change = ((last / prev) - 1.0) * 100 if prev not in (None, 0) else None
        idx = close_col.index[-1]
        as_of = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)

        note = ""
        if symbol == "KRW=X":
            note = (
                "Latest yfinance daily FX observation; NOT a Korea 15:30 closing FX rate. "
                "Use a Korea-close official/reported USD/KRW observation for cross-market interpretation."
            )

        return MarketQuote(
            symbol=symbol,
            label=label,
            market=market,
            as_of=as_of,
            close=round(last, 4),
            previous_close=round(prev, 4) if prev is not None else None,
            change_pct=round(change, 3) if change is not None else None,
            status="OK",
            note=note,
        )
    except Exception as exc:
        return MarketQuote(
            symbol=symbol, label=label, market=market,
            status="ERROR", note=f"{type(exc).__name__}: {exc}"
        )


def collect_market_snapshot(timezone: str = "Europe/Berlin") -> MarketSnapshot:
    quotes = [
        _quote(symbol, label, market)
        for symbol, (label, market) in TICKERS.items()
    ]
    return MarketSnapshot(
        generated_at=datetime.now(ZoneInfo(timezone)).isoformat(),
        quotes=quotes,
    )


def _anchor_date(snapshot: MarketSnapshot, anchor: str, fallback_symbols: set[str]) -> str | None:
    for q in snapshot.quotes:
        if q.symbol == anchor and q.status == "OK" and q.as_of:
            return q.as_of

    dates = [
        q.as_of
        for q in snapshot.quotes
        if q.symbol in fallback_symbols and q.status == "OK" and q.as_of
    ]
    if not dates:
        return None

    counts = Counter(dates)
    return counts.most_common(1)[0][0]


def latest_market_date(snapshot: MarketSnapshot, market: str) -> str | None:
    """Return the completed regular-session date for the requested market.

    US is anchored to S&P 500, with Nasdaq/SOX/10Y majority fallback.
    Korea is anchored to KOSPI, with Korea equity majority fallback.
    This intentionally avoids VIX or 24-hour FX timestamps advancing the cycle date.
    """
    if market == "US":
        return _anchor_date(snapshot, US_DATE_ANCHOR, US_DATE_FALLBACK)
    if market == "KOREA":
        return _anchor_date(snapshot, KOREA_DATE_ANCHOR, KOREA_DATE_FALLBACK)
    return None
