# Morning Market Cycle

A manual AI-assisted market research pipeline for **랩노트: 시장을 기록하다**.

The goal is not to archive every market headline or create daily trading signals. Phase 3 separates **daily market observation** from **weekly portfolio decisions**.

## Phase 3 operating rule

```text
Daily   = Observe
Weekly  = Decide
Monthly = Rebalance strategy
```

The system keeps the existing U.S. / Korea / cross-market newsletter structure, then adds a **private Portfolio Watch** to the email. Detailed ADD / HOLD / TRIM / EXIT decisions are made later in the weekly portfolio review, not in the daily pipeline.

## Current workflow

```text
Manual request / GitHub Actions workflow_dispatch
        ↓
Market data snapshot
        ↓
US Research + Korea Research
        ↓
Event scoring / selection
        ↓
US → Korea cross-market synthesis
        ↓
Morning Market Brief
        ↓
Learning Signal
        ↓
Private Portfolio Watch (email only, optional)
        ↓
Email delivery
        ↓
Public Daily JSON + Markdown saved to GitHub
        ↓
Optional Daily Market Filter in Notion
        ↓
Weekly Market Lab
        ↓
Weekly Portfolio Review
```

This repository is **manual-run only**. There is no scheduled GitHub Actions run and no automatic run on push.

## Daily Morning Market Brief

The brief remains a 3–5 minute market summary:

1. one-line market summary
2. U.S. market
3. Korean market
4. US → Korea transmission
5. material portfolio impact from the day's events
6. private Portfolio Watch in the email
7. additional headlines
8. observation questions

The synthesis stage should not create generic portfolio filler. It should only describe a portfolio connection when the supplied data supports a concrete path such as rates, FX, earnings, industry pricing, flows, or index exposure.

## Private Portfolio Watch

`src/portfolio_watch.py` is the Phase 3 strategic-bias layer.

It reads the private Notion **Portfolio Holdings** and **Portfolio Strategy** data sources at runtime, calculates current asset-group weights, compares them with Target / Min / Max, and displays at most three high-priority signals in the email:

```text
INCREASE BIAS
HOLD
REDUCE BIAS
EXIT PLAN
THESIS ALERT
```

These are **not daily order instructions**. The meaning is directional:

- `INCREASE BIAS` — strategically underweight; future new cash has higher priority
- `REDUCE BIAS` — strategically overweight; do not use good daily news as an automatic add signal
- `EXIT PLAN` — an existing exit plan remains active
- `HOLD` — inside the strategic band
- `THESIS ALERT` — reserved for a material strategic review condition

Actual `ADD CANDIDATE / HOLD / NO NEW BUY / TRIM CANDIDATE / EXIT ON RECOVERY` decisions belong in the weekly portfolio review.

### Privacy boundary

This repository is public, so private portfolio strategy data must **never** be committed to `data/runs/`.

The Portfolio Watch object is created in memory and passed only to the email renderer. It is intentionally excluded from:

```text
data/runs/YYYY-MM-DD.json
data/runs/YYYY-MM-DD.md
```

If the private Notion connection is unavailable, the normal market newsletter still works and the email falls back to the existing generic portfolio-impact section.

## Weekly decision layer

The repository remains the daily research/data layer. The detailed weekly investment decision is performed in Notion / ChatGPT using:

```text
Daily JSONs
+ Weekly Market Lab
+ Portfolio Holdings
+ Portfolio Strategy
+ Portfolio Transactions
        ↓
Weekly Portfolio Review
        ↓
ADD / HOLD / NO NEW BUY / TRIM / EXIT
+ next-week new-cash priority
```

The weekly review is where one-week market evidence is compared with Investment Thesis and strategic allocation. A weekly review does **not** imply that a trade must occur every week.

## Market-cycle rule

The intended daily comparison is:

**latest completed U.S. regular session → completed Korean regular session → cross-market verification**

For example, a Germany-morning brief on October 8 compares the October 7 U.S. close with the October 8 Korean close. The pipeline prevents an in-progress later U.S. session from being mixed into the same Daily Market Cycle.

Korea is researched independently. Domestic policy, industry, company, earnings, and flow factors are not treated as simple reactions to the U.S. market.

## Public outputs

A normal full run produces:

```text
data/runs/YYYY-MM-DD.json
data/runs/YYYY-MM-DD.md
```

The JSON is the canonical public machine-readable daily market record. It contains:

- market snapshot
- U.S. research
- Korea research
- event scores
- selected events
- Morning Market Brief
- US → Korea transmission assessment
- generic portfolio relevance
- Learning Signal
- API usage / estimated cost
- session information
- email delivery status

It does **not** contain private target weights, current portfolio weights, Add/Trim conditions, or the private Portfolio Watch.

## Learning Signal

`src/learning_signal.py` performs a deterministic first-stage learning screen after the Morning Brief is generated.

```text
SIGNAL     → Daily Market Filter recommended
NO SIGNAL  → reading the email may be sufficient
```

Learning Signal answers **“is this worth studying further?”**, not **“should I trade?”**.

## Daily Market Filter / Weekly Market Lab

```text
Daily JSON
   ↓
Learning Signal
   ↓
Daily Market Filter (when useful)
   ↓
PASS / WATCH / STUDY CANDIDATE
   ↓
Weekly Market Lab
   ↓
Weekly Portfolio Review (private)
```

The Daily Market Filter is for learning/blog selection. The Weekly Market Lab is for market-learning review. The Weekly Portfolio Review is the separate investment-decision layer.

## Optional commentary

`당잠사` and `12시에 만나요` are not required inputs. They can be used as optional commentary, while market data, primary sources, trusted reporting, and AI research remain the base pipeline.

## Research design

Research is separated into U.S. and Korea stages:

- `prompts/research_us.md`
- `prompts/research_korea.md`
- `prompts/synthesis.md`

The synthesis prompt explicitly avoids vague portfolio commentary and does not guess private allocation rules.

## Market data

The prototype uses `yfinance` for convenient market snapshots. It is not treated as the long-term authoritative data layer.

Current instruments include S&P 500, Nasdaq Composite, SOX, VIX, U.S. 10Y, KOSPI, KOSDAQ, Samsung Electronics, SK Hynix, and USD/KRW.

Important caveats:

- missing market values remain missing; never invent them
- the yfinance USD/KRW observation is not treated as the official Korea 15:30 closing FX rate
- Korean foreign-investor flow should be verified from KRX or reliable reporting

## Setup

Python 3.12 is used in GitHub Actions.

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
```

Core settings:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=...
BRIEF_TIMEZONE=Europe/Berlin
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
EMAIL_FROM=...
EMAIL_TO=...
```

### Optional private Notion Portfolio Watch

To enable Phase 3 Portfolio Watch, configure these as **GitHub Actions Secrets**:

```text
NOTION_TOKEN
NOTION_STRATEGY_DATA_SOURCE_ID
NOTION_HOLDINGS_DATA_SOURCE_ID
```

Optional variable:

```text
NOTION_API_VERSION=2025-09-03
```

The Notion integration associated with `NOTION_TOKEN` must have read access to both Portfolio Strategy and Portfolio Holdings.

Do not place live tokens, database contents, target weights, or portfolio snapshots in this repository.

## Run locally

```bash
python main.py --skip-research   # market data only
python main.py                   # full pipeline
python main.py --skip-email      # research + public record, no email
python main.py --date YYYY-MM-DD
```

## Run with GitHub Actions

Open:

```text
GitHub → Actions → Morning Market Brief — Manual → Run workflow
```

For a normal run, leave:

```text
email_test_only = false
skip_research   = false
skip_email      = false
```

The workflow sends the private email and commits only the public Daily JSON / Markdown outputs.

## Repository role

This project is the **daily market research and data-generation layer** of the Lab Notes system.

Its job is to reduce daily information into an auditable market record and a small strategic Portfolio Watch, while keeping the higher-consequence investment decision at the weekly review layer.
