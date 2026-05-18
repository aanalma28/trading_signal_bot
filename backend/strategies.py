import pandas as pd
# pyrefly: ignore [missing-import]
import pandas_ta as ta

def run_reversal_backtest(df, stop_loss_pct=0.02):
    print("Calculating Technical Indicators (Reversal)...")
    # EMA
    df['EMA_9'] = ta.ema(df['close'], length=9)
    df['EMA_21'] = ta.ema(df['close'], length=21)
    
    # RSI
    df['RSI'] = ta.rsi(df['close'], length=14)
    
    # Heatmap Proxy (Swing High & Low)
    window = 30
    df['Swing_High'] = df['high'].rolling(window=window, min_periods=5).max().shift(1)
    df['Swing_Low'] = df['low'].rolling(window=window, min_periods=5).min().shift(1)
    
    df['openInterest'] = df['openInterest'].ffill().bfill()
    df['OI_Change'] = df['openInterest'].pct_change() * 100
    df['OI_Change'] = df['OI_Change'].fillna(0)
    df['fundingRate'] = df['fundingRate'].fillna(0)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    signals = []
    
    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        candle_range = current['high'] - current['low']
        
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
        
        score_bull = sum([candle_bull, oi_bull, funding_bull, rsi_bull, momentum_bull])
        
        if heatmap_bull and sweep_bull and score_bull >= 3:
            total_met = score_bull + 3
            stars = "⭐⭐⭐⭐⭐" if total_met >= 8 else "⭐⭐⭐⭐" if total_met >= 6 else "⭐⭐⭐"
            checklist = [
                {"condition": "Heatmap: Ada area cerah di bawah", "met": bool(heatmap_bull)},
                {"condition": "Liquidity Sweep: Harga menusuk ke bawah lalu reclaim cepat", "met": bool(sweep_bull)},
                {"condition": "Karakter Candle: Muncul Pin Bar atau Engulfing", "met": bool(candle_bull)},
                {"condition": "OI: Turun tajam saat sweep", "met": bool(oi_bull)},
                {"condition": "Funding Rate: Negatif/turun", "met": bool(funding_bull)},
                {"condition": "RSI: Terjadi Divergence", "met": bool(rsi_bull)},
                {"condition": "Struktur (ChoCh): Harga menembus swing (Proxy)", "met": True}, # Proxy
                {"condition": "EMA: Close di atas EMA 9/21", "met": bool(momentum_bull)}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'LONG',
                'Entry_Price': current['close'],
                'Stars': stars,
                'Checklist': checklist
            })
            
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
        
        score_bear = sum([candle_bear, oi_bear, funding_bear, rsi_bear, momentum_bear])
        
        if heatmap_bear and sweep_bear and score_bear >= 3:
            total_met = score_bear + 3
            stars = "⭐⭐⭐⭐⭐" if total_met >= 8 else "⭐⭐⭐⭐" if total_met >= 6 else "⭐⭐⭐"
            checklist = [
                {"condition": "Heatmap: Ada area cerah di atas", "met": bool(heatmap_bear)},
                {"condition": "Liquidity Sweep: Harga menusuk ke atas lalu reject cepat", "met": bool(sweep_bear)},
                {"condition": "Karakter Candle: Muncul Pin Bar atau Engulfing", "met": bool(candle_bear)},
                {"condition": "OI: Turun tajam saat sweep", "met": bool(oi_bear)},
                {"condition": "Funding Rate: Positif/naik", "met": bool(funding_bear)},
                {"condition": "RSI: Terjadi Divergence", "met": bool(rsi_bear)},
                {"condition": "Struktur (ChoCh): Harga menembus swing (Proxy)", "met": True},
                {"condition": "EMA: Close di bawah EMA 9/21", "met": bool(momentum_bear)}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'SHORT',
                'Entry_Price': current['close'],
                'Stars': stars,
                'Checklist': checklist
            })
            
    return evaluate_pnl(df, signals, stop_loss_pct)

def is_in_active_session(timestamp):
    hour = timestamp.hour
    is_london = (7 <= hour <= 10)
    is_us = (12 <= hour <= 16)
    return is_london or is_us

def run_continuation_backtest(df, stop_loss_pct=0.02):
    print("Calculating Technical Indicators (Continuation)...")
    df['EMA_9'] = ta.ema(df['close'], length=9)
    df['EMA_21'] = ta.ema(df['close'], length=21)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['Volume_SMA'] = ta.sma(df['volume'], length=20)
    
    window = 30
    df['Swing_High'] = df['high'].rolling(window=window, min_periods=5).max().shift(1)
    df['Swing_Low'] = df['low'].rolling(window=window, min_periods=5).min().shift(1)
    
    df['openInterest'] = df['openInterest'].ffill().bfill()
    df['OI_Change'] = df['openInterest'].pct_change() * 100
    df['OI_Change'] = df['OI_Change'].fillna(0)
    df['fundingRate'] = df['fundingRate'].fillna(0)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    signals = []
    
    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        candle_range = current['high'] - current['low']
        is_active_session = is_in_active_session(current['timestamp'])
        
        # BULLISH CONTINUATION
        trend_bull = current['EMA_50'] > current['EMA_200'] and current['close'] > current['Swing_Low']
        sweep_bull = (current['low'] < current['Swing_Low']) and (current['close'] > current['Swing_Low'])
        
        lower_tail = min(current['open'], current['close']) - current['low']
        candle_bull = (lower_tail / candle_range > 0.6) if candle_range > 0 else False
        
        momentum_bull = current['close'] > current['EMA_9'] or current['close'] > current['EMA_21']
        volume_bull = current['volume'] > current['Volume_SMA']
        oi_bull = current['OI_Change'] < -0.5
        funding_bull = current['fundingRate'] < 0
        
        score_bull = sum([candle_bull, momentum_bull, volume_bull, oi_bull, funding_bull, is_active_session])
        
        if trend_bull and sweep_bull and score_bull >= 3:
            total_met = score_bull + 4
            stars = "⭐⭐⭐⭐⭐" if total_met >= 9 else "⭐⭐⭐⭐" if total_met >= 7 else "⭐⭐⭐"
            checklist = [
                {"condition": "1. Trend Utama Kuat (EMA 50 > 200)", "met": bool(trend_bull)},
                {"condition": "2. Harga sweep ke arah berlawanan", "met": bool(sweep_bull)},
                {"condition": "3. OI turun tajam saat sweep", "met": bool(oi_bull)},
                {"condition": "4. Reclaim struktur minor", "met": True},
                {"condition": "5. Candle continuation kuat", "met": bool(candle_bull)},
                {"condition": "6. Harga kembali close sesuai tren (EMA 9/21)", "met": bool(momentum_bull)},
                {"condition": "7. Peningkatan volume", "met": bool(volume_bull)},
                {"condition": "8. Funding rate berlawanan tren", "met": bool(funding_bull)},
                {"condition": "9. Volatilitas tinggi (London/US Open)", "met": bool(is_active_session)},
                {"condition": "10. Struktur HTF terjaga", "met": True}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'LONG',
                'Entry_Price': current['close'],
                'Stars': stars,
                'Checklist': checklist
            })
            
        # BEARISH CONTINUATION
        trend_bear = current['EMA_50'] < current['EMA_200'] and current['close'] < current['Swing_High']
        sweep_bear = (current['high'] > current['Swing_High']) and (current['close'] < current['Swing_High'])
        
        upper_tail = current['high'] - max(current['open'], current['close'])
        candle_bear = (upper_tail / candle_range > 0.6) if candle_range > 0 else False
        
        momentum_bear = current['close'] < current['EMA_9'] or current['close'] < current['EMA_21']
        volume_bear = current['volume'] > current['Volume_SMA']
        oi_bear = current['OI_Change'] < -0.5
        funding_bear = current['fundingRate'] > 0
        
        score_bear = sum([candle_bear, momentum_bear, volume_bear, oi_bear, funding_bear, is_active_session])
        
        if trend_bear and sweep_bear and score_bear >= 3:
            total_met = score_bear + 4
            stars = "⭐⭐⭐⭐⭐" if total_met >= 9 else "⭐⭐⭐⭐" if total_met >= 7 else "⭐⭐⭐"
            checklist = [
                {"condition": "1. Trend Utama Kuat (EMA 50 < 200)", "met": bool(trend_bear)},
                {"condition": "2. Harga sweep ke arah berlawanan", "met": bool(sweep_bear)},
                {"condition": "3. OI turun tajam saat sweep", "met": bool(oi_bear)},
                {"condition": "4. Reclaim struktur minor", "met": True},
                {"condition": "5. Candle continuation kuat", "met": bool(candle_bear)},
                {"condition": "6. Harga kembali close sesuai tren (EMA 9/21)", "met": bool(momentum_bear)},
                {"condition": "7. Peningkatan volume", "met": bool(volume_bear)},
                {"condition": "8. Funding rate berlawanan tren", "met": bool(funding_bear)},
                {"condition": "9. Volatilitas tinggi (London/US Open)", "met": bool(is_active_session)},
                {"condition": "10. Struktur HTF terjaga", "met": True}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'SHORT',
                'Entry_Price': current['close'],
                'Stars': stars,
                'Checklist': checklist
            })
            
    return evaluate_pnl(df, signals, stop_loss_pct)

def evaluate_pnl(df, signals, stop_loss_pct):
    final_signals = []
    for s in signals:
        signal_time = pd.to_datetime(s['Time'])
        signal_idx_list = df.index[df['timestamp'] == signal_time].tolist()
        if not signal_idx_list: continue
        signal_idx = signal_idx_list[0]
        
        future_df = df.iloc[signal_idx+1:]
        current_close = s['Entry_Price']
        
        if s['Type'] == 'LONG':
            sl_price = current_close * (1 - stop_loss_pct)
            tp_price = current_close * (1 + (stop_loss_pct * 2))
            s['SL_Price'] = sl_price
            s['TP_Price'] = tp_price
            
            max_price_reached = current_close
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['high'] > max_price_reached:
                    max_price_reached = f_bar['high']
                if f_bar['low'] <= sl_price:
                    break
            profit_pct = (max_price_reached - current_close) / current_close
            s['Max_RR'] = profit_pct / stop_loss_pct
        else:
            sl_price = current_close * (1 + stop_loss_pct)
            tp_price = current_close * (1 - (stop_loss_pct * 2))
            s['SL_Price'] = sl_price
            s['TP_Price'] = tp_price
            
            min_price_reached = current_close
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['low'] < min_price_reached:
                    min_price_reached = f_bar['low']
                if f_bar['high'] >= sl_price:
                    break
            profit_pct = (current_close - min_price_reached) / current_close
            s['Max_RR'] = profit_pct / stop_loss_pct
            
        final_signals.append(s)
    return final_signals
