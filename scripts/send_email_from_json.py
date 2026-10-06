from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.email_sender import send_morning_brief_email
from src.schemas import MorningBrief


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Morning Brief email from an existing MVP2 JSON file.")
    parser.add_argument("json_path", help="Path to an existing MVP2 JSON file")
    args = parser.parse_args()

    path = Path(args.json_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    brief = MorningBrief.model_validate(data["morning_brief"])
    all_events = [
        *data.get("us_research", {}).get("events", []),
        *data.get("korea_research", {}).get("events", []),
    ]

    result = send_morning_brief_email(
        brief_date=data["brief_date"],
        us_market_date=data.get("us_market_date"),
        korea_market_date=data.get("korea_market_date"),
        brief=brief,
        estimated_api_cost_usd=data.get("estimated_api_cost_usd"),
        all_events=all_events,
        selected_event_keys=data.get("selected_event_keys", []),
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") != "SENT":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
