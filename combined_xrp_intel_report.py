#!/usr/bin/env python3
"""
combined_xrp_intel_report.py
Fully working XRP report bot – Nov 2025 edition
Uses CryptoCompare (no blocking, no key, real OHLCV)
"""

import os
import requests
import feedparser
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime

# ---------------------------- CONFIG ----------------------------

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if DISCORD_WEBHOOK:
    print("DEBUG: DISCORD_WEBHOOK loaded successfully")
else:
    print("DEBUG: DISCORD_WEBHOOK not set – skipping Discord send")

CSV_FILE = "xrp_history.csv"

# ---------------------------- UTILITIES ----------------------------

def fmt(x):
    if isinstance(x, (int, float)):
        return f"{x:,.4f}".rstrip("0").rstrip(".")
    return str(x)

def send_discord(content: str):
    if not DISCORD_WEBHOOK:
        print("DEBUG: No webhook → skipping send")
        return
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": content}, timeout=10)
        print(f"DEBUG: Discord → {r.status_code}")
    except Exception as e:
        print("DEBUG: Discord send failed:", e)

# ---------------------------- DATA FETCHING ----------------------------

def fetch_xrp_hourly_data() -> pd.DataFrame:
    """Fetch ~2000 hours (~83 days) of real XRP/USDT OHLCV from CryptoCompare (free & reliable)"""
    print("Fetching XRP hourly data from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    params = {
        "fsym": "XRP",
        "tsym": "USDT",
        "limit": 2000,   # max free = 2000
        "aggregate": 1
    }
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()["Data"]["Data"]

    df = pd.DataFrame(data)
    df = df[df["time"] > 0]  # filter empty
    df["open_time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"volumeto": "volume"})  # real USDT volume
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("open_time").reset_index(drop=True)
    print(f"Fetched {len(df)} hourly candles")
    return df

# ---------------------------- INDICATORS ----------------------------

def compute_indicators(df: pd.DataFrame):
    close = df["close"]
    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    macd = MACD(close)
    return {
        "rsi": rsi,
        "macd_line": macd.macd().iloc[-1],
        "macd_signal": macd.macd_signal().iloc[-1],
        "macd_hist": macd.macd_diff(),
        "ma50": close.rolling(50).mean().iloc[-1],
        "ma200": close.rolling(200).mean().iloc[-1],
    }

def detect_volume_spike(df: pd.DataFrame):
    recent = df["volume"].iloc[-1]
    avg = df["volume"].rolling(24).mean().iloc[-1]
    ratio = recent / avg if avg > 0 else 1
    level = "NORMAL"
    if ratio >= 1.50: level = "EXTREME"
    elif ratio >= 1.30: level = "STRONG"
    elif ratio >= 1.15: level = "CAUTION"
    return {"ratio": round(ratio, 2), "level": level}

def macd_histogram_trend(hist):
    if len(hist) < 2: return "N/A"
    return "Increasing 🟢" if hist.iloc[-1] > hist.iloc[-2] else "Decreasing 🔴"

def fetch_crypto_news():
    try:
        feed = feedparser.parse("https://cryptonews.com/news/rss/")
        return "\n".join([f"• {e.title}" for e in feed.entries[:6]])
    except:
        return "No news right now"

# ---------------------------- MESSAGE ----------------------------

def compose_message(df: pd.DataFrame, price: float):
    ind = compute_indicators(df)
    vol = detect_volume_spike(df)
    recent_high = df["high"].tail(24).max()
    recent_low = df["low"].tail(24).min()

    # Simple score
    bull = bear = 50
    if price > ind["ma50"]: bull += 15; bear -= 15
    if ind["macd_line"] > ind["macd_signal"]: bull += 20; bear -= 20
    if ind["rsi"] < 30: bull += 10
    if ind["rsi"] > 70: bear += 10
    bull = min(100, max(0, bull))
    bear = 100 - bull

    vol_text = f"**{vol['level']} VOLUME** ({vol['ratio']}x 24h avg) 🔥" if vol["level"] != "NORMAL" else "Normal volume"

    message = f"""
**🚨 XRP Combined Intel Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}**

**Price:** `${fmt(price)}`
**24h High/Low:** `${fmt(recent_high)}` / `${fmt(recent_low)}`

**Indicators**
• RSI (14): `{fmt(ind['rsi'])}`
• MACD: `{fmt(ind['macd_line'])}` | Signal: `{fmt(ind['macd_signal'])}` | Hist: {macd_histogram_trend(ind['macd_hist'])}
• MA50: `{fmt(ind['ma50'])}` | MA200: `{fmt(ind['ma200'])}`

**Trend Strength:** Bullish {bull}% | Bearish {bear}%
**Volume:** {vol_text}

**Latest Crypto News**
{fetch_crypto_news()}

*Data: {len(df)} hourly candles → updated automatically*
    """.strip()
    return message

# ---------------------------- MAIN ----------------------------

def main():
    fresh_df = fetch_xrp_hourly_data()

    # Load or create CSV
    try:
        old_df = pd.read_csv(CSV_FILE, parse_dates=["open_time"])
        print(f"Loaded {len(old_df)} rows from CSV")
    except FileNotFoundError:
        old_df = pd.DataFrame()

    # Merge & dedupe
    if not old_df.empty:
        latest = fresh_df["open_time"].max()
        old_df = old_df[old_df["open_time"] < latest]
        df = pd.concat([old_df, fresh_df]).drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    else:
        df = fresh_df

    df.to_csv(CSV_FILE, index=False)
    print(f"Saved {len(df)} rows to CSV")

    if len(df) < 250:
        print("Not enough data yet")
        return

    message = compose_message(df, df["close"].iloc[-1])
    send_discord(message)
    print("Report sent!")

if __name__ == "__main__":
    main()
