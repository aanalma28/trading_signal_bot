# pyrefly: ignore [missing-import]
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from typing import Optional
from datetime import datetime, timezone
import subprocess
import sys
import os

from data_fetcher import fetch_all_data
from strategies import run_reversal_backtest, run_continuation_backtest

import pandas as pd

app = FastAPI()

# Global variable to hold the bot process
bot_process = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BacktestRequest(BaseModel):
    strategy: str # "reversal" or "continuation"
    symbol: str
    interval: str
    start_date: str
    end_date: str
    initial_balance: float
    stop_loss_pct: float
    monthly_topup: float = 0.0

def is_bot_running():
    try:
        subprocess.check_output(["pgrep", "-f", "bot_telegram.py"])
        return True
    except subprocess.CalledProcessError:
        return False

@app.get("/api/bot/status")
def get_bot_status():
    return {"running": is_bot_running()}

@app.post("/api/bot/start")
def start_bot():
    if is_bot_running():
        return {"status": "already_running"}
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    bot_script_path = os.path.join(current_dir, "bot_telegram.py")
    
    subprocess.Popen([sys.executable, bot_script_path])
    return {"status": "started"}

@app.post("/api/bot/stop")
def stop_bot():
    if is_bot_running():
        subprocess.run(["pkill", "-f", "bot_telegram.py"])
        return {"status": "stopped"}
    return {"status": "not_running"}


@app.post("/api/backtest")
def run_backtest(req: BacktestRequest):
    try:
        start_dt_naive = datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt_naive = datetime.strptime(req.end_date, "%Y-%m-%d")
        limit_days = (end_dt_naive - start_dt_naive).days
        
        if limit_days <= 0:
            raise HTTPException(status_code=400, detail="Tanggal akhir harus setelah tanggal awal")
            
        end_dt_with_time = end_dt_naive.replace(hour=23, minute=59, second=59)
        end_time_ms = int(end_dt_with_time.replace(tzinfo=timezone.utc).timestamp() * 1000)

        df = fetch_all_data(req.symbol, req.interval, limit_days, end_time_ms)
        if df.empty:
            raise HTTPException(status_code=404, detail="Gagal mengambil data dari Binance")
            
        if req.strategy == "reversal":
            signals = run_reversal_backtest(df, req.stop_loss_pct / 100.0)
        elif req.strategy == "continuation":
            signals = run_continuation_backtest(df, req.stop_loss_pct / 100.0)
        else:
            raise HTTPException(status_code=400, detail="Strategi tidak dikenali")
            
        # PnL simulation based on signals
        current_balance = req.initial_balance
        rr_2_count = 0
        rr_3_count = 0
        rr_5_count = 0
        
        results = []
        stop_loss_dec = req.stop_loss_pct / 100.0
        
        start_date = start_dt_naive
        next_topup_date = start_date + pd.Timedelta(days=30)
            
        total_topup = 0.0
        
        for s in signals:
            dt = pd.to_datetime(s['Time'])
            
            while dt >= next_topup_date:
                current_balance += req.monthly_topup
                total_topup += req.monthly_topup
                next_topup_date += pd.Timedelta(days=30)
                
            rr = s['Max_RR']
            status = "LOSS"
            
            # RR >= 2 is considered a WIN since we target RR 1:2
            if rr >= 2:
                current_balance += current_balance * (stop_loss_dec * 2)
                status = "WIN"
            else:
                current_balance -= current_balance * stop_loss_dec

            if rr >= 5: rr_5_count += 1
            if rr >= 3: rr_3_count += 1
            if rr >= 2: rr_2_count += 1
                
            results.append({
                "time": s["Time"],
                "type": s["Type"],
                "entry_price": s["Entry_Price"],
                "sl_price": s.get("SL_Price", 0),
                "tp_price": s.get("TP_Price", 0),
                "stars": s.get("Stars", "⭐⭐⭐"),
                "max_rr": rr,
                "status": status,
                "balance_after": current_balance,
                "checklist": s["Checklist"]
            })
            
        # Ensure topups continue until the end of the dataframe
        end_date = end_dt_with_time
            
        while end_date >= next_topup_date:
            current_balance += req.monthly_topup
            total_topup += req.monthly_topup
            next_topup_date += pd.Timedelta(days=30)
            
        total_signals = len(signals)
        total_wins = rr_2_count
        win_rate = (total_wins / total_signals * 100) if total_signals > 0 else 0
        total_invested = req.initial_balance + total_topup
        total_pnl = ((current_balance - total_invested) / total_invested * 100) if total_invested > 0 else 0
        
        return {
            "statistics": {
                "total_signals": total_signals,
                "total_wins": total_wins,
                "total_loss": total_signals - total_wins,
                "win_rate": win_rate,
                "initial_balance": req.initial_balance,
                "total_invested": total_invested,
                "final_balance": current_balance,
                "total_pnl": total_pnl,
                "rr_1_2": rr_2_count,
                "rr_1_3": rr_3_count,
                "rr_1_5": rr_5_count
            },
            "trades": results
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
