#!/usr/bin/env python3
"""
combined_xrp_intel_report.py
Combined Crypto Intel + XRP 12-Hour Report
Fully working version for GitHub Actions
"""

import os
import requests
import feedparser
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime

# ---------------------------- CONFIG ----------------------------

# Safely load Discord webhook from GitHub Secrets
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if DISCORD_WEBHOOK:
    print("DEBUG: DISCORD_WEBHOOK loaded successfully")
else:
    print("DEBUG: DISCORD_WEBHOOK not set – will skip sending to Discord")

CSV_FILE = "xrp_history.csv"

VOLUME_SPIKE_LEVELS = {"caution": 1.15, "strong": 1.30, "extreme": 1.50}
RSI_WINDOW = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SWING_WINDOW = 24

# ---------------------------- UTILITIES ----------------------------

def fmt(x):
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    try:
        return f"{float(x):,.4f}"
    except:
        return str(x)

def send_discord(content: str, webhook: str = DISCORD_WEBHOOK):
    if not webhook:
        print("DEBUG: Webhook not set, skipping Discord send")
        return
    try:
        r = requests.post(webhook, json={"content": content}, timeout=10)
        print(f"DEBUG: Discord POST status {r.status_code}")
        if r.status_code not in (200, 204):
            print(f"DEBUG: Discord error {r.status_code}: {r.text[:300]}")
        else:
            print("DEBUG: Discord message sent successfully")
    except Exception as e:
        print("DEBUG: Failed to send to Discord:", e)

# ---------------------------- DATA FETCHING ----------------------------

def fetch_xrp_hourly_data() -> pd.DataFrame:
    """Fetch last ~41 days of hourly XRP/USDT candles from Binance"""
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": "XRPUSDT",
        "interval": "1h",
        "limit": 1000  # max allowed
    }
    print("Fetching fresh XRP data from Binance...")
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df.sort_values("open_time").reset_index(drop=True)
    return df

# ---------------------------- INDICATORS ----------------------------

def compute_indicators(df):
    rsi = RSIIndicator(df['close'], window=RSI_WINDOW).rsi().iloc[-1]
    macd_ind = MACD(df['close'], window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
    macd_line = macd_ind.macd().iloc[-1]
    macd_signal = macd_ind.macd_signal().iloc[-1]
    macd_hist_series = macd_ind.macd_diff()
    ma50 = df['close'].rolling(50).mean().iloc[-1]
    ma200 = df['close'].rolling(200).mean().iloc[-1]
    return {
        "rsi": rsi,
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_hist_series": macd_hist_series,
        "ma50": ma50,
        "ma200": ma200
    }

def detect_volume_spike(df):
    recent_vol = df['volume'].iloc[-1]
    avg_vol = df['volume'].rolling(SWING_WINDOW).mean().iloc[-1]
    ratio = recent_vol / avg_vol if avg_vol > 0 else 0
    level = "NONE"
    if ratio >= VOLUME_SPIKE_LEVELS["extreme"]:
        level = "EXTREME"
    elif ratio >= VOLUME_SPIKE_LEVELS["strong"]:
        level = "STRONG"
    elif ratio >= VOLUME_SPIKE_LEVELS["caution"]:
        level = "CAUTION"
    return {"ratio": ratio, "level": level}

def macd_histogram_trend(hist_series):
    if len(hist_series) < 2:
        return "N/A"
    if hist_series.iloc[-1] > hist_series.iloc[-2]:
        return "Increasing 🟢"
    elif hist_series.iloc[-1] < hist_series.iloc[-2]:
        return "Decreasing 🔴"
    return "Flat"

def support_resistance(df):
    return {
        "recent_high": df['high'].tail(24).max(),
        "recent_low": df['low'].tail(24).min()
    }

def compute_dynamic_levels(df):
    high = df['high'].tail(72).max()   # last 3 days
    low = df['low'].tail(72).min()
    range_ = high - low
    return {
        "breakout_weak": low + range_ * 0.4,
        "breakout_strong": low + range_ * 0.7,
        "breakdown_weak": low + range_ * 0.3,
        "breakdown_strong": low + range_ * 0.15,
        "danger": low
    }

def fetch_crypto_news():
    try:
        feed = feedparser.parse("https://cryptonews.com/news/rss/")
        entries = feed.entries[:6]
        news = "\n".join([f"• {e.title}" for e in entries])
        return news
    except Exception as e:
        print("DEBUG: Failed to fetch news:", e)
        return "No news available at this time."

# ---------------------------- MESSAGE COMPOSER ----------------------------

def compose_discord_message(df, live_price):
    indicators = compute_indicators(df)
    price = float(live_price)
    vol = detect_volume_spike(df)
    sr = support_resistance(df)
    levels = compute_dynamic_levels(df)

    # Volume text
    if vol["level"] == "EXTREME":
        vol_text = f"**EXTREME VOLUME SPIKE** ({vol['ratio']:.2f}x avg) 🔥"
    elif vol["level"] == "STRONG":
        vol_text = f"**Strong volume spike** ({vol['ratio']:.2f}x avg)"
    elif vol["level"] == "CAUTION":
        vol_text = f"Caution: volume elevated ({vol['ratio']:.2f}x avg)"
    else:
        vol_text = "Normal volume"

    # Simple bullish/bearish score
    bullish = 50
    bearish = 50
    if price > indicators["ma50"]: bullish += 15; bearish -= 15
    if indicators["macd_line"] > indicators["macd_signal"]: bullish += 20; bearish -= 20
    if indicators["rsi"] < 30: bullish += 15; bearish -= 15
    elif indicators["rsi"] > 70: bearish += 15; bullish -= 15
    if indicators["ma50"] > indicators["ma200"]: bullish += 10; bearish -= 10
    bullish = max(0, min(100, bullish))
    bearish = max(0, min(100, bearish))

    trend = "Bullish 🟢" if bullish > bearish else "Bearish 🔴"

    # Caution levels
    caution = []
    if vol["ratio"] >= 1.50 or price >= levels["breakout_strong"] * 1.05 or price <= levels["danger"]:
        caution.append("🚨 **DANGER ZONE** 🔴")
    elif vol["ratio"] >= 1.30 or price >= levels["breakout_strong"]:
        caution.append("🟠 **Strong Caution**")
    elif vol["ratio"] >= 1.15:
        caution.append("🟡 Weak Caution")
    caution_text = "\n".join(caution) if caution else "✅ Safe levels"

    news = fetch_crypto_news()

    message = f"""
**🚨 XRP Combined Intelligence Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}**

**💰 Price:** `${fmt(price)}`
**📊 24h High/Low:** `${fmt(sr['recent_high'])}` / `${fmt(sr['recent_low'])}`

**Technical Indicators**
• RSI (14): `{fmt(indicators['rsi'])}`
• MACD: `{fmt(indicators['macd_line'])}` | Signal: `{fmt(indicators['macd_signal'])}` | Histogram: {macd_histogram_trend(indicators['macd_hist_series'])}
• MA50: `{fmt(indicators['ma50'])}` | MA200: `{fmt(indicators['ma200'])}`

**📈 Bullish Probability:** `{bullish}%` | **📉 Bearish:** `{bearish}%` → **Trend: {trend}**

**Volume:** {vol_text}
**Caution Level:** {caution_text}

**📰 Latest Crypto Headlines**
{news}

*Data: {len(df)} hourly candles | Updated automatically via GitHub Actions*
"""

    return message.strip()

# ---------------------------- MAIN ----------------------------

def main():
    # 1. Fetch fresh data
    fresh_df = fetch_xrp_hourly_data()

    # 2. Load existing CSV (if any)
    try:
        old_df = pd.read_csv(CSV_FILE, parse_dates=["open_time"])
        print(f"Loaded existing CSV with {len(old_df)} rows")
    except FileNotFoundError:
        old_df = pd.DataFrame()
        print("No existing CSV – creating new one")

    # 3. Update dataframe (avoid duplicates)
    if not old_df.empty:
        latest_ts = fresh_df["open_time"].max()
        old_df = old_df[old_df["open_time"] < latest_ts]
        df = pd.concat([old_df, fresh_df], ignore_index=True)
    else:
        df = fresh_df

    # 4. Save updated CSV
    df.to_csv(CSV_FILE, index=False)
    print(f"Saved updated xrp_history.csv → {len(df)} rows")

    # 5. Generate and send report (only if enough data)
    if len(df) < 200:
        print("Not enough data yet for reliable indicators")
        return

    live_price = df["close"].iloc[-1]
    message = compose_discord_message(df, live_price)
    send_discord(message)

if __name__ == "__main__":
    main()
