import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta
import os

WEBHOOK_URL = "https://discord.com/api/webhooks/1439145854899589141/s5vTSsu_z-Wx1HxgV1C-pSt3LO9jo_brrsoFbXRoBfjlcxD1Ut7tFC_6TlpicqC8P6HY"
CSV_FILE = "xrp_history.csv"

# ----------------------------
# Step 1: Fetch 7-day hourly CSV
# ----------------------------
def fetch_7d_hourly_csv():
    """
    Fetch 7-day hourly XRP data from CoinGecko and save to CSV.
    """
    url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart?vs_currency=usd&days=7"
    data = requests.get(url, timeout=15).json()

    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    if not prices:
        print("❌ No price data returned from CoinGecko")
        return

    df_prices = pd.DataFrame(prices, columns=["timestamp", "close"])
    df_vol = pd.DataFrame(volumes, columns=["timestamp", "volume"])

    df_prices["timestamp"] = pd.to_datetime(df_prices["timestamp"], unit="ms")
    df_vol["timestamp"] = pd.to_datetime(df_vol["timestamp"], unit="ms")

    df = pd.merge(df_prices, df_vol, on="timestamp", how="left")
    df["high"] = df["close"]
    df["low"] = df["close"]

    df.to_csv(CSV_FILE, index=False)
    print("✅ 7-day hourly CSV saved as xrp_history.csv")

# ----------------------------
# Step 2: Fetch current price
# ----------------------------
def fetch_current_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd&include_24hr_vol=true"
    try:
        data = requests.get(url, timeout=10).json()
        price = float(data["ripple"]["usd"])
        volume = float(data["ripple"]["usd_24h_vol"])
        timestamp = datetime.utcnow()
        return {"timestamp": timestamp, "close": price, "volume": volume, "high": price, "low": price}
    except Exception as e:
        print("❌ Failed to fetch current price:", e)
        return None

# ----------------------------
# Step 3: Update history CSV
# ----------------------------
def update_history(current):
    df_new = pd.DataFrame([current])

    # Read CSV without parsing dates yet
    df_hist = pd.read_csv(CSV_FILE)

    # Merge new data
    df_hist = pd.concat([df_hist, df_new], ignore_index=True)

    # Convert timestamp column to datetime, infer format, coerce errors
    df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], errors="coerce", utc=True)

    # Drop any rows with invalid timestamps
    df_hist = df_hist.dropna(subset=["timestamp"])

    # Keep only last 7 days
    seven_days_ago = pd.Timestamp.utcnow() - pd.Timedelta(days=7)
    df_hist = df_hist[df_hist["timestamp"] >= seven_days_ago]

    # Save CSV
    df_hist.to_csv(CSV_FILE, index=False)

# ----------------------------
# Step 4: Analyze indicators
# ----------------------------
def analyze(df):
    df["close"] = df["close"].astype(float)
    price = df["close"].iloc[-1]

    rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    macd_line = MACD(df["close"]()_
