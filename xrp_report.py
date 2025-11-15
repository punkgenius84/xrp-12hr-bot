import requests
import pandas as pd

CSV_FILE = "xrp_history.csv"

def fetch_30d_hourly_csv():
    url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart?vs_currency=usd&days=30"
    data = requests.get(url, timeout=15).json()

    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    df_prices = pd.DataFrame(prices, columns=["timestamp", "close"])
    df_vol = pd.DataFrame(volumes, columns=["timestamp", "volume"])

    df_prices["timestamp"] = pd.to_datetime(df_prices["timestamp"], unit="ms", errors="coerce")
    df_vol["timestamp"] = pd.to_datetime(df_vol["timestamp"], unit="ms", errors="coerce")

    df = pd.merge(df_prices, df_vol, on="timestamp", how="left")
    df["high"] = df["close"]
    df["low"] = df["close"]

    df.to_csv(CSV_FILE, index=False)
    print("✅ 30-day hourly CSV saved as xrp_history.csv")
