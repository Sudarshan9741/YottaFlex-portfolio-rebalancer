# Architecture and design decisions

1. **Deterministic generation:** NumPy's seeded generator creates repeatable synthetic investors, instruments, holdings, prices, target allocations, fee tiers, constraints, and a separate ground-truth label file.
2. **Parent-first generation:** investors and portfolios precede instruments/holdings/prices/targets. IDs are generated in one place and foreign keys are validated after export.
3. **Rule-based engine:** Pandas performs joins and aggregation. This task asks for policy-constrained recommendations; explainable rules are preferred over a black-box ML model.
4. **Policy gates:** target-weight reconciliation, minimum trade value, excluded instruments, liquidity-tier fees, available sell quantity, and price freshness are surfaced in the proposal.
5. **Traceability and integrity:** each proposal and its trades are appended to SQLite event tables with a JSON payload, timestamp, unique IDs, foreign keys, status checks, and foreign-key enforcement. Legacy unconstrained event tables are copied forward without losing their records.
6. **API + browser UI:** FastAPI exposes portfolio, analysis, proposal, summary, and history endpoints. A small vanilla JavaScript interface avoids a complex frontend build chain.
7. **No financial advice:** the generated assets and all recommendations are synthetic simulations; no orders are transmitted.

## API

- `GET /api/health`
- `GET /api/summary`
- `GET /api/portfolios`
- `GET /api/portfolios/{portfolio_id}`
- `POST /api/portfolios/{portfolio_id}/rebalance`
- `GET /api/proposals`
- `POST /api/admin/regenerate?portfolios=20&instruments=100&trading_days=60&seed=20261022`
- Interactive OpenAPI docs: `/docs`

### Drift tolerance

`DRIFT_TOLERANCE` is an absolute weight threshold read from the portfolio constraints. Drift at or below the threshold is within policy and produces no trade for that asset class. Drift above the threshold is passed to the minimum-trade, price, eligibility, quantity, and fee gates.

### Persistence constraints

The generated `seed.sql` creates all core entity tables with primary keys, foreign keys, unique keys, `NOT NULL` fields, and checks for allowed enums, positive quantities/prices, non-negative fees, and target-weight ranges. Event persistence additionally uses a portfolio registry, a unique proposal ID, a unique trade ID, proposal-to-trade foreign keys, valid JSON payload checks, and allowed proposal statuses. Every application connection enables `PRAGMA foreign_keys = ON`.
