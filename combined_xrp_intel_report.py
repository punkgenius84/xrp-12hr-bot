#!/usr/bin/env python3
"""
XRP Combined Intel Report – Posts to Discord + X (Twitter)
Smart levels + clickable news
"""

import os
import requests
import feedparser
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")  # ← new

CSV_FILE = "xrp_history.csv"

def fmt(x):
    return f"{float(x):,.4f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)

def send_discord(msg):
    if not DISCORD_WEBHOOK: return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=15)
    except: pass

def post_to_x(text):
    if not X_BEARER_TOKEN:
        print("No X token → skipping post")
        return
    url = "https://api.x.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {X_BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"text": text}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 201:
            print("Posted to X successfully!")
        else:
            print(f"X post failed: {r.status_code} {r.text}")
    except Exception as e:
        print("X post error:", e)

# [keep all the functions exactly as in the last version: fetch_xrp_hourly_data, compute_indicators, volume_spike, dynamic_levels, flips_triggers, caution_level, get_news_section, build_message]

# ← paste the exact same functions from the last script here (fetch_xrp_hourly_data through build_message)

def main():
    fresh_df = fetch_xrp_hourly_data()

    old_df = pd.DataFrame()
    if os.path.exists(CSV_FILE):
        try:
            old_df = pd.read_csv(CSV_FILE)
            if "open_time" in old_df.columns:
                old_df["open_time"] = pd.to_datetime(old_df["open_time"])
        except: pass

    df = pd.concat([old_df, fresh_df]).drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)

    if len(df) < 300: return

    report = build_message(df)

    send_discord(report)
    print("Report sent to Discord")

    # Short version for X (under 280 chars)
    price = df["close"].iloc[-1]
    change_24h = (price / df["close"].iloc[-24] - 1) * 100 if len(df) >= 24 else 0
    x_text = f"""🚨 XRP Update — {datetime.utcnow().strftime('%b %d, %H:%M UTC')}

💰 Price: ${fmt(price)} ({change_24h:+.2f}% 24h)
📊 RSI: {fmt(df['close'].rsi(14).iloc[-1])}
🔍 Trend: {'Bullish 🟢' if df['close'].iloc[-1] > df['close'].rolling(50).mean().iloc[-1] else 'Bearish 🔴'}

⚠️ {flips_triggers(price, dynamic_levels(df))}

Full report in comments 👇
#XRP #Ripple #Crypto"""

    post_to_x(x_text)
    print("Posted short version to X")

if __name__ == "__main__":
    main()
