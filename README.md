# YottaFlex AI — Portfolio Rebalancer

A runnable, rules-based portfolio rebalancing simulation built for the YottaFlex AI candidate project. It compares synthetic holdings with target asset allocation, applies policy constraints, proposes simulated trades, estimates fees, reports exceptions, recomputes post-trade allocation, and records proposal history.

> **Educational simulation only. Not financial advice. No real trades are placed.**

## Features

- Fixed-seed synthetic data generator with deterministic IDs.
- Parent-first entities and FK/PK validation.
- CSV and JSON exports for all core tables, plus source manifest and validation summary.
- Portfolio value, asset-class current weights, target weights, and drift calculations.
- Configured drift tolerance and minimum trade value, excluded instruments, liquidity fee tiers, sell quantity limits, and missing/stale price flags.
- Rebalance proposals and simplified post-trade allocation simulation.
- Append-only SQLite proposal/trade event history with foreign keys, uniqueness, JSON, status, and value checks.
- Browser dashboard and FastAPI `/docs` API documentation.
- Separate `ground_truth.csv` labels; ground truth is not an engine input.
- Tests for reproducibility, data validation, calculation, history, and invalid portfolio IDs.

## Requirements

- Python 3.11 recommended (Python 3.10+ should work).
- Internet is needed only to install packages; runtime uses local synthetic data.

## Quick start (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m app.generator --out data --portfolios 20 --instruments 100 --trading-days 60 --seed 20261022
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the dashboard and `http://127.0.0.1:8000/docs` for API docs.

## macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m app.generator --out data --portfolios 20 --instruments 100 --trading-days 60 --seed 20261022
uvicorn app.main:app --reload
```

## Generate full requested scale

The full configuration generates 1,000 portfolios, 5,000 instruments/holdings, and 250 business-day price observations per instrument. This can create a large price export; generate it on demand rather than committing the full generated output unless repository size is acceptable.

```bash
python -m app.generator --out data/full --portfolios 1000 --instruments 5000 --trading-days 250 --seed 20261022
```

The generator uses the same logic and seed for starter and full datasets. It creates CSV and JSON files, a portable `seed.sql` SQLite dump, `source_manifest.json` with SHA-256 checksums, and `validation_summary.json`.

## Verify the project

```bash
pytest -q
python -m app.generator --out data/check-a --portfolios 6 --instruments 30 --trading-days 20 --seed 20261022
python -m app.generator --out data/check-b --portfolios 6 --instruments 30 --trading-days 20 --seed 20261022
```

Compare all CSV and JSON files in `check-a` and `check-b` byte-for-byte (or compare SHA-256 values) to verify deterministic reproducibility. `validation_summary.json` reports primary-key uniqueness, foreign-key integrity, allowed values, target reconciliation, date consistency, positive values, and row counts.

## Typical workflow

1. Start the app and select a portfolio.
2. Click **Analyze portfolio** to inspect target vs current weights and drift.
3. Click **Generate proposal** to apply constraints and generate simulated trades.
4. Inspect estimated fees, exception flags, post-trade allocation, and saved proposal history.
5. Use `/api/portfolios/{portfolio_id}` or `/api/portfolios/{portfolio_id}/rebalance` via `/docs` to inspect JSON outputs.

## Dataset and tables

`investor_profiles`, `portfolios`, `instruments`, `holdings`, `market_prices`, `target_allocations`, `fee_schedules`, `constraints`, `trades`, `rebalance_proposals`, and `ground_truth` are exported as both CSV and JSON. See [`docs/data-dictionary.md`](docs/data-dictionary.md) for fields, keys, cardinalities, rules, and limitations. See [`docs/architecture.md`](docs/architecture.md) for design choices and API endpoints.

## Exception and ground-truth handling

`ground_truth.csv` documents expected decisions for the requested negative scenarios (invalid target total, trade exceeds holding, excluded instrument, omitted fees, and unflagged stale price). It is not joined into calculation features. Runtime proposals also surface actual detected conditions such as invalid target totals, missing/stale prices, and no eligible instrument. The labels are intended as a documented evaluation checklist, not as random labels attached to input features.

## Drift tolerance and business rules

Each portfolio has a `DRIFT_TOLERANCE` constraint, expressed as an absolute allocation-weight difference. A class whose absolute current-to-target drift is less than or equal to this value is not traded. A class above the tolerance is eligible for a BUY or SELL proposal, subject to the minimum trade value, price freshness, instrument eligibility, available quantity, and fee rules. Equality is intentionally treated as within tolerance.

SQLite seed exports define explicit primary keys, foreign keys, unique constraints, non-null fields, and checks for allowed values and non-negative monetary fields. Proposal history uses an append-only event model. Existing legacy event tables are copied into constrained tables without deleting their records when a proposal is next persisted.

### API examples

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/portfolios
Invoke-RestMethod http://127.0.0.1:8000/api/portfolios/PORT-INV-000001-01
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/portfolios/PORT-INV-000001-01/rebalance
Invoke-RestMethod "http://127.0.0.1:8000/api/admin/regenerate?portfolios=20&instruments=100&trading_days=60&seed=20261022" -Method Post
```

The full-scale reproducibility command uses seed `20261022`, 1,000 portfolios, 5,000 instruments/holdings, and 250 trading days. The verified run produced 1,204,728 price rows and passed every validation check; two same-seed runs produced matching CSV hashes. The generated full-scale output should remain temporary unless repository storage is intentionally increased.

## AI use disclosure

See [`prompt-history/prompts.md`](prompt-history/prompts.md). The project was drafted with AI assistance. Review, run, test, and understand the implementation before submitting; append every additional prompt sent to any AI tool. Do not claim AI-generated code was independently authored without assistance.

## Security and provenance

All records are synthetic. No credentials or external personal data are required. Do not commit `.env`, tokens, credentials, or private data. The API is intended for local evaluation and should not be exposed publicly without authentication and production hardening.
