from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from src.market_data import collect_market_snapshot, latest_market_date
from src.research import run_research
from src.schemas import MvpRun


def main() -> None:
    parser = argparse.ArgumentParser(description="Morning Market Cycle MVP 1")
    parser.add_argument("--date", help="Brief date YYYY-MM-DD. Defaults to Europe/Berlin today.")
    parser.add_argument("--skip-research", action="store_true", help="Collect only market data.")
    args = parser.parse_args()

    load_dotenv()
    tz = os.getenv("BRIEF_TIMEZONE", "Europe/Berlin")
    brief_date = args.date or datetime.now(ZoneInfo(tz)).date().isoformat()

    snapshot = collect_market_snapshot(tz)
    us_market_date = latest_market_date(snapshot, "US")
    korea_market_date = latest_market_date(snapshot, "KOREA")

    warnings: list[str] = []
    if not us_market_date:
        warnings.append("US market date could not be inferred from regular-session anchor data.")
    if not korea_market_date:
        warnings.append("Korea market date could not be inferred from regular-session anchor data.")

    fx_quote = next((q for q in snapshot.quotes if q.symbol == "KRW=X"), None)
    if fx_quote and fx_quote.status == "OK":
        warnings.append(
            "USD/KRW from yfinance is a latest FX observation, not the Korea 15:30 closing rate; "
            "use official/reported Korea-close FX for cross-market interpretation."
        )

    if args.skip_research:
        output = {
            "schema_version": "mvp1-market-data-only-v2",
            "brief_date": brief_date,
            "us_market_date": us_market_date,
            "korea_market_date": korea_market_date,
            "market_snapshot": snapshot.model_dump(mode="json"),
            "warnings": warnings,
        }
    else:
        us_result = run_research("US", us_market_date or brief_date)
        korea_result = run_research("KOREA", korea_market_date or brief_date)

        api_usage = [us_result.usage, korea_result.usage]
        known_costs = [
            item.estimated_total_cost_usd
            for item in api_usage
            if item.estimated_total_cost_usd is not None
        ]
        estimated_api_cost_usd = round(sum(known_costs), 6) if len(known_costs) == len(api_usage) else None

        output = MvpRun(
            brief_date=brief_date,
            us_market_date=us_market_date,
            korea_market_date=korea_market_date,
            market_snapshot=snapshot,
            us_research=us_result.bundle,
            korea_research=korea_result.bundle,
            api_usage=api_usage,
            estimated_api_cost_usd=estimated_api_cost_usd,
            warnings=warnings,
        ).model_dump(mode="json")

    out_dir = Path("data/runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{brief_date}.json"
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
