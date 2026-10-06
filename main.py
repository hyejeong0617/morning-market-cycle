from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from src.email_sender import send_morning_brief_email
from src.market_data import collect_market_snapshot, latest_market_date
from src.notion_store import sync_market_inbox
from src.render import render_morning_brief_markdown
from src.research import run_research
from src.scoring import score_and_select
from src.schemas import Mvp2Run
from src.session_status import detect_session_status
from src.synthesis import run_synthesis


def main() -> None:
    parser = argparse.ArgumentParser(description="Morning Market Cycle MVP 2")
    parser.add_argument("--date", help="Brief date YYYY-MM-DD. Defaults to Europe/Berlin today.")
    parser.add_argument("--skip-research", action="store_true", help="Collect only market data.")
    parser.add_argument("--skip-notion", action="store_true", help="Do not sync selected events to Market Inbox.")
    parser.add_argument("--skip-email", action="store_true", help="Do not send the Morning Brief email.")
    args = parser.parse_args()

    load_dotenv()
    tz = os.getenv("BRIEF_TIMEZONE", "Europe/Berlin")
    brief_date = args.date or datetime.now(ZoneInfo(tz)).date().isoformat()

    snapshot = collect_market_snapshot(tz)
    us_market_date = latest_market_date(snapshot, "US")
    korea_market_date = latest_market_date(snapshot, "KOREA")
    session_info = detect_session_status(brief_date, us_market_date, korea_market_date)

    warnings: list[str] = []
    if not us_market_date:
        warnings.append("US market date could not be inferred from regular-session anchor data.")
    if not korea_market_date:
        warnings.append("Korea market date could not be inferred from regular-session anchor data.")
    if session_info["us_status"] == "NO_NEW_SESSION":
        warnings.append("US market had no new completed session for the expected cycle date; use news since the latest actual close.")
    if session_info["korea_status"] == "NO_NEW_SESSION":
        warnings.append("Korean market had no new completed session for the expected cycle date; use news since the latest actual close.")

    fx_quote = next((q for q in snapshot.quotes if q.symbol == "KRW=X"), None)
    if fx_quote and fx_quote.status == "OK":
        warnings.append(
            "USD/KRW from yfinance is a latest FX observation, not the Korea 15:30 closing rate; "
            "use official/reported Korea-close FX for cross-market interpretation."
        )

    out_dir = Path("data/runs")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.skip_research:
        output = {
            "schema_version": "mvp2-market-data-only",
            "brief_date": brief_date,
            "us_market_date": us_market_date,
            "korea_market_date": korea_market_date,
            "session_info": session_info,
            "market_snapshot": snapshot.model_dump(mode="json"),
            "warnings": warnings,
        }
    elif session_info["both_closed"]:
        output = {
            "schema_version": "mvp2-no-publication",
            "brief_date": brief_date,
            "us_market_date": us_market_date,
            "korea_market_date": korea_market_date,
            "session_info": session_info,
            "market_snapshot": snapshot.model_dump(mode="json"),
            "publication_status": "SKIPPED_BOTH_MARKETS_CLOSED",
            "notion_sync": {"status": "SKIPPED", "reason": "Both markets had no new session."},
            "email_delivery": {"status": "SKIPPED", "reason": "Both markets had no new session."},
            "warnings": warnings,
        }
    else:
        us_result = run_research(
            "US", us_market_date or brief_date,
            brief_date=brief_date,
            session_status=session_info["us_status"],
            is_monday=session_info["is_monday"],
        )
        korea_result = run_research(
            "KOREA", korea_market_date or brief_date,
            brief_date=brief_date,
            session_status=session_info["korea_status"],
            is_monday=session_info["is_monday"],
        )

        all_events = us_result.bundle.events + korea_result.bundle.events
        event_scores, selected_events = score_and_select(all_events, max_events=5)
        selected_event_keys = [e.event_key for e in selected_events]

        morning_brief, synthesis_usage = run_synthesis(
            brief_date=brief_date,
            us_market_date=us_market_date,
            korea_market_date=korea_market_date,
            snapshot=snapshot,
            selected_events=selected_events,
            session_info=session_info,
        )

        api_usage = [us_result.usage, korea_result.usage, synthesis_usage]
        known_costs = [u.estimated_total_cost_usd for u in api_usage if u.estimated_total_cost_usd is not None]
        estimated_api_cost_usd = round(sum(known_costs), 6) if len(known_costs) == len(api_usage) else None

        output = Mvp2Run(
            brief_date=brief_date,
            us_market_date=us_market_date,
            korea_market_date=korea_market_date,
            market_snapshot=snapshot,
            us_research=us_result.bundle,
            korea_research=korea_result.bundle,
            event_scores=event_scores,
            selected_event_keys=selected_event_keys,
            morning_brief=morning_brief,
            api_usage=api_usage,
            estimated_api_cost_usd=estimated_api_cost_usd,
            warnings=warnings,
        ).model_dump(mode="json")
        output["session_info"] = session_info

        markdown = render_morning_brief_markdown(
            brief_date=brief_date,
            us_market_date=us_market_date,
            korea_market_date=korea_market_date,
            brief=morning_brief,
            estimated_api_cost_usd=estimated_api_cost_usd,
        )
        md_path = out_dir / f"{brief_date}.md"
        md_path.write_text(markdown, encoding="utf-8")
        output["morning_brief_markdown"] = str(md_path)

        if args.skip_notion:
            notion_sync = {"status": "SKIPPED", "reason": "--skip-notion supplied", "created": 0, "duplicates": 0}
        else:
            try:
                notion_sync = sync_market_inbox(
                    brief_date=brief_date,
                    us_market_date=us_market_date,
                    korea_market_date=korea_market_date,
                    selected_events=selected_events,
                    event_scores=event_scores,
                    morning_brief=morning_brief,
                )
            except Exception as exc:
                notion_sync = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}", "created": 0, "duplicates": 0}
                warnings.append(f"Market Inbox sync failed: {type(exc).__name__}: {exc}")
        output["notion_sync"] = notion_sync

        if args.skip_email:
            email_delivery = {"status": "SKIPPED", "reason": "--skip-email supplied"}
        else:
            try:
                email_delivery = send_morning_brief_email(
                    brief_date=brief_date,
                    us_market_date=us_market_date,
                    korea_market_date=korea_market_date,
                    brief=morning_brief,
                    all_events=all_events,
                    selected_event_keys=selected_event_keys,
                    estimated_api_cost_usd=estimated_api_cost_usd,
                )
            except Exception as exc:
                email_delivery = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
                warnings.append(f"Morning Brief email failed: {type(exc).__name__}: {exc}")
        output["email_delivery"] = email_delivery
        output["warnings"] = warnings

    out_path = out_dir / f"{brief_date}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
