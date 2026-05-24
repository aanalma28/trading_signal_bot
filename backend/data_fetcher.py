import requests
import pandas as pd
import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_paginated_klines(symbol, interval="15m", limit_days=30, end_time_ms=None):
    total_candles = int((limit_days * 24 * 60) / int(interval.replace('m', ''))) if 'm' in interval else 1000
    if interval == '1h': total_candles = limit_days * 24
    if interval == '4h': total_candles = limit_days * 6
    
    url = "https://fapi.binance.com/fapi/v1/klines"
    all_data = []
    end_time = end_time_ms
    
    print(f"Fetching OHLCV for {symbol} (Target: {total_candles} candles)...")
    while len(all_data) < total_candles:
        limit = min(1000, total_candles - len(all_data))
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if end_time:
            params["endTime"] = end_time
            
        response = requests.get(url, params=params, verify=False)
        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from Binance (klines). Response text: {response.text}")
            raise Exception("Gagal terhubung ke Binance. Kemungkinan IP VPS Anda diblokir atau terkena limit.")
        
        if not data or type(data) is dict or len(data) == 0:
            break
            
        all_data = data + all_data
        end_time = data[0][0] - 1
        time.sleep(0.1)
        
    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"])
    if not df.empty:
        df.drop_duplicates(subset=['timestamp'], inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
    return df

def fetch_paginated_oi(symbol, period="15m", total_candles=3000, end_time_ms=None):
    url = "https://fapi.binance.com/futures/data/openInterestHist"
    all_data = []
    end_time = end_time_ms
    
    print(f"Fetching Open Interest for {symbol}...")
    while len(all_data) < total_candles:
        limit = min(500, total_candles - len(all_data))
        params = {"symbol": symbol, "period": period, "limit": limit}
        if end_time:
            params["endTime"] = end_time
            
        response = requests.get(url, params=params, verify=False)
        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from Binance (openInterest). Response text: {response.text}")
            raise Exception("Gagal terhubung ke Binance. Kemungkinan IP VPS Anda diblokir atau terkena limit.")
        
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

def fetch_funding_rate(symbol, limit=1000, end_time_ms=None):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": limit}
    if end_time_ms:
        params["endTime"] = end_time_ms
    try:
        response_json = requests.get(url, params=params, verify=False).json()
    except Exception as e:
        print(f"Error parsing JSON from Binance (fundingRate).")
        raise Exception("Gagal terhubung ke Binance. Kemungkinan IP VPS Anda diblokir.")
    df = pd.DataFrame(response_json)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms")
        df["fundingRate"] = df["fundingRate"].astype(float)
        df = df[["timestamp", "fundingRate"]]
    return df

def fetch_paginated_ls_ratio(symbol, period="15m", total_candles=3000, end_time_ms=None):
    url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
    all_data = []
    end_time = end_time_ms
    
    print(f"Fetching LS Ratio for {symbol}...")
    while len(all_data) < total_candles:
        limit = min(500, total_candles - len(all_data))
        params = {"symbol": symbol, "period": period, "limit": limit}
        if end_time:
            params["endTime"] = end_time
            
        response = requests.get(url, params=params, verify=False)
        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from Binance (LS ratio). Response text: {response.text}")
            raise Exception("Gagal terhubung ke Binance. Kemungkinan IP VPS Anda diblokir atau terkena limit.")
        
        if not data or type(data) is dict or len(data) == 0:
            break
            
        all_data = data + all_data
        end_time = data[0]['timestamp'] - 1
        time.sleep(0.1)
        
    df = pd.DataFrame(all_data)
    if not df.empty:
        df.drop_duplicates(subset=['timestamp'], inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["longShortRatio"] = df["longShortRatio"].astype(float)
        df = df[["timestamp", "longShortRatio"]]
    return df

def fetch_all_data(symbol, interval, limit_days, end_time_ms=None):
    total_candles = int((limit_days * 24 * 60) / int(interval.replace('m', ''))) if 'm' in interval else 1000
    df_klines = fetch_paginated_klines(symbol, interval, limit_days, end_time_ms)
    if df_klines.empty: return pd.DataFrame()
    
    df_oi = fetch_paginated_oi(symbol, interval, total_candles, end_time_ms)
    df_ls = fetch_paginated_ls_ratio(symbol, interval, total_candles, end_time_ms)
    df_funding = fetch_funding_rate(symbol, 1000, end_time_ms)
    
    # Merge
    if not df_oi.empty:
        df = pd.merge(df_klines, df_oi, on="timestamp", how="left")
    else:
        df = df_klines.copy()
        df['openInterest'] = float('nan')
        
    if not df_ls.empty:
        df = pd.merge(df, df_ls, on="timestamp", how="left")
    else:
        df['longShortRatio'] = 1.0
        
    if not df_funding.empty:
        df = pd.merge_asof(df.sort_values('timestamp'), df_funding.sort_values('timestamp'), on='timestamp', direction='backward')
    else:
        df['fundingRate'] = 0.0
    
    return df
