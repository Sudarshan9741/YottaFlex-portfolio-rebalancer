"""Rule-based rebalancing engine. Recommendations are simulations, never live orders."""
from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path
import json, sqlite3, uuid
import pandas as pd
from app.config import DATA_DIR, DB_PATH

TABLE_FILES = {"investor_profiles":"investor_profiles.csv","portfolios":"portfolios.csv","instruments":"instruments.csv",
"holdings":"holdings.csv","market_prices":"market_prices.csv","target_allocations":"target_allocations.csv",
"fee_schedules":"fee_schedules.csv","constraints":"constraints.csv"}


def load_data(data_dir: Path = DATA_DIR) -> dict[str,pd.DataFrame]:
    return {name: pd.read_csv(data_dir / filename) for name,filename in TABLE_FILES.items()}


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_event_schema(connection: sqlite3.Connection) -> None:
    for table in ("proposal_events", "trade_events"):
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if row and "FOREIGN KEY" not in (row[0] or "").upper():
            legacy = f"{table}_legacy"
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (legacy,),
            ).fetchone():
                legacy = f"{table}_legacy_v2"
            connection.execute(f"ALTER TABLE {table} RENAME TO {legacy}")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS portfolio_registry (
            portfolio_id TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS proposal_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL UNIQUE,
            portfolio_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('PROPOSED', 'NO_TRADE', 'REJECTED')),
            payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
            FOREIGN KEY (portfolio_id) REFERENCES portfolio_registry(portfolio_id)
        );
        CREATE TABLE IF NOT EXISTS trade_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            trade_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
            FOREIGN KEY (proposal_id) REFERENCES proposal_events(proposal_id)
        );
        CREATE INDEX IF NOT EXISTS idx_proposal_events_portfolio
            ON proposal_events(portfolio_id);
        CREATE INDEX IF NOT EXISTS idx_trade_events_proposal
            ON trade_events(proposal_id);
        """
    )
    for legacy in ("proposal_events_legacy", "proposal_events_legacy_v2"):
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (legacy,),
        ).fetchone():
            connection.execute(
                f"INSERT OR IGNORE INTO portfolio_registry(portfolio_id) "
                f"SELECT DISTINCT portfolio_id FROM {legacy}"
            )
            connection.execute(
                f"INSERT OR IGNORE INTO proposal_events "
                f"(event_id, proposal_id, portfolio_id, created_at, status, payload_json) "
                f"SELECT event_id, proposal_id, portfolio_id, created_at, status, payload_json FROM {legacy}"
            )
    for legacy in ("trade_events_legacy", "trade_events_legacy_v2"):
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (legacy,),
        ).fetchone():
            connection.execute(
                f"INSERT OR IGNORE INTO trade_events "
                f"(event_id, proposal_id, trade_id, created_at, payload_json) "
                f"SELECT event_id, proposal_id, trade_id, created_at, payload_json FROM {legacy}"
            )


def latest_price(prices: pd.DataFrame, instrument_id: str) -> dict | None:
    rows=prices[prices.instrument_id == instrument_id].copy()
    if rows.empty: return None
    rows["price_date"] = pd.to_datetime(rows.price_date)
    r=rows.sort_values("price_date").iloc[-1]
    age=(pd.Timestamp(date.today()) - r.price_date.normalize()).days
    # Synthetic history ends on a fixed date; stale checks are based on data's own latest date
    # and the latest date across the dataset, making the simulation reproducible.
    global_latest=pd.to_datetime(prices.price_date).max().normalize()
    age=(global_latest-r.price_date.normalize()).days
    return {"price":float(r.close_price),"date":str(r.price_date.date()),"age_days":int(age),"stale":age>5}


def compute_portfolio(portfolio_id: str, data: dict[str,pd.DataFrame]) -> dict:
    portfolios=data["portfolios"]; holdings=data["holdings"]; instruments=data["instruments"]
    if portfolio_id not in set(portfolios.portfolio_id): raise KeyError(f"Unknown portfolio: {portfolio_id}")
    ph=holdings[holdings.portfolio_id == portfolio_id].merge(instruments,on="instrument_id",validate="many_to_one")
    prices=data["market_prices"]
    rows=[]
    for _,h in ph.iterrows():
        px=latest_price(prices,h.instrument_id)
        rows.append({**h.to_dict(),"market_price":px["price"] if px else None,
            "price_date":px["date"] if px else None,"price_stale":px["stale"] if px else True,
            "market_value":float(h.quantity)*px["price"] if px else None})
    values=pd.DataFrame(rows)
    if values.empty: total=0.0
    else: total=float(values.market_value.fillna(0).sum())
    class_rows=[]
    targets=data["target_allocations"][data["target_allocations"].portfolio_id == portfolio_id]
    target_total=float(targets.target_weight.sum()) if not targets.empty else 0
    valid_target=abs(target_total-1.0) <= 1e-6
    for _,t in targets.iterrows():
        class_value=float(values.loc[values.asset_class==t.asset_class,"market_value"].fillna(0).sum())
        current_weight=class_value/total if total>0 else 0
        class_rows.append({"asset_class":t.asset_class,"target_weight":float(t.target_weight),
            "current_weight":current_weight,"drift":current_weight-float(t.target_weight),
            "current_value":class_value,"target_value":total*float(t.target_weight)})
    return {"portfolio_id":portfolio_id,"total_value":round(total,2),"target_weight_total":round(target_total,6),
        "target_weights_valid":valid_target,"holdings":values.where(pd.notnull(values),None).to_dict(orient="records"),
        "allocation":class_rows}


def create_proposal(portfolio_id: str, data: dict[str,pd.DataFrame], db_path: Path = DB_PATH) -> dict:
    snapshot=compute_portfolio(portfolio_id,data)
    portfolio_id=snapshot["portfolio_id"]
    if not snapshot["target_weights_valid"]:
        result={"proposal_id":f"RB-{datetime.now():%Y}-{uuid.uuid4().hex[:6].upper()}","portfolio_id":portfolio_id,
          "status":"REJECTED","reason":"Target allocation weights do not sum to 100%.","trades":[],"exceptions":[{"issue_type":"WEIGHTS_NOT_100","severity":"ERROR"}],"estimated_fees":0.0,"post_trade_allocation":snapshot["allocation"]}
        persist_event(result,db_path); return result
    if snapshot["total_value"] <= 0:
        result={"proposal_id":f"RB-{datetime.now():%Y}-{uuid.uuid4().hex[:6].upper()}","portfolio_id":portfolio_id,"status":"REJECTED","reason":"No valid priced holdings available.","trades":[],"exceptions":[{"issue_type":"NO_VALID_PRICES","severity":"ERROR"}],"estimated_fees":0.0,"post_trade_allocation":snapshot["allocation"]}
        persist_event(result,db_path); return result
    inst=data["instruments"].set_index("instrument_id")
    constraints=data["constraints"]; pc=constraints[constraints.portfolio_id==portfolio_id]
    min_trade=float(pc.loc[pc.constraint_type=="MIN_TRADE_VALUE","value"].iloc[0]) if not pc[pc.constraint_type=="MIN_TRADE_VALUE"].empty else 100.0
    drift_tolerance=float(pc.loc[pc.constraint_type=="DRIFT_TOLERANCE","value"].iloc[0]) if not pc[pc.constraint_type=="DRIFT_TOLERANCE"].empty else 0.0
    fee_schedules=data["fee_schedules"].set_index("tier")
    target_by_class={a["asset_class"]:a for a in snapshot["allocation"]}
    exceptions=[]; trades=[]
    # Trade value is distributed across eligible instruments in the asset class.
    for asset,alloc in target_by_class.items():
        gap=alloc["target_value"]-alloc["current_value"]
        if abs(float(alloc["drift"])) <= drift_tolerance:
            continue
        if abs(gap)<min_trade: continue
        side="BUY" if gap>0 else "SELL"
        candidates=[h for h in snapshot["holdings"] if h["asset_class"]==asset and h.get("market_price") and not h.get("price_stale")]
        if side=="BUY":
            # Do not buy excluded instruments; prefer high-liquidity eligible instruments.
            candidates=[h for h in candidates if not bool(h["is_excluded"]) and bool(h["active"])]
            candidates.sort(key=lambda h:(h["liquidity_tier"]!="HIGH",h["instrument_id"]))
        else:
            candidates=[h for h in candidates if float(h["quantity"])>0 and not bool(h["is_excluded"]) and bool(h["active"])]
            candidates.sort(key=lambda h:(bool(h["is_excluded"]),h["instrument_id"]))
        if not candidates:
            exceptions.append({"issue_type":"NO_ELIGIBLE_INSTRUMENT","asset_class":asset,"severity":"WARNING","message":f"No eligible instrument for {side} in {asset}."}); continue
        h=candidates[0]; px=float(h["market_price"]); qty=round(abs(gap)/px,4)
        if side=="SELL" and qty>float(h["quantity"]):
            qty=round(float(h["quantity"]),4)
            exceptions.append({"issue_type":"TRADE_EXCEEDS_HOLDING_PREVENTED","instrument_id":h["instrument_id"],"severity":"WARNING","message":"Sell quantity capped at available holding."})
        trade_value=round(qty*px,2)
        if trade_value<min_trade: continue
        tier=h["liquidity_tier"]
        if tier not in fee_schedules.index:
            exceptions.append({
                "issue_type":"FEES_MISSING",
                "instrument_id":h["instrument_id"],
                "severity":"ERROR",
                "message":f"No fee schedule exists for liquidity tier {tier}.",
            })
            continue
        fee=round(max(float(fee_schedules.loc[tier,"minimum_fee"]),trade_value*float(fee_schedules.loc[tier,"rate_bps"])/10000),2)
        trades.append({"trade_id":f"TR-{uuid.uuid4().hex[:10].upper()}","instrument_id":h["instrument_id"],"asset_class":asset,"side":side,"quantity":qty,"price":px,"trade_value":trade_value,"estimated_fee":fee,"fee_tier":tier,"status":"PROPOSED"})
    # Explicit exception reporting for missing/stale prices and excluded instruments.
    for h in snapshot["holdings"]:
        if not h.get("market_price"):
            exceptions.append({"issue_type":"MISSING_PRICE","instrument_id":h["instrument_id"],"severity":"ERROR","message":"No market price; instrument excluded from calculations."})
        elif h.get("price_stale"):
            exceptions.append({"issue_type":"STALE_PRICE","instrument_id":h["instrument_id"],"severity":"WARNING","message":"Price is older than the dataset's latest date; no trade proposed from this holding."})
    # Simulate post-trade values from proposed trades, retaining original history.
    post_values={a["asset_class"]:a["current_value"] for a in snapshot["allocation"]}
    for tr in trades:
        delta=tr["trade_value"] if tr["side"]=="BUY" else -tr["trade_value"]
        post_values[tr["asset_class"]]=post_values.get(tr["asset_class"],0)+delta-tr["estimated_fee"]
    post_total=sum(post_values.values())
    post_alloc=[{"asset_class":asset,"post_trade_value":round(value,2),"post_trade_weight":round(value/post_total,6) if post_total else 0,
        "target_weight":target_by_class[asset]["target_weight"]} for asset,value in post_values.items()]
    status="PROPOSED" if trades else "NO_TRADE"
    result={"proposal_id":f"RB-{datetime.now():%Y}-{uuid.uuid4().hex[:6].upper()}","portfolio_id":portfolio_id,
        "status":status,"reason":"Rules-based simulation; no orders are executed.","trades":trades,"exceptions":exceptions,
        "estimated_fees":round(sum(t["estimated_fee"] for t in trades),2),"post_trade_allocation":post_alloc,
        "current_total_value":snapshot["total_value"],"target_weight_total":snapshot["target_weight_total"]}
    persist_event(result,db_path); return result


def persist_event(proposal: dict, db_path: Path = DB_PATH) -> None:
    """Append-only event persistence: each proposal and trade is recorded, never overwritten."""
    db_path.parent.mkdir(parents=True,exist_ok=True)
    with connect_sqlite(db_path) as con:
        _ensure_event_schema(con)
        con.execute("INSERT OR IGNORE INTO portfolio_registry(portfolio_id) VALUES(?)",
                    (proposal["portfolio_id"],))
        now=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        con.execute("INSERT INTO proposal_events(proposal_id,portfolio_id,created_at,status,payload_json) VALUES(?,?,?,?,?)",
                    (proposal["proposal_id"],proposal["portfolio_id"],now,proposal["status"],json.dumps(proposal)))
        for trade in proposal.get("trades",[]):
            con.execute("INSERT INTO trade_events(proposal_id,trade_id,created_at,payload_json) VALUES(?,?,?,?)",
                        (proposal["proposal_id"],trade["trade_id"],now,json.dumps(trade)))
        con.commit()
