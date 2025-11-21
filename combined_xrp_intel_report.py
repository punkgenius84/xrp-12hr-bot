#!/usr/bin/env python3
"""
combined_xrp_intel_report.py

Combined Crypto Intel + XRP 12-Hour Report
- Full Discord report with indicators, alerts, patterns, news
- Volume spike and MACD crossover alerts
- Multi-timeframe confirmations
- Updates xrp_history.csv automatically
- Dynamic caution/strong/danger levels
- DEBUG mode added for GitHub Actions
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

# Load Discord webhook from environment at the very top
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
print("DEBUG: DISCORD_WEBHOOK =", DISCORD_WEBHOOK)  # <-- debug

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

def send_discord(content: str, webhook: str = DISCORD_WEBHOOK):
    if not webhook:
        print("DEBUG: Webhook not set, skipping Discord send")
        return
    try:
        r = requests.post(webhook, json={"content": content}, timeout=10)
        print(f"DEBUG: Discord POST status {r.status_code}")  # debug
        if r.status_code not in (200, 204):
            print(f"Discord responded {r.status_code}: {r.text[:300]}")
        else:
            print("Discord message sent successfully")
    except Exception as e:
        print("Failed to send to Discord:", e)


# ----------------------------
# COMPOSE DISCORD MESSAGE
# ----------------------------
def compose_discord_message(df, live_price):
    indicators = compute_indicators(df)
    price = float(live_price)
    
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

_Data window: last {len(df)} hourly candles (30-day history)._
"""
    return message
