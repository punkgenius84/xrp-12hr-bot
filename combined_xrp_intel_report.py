#!/usr/bin/env python3
"""
XRP Report Bot - Fully working November 2025
CryptoCompare data + bulletproof CSV handling
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
    print("DEBUG: Webhook loaded")
else:
    print("DEBUG: No webhook")

CSV_FILE = "xrp_history.csv"

# ---------------------------- HELPERS ----------------------------
def fmt(x):
    return f"{float(x):,.4f}".rstrip("0").rstrip(".")

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("DRY RUN:\n" + msg[:1000])
        return
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=10)
        print(f"Discord response: {r.status_code}")
    except Exception as e:
        print("Send failed:", e)

# ---------------------------- DATA ----------------------------
def fetch_xrp_hourly_data() -> pd.DataFrame:
    print("Fetching XRP hourly data from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    params = {"fsym": "XRP", "tsym": "USDT", "limit": 2000}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame([d for d in data if d["time"] > 0])
    df["open_time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"volumeto": "volume"})
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    print(f"Fetched {len(df)} candles")
    return df

# ---------------------------- INDICATORS ----------------------------
def get_indicators(df):
    c = df["close"]
    rsi = RSIIndicator(c, window=14).rsi().iloc[-1]
    macd = MACD(c)
    return {
        "rsi": rsi,
        "macd": macd.macd().iloc[-1],
        "signal": macd.macd_signal().iloc[-1],
        "ma50": c.rolling(50).mean().iloc[-1],
        "ma200": c.rolling(200).mean().iloc[-1],
    }

def volume_text(df):
    ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    ratio = round(ratio, 2)
    if ratio >= 1.5: return f"**EXTREME** {ratio}x 🔥"
    if ratio >= 1.3: return f"**STRONG** {ratio}x ⚡"
    if ratio >= 1.15: return f"Caution {ratio}x ⚠️"
    return f"Normal {ratio}x"

def get_news():
    try:
        f = feedparser.parse("https://cryptonews.com/news/rss/")
        return "\n".join(f"• {e.title}" for e in f.entries[:6])
    except:
        return "• News unavailable"

# ---------------------------- MESSAGE ----------------------------
def build_message(df, price):
    i = get_indicators(df)
    h24 = df["high"].tail(24).max()
    l24 = df["low"].tail(24).min()

    bull = 50
    if price > i["ma50"]: bull += 18
    if i["macd"] > i["signal"]: bull += 22
    if i["rsi"] < 30: bull += 10
    bull = min(100, max(0, bull))

    return f"""
**🚨 XRP Intel Report — {datetime.utcnow().strftime('%b %d %H:%M UTC')}**

**Price:** `${fmt(price)}`  
**24h Range:** `${fmt(h24)}` – `${fmt(l24)}`

**Indicators**
• RSI (14): `{fmt(i['rsi'])}`
• MACD: `{fmt(i['macd'])}` | Signal: `{fmt(i['signal'])}`
• MA50: `{fmt(i['ma50'])}` | MA200: `{fmt(i['ma200'])}`
• Volume: {volume_text(df)}

**Trend:** {'🟢 Bullish' if bull > 50 else '🔴 Bearish'} ({bull}% confidence)

**News**
{get_news()}

*Auto-updated • {len(df)} hourly candles*
    """.strip()

# ---------------------------- MAIN (NO MORE parse_dates CRASH) ----------------------------
def main():
    fresh_df = fetch_xrp_hourly_data()

    # Load old CSV safely – NO parse_dates argument!
    if os.path.exists(CSV_FILE):
        try:
            old_df = pd.read_csv(CSV_FILE)  # ← THIS LINE CHANGED
            if "open_time" in old_df.columns:
                old_df["open_time"] = pd.to_datetime(old_df["open_time"])
                print(f"Loaded {len(old_df)} old rows")
            else:
                print("Old CSV wrong format → ignoring")
                old_df = pd.DataFrame()
        except Exception as e:
            print(f"CSV error ({e}) → starting fresh")
            old_df = pd.DataFrame()
    else:
        old_df = pd.DataFrame()
        print("No CSV found → starting fresh")

    # Merge
    if not old_df.empty:
        df = pd.concat([old_df, fresh_df]).drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
    else:
        df = fresh_df

    df.to_csv(CSV_FILE, index=False)
    print(f"Saved {len(df)} rows to CSV")

    if len(df) < 250:
        print("Not enough data yet")
        return

    send_discord(build_message(df, df["close"].iloc[-1]))
    print("Report sent!")

if __name__ == "__main__":
    main()
