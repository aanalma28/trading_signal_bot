import requests
import pandas as pd
# pyrefly: ignore [missing-import]
import pandas_ta as ta
import numpy as np
import time
from datetime import datetime

def fetch_paginated_klines(symbol, interval="15m", total_limit=2880): # 2880 = 30 days
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
            
        all_data = data + all_data # Prepend older data
        end_time = data[0][0] - 1 # Waktu sebelum candle pertama
        time.sleep(0.1) # Hindari rate limit
        
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

def fetch_funding_rate(symbol, limit=1000): # 1000 sudah mengcover > 1 tahun
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": limit}
    response = requests.get(url, params=params).json()
    df = pd.DataFrame(response)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms")
        df["fundingRate"] = df["fundingRate"].astype(float)
        df = df[["timestamp", "fundingRate"]]
    return df

def main():
    symbol = "PENGUUSDT"
    print(f"Memulai Backtest Ekstensif untuk {symbol}...")
    
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
    df['EMA_9'] = ta.ema(df['close'], length=9)
    df['EMA_21'] = ta.ema(df['close'], length=21)
    df['RSI_14'] = ta.rsi(df['close'], length=14)
    
    # Proxy Heatmap
    window = 30
    df['Swing_High'] = df['high'].rolling(window=window, min_periods=5).max().shift(1)
    df['Swing_Low'] = df['low'].rolling(window=window, min_periods=5).min().shift(1)
    
    df['OI_Change'] = df['openInterest'].pct_change() * 100
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    print("Menjalankan Logika Backtest (Tracking RR Maximum)...")
    signals = []
    
    # Parameter Risk Management Base
    STOP_LOSS_PCT = 0.02   # Base SL 2%
    
    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        candle_range = current['high'] - current['low']
        
        # BULLISH (LONG)
        sweep_bullish = (current['low'] < current['Swing_Low']) and (current['close'] > current['Swing_Low'])
        lower_tail = min(current['open'], current['close']) - current['low']
        is_pin_bar_bull = (lower_tail / candle_range > 0.6) if candle_range > 0 else False
        is_engulfing_bull = (current['close'] > prev['open']) and (current['open'] < prev['close']) and (prev['close'] < prev['open'])
        candle_bullish = is_pin_bar_bull or is_engulfing_bull
        oi_drop_bullish = current['OI_Change'] < -0.5
        funding_bullish = current['fundingRate'] < 0
        rsi_div_bullish = (current['low'] < prev['low']) and (current['RSI_14'] > prev['RSI_14'])
        ema_bullish = (current['close'] > current['EMA_9']) or (current['close'] > current['EMA_21'])
        
        bullish_score = sum([candle_bullish, oi_drop_bullish, funding_bullish, rsi_div_bullish, ema_bullish])
        
        if sweep_bullish and bullish_score >= 3:
            signal = {
                'Time': current['timestamp'], 'Type': 'LONG', 
                'Entry_Price': current['close'], 'Score': f"{bullish_score}/5"
            }
            
            future_df = df.iloc[i+1:]
            sl_price = current['close'] * (1 - STOP_LOSS_PCT)
            max_price_reached = current['close']
            result_rr = 0.0
            
            # Melacak Maximum Favorable Excursion sebelum kena SL
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['high'] > max_price_reached:
                    max_price_reached = f_bar['high']
                    
                if f_bar['low'] <= sl_price:
                    break
            
            # Menghitung Max RR (Rasio Profit Maksimum dibanding SL 2%)
            profit_pct = (max_price_reached - current['close']) / current['close']
            result_rr = profit_pct / STOP_LOSS_PCT
            
            signal['Max_RR'] = result_rr
            signals.append(signal)
            
        # BEARISH (SHORT)
        sweep_bearish = (current['high'] > current['Swing_High']) and (current['close'] < current['Swing_High'])
        upper_tail = current['high'] - max(current['open'], current['close'])
        is_pin_bar_bear = (upper_tail / candle_range > 0.6) if candle_range > 0 else False
        is_engulfing_bear = (current['close'] < prev['open']) and (current['open'] > prev['close']) and (prev['close'] > prev['open'])
        candle_bearish = is_pin_bar_bear or is_engulfing_bear
        oi_drop_bearish = current['OI_Change'] < -0.5
        funding_bearish = current['fundingRate'] > 0
        rsi_div_bearish = (current['high'] > prev['high']) and (current['RSI_14'] < prev['RSI_14'])
        ema_bearish = (current['close'] < current['EMA_9']) or (current['close'] < current['EMA_21'])
        
        bearish_score = sum([candle_bearish, oi_drop_bearish, funding_bearish, rsi_div_bearish, ema_bearish])
        
        if sweep_bearish and bearish_score >= 3:
            signal = {
                'Time': current['timestamp'], 'Type': 'SHORT', 
                'Entry_Price': current['close'], 'Score': f"{bearish_score}/5"
            }
            
            future_df = df.iloc[i+1:]
            sl_price = current['close'] * (1 + STOP_LOSS_PCT)
            min_price_reached = current['close']
            result_rr = 0.0
            
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['low'] < min_price_reached:
                    min_price_reached = f_bar['low']
                    
                if f_bar['high'] >= sl_price:
                    break
                    
            profit_pct = (current['close'] - min_price_reached) / current['close']
            result_rr = profit_pct / STOP_LOSS_PCT
            
            signal['Max_RR'] = result_rr
            signals.append(signal)
            
    print("="*70)
    print(f"Total Sinyal (1 Bulan Terakhir): {len(signals)}")
    print(f"Toleransi Stop Loss (Base): {STOP_LOSS_PCT*100}%")
    print("-" * 70)
    
    rr_2_count = 0
    rr_3_count = 0
    rr_5_count = 0
    
    # Simulasi Saldo
    initial_balance = 10.0
    current_balance = initial_balance
    
    for s in signals:
        rr = s['Max_RR']
        status = "[LOSS]"
        
        # PnL Calculation (Menggunakan Compounding)
        if rr >= 2:
            # Dianggap WIN di RR 1:2 (Profit 4%)
            current_balance += current_balance * (STOP_LOSS_PCT * 2)
        else:
            # Dianggap LOSS (Rugi 2%)
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
        
    total_signals = len(signals)
    total_wins_rr2 = rr_2_count + rr_3_count + rr_5_count
    win_rate = (total_wins_rr2 / total_signals * 100) if total_signals > 0 else 0.0
    total_profit_pct = ((current_balance - initial_balance) / initial_balance) * 100
    
    print("=" * 70)
    print("STATISTIK KEMAMPUAN MENYENTUH TAKE PROFIT:")
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
