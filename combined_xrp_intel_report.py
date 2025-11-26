#!/usr/bin/env python3
"""
XRP AI BOT — FINAL WITH YOUR ORIGINAL BEAUTIFUL EMBED
"""

import requests
import pandas as pd
import os
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed
import tweepy

CSV_FILE = "xrp_history.csv"

# Secrets
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
client = tweepy.Client(
    bearer_token=os.environ["X_BEARER_TOKEN"],
    consumer_key=os.environ["X_API_KEY"],
    consumer_secret=os.environ["X_API_SECRET"],
    access_token=os.environ["X_ACCESS_TOKEN"],
    access_token_secret=os.environ["X_ACCESS_SECRET"]
)

# -----------------------------
# Data + CSV (unchanged)
# -----------------------------
def fetch_xrp_hourly_data():
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    resp = requests.get(url, params={"fsym": "XRP", "tsym": "USDT", "limit": 2000}, timeout=20)
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame([d for d in data if d["time"] > 0])
    df["open_time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"volumeto": "volume"}, inplace=True)
    return df[["open_time", "open", "high", "low", "close", "volume"]]

def load_csv():
    try:
        df = pd.read_csv(CSV_FILE)
        df["open_time"] = pd.to_datetime(df["open_time"])
        return df
    except:
        return pd.DataFrame()

# -----------------------------
# Pure pandas swings (100% stable)
# -----------------------------
def find_swings(df, window=50):
    high_roll = df['high'].rolling(window=2*window+1, center=True).max()
    low_roll = df['low'].rolling(window=2*window+1, center=True).min()
    is_high = df['high'] == high_roll
    is_low = df['low'] == low_roll
    swings = pd.DataFrame({'high': df['high'].where(is_high), 'low': df['low'].where(is_low)}).dropna(how='all')
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
# YOUR ORIGINAL INDICATORS (fully restored)
# -----------------------------
def check_macd_rsi_alerts(df):
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['signal'] = df['macd'].ewm(span=9).mean()
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff(1).clip(lower=0).rolling(14).mean() /
                                 abs(df['close'].diff(1)).rolling(14).mean())))
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    alerts = []
    if prev['macd'] < prev['signal'] and latest['macd'] > latest['signal']:
        alerts.append("MACD Bullish Crossover")
    elif prev['macd'] > prev['signal'] and latest['macd'] < latest['signal']:
        alerts.append("MACD Bearish Crossover")
    if latest['rsi'] > 70: alerts.append("RSI Overbought")
    if latest['rsi'] < 30: alerts.append("RSI Oversold")
    avg_vol = df['volume'].tail(50).mean()
    if latest['volume'] > avg_vol * 2: alerts.append("Volume Spike")
    return "\n".join(alerts) if alerts else "No Alerts"

def detect_chart_patterns(df):
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []
    if prev['ema50'] < prev['ema200'] and latest['ema50'] > latest['ema200']:
        signals.append("EMA50/200 Golden Cross")
    elif prev['ema50'] > prev['ema200'] and latest['ema50'] < latest['ema200']:
        signals.append("EMA50/200 Death Cross")
    if latest['close'] > latest['ema50'] > latest['ema200']:
        signals.append("Strong Bullish")
    elif latest['close'] < latest['ema50'] < latest['ema200']:
        signals.append("Strong Bearish")
    return "\n".join(signals) if signals else "Neutral"

# -----------------------------
# YOUR ORIGINAL GORGEOUS EMBED — 100% RESTORED
# -----------------------------
def send_beautiful_embed(structure, alerts, patterns):
    price = df['close'].iloc[-1]
    change_24h = ((price / df['close'].iloc[-25]) - 1) * 100 if len(df) > 25 else 0

    embed = DiscordEmbed(title="XRP AI BOT — 12-Hour Intel Report", color=0x9b59b6)
    embed.add_embed_field(name="Market Structure", value=structure, inline=False)
    embed.add_embed_field(name="Current Price", value=f"${price:.4f}", inline=True)
    embed.add_embed_field(name="24h Change", value=f"{change_24h:+.2f}%", inline=True)
    embed.add_embed_field(name="MACD / RSI / Volume", value=alerts or "No Alerts", inline=False)
    embed.add_embed_field(name="Patterns & Flips", value=patterns or "Neutral", inline=False)
    embed.set_thumbnail(url="https://cryptologos.cc/logos/xrp-xrp-logo.png")
    embed.set_footer(text=f"Data: {len(df)} candles • Updated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    embed.set_timestamp()

    webhook = DiscordWebhook(url=DISCORD_WEBHOOK)
    webhook.add_embed(embed)
    webhook.execute()
    print("Beautiful embed sent to Discord!")

    # X post
    try:
        client.create_tweet(text=f"XRP Update — {structure} — ${price:.4f} ({change_24h:+.2f}%) #XRP #Crypto")
        print("X post sent!")
    except Exception as e:
        print("X failed:", e)

# -----------------------------
# Main
# -----------------------------
def main():
    global df
    new = fetch_xrp_hourly_data()
    if new.empty: return
    old = load_csv()
    df = pd.concat([old, new]).drop_duplicates(subset="open_time").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"Saved CSV — {len(df)} rows")

    structure = compute_market_structure(df)
    alerts = check_macd_rsi_alerts(df)
    patterns = detect_chart_patterns(df)

    print("Market Structure:", structure)
    send_beautiful_embed(structure, alerts, patterns)

if __name__ == "__main__":
    main()
