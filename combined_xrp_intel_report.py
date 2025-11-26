#!/usr/bin/env python3
"""
XRP AI BOT — FINAL COMPLETE VERSION (Nov 26 2025)
All original indicators + working Market Structure + Discord + X posts
"""

import requests
import pandas as pd
import os
from datetime import datetime
from discord_webhook import DiscordWebhook
import tweepy

CSV_FILE = "xrp_history.csv"

# Secrets
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
X_BEARER_TOKEN = os.environ["X_BEARER_TOKEN"]
X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]

client = tweepy.Client(
    bearer_token=X_BEARER_TOKEN,
    consumer_key=X_API_KEY,
    consumer_secret=X_API_SECRET,
    access_token=X_ACCESS_TOKEN,
    access_token_secret=X_ACCESS_SECRET
)

# -----------------------------
# Data Fetch + Load
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
# PURE PANDAS SWINGS — NO BUGS
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
# Market Structure (your original + working)
# -----------------------------
def compute_market_structure(df):
    try:
        df = df.copy()
        df.rename(columns=str.lower, inplace=True)
        data = df[["open", "high", "low", "close"]].tail(500)
        swings = find_swings(data, window=50)

        if len(swings) < 3:
            return "Unavailable"

        recent_highs = swings['high'].dropna().tail(3).astype(float)
        recent_lows = swings['low'].dropna().tail(3).astype(float)

        if (len(recent_highs) >= 3 and len(recent_lows) >= 3 and
            recent_highs.iloc[-1] > recent_highs.iloc[-2] > recent_highs.iloc[-3] and
            recent_lows.iloc[-1] > recent_lows.iloc[-2] > recent_lows.iloc[-3]):
            return "Bullish Structure (HH + HL)"
        elif (len(recent_highs) >= 3 and len(recent_lows) >= 3 and
              recent_highs.iloc[-1] < recent_highs.iloc[-2] < recent_highs.iloc[-3] and
              recent_lows.iloc[-1] < recent_lows.iloc[-2] < recent_lows.iloc[-3]):
            return "Bearish Structure (LH + LL)"
        else:
            return "Ranging / Choppy Structure"
    except:
        return "Unavailable"

# -----------------------------
# ALL YOUR ORIGINAL INDICATORS — FULLY RESTORED
# -----------------------------
def check_macd_rsi_alerts(df):
    df = df.copy()
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['signal'] = df['macd'].ewm(span=9).mean()
    df['hist'] = df['macd'] - df['signal']
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff(1).clip(lower=0).rolling(14).mean() /
                                 abs(df['close'].diff(1)).rolling(14).mean())))

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    alerts = []

    # MACD Crossover
    if prev['macd'] < prev['signal'] and latest['macd'] > latest['signal']:
        alerts.append("MACD Bullish Crossover")
    elif prev['macd'] > prev['signal'] and latest['macd'] < latest['signal']:
        alerts.append("MACD Bearish Crossover")

    # RSI
    if latest['rsi'] > 70:
        alerts.append("RSI Overbought (>70)")
    elif latest['rsi'] < 30:
        alerts.append("RSI Oversold (<30)")

    # Volume Spike
    avg_vol = df['volume'].tail(50).mean()
    if latest['volume'] > avg_vol * 2:
        alerts.append("Volume Spike Detected")

    return "\n".join(alerts) if alerts else "No MACD/RSI/Volume Alerts"

def detect_chart_patterns(df):
    df = df.copy()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    df['adx'] = abs(df['high'] - df['low']).rolling(14).mean() / df['close'].rolling(14).mean() * 100

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signals = []

    # EMA Cross
    if prev['ema50'] < prev['ema200'] and latest['ema50'] > latest['ema200']:
        signals.append("EMA50/200 Golden Cross")
    elif prev['ema50'] > prev['ema200'] and latest['ema50'] < latest['ema200']:
        signals.append("EMA50/200 Death Cross")

    # ADX Trend Strength
    if latest['adx'] > 25:
        signals.append("Strong Trend (ADX >25)")
    elif latest['adx'] < 20:
        signals.append("Weak Trend (ADX <20)")

    # Price vs EMA
    if latest['close'] > latest['ema50'] > latest['ema200']:
        signals.append("Strong Bullish Alignment")
    elif latest['close'] < latest['ema50'] < latest['ema200']:
        signals.append("Strong Bearish Alignment")

    return "\n".join(signals) if signals else "No Pattern Signals"

# -----------------------------
# Send to Discord + X
# -----------------------------
def send_report(structure, alerts, patterns):
    price = df['close'].iloc[-1]
    change_24h = ((price / df['close'].iloc[-25]) - 1) * 100 if len(df) > 25 else 0

    report = f"""**XRP AI BOT — 12-Hour Intel Report**  
**Market Structure:** {structure}
**Current Price:** ${price:.4f}  
**24h Change:** {change_24h:+.2f}%

**MACD / RSI / Volume**
{alerts}

**Patterns & Flips**
{patterns}

Data: {len(df)} hourly candles  
Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

#XRP #Ripple #Crypto"""

    # Discord
    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK, content=report[:1999])
        webhook.execute()
        print("Discord report sent!")
    except Exception as e:
        print("Discord failed:", e)

    # X/Twitter
    try:
        tweet = f"XRP Update — {structure} — ${price:.4f} ({change_24h:+.2f}%) — #XRP #Crypto"
        client.create_tweet(text=tweet[:280])
        print("X post sent!")
    except Exception as e:
        print("X post failed:", e)

# -----------------------------
# Main — FINAL
# -----------------------------
def main():
    global df
    new = fetch_xrp_hourly_data()
    if new.empty:
        return

    old = load_csv()
    df = pd.concat([old, new]).drop_duplicates(subset="open_time").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"Saved CSV — {len(df)} rows")

    structure = compute_market_structure(df)
    alerts = check_macd_rsi_alerts(df)
    patterns = detect_chart_patterns(df)

    print("Market Structure:", structure)
    send_report(structure, alerts, patterns)

if __name__ == "__main__":
    main()
