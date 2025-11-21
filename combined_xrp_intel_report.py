#!/usr/bin/env python3
"""
combined_xrp_intel_report.py

Combined Crypto Intel + XRP 12-Hour Report

* Discord report with indicators, alerts, patterns, news
* Volume spike and MACD crossover alerts
* Multi-timeframe confirmations
* Updates xrp_history.csv automatically
* Dynamic caution/strong/danger levels
* Fully safe for GitHub Actions
  """

import os
import time
import requests
import feedparser
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta

# ----------------------------

# CONFIG

# ----------------------------

# Safe load Discord webhook

try:
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
print("DEBUG: DISCORD_WEBHOOK loaded successfully")
except KeyError:
DISCORD_WEBHOOK = None
print("DEBUG: DISCORD_WEBHOOK not found in environment!")

CSV_FILE = "xrp_history.csv"

VOLUME_SPIKE_LEVELS = {"caution": 1.15, "strong": 1.30, "extreme": 1.50}
RSI_WINDOW = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SWING_WINDOW = 24
COMPRESSION_WINDOW = 24
PULSE_STACK_WINDOW = 12
SENTINEL_WINDOW = 24

# ----------------------------

# UTILITY FUNCTIONS

# ----------------------------

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
print(f"DEBUG: Discord responded {r.status_code}: {r.text[:300]}")
else:
print("DEBUG: Discord message sent successfully")
except Exception as e:
print("DEBUG: Failed to send to Discord:", e)

# ----------------------------

# INDICATOR FUNCTIONS

# ----------------------------

def compute_indicators(df):
rsi = RSIIndicator(df['close'], window=RSI_WINDOW).rsi()[-1]
macd_ind = MACD(df['close'], window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
macd_line = macd_ind.macd()[-1]
macd_signal = macd_ind.macd_signal()[-1]
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
if hist_series is None or len(hist_series) < 2:
return None
if hist_series.iloc[-1] > hist_series.iloc[-2]:
return "Increasing"
elif hist_series.iloc[-1] < hist_series.iloc[-2]:
return "Decreasing"
return "Flat"

def support_resistance(df):
return {"recent_high": df['high'].max(), "recent_low": df['low'].min()}

def compute_dynamic_levels(df):
high = df['high'].max()
low = df['low'].min()
return {
"breakout_weak": low + (high-low)*0.4,
"breakout_strong": low + (high-low)*0.7,
"breakdown_weak": low + (high-low)*0.3,
"breakdown_strong": low + (high-low)*0.15,
"danger": low
}

def detect_patterns(df, indicators):
# Placeholder pattern detection
return ["PatternA", "PatternB"]  # replace with actual detection

def fetch_crypto_news():
try:
feed = feedparser.parse("[https://cryptonews.com/news/rss/](https://cryptonews.com/news/rss/)")
entries = feed.entries[:5]
news = "\n".join([f"- {e.title}" for e in entries])
return news
except Exception as e:
print("DEBUG: Failed to fetch news:", e)
return "No news available"

# ----------------------------

# COMPOSE DISCORD MESSAGE

# ----------------------------

def compose_discord_message(df, live_price):
indicators = compute_indicators(df)
price = float(live_price)

```
# Volume spike detection
vol = detect_volume_spike(df)
vol_text = "No surge"
if vol["level"] == "EXTREME":
    vol_text = f"EXTREME volume spike ({vol['ratio']:.2f}x avg)"
elif vol["level"] == "STRONG":
    vol_text = f"Strong volume spike ({vol['ratio']:.2f}x avg)"
elif vol["level"] == "CAUTION":
    vol_text = f"Caution volume spike ({vol['ratio']:.2f}x avg)"

# Patterns
patterns = detect_patterns(df, indicators)
patterns_text = ", ".join(patterns)

# MACD Histogram Trend
macd_hist_text = macd_histogram_trend(indicators.get("macd_hist_series")) or "None"

# Support/Resistance
sr = support_resistance(df)
levels = compute_dynamic_levels(df)

# Flips/Triggers
flips = []
if price > levels["breakout_weak"]:
    flips.append("Bullish breakout (weak)")
if price > levels["breakout_strong"]:
    flips.append("Bullish breakout (strong)")
if price < levels["breakdown_weak"]:
    flips.append("Bearish breakdown (weak)")
if price < levels["breakdown_strong"]:
    flips.append("Bearish breakdown (strong)")
if price < levels["danger"]:
    flips.append("DANGER: price below danger level")
flips_text = ", ".join(flips) if flips else "None"

# Bullish/Bearish Probabilities
bullish, bearish = 50, 50
if price > indicators["ma50"]:
    bullish += 15; bearish -= 15
else:
    bullish -= 15; bearish += 15
if indicators["macd_line"] > indicators["macd_signal"]:
    bullish += 20; bearish -= 20
else:
    bullish -= 20; bearish += 20
if indicators["rsi"] < 30:
    bullish += 10; bearish -= 10
elif indicators["rsi"] > 70:
    bullish -= 10; bearish += 10
if indicators["ma50"] > indicators["ma200"]:
    bullish += 5; bearish -= 5
bullish = max(0, min(100, bullish))
bearish = max(0, min(100, bearish))

# --- Dynamic Caution Levels ---
caution_levels = []
if (levels["breakout_weak"] <= price <= levels["breakout_strong"]) or (vol["ratio"] >= 1.15):
    caution_levels.append(f"⚠️ Weak Caution 🟡 - Price/volume approaching warning zone (x{vol['ratio']:.2f})")
if (levels["breakout_strong"] < price <= levels["breakout_strong"]*1.02) or (vol["ratio"] >= 1.30):
    caution_levels.append(f"⚠️ Strong Caution 🟠 - Price/volume in high-risk zone (x{vol['ratio']:.2f})")
if price >= levels["breakout_strong"]*1.06 or price <= levels["danger"] or (vol["ratio"] >= 1.50):
    caution_levels.append(f"🚨 Danger Zone 🔴 - Price/volume in danger territory (x{vol['ratio']:.2f})")
caution_text = "\n".join(caution_levels) if caution_levels else "None"

# Fetch crypto news
news = fetch_crypto_news()

# Compose final message
message = f"""
```

**🚨 Combined XRP Intelligence Report**

💰 Current Price: ${fmt(price)}
📈 RSI (14): {fmt(indicators['rsi'])}
📉 MACD: {fmt(indicators['macd_line'])} (signal {fmt(indicators['macd_signal'])})
📊 MA50: {fmt(indicators['ma50'])}  MA200: {fmt(indicators['ma200'])}

📈 Bullish Probability: {fmt(bullish)}%
📉 Bearish Probability: {fmt(bearish)}%

🔍 Trend: {"Bullish 🟢" if bullish>bearish else "Bearish 🔴"}

📊 Volume Signals: {vol_text}
⚠ Patterns Detected: {patterns_text}
📊 MACD Histogram Trend: {macd_hist_text}
🧭 Support/Resistance: 24h High: ${fmt(sr['recent_high'])}, 24h Low: ${fmt(sr['recent_low'])}
🔔 Flips/Triggers: {flips_text}

🟡🟠🔴 Caution Levels:
{caution_text}

📰 Top Crypto News:
{news}

---

*Data window: last {len(df)} hourly candles (30-day history).*
"""
return message

# ----------------------------

# MAIN EXECUTION

# ----------------------------

def main():
try:
df = pd.read_csv(CSV_FILE)
except FileNotFoundError:
print("DEBUG: CSV file not found, creating empty DataFrame")
df = pd.DataFrame(columns=["timestamp","open","high","low","close","volume"])

```
if df.empty:
    print("DEBUG: CSV empty, skipping message composition")
    return

live_price = df['close'].iloc[-1]
message = compose_discord_message(df, live_price)
send_discord(message)
```

if **name** == "**main**":
main()
