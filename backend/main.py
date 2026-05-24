# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, Depends, Request
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

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from data_fetcher import fetch_all_data
from strategies import run_reversal_backtest, run_continuation_backtest

import pandas as pd

from database import engine, Base, get_db
import models
import auth
# pyrefly: ignore [missing-import]
from slowapi import Limiter, _rate_limit_exceeded_handler
# pyrefly: ignore [missing-import]
from slowapi.util import get_remote_address
# pyrefly: ignore [missing-import]
from slowapi.errors import RateLimitExceeded

# Inisialisasi DB
Base.metadata.create_all(bind=engine)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Buat default user saat startup
def init_db():
    db = next(get_db())
    if not db.query(models.User).first():
        admin = models.User(username="admin", hashed_password=auth.get_password_hash("admin123"), role="admin")
        user = models.User(username="user", hashed_password=auth.get_password_hash("user123"), role="user")
        db.add(admin)
        db.add(user)
        db.commit()

init_db()

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
    monthly_topup: float = 0.0

def is_bot_running():
    try:
        subprocess.check_output(["pgrep", "-f", "bot_telegram.py"])
        return True
    except subprocess.CalledProcessError:
        return False

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or not auth.verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Username atau password salah")
    
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

@app.get("/api/bot/status")
def get_bot_status(current_user: models.User = Depends(auth.get_current_user)):
    return {"running": is_bot_running()}

@app.post("/api/bot/start")
def start_bot(current_user: models.User = Depends(auth.require_admin)):
    if is_bot_running():
        return {"status": "already_running"}
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    bot_script_path = os.path.join(current_dir, "bot_telegram.py")
    
    subprocess.Popen([sys.executable, "-u", bot_script_path])
    return {"status": "started"}

@app.post("/api/bot/stop")
def stop_bot(current_user: models.User = Depends(auth.require_admin)):
    if is_bot_running():
        subprocess.run(["pkill", "-f", "bot_telegram.py"])
        return {"status": "stopped"}
    return {"status": "not_running"}


@app.post("/api/backtest")
@limiter.limit("20/minute")
def run_backtest(request: Request, req: BacktestRequest, current_user: models.User = Depends(auth.get_current_user)):
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
            signals = run_reversal_backtest(df)
        elif req.strategy == "continuation":
            signals = run_continuation_backtest(df)
        else:
            raise HTTPException(status_code=400, detail="Strategi tidak dikenali")
            
        # PnL simulation based on signals
        current_balance = req.initial_balance
        rr_2_count = 0
        rr_3_count = 0
        rr_5_count = 0
        
        results = []
        stop_loss_dec = 0.02  # Hardcode 2% account risk per trade
        
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
            
            target_rr = s.get('TP_RR', 2.0)
            
            # Jika Max_RR melebihi atau sama dengan target RR, maka dianggap WIN
            if rr >= target_rr:
                current_balance += current_balance * (stop_loss_dec * target_rr)
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
                "target_note": s.get("Target_Note", ""),
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
