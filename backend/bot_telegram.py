import os
import time
import requests
import schedule
from datetime import datetime
import pandas as pd
# pyrefly: ignore [missing-import]
import pandas_ta as ta
from dotenv import load_dotenv

# Import fungsi dari data_fetcher
from data_fetcher import fetch_paginated_klines, fetch_paginated_oi, fetch_funding_rate, fetch_paginated_ls_ratio

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOL = "PENGUUSDT"

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Bot Token atau Chat ID belum diset! Tidak bisa mengirim pesan.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Gagal mengirim pesan: {response.text}")
        else:
            print("Pesan berhasil dikirim ke Telegram.")
    except Exception as e:
        print(f"Error saat mengirim pesan Telegram: {e}")

def get_live_data():
    print(f"[{datetime.now()}] Mengambil data live {SYMBOL}...")
    # Fetch 1H data for HTF Trend (EMA 50 & 200)
    df_1h = fetch_paginated_klines(SYMBOL, "1h", limit_days=10)
    
    # Fetch 15m data for entry details (Butuh >150 candle untuk Major S/R)
    df_15m_klines = fetch_paginated_klines(SYMBOL, "15m", limit_days=3) # 3 hari = 288 candle
    df_15m_oi = fetch_paginated_oi(SYMBOL, "15m", 288)
    df_15m_ls = fetch_paginated_ls_ratio(SYMBOL, "15m", 288)
    df_funding = fetch_funding_rate(SYMBOL, 50)
    
    # Merge 15m data
    df_15m = pd.merge(df_15m_klines, df_15m_oi, on="timestamp", how="left")
    if not df_15m_ls.empty:
        df_15m = pd.merge(df_15m, df_15m_ls, on="timestamp", how="left")
    else:
        df_15m['longShortRatio'] = 1.0
    df_15m = pd.merge_asof(df_15m.sort_values('timestamp'), df_funding.sort_values('timestamp'), on='timestamp', direction='backward')
    df_15m['fundingRate'] = df_15m['fundingRate'].fillna(0.0)
    df_15m['openInterest'] = df_15m['openInterest'].ffill().bfill()
    df_15m['longShortRatio'] = df_15m['longShortRatio'].ffill().bfill()
    
    return df_1h, df_15m

def is_in_active_session(timestamp):
    hour = timestamp.hour
    is_london = (7 <= hour <= 10)
    is_us = (12 <= hour <= 16)
    return is_london or is_us

def analyze_market():
    try:
        df_1h, df_15m = get_live_data()
        
        if df_1h.empty or df_15m.empty:
            print("Gagal mengambil data.")
            return

        # Calculate HTF (1H) Indicators
        df_1h['EMA_50'] = ta.ema(df_1h['close'], length=50)
        df_1h['EMA_200'] = ta.ema(df_1h['close'], length=200)
        
        last_1h = df_1h.iloc[-2] # Mengambil candle terakhir yang sudah close
        
        # Calculate LTF (15m) Indicators
        df_15m['EMA_9'] = ta.ema(df_15m['close'], length=9)
        df_15m['EMA_21'] = ta.ema(df_15m['close'], length=21)
        df_15m['RSI'] = ta.rsi(df_15m['close'], length=14)
        df_15m['Volume_SMA'] = ta.sma(df_15m['volume'], length=20)
        df_15m['ATR'] = ta.atr(df_15m['high'], df_15m['low'], df_15m['close'], length=14)
        
        # Minor S/R
        df_15m['Swing_High'] = df_15m['high'].rolling(window=30, min_periods=5).max().shift(1)
        df_15m['Swing_Low'] = df_15m['low'].rolling(window=30, min_periods=5).min().shift(1)
        
        # Major S/R
        df_15m['Major_Swing_High'] = df_15m['high'].rolling(window=150, min_periods=10).max().shift(1)
        df_15m['Major_Swing_Low'] = df_15m['low'].rolling(window=150, min_periods=10).min().shift(1)
        
        df_15m['OI_Change'] = df_15m['openInterest'].pct_change() * 100
        df_15m['OI_Change'] = df_15m['OI_Change'].fillna(0)
        
        # Gunakan iloc[-2] karena iloc[-1] adalah candle yang masih berjalan
        current = df_15m.iloc[-2]
        prev = df_15m.iloc[-3]
        
        candle_range = current['high'] - current['low']
        atr = current['ATR'] if pd.notna(current['ATR']) else candle_range
        is_active_session = is_in_active_session(current['timestamp'])
        
        message = ""
        
        # ==========================================
        # 1. CEK STRATEGI REVERSAL (15m Fokus)
        # ==========================================
        # BULLISH REVERSAL
        heatmap_bull = current['low'] < current['Swing_Low']
        sweep_bull = (current['low'] < current['Swing_Low']) and (current['close'] > current['Swing_Low'])
        
        lower_tail = min(current['open'], current['close']) - current['low']
        is_pin_bar_bull = (lower_tail / candle_range > 0.6) if candle_range > 0 else False
        is_engulfing_bull = (current['close'] > prev['open']) and (current['open'] < prev['close']) and (prev['close'] < prev['open'])
        candle_bull = is_pin_bar_bull or is_engulfing_bull
        
        oi_bull = current['OI_Change'] < -0.5
        funding_bull = current['fundingRate'] < 0
        rsi_bull = current['RSI'] > prev['RSI'] and current['low'] < prev['low']
        momentum_bull = current['close'] > current['EMA_9'] or current['close'] > current['EMA_21']
        
        ls_ratio = current.get('longShortRatio', 1.0)
        imbalance_favorable_bull = ls_ratio < 0.95
        imbalance_unfavorable_bull = ls_ratio > 1.05
        
        if heatmap_bull and sweep_bull:
            score = sum([candle_bull, oi_bull, funding_bull, rsi_bull, momentum_bull]) + 3
            if imbalance_favorable_bull:
                score += 2
            elif imbalance_unfavorable_bull:
                score -= 2
                
            entry_price = current['close']
            sl_price = current['Swing_Low'] - (0.5 * atr)
            min_risk = entry_price * 0.005
            if sl_price >= entry_price or (entry_price - sl_price) < min_risk:
                sl_price = entry_price - min_risk
            risk = entry_price - sl_price
            
            major_res = current['Major_Swing_High']
            rr_to_res = (major_res - entry_price) / risk if risk > 0 else 0
            
            if rr_to_res >= 2.0:
                tp_rr = min(rr_to_res, 5.0)
                tp_price = entry_price + (risk * tp_rr)
                score += 2
                target_note = f"Major Resistance (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price + (risk * 2.0)
                score -= 1
                target_note = "Forced RR 1:2 (Major Res Terlalu Dekat)"
                
            stars = "⭐⭐⭐⭐⭐" if score >= 8 else "⭐⭐⭐⭐" if score >= 6 else "⭐⭐⭐"
            if score >= 5: # Minimal grade C
                sl_pct = (risk / entry_price) * 100
                message += f"🟢 *LONG SIGNAL: LIQUIDITY REVERSAL*\n"
                message += f"Pair: {SYMBOL}\nTimeframe: 15m\nRating: {stars}\n\n"
                message += f"🎯 *Target: {target_note}*\n"
                message += f"Entry: `{entry_price:.5f}`\n"
                message += f"SL ({sl_pct:.2f}%): `{sl_price:.5f}` (ATR Buffer)\n"
                message += f"TP: `{tp_price:.5f}`\n\n"
                message += f"*Checklist:*\n"
                message += f"✅ Heatmap: Harga masuk area swing low\n"
                message += f"✅ Liquidity Sweep: Reclaim support cepat\n"
                message += f"✅ Struktur: Harga menembus proxy CHoCH\n"
                message += f"{'✅' if candle_bull else '❌'} Candle Pattern: Pin Bar / Engulfing\n"
                message += f"{'✅' if oi_bull else '❌'} OI: Turun tajam saat sweep\n"
                message += f"{'✅' if funding_bull else '❌'} Funding Rate: Negatif\n"
                message += f"{'✅' if rsi_bull else '❌'} RSI: Divergence terjadi\n"
                message += f"{'✅' if not imbalance_unfavorable_bull else '❌'} Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})\n"
                message += f"{'✅' if momentum_bull else '❌'} EMA: Close di atas 9/21\n"
                
        # BEARISH REVERSAL
        heatmap_bear = current['high'] > current['Swing_High']
        sweep_bear = (current['high'] > current['Swing_High']) and (current['close'] < current['Swing_High'])
        
        upper_tail = current['high'] - max(current['open'], current['close'])
        is_pin_bar_bear = (upper_tail / candle_range > 0.6) if candle_range > 0 else False
        is_engulfing_bear = (current['close'] < prev['open']) and (current['open'] > prev['close']) and (prev['close'] > prev['open'])
        candle_bear = is_pin_bar_bear or is_engulfing_bear
        
        oi_bear = current['OI_Change'] < -0.5
        funding_bear = current['fundingRate'] > 0
        rsi_bear = current['RSI'] < prev['RSI'] and current['high'] > prev['high']
        momentum_bear = current['close'] < current['EMA_9'] or current['close'] < current['EMA_21']
        
        imbalance_favorable_bear = ls_ratio > 1.05
        imbalance_unfavorable_bear = ls_ratio < 0.95
        
        if heatmap_bear and sweep_bear:
            score = sum([candle_bear, oi_bear, funding_bear, rsi_bear, momentum_bear]) + 3
            if imbalance_favorable_bear:
                score += 2
            elif imbalance_unfavorable_bear:
                score -= 2
                
            entry_price = current['close']
            sl_price = current['Swing_High'] + (0.5 * atr)
            min_risk = entry_price * 0.005
            if sl_price <= entry_price or (sl_price - entry_price) < min_risk:
                sl_price = entry_price + min_risk
            risk = sl_price - entry_price
            
            major_sup = current['Major_Swing_Low']
            rr_to_sup = (entry_price - major_sup) / risk if risk > 0 else 0
            
            if rr_to_sup >= 2.0:
                tp_rr = min(rr_to_sup, 5.0)
                tp_price = entry_price - (risk * tp_rr)
                score += 2
                target_note = f"Major Support (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price - (risk * 2.0)
                score -= 1
                target_note = "Forced RR 1:2 (Major Sup Terlalu Dekat)"
                
            stars = "⭐⭐⭐⭐⭐" if score >= 8 else "⭐⭐⭐⭐" if score >= 6 else "⭐⭐⭐"
            if score >= 5:
                sl_pct = (risk / entry_price) * 100
                message += f"🔴 *SHORT SIGNAL: LIQUIDITY REVERSAL*\n"
                message += f"Pair: {SYMBOL}\nTimeframe: 15m\nRating: {stars}\n\n"
                message += f"🎯 *Target: {target_note}*\n"
                message += f"Entry: `{entry_price:.5f}`\n"
                message += f"SL ({sl_pct:.2f}%): `{sl_price:.5f}` (ATR Buffer)\n"
                message += f"TP: `{tp_price:.5f}`\n\n"
                message += f"*Checklist:*\n"
                message += f"✅ Heatmap: Harga masuk area swing high\n"
                message += f"✅ Liquidity Sweep: Reject resistance cepat\n"
                message += f"✅ Struktur: Harga menembus proxy CHoCH\n"
                message += f"{'✅' if candle_bear else '❌'} Candle Pattern: Pin Bar / Engulfing\n"
                message += f"{'✅' if oi_bear else '❌'} OI: Turun tajam saat sweep\n"
                message += f"{'✅' if funding_bear else '❌'} Funding Rate: Positif\n"
                message += f"{'✅' if rsi_bear else '❌'} RSI: Divergence terjadi\n"
                message += f"{'✅' if not imbalance_unfavorable_bear else '❌'} Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})\n"
                message += f"{'✅' if momentum_bear else '❌'} EMA: Close di bawah 9/21\n"


        # ==========================================
        # 2. CEK STRATEGI CONTINUATION (1H Trend + 15m Sweep)
        # ==========================================
        trend_bull = last_1h['EMA_50'] > last_1h['EMA_200']
        volume_bull = current['volume'] > current['Volume_SMA']
        
        if trend_bull and sweep_bull:
            score = sum([candle_bull, momentum_bull, volume_bull, oi_bull, funding_bull, is_active_session]) + 4
            if imbalance_favorable_bull:
                score += 2
            elif imbalance_unfavorable_bull:
                score -= 2
                
            entry_price = current['close']
            sl_price = current['Swing_Low'] - (0.5 * atr)
            min_risk = entry_price * 0.005
            if sl_price >= entry_price or (entry_price - sl_price) < min_risk:
                sl_price = entry_price - min_risk
            risk = entry_price - sl_price
            
            major_res = current['Major_Swing_High']
            rr_to_res = (major_res - entry_price) / risk if risk > 0 else 0
            if rr_to_res >= 2.0:
                tp_rr = min(rr_to_res, 5.0)
                tp_price = entry_price + (risk * tp_rr)
                score += 2
                target_note = f"Major Resistance (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price + (risk * 2.0)
                score -= 1
                target_note = "Forced RR 1:2 (Major Res Terlalu Dekat)"
                
            stars = "⭐⭐⭐⭐⭐" if score >= 9 else "⭐⭐⭐⭐" if score >= 7 else "⭐⭐⭐"
            if score >= 6:
                sl_pct = (risk / entry_price) * 100
                message += f"🟢 *LONG SIGNAL: TREND CONTINUATION*\n"
                message += f"Pair: {SYMBOL}\nTimeframe: 15m (1H Trend)\nRating: {stars}\n\n"
                message += f"🎯 *Target: {target_note}*\n"
                message += f"Entry: `{entry_price:.5f}`\n"
                message += f"SL ({sl_pct:.2f}%): `{sl_price:.5f}` (ATR Buffer)\n"
                message += f"TP: `{tp_price:.5f}`\n\n"
                message += f"*Checklist:*\n"
                message += f"✅ Trend HTF: EMA 50 > 200 (1H)\n"
                message += f"✅ Struktur HTF Terjaga\n"
                message += f"✅ Liquidity Sweep 15m\n"
                message += f"✅ Reclaim Struktur Minor\n"
                message += f"{'✅' if oi_bull else '❌'} OI: Turun tajam saat sweep\n"
                message += f"{'✅' if candle_bull else '❌'} Candle Pattern: Pin bar / Rejection\n"
                message += f"{'✅' if momentum_bull else '❌'} EMA: Close di atas 9/21\n"
                message += f"{'✅' if volume_bull else '❌'} Volume: Meningkat\n"
                message += f"{'✅' if funding_bull else '❌'} Funding Rate: Negatif\n"
                message += f"{'✅' if not imbalance_unfavorable_bull else '❌'} Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})\n"
                message += f"{'✅' if is_active_session else '❌'} Session: Volatilitas tinggi (London/US)\n"

        trend_bear = last_1h['EMA_50'] < last_1h['EMA_200']
        volume_bear = current['volume'] > current['Volume_SMA']
        
        if trend_bear and sweep_bear:
            score = sum([candle_bear, momentum_bear, volume_bear, oi_bear, funding_bear, is_active_session]) + 4
            if imbalance_favorable_bear:
                score += 2
            elif imbalance_unfavorable_bear:
                score -= 2
                
            entry_price = current['close']
            sl_price = current['Swing_High'] + (0.5 * atr)
            min_risk = entry_price * 0.005
            if sl_price <= entry_price or (sl_price - entry_price) < min_risk:
                sl_price = entry_price + min_risk
            risk = sl_price - entry_price
            
            major_sup = current['Major_Swing_Low']
            rr_to_sup = (entry_price - major_sup) / risk if risk > 0 else 0
            if rr_to_sup >= 2.0:
                tp_rr = min(rr_to_sup, 5.0)
                tp_price = entry_price - (risk * tp_rr)
                score += 2
                target_note = f"Major Support (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price - (risk * 2.0)
                score -= 1
                target_note = "Forced RR 1:2 (Major Sup Terlalu Dekat)"
                
            stars = "⭐⭐⭐⭐⭐" if score >= 9 else "⭐⭐⭐⭐" if score >= 7 else "⭐⭐⭐"
            if score >= 6:
                sl_pct = (risk / entry_price) * 100
                message += f"🔴 *SHORT SIGNAL: TREND CONTINUATION*\n"
                message += f"Pair: {SYMBOL}\nTimeframe: 15m (1H Trend)\nRating: {stars}\n\n"
                message += f"🎯 *Target: {target_note}*\n"
                message += f"Entry: `{entry_price:.5f}`\n"
                message += f"SL ({sl_pct:.2f}%): `{sl_price:.5f}` (ATR Buffer)\n"
                message += f"TP: `{tp_price:.5f}`\n\n"
                message += f"*Checklist:*\n"
                message += f"✅ Trend HTF: EMA 50 < 200 (1H)\n"
                message += f"✅ Struktur HTF Terjaga\n"
                message += f"✅ Liquidity Sweep 15m\n"
                message += f"✅ Reclaim Struktur Minor\n"
                message += f"{'✅' if oi_bear else '❌'} OI: Turun tajam saat sweep\n"
                message += f"{'✅' if candle_bear else '❌'} Candle Pattern: Pin bar / Rejection\n"
                message += f"{'✅' if momentum_bear else '❌'} EMA: Close di bawah 9/21\n"
                message += f"{'✅' if volume_bear else '❌'} Volume: Meningkat\n"
                message += f"{'✅' if funding_bear else '❌'} Funding Rate: Positif\n"
                message += f"{'✅' if not imbalance_unfavorable_bear else '❌'} Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})\n"
                message += f"{'✅' if is_active_session else '❌'} Session: Volatilitas tinggi (London/US)\n"

        if message != "":
            send_telegram_message(message)
        else:
            print(f"[{datetime.now()}] Tidak ada sinyal yang memenuhi syarat untuk {SYMBOL}.")
            
        print("Menunggu jadwal cek berikutnya (Menit ke :00, :15, :30, :45)...")
            
    except Exception as e:
        print(f"Terjadi kesalahan saat analisa: {e}")

def run_bot():
    print("Mulai Bot Telegram untuk Liquidity Sweep...")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("PERINGATAN: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset di file .env!")
        print("Bot akan tetap berjalan mencetak log, tetapi tidak bisa mengirim pesan Telegram.")
    
    # Jalankan saat script pertama kali dibuka (untuk testing)
    analyze_market()
    
    # Jadwalkan setiap menit ke-15, 30, 45, 00 sesuai penutupan candle 15m
    schedule.every().hour.at(":00").do(analyze_market)
    schedule.every().hour.at(":15").do(analyze_market)
    schedule.every().hour.at(":30").do(analyze_market)
    schedule.every().hour.at(":45").do(analyze_market)
    
    print("Menunggu jadwal cek berikutnya (Menit ke :00, :15, :30, :45)...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_bot()
