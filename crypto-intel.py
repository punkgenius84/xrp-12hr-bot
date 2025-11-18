#!/usr/bin/env python3
"""
crypto-intel.py (v3.0) - Simplified Crypto Intel for GitHub Actions

Features:
- Top 5 Market Movers
- Crypto News (CoinDesk RSS, English)
- Stablecoin dominance
- Fear & Greed Index
- Batched Discord message support
- No API keys required except Discord webhook
"""

import os
import time
import requests
import feedparser
from datetime import datetime

# ----------------------------
# CONFIG
# ----------------------------
WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not WEBHOOK:
    raise Exception("Missing DISCORD_WEBHOOK environment variable (repository secret).")

DISCORD_CHUNK_LIMIT = 1800  # safe chunk size for Discord messages

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
STABLECOIN_IDS = ["tether", "usd-coin", "binance-usd", "dai", "true-usd"]

# ----------------------------
# UTILITY FUNCTIONS
# ----------------------------
def send_raw(msg):
    """Send single message payload to Discord webhook."""
    try:
        r = requests.post(WEBHOOK, json={"content": msg}, timeout=10)
        if r.status_code in (200, 204):
            print("✅ Discord message sent")
        else:
            print(f"⚠️ Discord responded {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print("❌ Failed to send Discord message:", e)

def send_batched(messages):
    """Batch messages into Discord-safe chunks and send sequentially with small pauses."""
    chunk = ""
    for m in messages:
        if len(chunk) + len(m) + 2 > DISCORD_CHUNK_LIMIT:
            send_raw(chunk)
            time.sleep(1)
            chunk = m + "\n\n"
        else:
            chunk += (m + "\n\n")
    if chunk.strip():
        send_raw(chunk)

def fmt_usd(x):
    try:
        return f"${int(round(x)):,}"
    except Exception:
        return str(x)

# ----------------------------
# 0. Intro
# ----------------------------
send_raw("📡 **Crypto Intel Report – Starting Scan…**")
messages = []

# ----------------------------
# 1. Top 5 Market Movers
# ----------------------------
try:
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 5, "page": 1, "sparkline": "false"}
    r = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=15)
    markets = r.json() if r.status_code == 200 else []
    mm_msg = "📊 **Top Market Movers (24h)**\n\n"
    for coin in markets:
        name = coin.get("name", "N/A")
        price = coin.get("current_price", 0)
        change24 = coin.get("price_change_percentage_24h", 0)
        mm_msg += f"• **{name}** — ${price:.2f} ({change24:.2f}%)\n"
    messages.append(mm_msg)
except Exception as e:
    print("Market movers error:", e)
    messages.append("⚠️ Market overview unavailable.")

# ----------------------------
# 2. Crypto News (CoinDesk RSS)
# ----------------------------
try:
    news_msg = "📰 **Crypto News (Top Headlines)**\n\n"
    feed = feedparser.parse("https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml")
    entries = feed.entries[:8]  # top 8 headlines
    if entries:
        for entry in entries:
            title = entry.get("title", "No title")
            link = entry.get("link", "")
            news_msg += f"• **{title}**\n{link}\n\n"
    else:
        news_msg += "No headlines available.\n"
    messages.append(news_msg)
except Exception as e:
    print("News error:", e)
    messages.append("⚠️ Crypto news unavailable.")

# ----------------------------
# 3. Stablecoin Dominance (CoinGecko)
# ----------------------------
try:
    params = {"vs_currency": "usd", "ids": ",".join(STABLECOIN_IDS)}
    r = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=12)
    stable_data = r.json() if r.status_code == 200 else []
    stable_total = sum(item.get("market_cap", 0) for item in stable_data if isinstance(item, dict))
    # total top 250 market cap
    r2 = requests.get(COINGECKO_MARKETS_URL, params={"vs_currency":"usd","order":"market_cap_desc","per_page":250,"page":1}, timeout=15)
    top250 = r2.json() if r2.status_code == 200 else []
    total_mc = sum(item.get("market_cap", 0) for item in top250 if isinstance(item, dict))
    dominance_pct = (stable_total / total_mc * 100) if total_mc and stable_total else 0.0
    sc_msg = "💵 **Stablecoin Dominance (approx)**\n"
    sc_msg += f"• Stablecoin marketcap (selected): {fmt_usd(stable_total)}\n"
    sc_msg += f"• Top-250 marketcap total: {fmt_usd(total_mc)}\n"
    sc_msg += f"• Dominance (selected stablecoins): {dominance_pct:.2f}%\n"
    messages.append(sc_msg)
except Exception as e:
    print("Stablecoin error:", e)
    messages.append("⚠️ Stablecoin dominance unavailable.")

# ----------------------------
# 4. Fear & Greed Index (alternative.me)
# ----------------------------
try:
    fg = requests.get("https://api.alternative.me/fng/", timeout=8).json()
    if isinstance(fg, dict) and fg.get("data"):
        val = fg["data"][0]["value"]
        lbl = fg["data"][0]["value_classification"]
        messages.append(f"😨 **Fear & Greed Index:** {val} — {lbl}")
    else:
        messages.append("⚠️ F&G index unavailable.")
except Exception as e:
    print("F&G error:", e)
    messages.append("⚠️ F&G index unavailable.")

# ----------------------------
# 5. Final assembly & send
# ----------------------------
try:
    header = f"⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    final_messages = [header] + messages + ["✅ **Crypto Intel Report Complete**"]
    send_batched(final_messages)
except Exception as e:
    print("Final send error:", e)
    send_raw("⚠️ Failed to send final Crypto Intel report.")
