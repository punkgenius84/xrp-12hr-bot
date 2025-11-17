import requests
import os
import json
import pandas as pd

WEBHOOK = os.getenv("DISCORD_WEBHOOK")

if WEBHOOK is None:
    raise Exception("Discord webhook is missing. Add DISCORD_WEBHOOK in GitHub Secrets.")

# ----------------------------
# Helper to send message
# ----------------------------
def send(msg):
    payload = {"content": msg}
    requests.post(WEBHOOK, json=payload)

send("📡 **Crypto Intel Report – Starting Scan…**")

# ----------------------------
# 1. Market Overview
# ----------------------------
try:
    cmc = requests.get(
        "https://api.coinlore.net/api/tickers/?start=0&limit=20"
    ).json()

    top = cmc.get("data", [])[:10]

    msg = "📊 **Top Market Movers (24h)**\n\n"
    for c in top:
        msg += f"• **{c['name']}** — ${c['price_usd']} ({c['percent_change_24h']}%)\n"

    send(msg)
except:
    send("⚠️ Market overview unavailable.")

# ----------------------------
# 2. Whale Alerts (no API key required)
# ----------------------------
try:
    whale = requests.get("https://api.whale-alert.io/v1/transactions?limit=20").json()

    msg = "🐋 **Whale Activity (Recent)**\n\n"

    if "transactions" in whale:
        for t in whale["transactions"][:10]:
            amount = t.get("amount", 0)
            symbol = t.get("symbol", "???")
            from_addr = t.get("from", {}).get("owner", "Unknown")
            to_addr = t.get("to", {}).get("owner", "Unknown")

            msg += f"• {amount} {symbol} — {from_addr} ➜ {to_addr}\n"
    else:
        msg += "No whale data available."

    send(msg)
except:
    send("⚠️ Whale Alert unavailable.")

# ----------------------------
# 3. Crypto News
# ----------------------------
try:
    news = requests.get(
        "https://cryptopanic.com/api/v1/posts/?auth_token=ef2c4418f36f0ad41f9798f5d9ccf7a8f1a&filter=important"
    ).json()

    items = news.get("results", [])

    msg = "📰 **Crypto News (Top Headlines)**\n\n"
    for n in items[:8]:
        msg += f"• **{n.get('title', 'No title')}**\n{n.get('url', '')}\n\n"

    send(msg)
except:
    send("⚠️ Crypto news unavailable.")

# ----------------------------
# 4. Fear & Greed Index
# ----------------------------
try:
    fg = requests.get("https://api.alternative.me/fng/").json()
    value = fg["data"][0]["value"]
    classification = fg["data"][0]["value_classification"]

    send(f"😨 **Fear & Greed Index:** {value} — {classification}")
except:
    send("⚠️ F&G index unavailable.")

# ----------------------------
# 5. Final Status
# ----------------------------
send("✅ **Crypto Intel Report Complete**")
