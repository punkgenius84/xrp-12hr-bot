#!/usr/bin/env python3
"""
combined_xrp_intel_report.py — FINAL VERSION WITH REAL DISCORD + X POSTS
"""

import requests
import pandas as pd
import os
from datetime import datetime
from discord_webhook import DiscordWebhook
import tweepy

CSV_FILE = "xrp_history.csv"

# -----------------------------
# Secrets from GitHub (already set)
# -----------------------------
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
X_BEARER_TOKEN = os.environ["X_BEARER_TOKEN"]
X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]

# X/Twitter client
client = tweepy.Client(
    bearer_token=X_BEARER_TOKEN,
    consumer_key=X_API_KEY,
    consumer_secret=X_API_SECRET,
    access_token=X_ACCESS_TOKEN,
    access_token_secret=X_ACCESS_SECRET
)

# -----------------------------
# Fetch + Load (unchanged)
# -----------------------------
def fetch_xrp_hourly_data():
    print("Fetching XRP/USDT hourly from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    resp = requests.get(url, params={"fsym": "XRP", "tsym": "USDT", "limit": 2000}, timeout=20)
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame([d for d in data if d["time"] > 0])
    df["open_time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"volumeto": "volume"}, inplace=True)
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    return df

def load_csv():
    try:
        df = pd.read_csv(CSV_FILE)
        df["open_time"] = pd.to_datetime(df["open_time"])
        return df
    except:
        return pd.DataFrame()

# -----------------------------
# Pure pandas swing detection (100% stable)
# -----------------------------
def find_swings(df, window=50):
    high_roll = df['high'].rolling(window=2*window+1, center=True).max()
    low_roll = df['low'].rolling(window=2*window+1, center=True).min()
    is_high = df['high'] == high_roll
    is_low = df['low'] == low_roll
    swings = pd.DataFrame({
        'high': df['high'].where(is_high),
        'low': df['low'].where(is_low)
    }).dropna(how='all')
    return swings

# -----------------------------
# Market Structure (working)
# -----------------------------
def compute_market_structure(df):
    try:
        df = df.copy()
        df.rename(columns=str.lower, inplace=True)
        data = df[["open", "high", "low", "close"]].tail(500)
        swings = find_swings(data, window=50)

        if len(swings) < 3:
            return "No Clear Structure"

        recent_highs = swings['high'].dropna().tail(3).astype(float)
        recent_lows = swings['low'].dropna().tail(3).astype(float)

        if (len(recent_highs) >= 3 and len(recent_lows) >= 3 and
            recent_highs.iloc[-1] > recent_highs.iloc[-2] > recent_highs.iloc[-3] and
            recent_lows.iloc[-1] > recent_lows.iloc[-2] > recent_lows.iloc[-3]):
            return "Bullish Structure (Higher Highs & Higher Lows)"
        elif (len(recent_highs) >= 3 and len(recent_lows) >= 3 and
              recent_highs.iloc[-1] < recent_highs.iloc[-2] < recent_highs.iloc[-3] and
              recent_lows.iloc[-1] < recent_lows.iloc[-2] < recent_lows.iloc[-3]):
            return "Bearish Structure (Lower Highs & Lower Lows)"
        else:
            return "Ranging / Choppy Structure"
    except Exception as e:
        print("Structure error:", e)
        return "Structure Error"

# -----------------------------
# REAL DISCORD + X POSTING
# -----------------------------
def send_to_discord(message):
    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK, content=message[:1999])
        webhook.execute()
        print("Discord post sent!")
    except Exception as e:
        print("Discord failed:", e)

def post_to_x(message):
    try:
        client.create_tweet(text=message[:280])
        print("X post sent!")
    except Exception as e:
        print("X post failed:", e)

# -----------------------------
# Main — FINAL
# -----------------------------
def main():
    new = fetch_xrp_hourly_data()
    if new.empty:
        print("No new data.")
        return

    old = load_csv()
    df = pd.concat([old, new]).drop_duplicates(subset="open_time").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"Saved CSV — {len(df)} rows")

    structure = compute_market_structure(df)
    print("Market Structure:", structure)

    # Your full report
    report = f"""XRP 12-Hour Intel Report

Market Structure: {structure}

Last Price: ${df['close'].iloc[-1]:.4f}
24h Change: {((df['close'].iloc[-1] / df['close'].iloc[-25]) - 1)*100:+.2f}%

Data: {len(df)} hourly candles
Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

#XRP #Ripple #Crypto"""

    send_to_discord(report)
    post_to_x(f"XRP Update — {structure} — Price: ${df['close'].iloc[-1]:.4f} — #XRP #Crypto")

if __name__ == "__main__":
    main()
