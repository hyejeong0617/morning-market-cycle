# Morning Market Cycle

MVP for **랩노트: 시장을 기록하다**.

## MVP 1 goal

Produce one machine-readable JSON file containing:

1. Market data snapshot
2. US research
3. Korea research
4. Separate US/Korea market dates

MVP 1 deliberately does **not** yet:
- rank events,
- calculate US→Korea transmission,
- write to Notion Market Inbox,
- generate the final Morning Market Brief,
- send email,
- run Daily Market Filter automatically.

Those are the next stages.

## Why US and Korea are separate

The daily cycle is:

**latest completed US regular session → completed Korea regular session → cross-market verification**

Korea research must include domestic policy, industry, corporate and flow drivers rather than treating Korea as only a reaction to the US.

## Optional commentary

`당잠사` and `12시에 만나요` are not required inputs. They remain optional commentary sources outside this core pipeline.

## Setup

Python 3.11+ recommended.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Set:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.5
BRIEF_TIMEZONE=Europe/Berlin
```

## First test: market data only

```bash
python main.py --skip-research
```

This does not require an OpenAI API key.

## Full MVP 1 test

```bash
python main.py
```

Output is printed and saved under:

```text
data/runs/YYYY-MM-DD.json
```

## Market data caveat

MVP 1 uses `yfinance` for convenient prototyping. This is **not** treated as the long-term authoritative market-data layer. Missing data must remain missing; the pipeline should never invent a value.

Current tickers:

- S&P 500: `^GSPC`
- Nasdaq Composite: `^IXIC`
- PHLX Semiconductor: `^SOX`
- VIX: `^VIX`
- US 10Y proxy: `^TNX`
- KOSPI: `^KS11`
- KOSDAQ: `^KQ11`
- Samsung Electronics: `005930.KS`
- SK Hynix: `000660.KS`
- USD/KRW: `KRW=X`

Foreign-investor net flow is intentionally **not** faked in MVP 1 because yfinance does not provide the KRX investor-flow series needed for this project.

## Research design

The research stage uses the OpenAI Responses API with the hosted `web_search` tool and Structured Outputs.

Research is split into:
- `prompts/research_us.md`
- `prompts/research_korea.md`

Each result is constrained to a typed JSON schema.

## Next implementation stage

MVP 2:
1. Merge/deduplicate events by `event_key`
2. Evidence scoring
3. Importance scoring
4. Portfolio relevance normalization
5. US↔Korea transmission analysis

Then:
- Morning Brief generation
- Notion Market Inbox write
- Email delivery
- GitHub Actions scheduling
