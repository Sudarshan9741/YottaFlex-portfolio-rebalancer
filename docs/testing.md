# Validation and evaluation plan

## Automated checks

Run `pytest -q`. Tests cover deterministic output, primary/foreign-key validation, allowed values, target-weight reconciliation, scale bounds, allocation totals, drift tolerance below/at/above threshold, append-only event persistence, invalid portfolio handling, stale-price blocking, sell-quantity caps, fee calculation and missing fees, excluded instruments, SQL duplicate/FK rejection, API success/error responses, and ground-truth isolation.

## Manual acceptance checklist

- [x] Dashboard starts and shows portfolio/instrument/holding counts.
- [x] Portfolio analysis returns asset-class current weights, targets, and drift.
- [x] Target weights sum to 100% or proposal is rejected with a clear exception.
- [x] No BUY or SELL proposal is created for an excluded/inactive instrument.
- [x] Sell quantity is capped at the available holding quantity.
- [x] Fee estimate follows max(minimum fee, trade value × rate bps / 10,000).
- [x] Missing/stale price exceptions are visible.
- [x] Post-trade weights are recomputed from simulated values.
- [x] Repeated proposal requests append new event rows instead of overwriting previous rows.
- [x] Regenerating with the same seed produces the same records/checksums.

## Metrics to report

- Primary-key uniqueness rate (expected 100%).
- Foreign-key validity rate (expected 100%).
- Deterministic row-count and checksum agreement (expected 100% across same-seed runs).
- Target-weight reconciliation rate.
- Proposed-trade policy violation count (expected 0 for enforced constraints).
- Fee reconciliation error (expected $0.01 or less per trade due to rounding).
- Exception detection coverage against the five documented `ground_truth.csv` scenarios through focused test fixtures.

The latest focused run passed 16 tests. Compilation passed with `python -m compileall -q app tests`. The full-scale generator run passed validation with 1,000 portfolios, 5,000 instruments, 5,000 holdings, 250 trading days, and 1,204,728 market-price rows. Browser visual automation was not available; the dashboard HTTP endpoint and API integration were tested.

## Known limitation

The ground-truth file remains a separate scenario label/checklist and is never loaded into engine inputs. The tests exercise each scenario with isolated in-memory fixtures rather than corrupting the baseline exports. The simulator still does not model taxes, bid/ask spreads, partial fills, market impact, currency conversion, or live brokerage execution.
