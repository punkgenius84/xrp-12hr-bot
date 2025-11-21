#!/usr/bin/env python3
"""
XRP Combined Intel Report – With Clickable News + Thumbnails
Perfect for Discord (auto-previews!)
"""

import os
import requests
import feedparser
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CSV_FILE = "xrp_history.csv"

def fmt(x):
    return f"{float(x):,.4f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)

def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print("DRY RUN:\n" + msg)
        return
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=15)
        print(f"Discord → {r.status_code}")
    except Exception as e:
        print("Send failed:", e)

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

def compute_indicators(df):
    c = df["close"]
    rsi = RSIIndicator(c, window=14).rsi().iloc[-1]
    macd = MACD(c, window_fast=12, window_slow=26, window_sign=9)
    hist = macd.macd_diff()
    return {
        "rsi": rsi,
        "macd": macd.macd().iloc[-1],
        "signal": macd.macd_signal().iloc[-1],
        "hist_trend": "Increasing 🟢" if len(hist) > 1 and hist.iloc[-1] > hist.iloc[-2] else "Decreasing 🔴",
        "ma50": c.rolling(50).mean().iloc[-1],
        "ma200": c.rolling(200).mean().iloc[-1],
    }

def volume_spike(df):
    ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    ratio = round(ratio, 2)
    if ratio >= 1.5: return f"**EXTREME SURGE** {ratio}x 🔥"
    if ratio >= 1.3: return f"**Strong surge** {ratio}x ⚡"
    if ratio >= 1.15: return f"Caution — elevated {ratio}x ⚠️"
    return "No surge"

def dynamic_levels(df):
    high = df["high"].tail(72).max()
    low = df["low"].tail(72).min()
    r = high - low
    return {
        "breakout_weak": low + r * 0.4,
        "breakout_strong": low + r * 0.7,
        "breakdown_weak": low + r * 0.3,
        "breakdown_strong": low + r * 0.15,
        "danger": low
    }

def flips_triggers(price, levels):
    triggers = []
    if price > levels["breakout_strong"]: triggers.append("🚀 Strong Bullish Breakout")
    elif price > levels["breakout_weak"]: triggers.append("Bullish breakout (weak)")
    if price < levels["breakdown_strong"]: triggers.append("💥 Strong Bearish Breakdown")
    elif price < levels["breakdown_weak"]: triggers.append("Bearish breakdown (weak)")
    if price < levels["danger"]: triggers.append("🚨 DANGER ZONE ACTIVE")
    return ", ".join(triggers) if triggers else "None"

def caution_level(price, vol_ratio, levels):
    if vol_ratio >= 1.5 or price > levels["breakout_strong"] * 1.02 or price < levels["danger"]:
        return "🚨 **DANGER ZONE** 🔴"
    if vol_ratio >= 1.3 or price > levels["breakout_strong"]:
        return "🟠 **Strong Caution**"
    if vol_ratio >= 1.15:
        return "🟡 Weak Caution"
    return "✅ Safe levels"

# ================================
# BEAUTIFUL CLICKABLE NEWS WITH THUMBNAILS
# ================================
def get_news_section():
    try:
        feed = feedparser.parse("https://cryptonews.com/news/rss/")
        news_lines = []
        for entry in feed.entries[:5]:  # top 5 stories
            title = entry.title.strip()
            link = entry.link.strip()
            # Discord will auto-unfurl the preview (with thumbnail!) if we just send the URL on its own line
            news_lines.append(f"**{title}**\n{link}\n")
        return "\n".join(news_lines) if news_lines else "No recent news"
    except Exception as e:
        print("News fetch failed:", e)
        return "News temporarily unavailable"

# ================================
# MESSAGE
# ================================
def build_message(df):
    price = df["close"].iloc[-1]
    i = compute_indicators(df)
    vol_text = volume_spike(df)
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    levels = dynamic_levels(df)
    triggers = flips_triggers(price, levels)
    caution = caution_level(price, vol_ratio, levels)
    high24 = df["high"].tail(24).max()
    low24 = df["low"].tail(24).min()

    bull = 50
    if price > i["ma50"]: bull += 15
    if i["macd"] > i["signal"]: bull += 20
    if i["rsi"] < 30: bull += 10
    elif i["rsi"] > 70: bull -= 15
    bull = min(100, max(0, bull))
    bear = 100 - bull

    return f"""
**🚨 Combined XRP Intelligence Report — {datetime.utcnow().strftime('%b %d, %H:%M UTC')}**

💰 **Current Price:** `${fmt(price)}`
📈 **RSI (14):** `{fmt(i['rsi'])}`
📉 **MACD:** `{fmt(i['macd'])}` (signal `{fmt(i['signal'])}`)
📊 **MA50:** `{fmt(i['ma50'])}`  **MA200:** `{fmt(i['ma200'])}`

📈 **Bullish Probability:** `{bull}%`
📉 **Bearish Probability:** `{bear}%`
🔍 **Trend:** `{'Bullish 🟢' if bull > bear else 'Bearish 🔴'}`

📊 **Volume Signals:** {vol_text}
📊 **MACD Histogram Trend:** {i['hist_trend']}
🧭 **24h High/Low:** `${fmt(high24)}` / `${fmt(low24)}`

📌 **Dynamic Levels**
• Breakout weak: `${fmt(levels['breakout_weak'])}`
• Breakout strong: `${fmt(levels['breakout_strong'])}`
• Breakdown weak: `${fmt(levels['breakdown_weak'])}`
• Breakdown strong: `${fmt(levels['breakdown_strong'])}`
• Danger: `${fmt(levels['danger'])}`

🔔 **Flips/Triggers:** {triggers}
**⚠️ Caution Level:** {caution}

**📰 Latest XRP & Crypto News** (click title for full article + preview)
{get_news_section()}

*Auto-updated via GitHub Actions • {len(df)} hourly candles*
    """.strip()

# ================================
# MAIN
# ================================
def main():
    fresh_df = fetch_xrp_hourly_data()

    # Safe CSV handling
    old_df = pd.DataFrame()
    if os.path.exists(CSV_FILE):
        try:
            old_df = pd.read_csv(CSV_FILE)
            if "open_time" in old_df.columns:
                old_df["open_time"] = pd.to_datetime(old_df["open_time"])
            else:
                old_df = pd.DataFrame()
        except:
            old_df = pd.DataFrame()

    df = pd.concat([old_df, fresh_df]).drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"Updated CSV → {len(df)} rows")

    if len(df) < 300:
        print("Not enough data yet")
        return

    send_discord(build_message(df))
    print("Beautiful report with clickable news sent!")

if __name__ == "__main__":
    main()
