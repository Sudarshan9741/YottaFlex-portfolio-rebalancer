"""Deterministic synthetic dataset generator. All anomaly labels are kept separate."""
from __future__ import annotations
import argparse, hashlib, json, sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from app.config import DATA_DIR, SEED

ASSET_CLASSES = ["Equity", "Bond", "Gold", "Cash", "RealEstate"]
RISK_PROFILES = {
    "Conservative": {"Equity": .25, "Bond": .50, "Gold": .10, "Cash": .10, "RealEstate": .05},
    "Balanced": {"Equity": .50, "Bond": .25, "Gold": .10, "Cash": .05, "RealEstate": .10},
    "Growth": {"Equity": .70, "Bond": .10, "Gold": .05, "Cash": .05, "RealEstate": .10},
}


def _id(prefix: str, n: int, width: int = 6) -> str:
    return f"{prefix}-{n:0{width}d}"


def generate_dataset(out_dir: str | Path = DATA_DIR, portfolios: int = 20,
                     instruments: int = 100, trading_days: int = 60,
                     seed: int = SEED, inject_anomalies: bool = True) -> dict:
    """Generate parent records before dependent records, with reproducible IDs and values."""
    if not 1 <= portfolios <= 1000:
        raise ValueError("portfolios must be between 1 and 1000")
    if not portfolios * 5 <= instruments <= 5000:
        raise ValueError("instruments must be between portfolios * 5 and 5000")
    if not 2 <= trading_days <= 250:
        raise ValueError("trading_days must be between 2 and 250")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-01-01")
    dates = pd.bdate_range(end="2026-10-22", periods=trading_days)

    investors, portfolio_rows = [], []
    profiles = list(RISK_PROFILES)
    for i in range(1, portfolios + 1):
        risk = profiles[(i - 1) % len(profiles)]
        inv_id = _id("INV", i)
        investors.append({"investor_id": inv_id, "risk_profile": risk,
                          "base_currency": "USD", "created_date": str(start.date())})
        portfolio_rows.append({"portfolio_id": f"PORT-{inv_id}-01", "investor_id": inv_id,
                               "portfolio_name": f"Portfolio {i:04d}", "currency": "USD",
                               "status": "ACTIVE", "created_date": str(start.date())})

    instruments_rows = []
    for i in range(1, instruments + 1):
        asset = ASSET_CLASSES[(i - 1) % len(ASSET_CLASSES)]
        instruments_rows.append({"instrument_id": _id("INS", i), "symbol": f"SYN{i:04d}",
            "instrument_name": f"Synthetic {asset} Instrument {i:04d}", "asset_class": asset,
            "currency": "USD", "is_excluded": bool(i % 23 == 0),
            "liquidity_tier": "LOW" if i % 7 == 0 else "HIGH", "active": True})

    investor_df = pd.DataFrame(investors); portfolio_df = pd.DataFrame(portfolio_rows)
    instrument_df = pd.DataFrame(instruments_rows)
    # Target allocation rows are dependent on investor risk profiles.
    targets = []
    for p in portfolio_rows:
        risk = investors[int(p["investor_id"].split("-")[-1]) - 1]["risk_profile"]
        for asset, weight in RISK_PROFILES[risk].items():
            targets.append({"target_id": f"TGT-{p['portfolio_id']}-{asset.upper()}",
                "portfolio_id": p["portfolio_id"], "asset_class": asset,
                "target_weight": weight, "effective_from": str(start.date()), "effective_to": None})
    target_df = pd.DataFrame(targets)

    # Holdings: each portfolio owns a deterministic selection of five distinct instruments.
    holdings, prices = [], []
    for p_idx, p in enumerate(portfolio_rows):
        chosen = [((p_idx * 5 + j) % instruments) for j in range(5)]
        # Base market values add to 100k; a small deterministic variation gives portfolio diversity.
        values = rng.dirichlet(np.ones(5) * 2) * float(rng.integers(70000, 160001))
        for j, inst_idx in enumerate(chosen):
            ins = instruments_rows[inst_idx]
            price = round(float(rng.uniform(15, 250)), 2)
            quantity = round(float(values[j] / price), 4)
            holdings.append({"holding_id": f"HOLD-{p['portfolio_id']}-{ins['instrument_id']}",
                "portfolio_id": p["portfolio_id"], "instrument_id": ins["instrument_id"],
                "quantity": quantity, "cost_basis": round(price * .96, 2),
                "as_of_date": str(dates[-1].date()), "status": "OPEN"})
            # Price random walk, with the latest record sometimes deliberately missing/stale.
            returns = rng.normal(0.0002, 0.012 if ins["asset_class"] == "Equity" else 0.004, len(dates))
            series = price * np.cumprod(1 + returns)
            for d, px in zip(dates, series):
                prices.append({"price_id": f"PX-{ins['instrument_id']}-{d.strftime('%Y%m%d')}",
                    "instrument_id": ins["instrument_id"], "price_date": str(d.date()),
                    "close_price": round(float(max(px, 0.5)), 4), "currency": "USD", "source": "SYNTHETIC"})

    holding_df = pd.DataFrame(holdings); price_df = pd.DataFrame(prices)
    # Deliberately create realistic data-quality conditions without damaging unrelated rows:
    # every 29th instrument has no price history; every 17th instrument has a stale tail.
    missing_ids = {_id("INS", i) for i in range(1, instruments + 1) if i % 29 == 0}
    stale_ids = {_id("INS", i) for i in range(1, instruments + 1) if i % 17 == 0}
    price_df = price_df[~price_df.instrument_id.isin(missing_ids)].copy()
    for stale_id in stale_ids:
        stale_rows = price_df[price_df.instrument_id == stale_id].sort_values("price_date").index
        if len(stale_rows) > 8:
            price_df = price_df.drop(stale_rows[-8:])
    fee_rows = [
        {"fee_schedule_id":"FEE-LOW", "tier":"LOW", "rate_bps":8.0, "minimum_fee":1.0, "effective_from":str(start.date())},
        {"fee_schedule_id":"FEE-HIGH", "tier":"HIGH", "rate_bps":3.0, "minimum_fee":0.5, "effective_from":str(start.date())},
    ]
    constraints = []
    for p in portfolio_rows:
        constraints += [
            {"constraint_id":f"CON-{p['portfolio_id']}-MIN", "portfolio_id":p["portfolio_id"], "constraint_type":"MIN_TRADE_VALUE", "value":100.0, "active":True},
            {"constraint_id":f"CON-{p['portfolio_id']}-DRIFT", "portfolio_id":p["portfolio_id"], "constraint_type":"DRIFT_TOLERANCE", "value":0.03, "active":True},
        ]
    trades, proposals, ground_truth = [], [], []
    # Optional labeled edge cases are isolated and do not silently corrupt base records.
    if inject_anomalies:
        if len(target_df):
            ground_truth.append({"case_id":"ANOM-001","entity_type":"TargetAllocation","entity_id":target_df.iloc[0]["portfolio_id"],"issue_type":"WEIGHTS_NOT_100","ground_truth":"INVALID_TARGET_TOTAL","expected_decision":"REJECT_REBALANCE"})
        if len(holding_df):
            ground_truth.append({"case_id":"ANOM-002","entity_type":"Trade","entity_id":"TRADE-EDGE-002","issue_type":"TRADE_EXCEEDS_HOLDING","ground_truth":"INVALID_SELL_QUANTITY","expected_decision":"REJECT_TRADE"})
        if len(instrument_df):
            excluded = instrument_df[instrument_df.is_excluded]
            if len(excluded): ground_truth.append({"case_id":"ANOM-003","entity_type":"Instrument","entity_id":excluded.iloc[0]["instrument_id"],"issue_type":"EXCLUDED_INSTRUMENT","ground_truth":"MUST_NOT_RECOMMEND","expected_decision":"BLOCK_TRADE"})
        ground_truth += [
            {"case_id":"ANOM-004","entity_type":"Trade","entity_id":"TRADE-EDGE-004","issue_type":"FEES_OMITTED","ground_truth":"FEE_REQUIRED","expected_decision":"FLAG_AND_RECALCULATE"},
            {"case_id":"ANOM-005","entity_type":"MarketPrice","entity_id":"PX-STALE-005","issue_type":"STALE_PRICE_UNFLAGGED","ground_truth":"STALE_PRICE","expected_decision":"FLAG_PRICE_AND_BLOCK"},
        ]

    frames = {"investor_profiles": investor_df, "portfolios": portfolio_df,
        "instruments": instrument_df, "holdings": holding_df, "market_prices": price_df,
        "target_allocations": target_df, "fee_schedules": pd.DataFrame(fee_rows),
        "constraints": pd.DataFrame(constraints), "trades": pd.DataFrame(trades),
        "rebalance_proposals": pd.DataFrame(proposals), "ground_truth": pd.DataFrame(ground_truth)}
    # Keep empty event tables schema-stable.
    frames["trades"] = pd.DataFrame(columns=["trade_id","proposal_id","portfolio_id","instrument_id","side","quantity","estimated_fee","status","created_at"])
    frames["rebalance_proposals"] = pd.DataFrame(columns=["proposal_id","portfolio_id","created_at","status","reason","total_estimated_fees"])
    for name, df in frames.items():
        df.to_csv(out / f"{name}.csv", index=False)
        df.to_json(out / f"{name}.json", orient="records", indent=2, date_format="iso")
    # Provide a portable SQL seed script as well as CSV/JSON exports.
    sql_path = out / "seed.sql"
    schema = {
        "investor_profiles": """CREATE TABLE investor_profiles (
            investor_id TEXT PRIMARY KEY NOT NULL,
            risk_profile TEXT NOT NULL CHECK (risk_profile IN ('Conservative','Balanced','Growth')),
            base_currency TEXT NOT NULL, created_date TEXT NOT NULL
        )""",
        "portfolios": """CREATE TABLE portfolios (
            portfolio_id TEXT PRIMARY KEY NOT NULL,
            investor_id TEXT NOT NULL, portfolio_name TEXT NOT NULL,
            currency TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('ACTIVE','INACTIVE')),
            created_date TEXT NOT NULL,
            FOREIGN KEY (investor_id) REFERENCES investor_profiles(investor_id)
        )""",
        "instruments": """CREATE TABLE instruments (
            instrument_id TEXT PRIMARY KEY NOT NULL, symbol TEXT NOT NULL UNIQUE,
            instrument_name TEXT NOT NULL,
            asset_class TEXT NOT NULL CHECK (asset_class IN ('Equity','Bond','Gold','Cash','RealEstate')),
            currency TEXT NOT NULL, is_excluded INTEGER NOT NULL CHECK (is_excluded IN (0,1)),
            liquidity_tier TEXT NOT NULL CHECK (liquidity_tier IN ('LOW','HIGH')),
            active INTEGER NOT NULL CHECK (active IN (0,1))
        )""",
        "holdings": """CREATE TABLE holdings (
            holding_id TEXT PRIMARY KEY NOT NULL, portfolio_id TEXT NOT NULL,
            instrument_id TEXT NOT NULL, quantity REAL NOT NULL CHECK (quantity > 0),
            cost_basis REAL NOT NULL CHECK (cost_basis > 0), as_of_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('OPEN','CLOSED')),
            UNIQUE (portfolio_id, instrument_id),
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id),
            FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
        )""",
        "market_prices": """CREATE TABLE market_prices (
            price_id TEXT PRIMARY KEY NOT NULL, instrument_id TEXT NOT NULL,
            price_date TEXT NOT NULL, close_price REAL NOT NULL CHECK (close_price > 0),
            currency TEXT NOT NULL, source TEXT NOT NULL,
            UNIQUE (instrument_id, price_date),
            FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
        )""",
        "target_allocations": """CREATE TABLE target_allocations (
            target_id TEXT PRIMARY KEY NOT NULL, portfolio_id TEXT NOT NULL,
            asset_class TEXT NOT NULL, target_weight REAL NOT NULL CHECK (target_weight BETWEEN 0 AND 1),
            effective_from TEXT NOT NULL, effective_to TEXT,
            CHECK (effective_to IS NULL OR effective_to >= effective_from),
            UNIQUE (portfolio_id, asset_class, effective_from),
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
        )""",
        "fee_schedules": """CREATE TABLE fee_schedules (
            fee_schedule_id TEXT PRIMARY KEY NOT NULL, tier TEXT NOT NULL UNIQUE,
            rate_bps REAL NOT NULL CHECK (rate_bps >= 0),
            minimum_fee REAL NOT NULL CHECK (minimum_fee >= 0), effective_from TEXT NOT NULL
        )""",
        "constraints": """CREATE TABLE constraints (
            constraint_id TEXT PRIMARY KEY NOT NULL, portfolio_id TEXT NOT NULL,
            constraint_type TEXT NOT NULL CHECK (constraint_type IN ('MIN_TRADE_VALUE','DRIFT_TOLERANCE')),
            value REAL NOT NULL CHECK (value >= 0), active INTEGER NOT NULL CHECK (active IN (0,1)),
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
        )""",
        "trades": """CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY NOT NULL, proposal_id TEXT,
            portfolio_id TEXT, instrument_id TEXT, side TEXT CHECK (side IN ('BUY','SELL') OR side IS NULL),
            quantity REAL CHECK (quantity > 0 OR quantity IS NULL),
            estimated_fee REAL CHECK (estimated_fee >= 0 OR estimated_fee IS NULL),
            status TEXT CHECK (status IN ('PROPOSED','APPROVED','REJECTED','EXECUTED') OR status IS NULL),
            created_at TEXT,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id),
            FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
        )""",
        "rebalance_proposals": """CREATE TABLE rebalance_proposals (
            proposal_id TEXT PRIMARY KEY NOT NULL, portfolio_id TEXT NOT NULL,
            created_at TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('PROPOSED','NO_TRADE','REJECTED')),
            reason TEXT NOT NULL, total_estimated_fees REAL NOT NULL CHECK (total_estimated_fees >= 0),
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
        )""",
        "ground_truth": """CREATE TABLE ground_truth (
            case_id TEXT PRIMARY KEY NOT NULL, entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL, issue_type TEXT NOT NULL,
            ground_truth TEXT NOT NULL, expected_decision TEXT NOT NULL
        )""",
    }

    def sql_value(value):
        return None if pd.isna(value) else value.item() if hasattr(value, "item") else value

    with sqlite3.connect(":memory:") as con:
        con.execute("PRAGMA foreign_keys = ON")
        for name in (
            "investor_profiles", "portfolios", "instruments", "holdings",
            "market_prices", "target_allocations", "fee_schedules", "constraints",
            "trades", "rebalance_proposals", "ground_truth",
        ):
            con.execute(schema[name])
            df = frames[name]
            columns = list(df.columns)
            placeholders = ",".join("?" for _ in columns)
            rows = [[sql_value(value) for value in row] for row in df.itertuples(index=False, name=None)]
            if rows:
                con.executemany(
                    f"INSERT INTO {name} ({','.join(columns)}) VALUES ({placeholders})",
                    rows,
                )
        with sql_path.open("w", encoding="utf-8") as handle:
            handle.write("-- Generated deterministic synthetic seed data with enforced SQLite integrity constraints.\n")
            handle.write("PRAGMA foreign_keys = ON;\nBEGIN TRANSACTION;\n")
            for name in (
                "investor_profiles", "portfolios", "instruments", "holdings",
                "market_prices", "target_allocations", "fee_schedules", "constraints",
                "trades", "rebalance_proposals", "ground_truth",
            ):
                handle.write(schema[name] + ";\n")
            for name in (
                "investor_profiles", "portfolios", "instruments", "holdings",
                "market_prices", "target_allocations", "fee_schedules", "constraints",
                "trades", "rebalance_proposals", "ground_truth",
            ):
                columns = list(frames[name].columns)
                for row in frames[name].itertuples(index=False, name=None):
                    quoted = [
                        con.execute("SELECT quote(?)", (sql_value(value),)).fetchone()[0]
                        for value in row
                    ]
                    handle.write(
                        f'INSERT INTO "{name}" ({",".join(columns)}) '
                        f"VALUES ({','.join(quoted)});\n"
                    )
            handle.write("COMMIT;\n")
    tracked = [out / f"{name}.{ext}" for name in frames for ext in ("csv", "json")] + [sql_path]
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    manifest = {"seed":seed,"portfolios":portfolios,"instruments":instruments,"holdings":len(holding_df),
        "trading_days":trading_days,"market_prices":len(price_df),"generated_at":"deterministic-no-clock-field",
        "files":{name:len(df) for name,df in frames.items()},"sha256":checksums}
    (out / "source_manifest.json").write_text(json.dumps(manifest, indent=2))
    summary = validate_dataset(out)
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2))
    return {"manifest":manifest,"validation":summary}


def validate_dataset(out_dir: str | Path) -> dict:
    out = Path(out_dir)
    read = lambda n: pd.read_csv(out / f"{n}.csv")
    inv, port, ins, hold, prices, targets, fees, constraints = [
        read(n) for n in [
            "investor_profiles", "portfolios", "instruments", "holdings",
            "market_prices", "target_allocations", "fee_schedules", "constraints",
        ]
    ]
    checks = {}
    checks["investor_primary_key_unique"] = bool(inv.investor_id.is_unique)
    checks["portfolio_primary_key_unique"] = bool(port.portfolio_id.is_unique)
    checks["instrument_primary_key_unique"] = bool(ins.instrument_id.is_unique)
    checks["instrument_symbol_unique"] = bool(ins.symbol.is_unique)
    checks["holding_primary_key_unique"] = bool(hold.holding_id.is_unique)
    checks["price_primary_key_unique"] = bool(prices.price_id.is_unique)
    checks["fee_schedule_primary_key_unique"] = bool(fees.fee_schedule_id.is_unique)
    checks["constraint_primary_key_unique"] = bool(constraints.constraint_id.is_unique)
    checks["portfolio_investor_fk_valid"] = bool(port.investor_id.isin(inv.investor_id).all())
    checks["holding_portfolio_fk_valid"] = bool(hold.portfolio_id.isin(port.portfolio_id).all())
    checks["holding_instrument_fk_valid"] = bool(hold.instrument_id.isin(ins.instrument_id).all())
    checks["price_instrument_fk_valid"] = bool(prices.instrument_id.isin(ins.instrument_id).all())
    checks["target_portfolio_fk_valid"] = bool(targets.portfolio_id.isin(port.portfolio_id).all())
    checks["constraint_portfolio_fk_valid"] = bool(constraints.portfolio_id.isin(port.portfolio_id).all())
    checks["holding_pair_unique"] = bool(
        not hold.duplicated(["portfolio_id", "instrument_id"]).any()
    )
    checks["investor_risk_profiles_allowed"] = bool(
        inv.risk_profile.isin(RISK_PROFILES).all()
    )
    checks["instrument_asset_classes_allowed"] = bool(
        ins.asset_class.isin(ASSET_CLASSES).all()
    )
    checks["instrument_liquidity_tiers_allowed"] = bool(
        ins.liquidity_tier.isin({"LOW", "HIGH"}).all()
    )
    checks["target_weights_allowed"] = bool(
        targets.target_weight.between(0, 1, inclusive="both").all()
    )
    checks["target_weights_reconcile"] = bool(
        targets.groupby("portfolio_id").target_weight.sum().sub(1).abs().le(1e-6).all()
    )
    checks["fee_values_non_negative"] = bool(
        (fees.rate_bps >= 0).all() and (fees.minimum_fee >= 0).all()
    )
    checks["constraint_values_non_negative"] = bool((constraints.value >= 0).all())
    checks["positive_prices"] = bool((prices.close_price > 0).all())
    checks["positive_holding_quantities"] = bool(
        (hold.quantity > 0).all() and (hold.cost_basis > 0).all()
    )
    checks["dates_are_ordered"] = bool(
        pd.to_datetime(prices.price_date).between(
            pd.to_datetime(inv.created_date).min(), pd.to_datetime(prices.price_date).max()
        ).all()
        and (pd.to_datetime(hold.as_of_date) == pd.to_datetime(prices.price_date).max()).all()
    )
    checks["price_dates_unique_per_instrument"] = bool(
        not prices.duplicated(["instrument_id", "price_date"]).any()
    )
    checks["all_checks_pass"] = all(checks.values())
    return {"checks":checks,"row_counts":{"investors":len(inv),"portfolios":len(port),"instruments":len(ins),"holdings":len(hold),"market_prices":len(prices),"target_allocations":len(targets)},"valid":checks["all_checks_pass"]}


def main():
    parser=argparse.ArgumentParser(description="Generate deterministic YottaFlex synthetic portfolio data")
    parser.add_argument("--out", default=str(DATA_DIR)); parser.add_argument("--portfolios", type=int, default=20)
    parser.add_argument("--instruments", type=int, default=100); parser.add_argument("--trading-days", type=int, default=60)
    parser.add_argument("--seed", type=int, default=SEED); parser.add_argument("--no-anomalies", action="store_true")
    args=parser.parse_args()
    result=generate_dataset(args.out,args.portfolios,args.instruments,args.trading_days,args.seed,not args.no_anomalies)
    print(json.dumps(result,indent=2))

if __name__ == "__main__": main()
