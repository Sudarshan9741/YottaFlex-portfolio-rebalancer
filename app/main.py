from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config import DB_PATH, DATA_DIR, ROOT
from app.generator import generate_dataset
from app.engine import connect_sqlite, load_data, compute_portfolio, create_proposal

app=FastAPI(title="YottaFlex Portfolio Rebalancer",version="1.0.0",description="Synthetic portfolio analysis and policy-constrained rebalance simulation.")
STATIC=ROOT/"static"
app.mount("/static",StaticFiles(directory=STATIC),name="static")

@app.on_event("startup")
def startup():
    if not (DATA_DIR/"portfolios.csv").exists():
        generate_dataset(DATA_DIR,portfolios=20,instruments=100,trading_days=60)

@app.get("/",response_class=HTMLResponse)
def home(): return (STATIC/"index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health(): return {"status":"ok","service":"portfolio-rebalancer","data_dir":str(DATA_DIR)}

@app.get("/api/summary")
def summary():
    data=load_data(); proposals=0
    if DB_PATH.exists():
        with connect_sqlite(DB_PATH) as con:
            try: proposals=con.execute("SELECT COUNT(*) FROM proposal_events").fetchone()[0]
            except sqlite3.OperationalError: pass
    return {"portfolios":len(data["portfolios"]),"instruments":len(data["instruments"]),"holdings":len(data["holdings"]),"prices":len(data["market_prices"]),"proposals_created":proposals}

@app.get("/api/portfolios")
def portfolios():
    data=load_data(); df=data["portfolios"].merge(data["investor_profiles"],on="investor_id",validate="many_to_one")
    return df.to_dict(orient="records")

@app.get("/api/portfolios/{portfolio_id}")
def portfolio_detail(portfolio_id:str):
    try: return compute_portfolio(portfolio_id,load_data())
    except KeyError as e: raise HTTPException(status_code=404,detail=str(e))

@app.post("/api/portfolios/{portfolio_id}/rebalance")
def rebalance(portfolio_id:str):
    try: return create_proposal(portfolio_id,load_data(),DB_PATH)
    except KeyError as e: raise HTTPException(status_code=404,detail=str(e))

@app.get("/api/proposals")
def proposal_history():
    if not DB_PATH.exists(): return []
    with connect_sqlite(DB_PATH) as con:
        try: rows=con.execute("SELECT payload_json FROM proposal_events ORDER BY event_id DESC LIMIT 100").fetchall()
        except sqlite3.OperationalError: return []
    import json
    return [json.loads(r[0]) for r in rows]

@app.post("/api/admin/regenerate")
def regenerate(portfolios:int=20,instruments:int=100,trading_days:int=60,seed:int=20261022):
    if not 1 <= portfolios <= 1000:
        raise HTTPException(status_code=400,detail="portfolios must be between 1 and 1000.")
    if not portfolios * 5 <= instruments <= 5000:
        raise HTTPException(status_code=400,detail="instruments must be between portfolios * 5 and 5000.")
    if not 2 <= trading_days <= 250:
        raise HTTPException(status_code=400,detail="trading_days must be between 2 and 250.")
    try:
        return generate_dataset(DATA_DIR,portfolios,instruments,trading_days,seed)
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
