from backend.data_fetcher import fetch_all_data
df = fetch_all_data("BTCUSDT", "15m", 150)
print(f"Klines start: {df['timestamp'].iloc[0] if not df.empty else 'N/A'}, End: {df['timestamp'].iloc[-1] if not df.empty else 'N/A'}")
print(f"DF shape before dropna: {df.shape}")
df.dropna(inplace=True)
print(f"DF shape after dropna: {df.shape}")
if not df.empty:
    print(f"Final start: {df['timestamp'].iloc[0]}, End: {df['timestamp'].iloc[-1]}")
