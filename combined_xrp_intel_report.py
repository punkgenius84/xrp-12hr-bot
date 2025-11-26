#!/usr/bin/env python3
"""
XRP Combined Intel Report – Discord + X Auto-Post (OAuth 1.0a User Context)
Smart adaptive levels · Clickable news · Works perfectly on GitHub Actions
November 2025 – FINAL VERSION
"""

import os
import requests
import feedparser
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime
from requests_oauthlib import OAuth1

# ========================= CONFIG =========================
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

CSV_FILE = "xrp_history.csv"

# ========================= HELPERS =========================
def fmt(x, decimals=4):
    if isinstance(x, (int, float)):
        formatted = f"{float(x):,.{decimals}f}".rstrip("0").rstrip(".")
        return formatted if '.' in formatted or 'e' in formatted.lower() else formatted + '.0' if decimals > 0 else formatted
    return str(x)

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=15)
        print("Full report sent to Discord")
    except Exception as e:
        print("Discord send failed:", e)

# ========================= X POST (OAuth 1.0a User Context) =========================
def post_to_x(text):
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        print("Missing X credentials → skipping X post")
        return

    url = "https://api.twitter.com/2/tweets"  # Note: X is Twitter API under the hood
    auth = OAuth1(
        X_API_KEY,
        client_secret=X_API_SECRET,
        resource_owner_key=X_ACCESS_TOKEN,
        resource_owner_secret=X_ACCESS_SECRET
    )
    payload = {"text": text}

    try:
        r = requests.post(url, json=payload, auth=auth, timeout=10)
        if r.status_code == 201:
            print("Successfully posted to X!")
        else:
            print(f"X post failed ({r.status_code}): {r.text}")
    except Exception as e:
        print("X post error:", e)

# ========================= DATA =========================
def fetch_xrp_hourly_data() -> pd.DataFrame:
    print("Fetching XRP/USDT hourly from CryptoCompare...")
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

# ========================= INDICATORS =========================
def compute_indicators(df):
    c = df["close"]
    rsi = RSIIndicator(c, window=14).rsi().iloc[-1]
    macd = MACD(c, window_fast=12, window_slow=26, window_sign=9)
    hist = macd.macd_diff()
    trend = "Increasing 🟢" if len(hist) > 1 and hist.iloc[-1] > hist.iloc[-2] else "Decreasing 🔴"
    return {
        "rsi": rsi,
        "macd": macd.macd().iloc[-1],
        "signal": macd.macd_signal().iloc[-1],
        "hist_trend": trend,
        "ma50": c.rolling(50).mean().iloc[-1],
        "ma200": c.rolling(200).mean().iloc[-1],
    }

def volume_spike(df):
    ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    ratio = round(ratio, 2)
    if ratio >= 1.5: return f"Extreme Surge {ratio}x 🔥"
    if ratio >= 1.3: return f"Strong Surge {ratio}x ⚡"
    if ratio >= 1.15: return f"Elevated {ratio}x ⚠️"
    return "Normal"

# ========================= SMART DYNAMIC LEVELS =========================
def dynamic_levels(df):
    price = df["close"].iloc[-1]
    recent_high = df["high"].tail(24).max()
    recent_low  = df["low"].tail(24).min()
    weekly_high = df["high"].tail(168).max()
    weekly_low  = df["low"].tail(168).min()

    drop_from_week = (weekly_high - price) / weekly_high if weekly_high > 0 else 0
    range_mode = "7-day"

    if drop_from_week > 0.10:
        high = recent_high
        low  = recent_low
        range_mode = "24h crash mode"
        print("Crash detected → using 24h range")
    else:
        high = weekly_high
        low  = weekly_low

    r = high - low if high > low else 0.0001

    return {
        "breakout_weak":    low + r * 0.382,
        "breakout_strong":  low + r * 0.618,
        "breakdown_weak":   low + r * 0.236,
        "breakdown_strong": low + r * 0.118,
        "danger":           low,
        "range_mode":       range_mode
    }

def flips_triggers(price, levels):
    triggers = []
    if price > levels["breakout_strong"]: triggers.append("🚀 Strong Bullish Breakout")
    elif price > levels["breakout_weak"]: triggers.append("Bullish Breakout (Weak)")
    if price < levels["breakdown_strong"]: triggers.append("💥 Strong Bearish Breakdown")
    elif price < levels["breakdown_weak"]: triggers.append("Bearish Breakdown (Weak)")
    if price < levels["danger"]: triggers.append("🚨 Danger Zone")
    return triggers[0] if triggers else "Stable"

def caution_level(price, vol_ratio, levels, price_change_1h):
    if vol_ratio >= 1.5 or price < levels["danger"] or abs(price_change_1h) >= 5:
        return "🚨 Danger 🔴"
    if vol_ratio >= 1.3 or price > levels["breakout_strong"] or abs(price_change_1h) >= 3:
        return "🟠 Strong Caution"
    if vol_ratio >= 1.15 or abs(price_change_1h) >= 2:
        return "🟡 Weak Caution"
    return "✅ Safe"

def get_news_section():
    try:
        feed = feedparser.parse("https://cryptonews.com/news/rss/")
        keywords = ["XRP", "Ripple", "BTC", "Bitcoin"]
        filtered_entries = [
            e for e in feed.entries
            if any(kw.lower() in (e.title + (e.description if 'description' in e else '')).lower() for kw in keywords)
        ]
        lines = []
        for e in filtered_entries[:5]:
            title = e.title.strip().replace("`", "'")
            link = e.link.strip()
            lines.append(f"**{title}**\n{link}\n")
        return "\n".join(lines) or "No relevant news"
    except Exception as e:
        print("News error:", e)
        return "News temporarily unavailable"

# ========================= DISCORD FULL REPORT =========================
def build_discord_message(df):
    price = df["close"].iloc[-1]
    i = compute_indicators(df)
    vol_text = volume_spike(df)
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    levels = dynamic_levels(df)
    triggers = flips_triggers(price, levels)
    price_change_1h = ((price / df["close"].iloc[-2]) - 1) * 100 if len(df) > 1 else 0
    caution = caution_level(price, vol_ratio, levels, price_change_1h)
    high24 = df["high"].tail(24).max()
    low24 = df["low"].tail(24).min()

    # Improved Bull/Bear Probability
    bull_score = 0
    if price > i["ma200"]: bull_score += 30  # Increased weight for longer-term MA
    if i["macd"] > i["signal"]: bull_score += 25
    if i["rsi"] < 30: bull_score += 20  # Oversold favors rebound
    elif i["rsi"] > 70: bull_score -= 20  # Overbought favors pullback
    if i["hist_trend"] == "Increasing 🟢": bull_score += 15
    if price_change_1h > 0: bull_score += min(10, price_change_1h * 2)  # Momentum boost
    bull = min(100, max(0, 50 + bull_score))  # Start at 50, adjust by score
    bear = 100 - bull

    price_change_alert = f"🚨 **1h Price Alert:** {price_change_1h:+.2f}% ({'🔥 Surge' if price_change_1h >= 5 else '💥 Drop' if price_change_1h <= -5 else 'Stable'})" if abs(price_change_1h) >= 5 else ""

    return f"""
**🚨 Combined XRP Intelligence Report — {datetime.utcnow().strftime('%b %d, %H:%M UTC')}**

💰 **Current Price:** `${fmt(price, 3)}`
{price_change_alert}
📈 **RSI (14):** `{fmt(i['rsi'], 2)}`
📉 **MACD:** `{fmt(i['macd'], 4)}` (signal `{fmt(i['signal'], 4)}`)
📊 **MA50:** `{fmt(i['ma50'], 4)}`  **MA200:** `{fmt(i['ma200'], 4)}`

📈 **Bullish Probability:** `{bull}%`
📉 **Bearish Probability:** `{bear}%`
🔍 **Trend:** `{'Bullish 🟢' if bull > bear else 'Bearish 🔴'}`

📊 **Volume Signals:** {vol_text}
📊 **MACD Histogram Trend:** {i['hist_trend']}
🧭 **24h High/Low:** `${fmt(high24, 4)}` / `${fmt(low24, 4)}`

📌 **Dynamic Levels** ({levels['range_mode']})
• Breakout weak: `${fmt(levels['breakout_weak'], 4)}`
• Breakout strong: `${fmt(levels['breakout_strong'], 4)}`
• Breakdown weak: `${fmt(levels['breakdown_weak'], 4)}`
• Breakdown strong: `${fmt(levels['breakdown_strong'], 4)}`
• Danger: `${fmt(levels['danger'], 4)}`

🔔 **Flips/Triggers:** {triggers}
**⚠️ Caution Level:** {caution}

**📰 Latest XRP, Ripple & BTC News** (click title for article + preview)
{get_news_section()}

*Auto-updated via GitHub Actions • {len(df)} hourly candles*
    """.strip()

# ========================= X TEASER =========================
def build_x_teaser(df):
    price = df["close"].iloc[-1]
    i = compute_indicators(df)
    prev_price_24h = df["close"].iloc[-24] if len(df) >= 24 else price
    change_24h = (price / prev_price_24h - 1) * 100
    price_change_1h = ((price / df["close"].iloc[-2]) - 1) * 100 if len(df) > 1 else 0
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    levels = dynamic_levels(df)
    main_trigger = flips_triggers(price, levels)
    caution = caution_level(price, vol_ratio, levels, price_change_1h)
    vol_text = volume_spike(df)

    # Bull probability calculation (duplicated for teaser)
    bull_score = 0
    if price > i["ma200"]: bull_score += 30
    if i["macd"] > i["signal"]: bull_score += 25
    if i["rsi"] < 30: bull_score += 20
    elif i["rsi"] > 70: bull_score -= 20
    if i["hist_trend"] == "Increasing 🟢": bull_score += 15
    if price_change_1h > 0: bull_score += min(10, price_change_1h * 2)
    bull = min(100, max(0, 50 + bull_score))

    price_alert_teaser = f" | 1h: {price_change_1h:+.1f}%" 

    return f"""🚨 XRP Intel Drop — {datetime.utcnow().strftime('%b %d, %H:%M')} UTC

💰 ${fmt(price, 3)} ({change_24h:+.1f}% 24h{price_alert_teaser})
📊 RSI: {fmt(i['rsi'], 2)} | Bull: {bull}%
🔥 {main_trigger} | Vol: {vol_text}
⚠️ {caution}

Full report in Discord 👇
https://discord.gg/HD8PdbW2
#XRP #Ripple #Crypto"""

# ========================= MAIN =========================
def main():
    fresh_df = fetch_xrp_hourly_data()

    old_df = pd.DataFrame()
    if os.path.exists(CSV_FILE):
        try:
            old_df = pd.read_csv(CSV_FILE)
            if "open_time" in old_df.columns:
                old_df["open_time"] = pd.to_datetime(old_df["open_time"])
        except Exception as e:
            print("CSV load failed:", e)

    df = pd.concat([old_df, fresh_df]).drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"Updated CSV → {len(df)} rows")

    if len(df) < 300:
        print("Not enough data yet")
        return

    # Send full report to Discord
    send_discord(build_discord_message(df))

    # Post teaser to X
    post_to_x(build_x_teaser(df))

if __name__ == "__main__":
    main()
