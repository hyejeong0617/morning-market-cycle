# Morning Market Cycle

A manual AI-assisted market research pipeline for **랩노트: 시장을 기록하다**.

The goal is not to archive every market headline. The system combines the **latest completed U.S. regular session** with the **completed Korean regular session**, checks how signals transmitted across markets, connects them to the portfolio, and stores the result as structured daily research data.

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
Email delivery
        ↓
Daily JSON + Markdown saved to GitHub
        ↓
Optional Daily Market Filter in Notion
```

This repository is now **manual-run only**.

There is no scheduled GitHub Actions run and no automatic run on push. The full pipeline runs only when the `Morning Market Brief — Manual` workflow is started manually.

## Market-cycle rule

The intended daily comparison is:

**latest completed U.S. regular session → completed Korean regular session → cross-market verification**

For example, a Germany-morning brief on October 8 compares:

```text
U.S. session: October 7 close
Korea session: October 8 close
```

The pipeline limits U.S. market data to the expected completed session date so that a delayed or afternoon execution does not accidentally mix in an in-progress U.S. session.

Korea is researched independently. Domestic policy, industry, company, earnings, and flow factors are not treated as simple reactions to the U.S. market.

## Outputs

A normal full run produces:

```text
data/runs/YYYY-MM-DD.json
data/runs/YYYY-MM-DD.md
```

The JSON is the canonical machine-readable daily record. It contains the main research inputs and decisions used by later Lab Notes workflows, including:

- market snapshot
- U.S. research
- Korea research
- event scores
- selected events
- Morning Market Brief
- US → Korea transmission assessment
- portfolio relevance
- Learning Signal
- API usage / estimated cost
- session information
- email delivery status

The Markdown file contains the rendered Morning Market Brief.

## Morning Market Brief

The current brief is designed to be readable in roughly five minutes and focuses on:

1. one-line market summary
2. U.S. market
3. Korean market
4. US → Korea transmission
5. portfolio relevance
6. additional headlines
7. observation questions

The system prioritizes useful market relationships over simply listing more news.

## Learning Signal

`src/learning_signal.py` performs a deterministic first-stage screen after the Morning Brief is generated.

It uses factors such as:

- event score
- portfolio relevance
- learning value
- US → Korea transmission

Possible outcomes are effectively:

```text
SIGNAL     → Daily Market Filter recommended
NO SIGNAL  → reading the email may be sufficient
```

Learning Signal is a screening rule, not the final learning decision. A user can still run the Daily Market Filter on a `NO SIGNAL` day.

## Daily Market Filter / Weekly Market Lab

This repository provides the raw daily research layer for the wider **랩노트: 시장을 기록하다** workflow.

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
```

`PASS` days do not require a separate Notion record. `WATCH` and `STUDY CANDIDATE` results are preserved in Notion and used together with the weekly Daily JSON files for review.

## Optional commentary

`당잠사` and `12시에 만나요` are **not required inputs** for this pipeline.

They can be used as optional commentary sources, but the Morning Market Brief should still work independently from market data, primary sources, trusted reporting, and AI research.

## Research design

Research is separated into U.S. and Korea stages:

- `prompts/research_us.md`
- `prompts/research_korea.md`

The research layer uses the OpenAI Responses API with web search and structured outputs.

Events are then scored using factors such as market impact, portfolio relevance, macro importance, evidence strength, and learning value before synthesis.

Source preference is broadly:

1. official / primary sources
2. trusted financial and economic reporting
3. commentary sources

## Market data

The prototype uses `yfinance` for convenient market snapshots. It is not treated as the long-term authoritative data layer.

Current instruments include:

- S&P 500: `^GSPC`
- Nasdaq Composite: `^IXIC`
- PHLX Semiconductor: `^SOX`
- VIX: `^VIX`
- U.S. 10Y yield proxy: `^TNX`
- KOSPI: `^KS11`
- KOSDAQ: `^KQ11`
- Samsung Electronics: `005930.KS`
- SK Hynix: `000660.KS`
- USD/KRW: `KRW=X`

Important caveats:

- missing market values must remain missing; the pipeline should never invent values
- the yfinance USD/KRW observation is not treated as the official Korea 15:30 closing FX rate
- Korean foreign-investor flow should be verified from KRX or reliable reporting rather than inferred from yfinance

## Setup

Python 3.12 is used in GitHub Actions.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Typical environment settings:

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

Do not commit credentials or API keys to this repository. Use GitHub Actions Secrets / Variables for workflow execution.

## Run locally

### Market data only

```bash
python main.py --skip-research
```

This skips the AI research stage.

### Full pipeline

```bash
python main.py
```

### Full pipeline without email

```bash
python main.py --skip-email
```

### Explicit brief date

```bash
python main.py --date YYYY-MM-DD
```

## Run with GitHub Actions

Open:

```text
GitHub → Actions → Morning Market Brief — Manual → Run workflow
```

For a normal Morning Market Brief run, leave these options `false`:

```text
email_test_only = false
skip_research   = false
skip_email      = false
```

That executes the full pipeline, sends the email, and commits the generated Daily JSON / Markdown files back to the repository.

Other modes:

- `email_test_only=true` — send the saved email fixture without running OpenAI research
- `skip_research=true` — market-data-only diagnostic run
- `skip_email=true` — run research and create the daily record without sending the email

## Repository role

This project is the **research and data-generation layer** of the Lab Notes system.

Its job is to reduce daily market information into a reusable, auditable record so that human effort can focus on:

- choosing worthwhile questions
- checking whether a market hypothesis held
- understanding portfolio exposure
- deciding what deserves a Learning Note
- reviewing changes in judgment through the Weekly Market Lab
