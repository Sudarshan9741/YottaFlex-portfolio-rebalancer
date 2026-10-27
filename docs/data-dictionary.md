# Data dictionary and relationship model

All data is synthetic, denominated in USD, and for education/testing only. IDs are immutable strings. Dates are ISO-8601 calendar dates. CSV and JSON exports are generated from the same fixed-seed records.

| Entity | Primary key | Fields and validation | Relationships / cardinality |
|---|---|---|---|
| InvestorProfile | `investor_id` | `risk_profile` enum: Conservative/Balanced/Growth (required); `base_currency` ISO-like code (required); `created_date` date | Investor 1:N Portfolio |
| Portfolio | `portfolio_id` | `investor_id` required FK; `portfolio_name` required; `currency`; `status` ACTIVE/INACTIVE; `created_date` | Portfolio N:1 InvestorProfile; Portfolio 1:N Holding, TargetAllocation, Constraint, RebalanceProposal |
| Instrument | `instrument_id` | unique `symbol`; `instrument_name`; `asset_class` enum Equity/Bond/Gold/Cash/RealEstate; `currency`; `is_excluded` boolean; `liquidity_tier` LOW/HIGH; `active` boolean | Instrument 1:N Holding, MarketPrice, Trade |
| Holding | `holding_id` | portfolio/instrument FKs required; `quantity > 0`; `cost_basis > 0`; `as_of_date`; `status` OPEN/CLOSED | Portfolio N:M Instrument through Holding; one holding per portfolio/instrument pair in generated data |
| MarketPrice | `price_id` | instrument FK; `price_date`; `close_price > 0`; currency; source SYNTHETIC | Instrument 1:N MarketPrice; multiple dated observations per instrument |
| TargetAllocation | `target_id` | portfolio FK; `asset_class`; `target_weight` in [0,1]; effective_from required; effective_to optional and >= effective_from | Portfolio 1:N TargetAllocation; effective dates permit history |
| Trade | `trade_id` | proposal/portfolio/instrument FKs in event record; side BUY/SELL; quantity > 0; estimated fee >= 0; status PROPOSED/APPROVED/REJECTED/EXECUTED | Proposal 1:N Trade; no live execution exists in this demo |
| FeeSchedule | `fee_schedule_id` | unique tier LOW/HIGH; `rate_bps >= 0`; `minimum_fee >= 0`; effective_from | FeeSchedule tier can apply to N trades; effective-dated rules |
| Constraint | `constraint_id` | portfolio FK; `constraint_type` MIN_TRADE_VALUE/DRIFT_TOLERANCE; numeric value; active boolean | Portfolio 1:N Constraint |
| RebalanceProposal | `proposal_id` | portfolio FK; created_at; status; reason; total estimated fees; append-only JSON payload stored in SQLite event log | Portfolio 1:N RebalanceProposal; Proposal 1:N Trade |

## Important rules

- IDs use the requested patterns: `INV-000001`, `PORT-INV-000001-01`, `INS-000001`, `HOLD-<portfolio-id>-<instrument-id>`, and `RB-YYYY-XXXXXX`.
- Each investor owns a portfolio in this starter generator; a portfolio has five holdings. Holdings bridge portfolios and instruments.
- Target allocations are effective-dated and derived from a documented risk profile mapping. Target weights must sum to 1.0 (100%).
- Market value = quantity × latest available price. Current weight = asset-class market value / total portfolio value. Drift = current weight − target weight.
- Trade fees = max(minimum fee, trade value × rate basis points / 10,000). Trades below the portfolio minimum trade value are skipped.
- Excluded or inactive instruments are not eligible for BUY proposals. SELL quantities are capped at the available holding.
- Price data missing or flagged stale is not used to create a trade from that holding. Synthetic price dates are fixed so generation is reproducible.
- `DRIFT_TOLERANCE` is an absolute weight threshold: drift less than or equal to the configured value is within policy and is not traded; drift above it proceeds through the remaining trade gates.
- SQL seed exports enforce primary keys, foreign keys, unique keys, non-null fields, allowed-value checks, positive quantity/price checks, and non-negative monetary checks.
- `ground_truth.csv` is a separate label file and is never loaded as an engine input. It records the expected handling of deliberate exception scenarios.

## Known modeling limitations

This is an educational rule-based simulator, not an investment recommendation engine. It does not model taxes, bid/ask spreads, partial fills, market impact, currency conversion, or live brokerage execution. The post-trade view is a simplified allocation simulation; proposal/event history is append-only and no prior event is overwritten.
