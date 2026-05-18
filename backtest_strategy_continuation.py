import requests
import pandas as pd
# pyrefly: ignore [missing-import]
import pandas_ta as ta
import numpy as np
import time
from datetime import datetime

def fetch_paginated_klines(symbol, interval="15m", total_limit=2880):
    url = "https://fapi.binance.com/fapi/v1/klines"
    all_data = []
    end_time = None
    
    print(f"Mengambil data OHLCV historis (Target: {total_limit} candle)...")
    while len(all_data) < total_limit:
        limit = min(1000, total_limit - len(all_data))
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if end_time:
            params["endTime"] = end_time
            
        response = requests.get(url, params=params)
        data = response.json()
        
        if not data or type(data) is dict:
            break
            
        all_data = data + all_data
        end_time = data[0][0] - 1
        time.sleep(0.1)
        
    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"])
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df

def fetch_paginated_oi(symbol, period="15m", total_limit=2880):
    url = "https://fapi.binance.com/futures/data/openInterestHist"
    all_data = []
    end_time = None
    
    print(f"Mengambil data Open Interest historis...")
    while len(all_data) < total_limit:
        limit = min(500, total_limit - len(all_data))
        params = {"symbol": symbol, "period": period, "limit": limit}
        if end_time:
            params["endTime"] = end_time
            
        response = requests.get(url, params=params)
        data = response.json()
        
        if not data or type(data) is dict or len(data) == 0:
            break
            
        all_data = data + all_data
        end_time = data[0]['timestamp'] - 1
        time.sleep(0.1)
        
    df = pd.DataFrame(all_data)
    if not df.empty:
        df.drop_duplicates(subset=['timestamp'], inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["sumOpenInterestValue"] = df["sumOpenInterestValue"].astype(float)
        df = df[["timestamp", "sumOpenInterestValue"]]
        df.rename(columns={"sumOpenInterestValue": "openInterest"}, inplace=True)
    return df

def fetch_funding_rate(symbol, limit=1000):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": limit}
    response = requests.get(url, params=params).json()
    df = pd.DataFrame(response)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms")
        df["fundingRate"] = df["fundingRate"].astype(float)
        df = df[["timestamp", "fundingRate"]]
    return df

def is_in_active_session(timestamp):
    # Waktu Binance API adalah UTC
    hour = timestamp.hour
    
    # London Open: 07:00 - 10:00 UTC (14:00 - 17:00 WIB)
    is_london = (7 <= hour <= 10)
    
    # US Open: 12:00 - 16:00 UTC (19:00 - 23:00 WIB)
    is_us = (12 <= hour <= 16)
    
    return is_london or is_us

def main():
    symbol = "PENGUUSDT"
    print(f"Memulai Backtest Ekstensif (Continuation Strategy) untuk {symbol}...")
    
    # 1. Fetch Data (~30 hari)
    df_klines = fetch_paginated_klines(symbol, "15m", 3000)
    df_oi = fetch_paginated_oi(symbol, "15m", 3000)
    df_funding = fetch_funding_rate(symbol, 1000)
    
    if df_klines.empty or df_oi.empty:
        print("Gagal mengambil data. Coba lagi.")
        return
        
    print(f"Data terkumpul: {len(df_klines)} candles.")
    
    # 2. Merge Datasets
    df = pd.merge(df_klines, df_oi, on="timestamp", how="left")
    df = pd.merge_asof(df.sort_values('timestamp'), df_funding.sort_values('timestamp'), on='timestamp', direction='backward')
    
    print("Menghitung Indikator Teknikal...")
    # EMA
    df['EMA_9'] = ta.ema(df['close'], length=9)
    df['EMA_21'] = ta.ema(df['close'], length=21)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    
    # Volume SMA
    df['Volume_SMA'] = ta.sma(df['volume'], length=20)
    
    # Heatmap Proxy (Swing High & Low)
    window = 30
    df['Swing_High'] = df['high'].rolling(window=window, min_periods=5).max().shift(1)
    df['Swing_Low'] = df['low'].rolling(window=window, min_periods=5).min().shift(1)
    
    df['OI_Change'] = df['openInterest'].pct_change() * 100
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    print("Menjalankan Logika Backtest Trend Continuation...")
    signals = []
    
    STOP_LOSS_PCT = 0.02   # Base SL 2%
    
    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        candle_range = current['high'] - current['low']
        
        is_active_session = is_in_active_session(current['timestamp'])
        
        # ---- KONDISI BULLISH CONTINUATION (LONG) ----
        # 1. Trend Filter
        trend_bullish = current['EMA_50'] > current['EMA_200'] and current['close'] > current['Swing_Low']
        
        # 2. Sweep: Harga turun ke bawah Swing Low lalu close di atasnya
        sweep_bullish = (current['low'] < current['Swing_Low']) and (current['close'] > current['Swing_Low'])
        
        # 3. Candle Continuation (Wick panjang di bawah atau body besar)
        lower_tail = min(current['open'], current['close']) - current['low']
        is_pin_bar_bull = (lower_tail / candle_range > 0.6) if candle_range > 0 else False
        is_engulfing_bull = (current['close'] > prev['open']) and (current['open'] < prev['close']) and (prev['close'] < prev['open'])
        candle_bullish = is_pin_bar_bull or is_engulfing_bull
        
        # 4. Reclaim / Momentum
        momentum_bullish = current['close'] > current['EMA_9'] or current['close'] > current['EMA_21']
        
        # 5. Volume Confirmation
        volume_bullish = current['volume'] > current['Volume_SMA']
        
        # 6. OI Drop
        oi_drop_bullish = current['OI_Change'] < -0.5
        
        # 7. Funding
        funding_bullish = current['fundingRate'] < 0
        
        # Skoring untuk syarat tambahan
        score = sum([candle_bullish, momentum_bullish, volume_bullish, oi_drop_bullish, funding_bullish, is_active_session])
        
        # Konfluensi Continuation
        if trend_bullish and sweep_bullish and score >= 3:
            signals.append({
                'Time': current['timestamp'], 'Type': 'LONG', 
                'Entry_Price': current['close'], 'Score': f"{score}/6"
            })
            
        # ---- KONDISI BEARISH CONTINUATION (SHORT) ----
        # 1. Trend Filter
        trend_bearish = current['EMA_50'] < current['EMA_200'] and current['close'] < current['Swing_High']
        
        # 2. Sweep: Harga naik ke atas Swing High lalu close di bawahnya
        sweep_bearish = (current['high'] > current['Swing_High']) and (current['close'] < current['Swing_High'])
        
        # 3. Candle Continuation
        upper_tail = current['high'] - max(current['open'], current['close'])
        is_pin_bar_bear = (upper_tail / candle_range > 0.6) if candle_range > 0 else False
        is_engulfing_bear = (current['close'] < prev['open']) and (current['open'] > prev['close']) and (prev['close'] > prev['open'])
        candle_bearish = is_pin_bar_bear or is_engulfing_bear
        
        # 4. Reclaim / Momentum
        momentum_bearish = current['close'] < current['EMA_9'] or current['close'] < current['EMA_21']
        
        # 5. Volume Confirmation
        volume_bearish = current['volume'] > current['Volume_SMA']
        
        # 6. OI Drop
        oi_drop_bearish = current['OI_Change'] < -0.5
        
        # 7. Funding
        funding_bearish = current['fundingRate'] > 0
        
        score_bear = sum([candle_bearish, momentum_bearish, volume_bearish, oi_drop_bearish, funding_bearish, is_active_session])
        
        if trend_bearish and sweep_bearish and score_bear >= 3:
            signals.append({
                'Time': current['timestamp'], 'Type': 'SHORT', 
                'Entry_Price': current['close'], 'Score': f"{score_bear}/6"
            })
            
    # --- PnL Calculation (Forward Checking for Signals) ---
    final_signals = []
    
    for s in signals:
        signal_time = s['Time']
        signal_idx_list = df.index[df['timestamp'] == signal_time].tolist()
        if not signal_idx_list: continue
        signal_idx = signal_idx_list[0]
        
        future_df = df.iloc[signal_idx+1:]
        current_close = s['Entry_Price']
        
        if s['Type'] == 'LONG':
            sl_price = current_close * (1 - STOP_LOSS_PCT)
            max_price_reached = current_close
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['high'] > max_price_reached:
                    max_price_reached = f_bar['high']
                if f_bar['low'] <= sl_price:
                    break
            profit_pct = (max_price_reached - current_close) / current_close
            s['Max_RR'] = profit_pct / STOP_LOSS_PCT
            
        else: # SHORT
            sl_price = current_close * (1 + STOP_LOSS_PCT)
            min_price_reached = current_close
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['low'] < min_price_reached:
                    min_price_reached = f_bar['low']
                if f_bar['high'] >= sl_price:
                    break
            profit_pct = (current_close - min_price_reached) / current_close
            s['Max_RR'] = profit_pct / STOP_LOSS_PCT
            
        final_signals.append(s)
            
    # Print Hasil & Statistik
    print("="*70)
    print(f"Total Sinyal (1 Bulan Terakhir): {len(final_signals)}")
    print(f"Toleransi Stop Loss (Base): {STOP_LOSS_PCT*100}%")
    print("-" * 70)
    
    rr_2_count = 0
    rr_3_count = 0
    rr_5_count = 0
    
    initial_balance = 10.0
    current_balance = initial_balance
    
    for s in final_signals:
        rr = s['Max_RR']
        status = "[LOSS]"
        
        if rr >= 2:
            current_balance += current_balance * (STOP_LOSS_PCT * 2)
        else:
            current_balance -= current_balance * STOP_LOSS_PCT

        if rr >= 5: 
            status = "[WIN ⭐⭐⭐] (Mencapai RR 1:5)"
            rr_5_count += 1
        elif rr >= 3:
            status = "[WIN ⭐⭐] (Mencapai RR 1:3)"
            rr_3_count += 1
        elif rr >= 2:
            status = "[WIN ⭐] (Mencapai RR 1:2)"
            rr_2_count += 1
            
        print(f"{s['Time']} | {s['Type']:<5} at {s['Entry_Price']:.6f} | Score: {s['Score']} | Max RR: 1:{rr:.1f} | Saldo: ${current_balance:.2f} | {status}")
        
    total_signals = len(final_signals)
    total_wins_rr2 = rr_2_count + rr_3_count + rr_5_count
    win_rate = (total_wins_rr2 / total_signals * 100) if total_signals > 0 else 0.0
    total_profit_pct = ((current_balance - initial_balance) / initial_balance) * 100
    
    print("=" * 70)
    print("STATISTIK CONTINUATION STRATEGY:")
    print(f"Sinyal menyentuh TP RR 1:2 : {total_wins_rr2} Trades")
    print(f"Sinyal menyentuh TP RR 1:3 : {rr_3_count + rr_5_count} Trades")
    print(f"Sinyal menyentuh TP RR 1:5 : {rr_5_count} Trades")
    print("-" * 70)
    print(f"Total Sinyal  : {total_signals} Trades")
    print(f"Total Win     : {total_wins_rr2} Trades (Tembus minimal RR 1:2)")
    print(f"Total Loss    : {total_signals - total_wins_rr2} Trades (Gagal menyentuh RR 1:2)")
    print(f"Rata-rata Win Rate (RR 1:2): {win_rate:.2f}%")
    print("-" * 70)
    print(f"Saldo Awal    : ${initial_balance:.2f}")
    print(f"Saldo Akhir   : ${current_balance:.2f} (Menggunakan Compounding)")
    print(f"Total PnL     : {total_profit_pct:.2f}%")
    print("=" * 70)

if __name__ == "__main__":
    main()
