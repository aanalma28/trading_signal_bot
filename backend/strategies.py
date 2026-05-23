import pandas as pd
# pyrefly: ignore [missing-import]
import pandas_ta as ta

def run_reversal_backtest(df, stop_loss_pct=0.02):
    print("Calculating Technical Indicators (Reversal)...")
    df['EMA_9'] = ta.ema(df['close'], length=9)
    df['EMA_21'] = ta.ema(df['close'], length=21)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # Minor S/R (Local Swings)
    df['Swing_High'] = df['high'].rolling(window=30, min_periods=5).max().shift(1)
    df['Swing_Low'] = df['low'].rolling(window=30, min_periods=5).min().shift(1)
    
    # Major S/R (Structural Swings / Liquidity Pools)
    df['Major_Swing_High'] = df['high'].rolling(window=150, min_periods=10).max().shift(1)
    df['Major_Swing_Low'] = df['low'].rolling(window=150, min_periods=10).min().shift(1)
    
    df['openInterest'] = df['openInterest'].ffill().bfill()
    df['OI_Change'] = df['openInterest'].pct_change() * 100
    df['OI_Change'] = df['OI_Change'].fillna(0)
    df['fundingRate'] = df['fundingRate'].fillna(0)
    if 'longShortRatio' not in df.columns:
        df['longShortRatio'] = 1.0
    df['longShortRatio'] = df['longShortRatio'].ffill().bfill()
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    signals = []
    
    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        candle_range = current['high'] - current['low']
        atr = current['ATR'] if pd.notna(current['ATR']) else candle_range
        
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
        
        # Heatmap Imbalance Logic
        ls_ratio = current.get('longShortRatio', 1.0)
        imbalance_favorable_bull = ls_ratio < 0.95
        imbalance_unfavorable_bull = ls_ratio > 1.05
        
        if imbalance_favorable_bull:
            score_bull += 2
        elif imbalance_unfavorable_bull:
            score_bull -= 2
        
        if heatmap_bull and sweep_bull and score_bull >= 3:
            # Dynamic SL: Below Sweep Low with ATR buffer
            entry_price = current['close']
            sl_price = current['Swing_Low'] - (0.5 * atr)
            
            min_risk = entry_price * 0.005
            if sl_price >= entry_price or (entry_price - sl_price) < min_risk:
                sl_price = entry_price - min_risk
            
            risk = entry_price - sl_price
            
            # Dynamic TP: Target Major Resistance
            major_resistance = current['Major_Swing_High']
            rr_to_res = (major_resistance - entry_price) / risk if risk > 0 else 0
            
            target_note = ""
            if rr_to_res >= 2.0:
                tp_rr = min(rr_to_res, 5.0)
                tp_price = entry_price + (risk * tp_rr)
                score_bull += 2
                target_note = f"Major Resistance (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price + (risk * 2.0)
                score_bull -= 1
                target_note = "Forced RR 1:2 (Major Res Terlalu Dekat)"
            
            total_met = score_bull + 3
            stars = "⭐⭐⭐⭐⭐" if total_met >= 8 else "⭐⭐⭐⭐" if total_met >= 6 else "⭐⭐⭐"
            
            checklist = [
                {"condition": "Heatmap: Ada area cerah di bawah", "met": bool(heatmap_bull)},
                {"condition": "Liquidity Sweep: Harga menusuk ke bawah lalu reclaim cepat", "met": bool(sweep_bull)},
                {"condition": "Karakter Candle: Muncul Pin Bar atau Engulfing", "met": bool(candle_bull)},
                {"condition": "OI: Turun tajam saat sweep", "met": bool(oi_bull)},
                {"condition": "Funding Rate: Negatif/turun", "met": bool(funding_bull)},
                {"condition": "RSI: Terjadi Divergence", "met": bool(rsi_bull)},
                {"condition": f"Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})", "met": not bool(imbalance_unfavorable_bull)},
                {"condition": "Struktur (ChoCh): Harga menembus swing (Proxy)", "met": True},
                {"condition": "EMA: Close di atas EMA 9/21", "met": bool(momentum_bull)}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'LONG',
                'Entry_Price': entry_price,
                'SL_Price': sl_price,
                'TP_Price': tp_price,
                'TP_RR': tp_rr,
                'Target_Note': target_note,
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
        
        # Heatmap Imbalance Logic
        imbalance_favorable_bear = ls_ratio > 1.05
        imbalance_unfavorable_bear = ls_ratio < 0.95
        
        if imbalance_favorable_bear:
            score_bear += 2
        elif imbalance_unfavorable_bear:
            score_bear -= 2
        
        if heatmap_bear and sweep_bear and score_bear >= 3:
            # Dynamic SL: Above Sweep High with ATR buffer
            entry_price = current['close']
            sl_price = current['Swing_High'] + (0.5 * atr)
            
            min_risk = entry_price * 0.005
            if sl_price <= entry_price or (sl_price - entry_price) < min_risk:
                sl_price = entry_price + min_risk
                
            risk = sl_price - entry_price
            
            # Dynamic TP: Target Major Support
            major_support = current['Major_Swing_Low']
            rr_to_sup = (entry_price - major_support) / risk if risk > 0 else 0
            
            target_note = ""
            if rr_to_sup >= 2.0:
                tp_rr = min(rr_to_sup, 5.0)
                tp_price = entry_price - (risk * tp_rr)
                score_bear += 2
                target_note = f"Major Support (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price - (risk * 2.0)
                score_bear -= 1
                target_note = "Forced RR 1:2 (Major Sup Terlalu Dekat)"
                
            total_met = score_bear + 3
            stars = "⭐⭐⭐⭐⭐" if total_met >= 8 else "⭐⭐⭐⭐" if total_met >= 6 else "⭐⭐⭐"
            
            checklist = [
                {"condition": "Heatmap: Ada area cerah di atas", "met": bool(heatmap_bear)},
                {"condition": "Liquidity Sweep: Harga menusuk ke atas lalu reject cepat", "met": bool(sweep_bear)},
                {"condition": "Karakter Candle: Muncul Pin Bar atau Engulfing", "met": bool(candle_bear)},
                {"condition": "OI: Turun tajam saat sweep", "met": bool(oi_bear)},
                {"condition": "Funding Rate: Positif/naik", "met": bool(funding_bear)},
                {"condition": "RSI: Terjadi Divergence", "met": bool(rsi_bear)},
                {"condition": f"Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})", "met": not bool(imbalance_unfavorable_bear)},
                {"condition": "Struktur (ChoCh): Harga menembus swing (Proxy)", "met": True},
                {"condition": "EMA: Close di bawah EMA 9/21", "met": bool(momentum_bear)}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'SHORT',
                'Entry_Price': entry_price,
                'SL_Price': sl_price,
                'TP_Price': tp_price,
                'TP_RR': tp_rr,
                'Target_Note': target_note,
                'Stars': stars,
                'Checklist': checklist
            })
            
    return evaluate_pnl(df, signals)

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
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # Minor S/R
    window = 30
    df['Swing_High'] = df['high'].rolling(window=window, min_periods=5).max().shift(1)
    df['Swing_Low'] = df['low'].rolling(window=window, min_periods=5).min().shift(1)
    
    # Major S/R
    df['Major_Swing_High'] = df['high'].rolling(window=150, min_periods=10).max().shift(1)
    df['Major_Swing_Low'] = df['low'].rolling(window=150, min_periods=10).min().shift(1)
    
    df['openInterest'] = df['openInterest'].ffill().bfill()
    df['OI_Change'] = df['openInterest'].pct_change() * 100
    df['OI_Change'] = df['OI_Change'].fillna(0)
    df['fundingRate'] = df['fundingRate'].fillna(0)
    if 'longShortRatio' not in df.columns:
        df['longShortRatio'] = 1.0
    df['longShortRatio'] = df['longShortRatio'].ffill().bfill()
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    signals = []
    
    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        candle_range = current['high'] - current['low']
        atr = current['ATR'] if pd.notna(current['ATR']) else candle_range
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
        
        # Heatmap Imbalance Logic
        ls_ratio = current.get('longShortRatio', 1.0)
        imbalance_favorable_bull = ls_ratio < 0.95
        imbalance_unfavorable_bull = ls_ratio > 1.05
        
        if imbalance_favorable_bull:
            score_bull += 2
        elif imbalance_unfavorable_bull:
            score_bull -= 2
        
        if trend_bull and sweep_bull and score_bull >= 3:
            entry_price = current['close']
            sl_price = current['Swing_Low'] - (0.5 * atr)
            min_risk = entry_price * 0.005
            if sl_price >= entry_price or (entry_price - sl_price) < min_risk:
                sl_price = entry_price - min_risk
            
            risk = entry_price - sl_price
            major_resistance = current['Major_Swing_High']
            rr_to_res = (major_resistance - entry_price) / risk if risk > 0 else 0
            
            target_note = ""
            if rr_to_res >= 2.0:
                tp_rr = min(rr_to_res, 5.0)
                tp_price = entry_price + (risk * tp_rr)
                score_bull += 2
                target_note = f"Major Resistance (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price + (risk * 2.0)
                score_bull -= 1
                target_note = "Forced RR 1:2 (Major Res Terlalu Dekat)"
                
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
                {"condition": f"9. Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})", "met": not bool(imbalance_unfavorable_bull)},
                {"condition": "10. Volatilitas tinggi (London/US Open)", "met": bool(is_active_session)},
                {"condition": "11. Struktur HTF terjaga", "met": True}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'LONG',
                'Entry_Price': entry_price,
                'SL_Price': sl_price,
                'TP_Price': tp_price,
                'TP_RR': tp_rr,
                'Target_Note': target_note,
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
        
        # Heatmap Imbalance Logic
        imbalance_favorable_bear = ls_ratio > 1.05
        imbalance_unfavorable_bear = ls_ratio < 0.95
        
        if imbalance_favorable_bear:
            score_bear += 2
        elif imbalance_unfavorable_bear:
            score_bear -= 2
        
        if trend_bear and sweep_bear and score_bear >= 3:
            entry_price = current['close']
            sl_price = current['Swing_High'] + (0.5 * atr)
            min_risk = entry_price * 0.005
            if sl_price <= entry_price or (sl_price - entry_price) < min_risk:
                sl_price = entry_price + min_risk
                
            risk = sl_price - entry_price
            major_support = current['Major_Swing_Low']
            rr_to_sup = (entry_price - major_support) / risk if risk > 0 else 0
            
            target_note = ""
            if rr_to_sup >= 2.0:
                tp_rr = min(rr_to_sup, 5.0)
                tp_price = entry_price - (risk * tp_rr)
                score_bear += 2
                target_note = f"Major Support (RR 1:{tp_rr:.1f})"
            else:
                tp_rr = 2.0
                tp_price = entry_price - (risk * 2.0)
                score_bear -= 1
                target_note = "Forced RR 1:2 (Major Sup Terlalu Dekat)"
                
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
                {"condition": f"9. Heatmap Imbalance (LS Ratio: {ls_ratio:.2f})", "met": not bool(imbalance_unfavorable_bear)},
                {"condition": "10. Volatilitas tinggi (London/US Open)", "met": bool(is_active_session)},
                {"condition": "11. Struktur HTF terjaga", "met": True}
            ]
            signals.append({
                'Time': current['timestamp'].isoformat(),
                'Type': 'SHORT',
                'Entry_Price': entry_price,
                'SL_Price': sl_price,
                'TP_Price': tp_price,
                'TP_RR': tp_rr,
                'Target_Note': target_note,
                'Stars': stars,
                'Checklist': checklist
            })
            
    return evaluate_pnl(df, signals)

def evaluate_pnl(df, signals):
    final_signals = []
    for s in signals:
        signal_time = pd.to_datetime(s['Time'])
        signal_idx_list = df.index[df['timestamp'] == signal_time].tolist()
        if not signal_idx_list: continue
        signal_idx = signal_idx_list[0]
        
        future_df = df.iloc[signal_idx+1:]
        current_close = s['Entry_Price']
        sl_price = s['SL_Price']
        tp_price = s['TP_Price']
        
        if s['Type'] == 'LONG':
            risk_pct = (current_close - sl_price) / current_close
            max_price_reached = current_close
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['high'] > max_price_reached:
                    max_price_reached = f_bar['high']
                if f_bar['low'] <= sl_price:
                    break
            profit_pct = (max_price_reached - current_close) / current_close
            s['Max_RR'] = profit_pct / risk_pct if risk_pct > 0 else 0
        else:
            risk_pct = (sl_price - current_close) / current_close
            min_price_reached = current_close
            for j in range(len(future_df)):
                f_bar = future_df.iloc[j]
                if f_bar['low'] < min_price_reached:
                    min_price_reached = f_bar['low']
                if f_bar['high'] >= sl_price:
                    break
            profit_pct = (current_close - min_price_reached) / current_close
            s['Max_RR'] = profit_pct / risk_pct if risk_pct > 0 else 0
            
        final_signals.append(s)
    return final_signals
