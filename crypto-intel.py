#!/usr/bin/env python3
"""
crypto-intel.py (v3.0) - Advanced Crypto Intel for GitHub Actions

Features:
- Market movers (top coins)
- Million+ on-chain whale transfers for multiple chains
- Biggest whale transfer in last 24h
- Exchange inflow/outflow summary and market pressure signal
- Stablecoin dominance (CoinGecko)
- News (Cryptopanic + CoinDesk RSS)
- Fear & Greed
- Batching for Discord message length safety
- No API keys required (public endpoints)
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime
import feedparser

# ----------------------------
# CONFIG
# ----------------------------
WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not WEBHOOK:
    raise Exception("Missing DISCORD_WEBHOOK environment variable (repository secret).")

CHAIN_ENDPOINTS = {
    "Bitcoin": "btc",
    "Ethereum": "eth",
    "XRP": "xrp",
    "Solana": "sol",
    "TRON": "trx",
    "Cardano": "ada",
    "Polygon": "matic",
    "Tether USDT": "usdt"
}

EXCHANGE_KEYWORDS = [
    "binance","coinbase","kraken","bitfinex","huobi","kucoin",
    "okx","mexc","gateio","bitstamp","bittrex","bitso","gemini"
]

MIN_TRANSFER_USD = 1_000_000
DISCORD_CHUNK_LIMIT = 1800

STABLECOIN_IDS = ["tether","usd-coin","binance-usd","dai","true-usd","tether-gold"]
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

# ----------------------------
# UTILITIES
# ----------------------------
def send_raw(msg):
    """Send single message payload to Discord webhook."""
    try:
        r = requests.post(WEBHOOK, json={"content": msg}, timeout=10)
        if r.status_code in (200,204):
            print("✅ Discord message sent")
        else:
            print(f"⚠️ Discord responded {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print("❌ Failed to send Discord message:", e)

def send_batched(messages):
    """Batch messages into Discord-safe chunks and send sequentially."""
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
# 1. Market Movers
# ----------------------------
try:
    params = {"vs_currency":"usd","order":"market_cap_desc","per_page":12,"page":1,"sparkline":"false"}
    r = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=15)
    markets = r.json() if r.status_code==200 else []
    mm = "📊 **Top Market Movers (24h)**\n\n"
    for coin in markets:
        name = coin.get("name","N/A")
        price = coin.get("current_price",0.0)
        change24 = coin.get("price_change_percentage_24h",0.0)
        mm += f"• **{name}** — ${price:.2f} ({change24:.2f}%)\n"
    messages.append(mm)
except Exception as e:
    print("Market movers error:", e)
    messages.append("⚠️ Market overview unavailable.")

# ----------------------------
# 2. Whale Alerts – On-Chain
# ----------------------------
try:
    whale_msg = "🐋 **On-Chain Whale Tracker (Million+ USD Transfers)**\n\n"
    datasets = {chain: f"https://bitinfocharts.com/api/large-transactions/{slug}" for chain,slug in CHAIN_ENDPOINTS.items()}

    biggest_transfer = {"amount":0,"chain":None,"tx":None}
    exchange_inflows = 0.0
    exchange_outflows = 0.0
    any_million_found = False

    for chain,url in datasets.items():
        try:
            res = requests.get(url, timeout=10)
            print(f"[whale] {chain} {url} => status {res.status_code}")
            if res.status_code != 200:
                whale_msg += f"**{chain}:** API returned {res.status_code}\n\n"
                continue
            data = res.json()
            if not isinstance(data,list) or len(data)==0:
                whale_msg += f"**{chain}:** No data\n\n"
                continue

            transfers = []
            for t in data:
                amt = float(t.get("amount_usd",0))
                if amt >= MIN_TRANSFER_USD:
                    transfers.append((amt,t))
                    any_million_found = True

            if not transfers:
                whale_msg += f"**{chain}:** No $1M+ transfers today\n\n"
                continue

            whale_msg += f"**{chain} – Top Transfers**\n"
            for amt,tx in transfers[:5]:
                sender = tx.get("from","?") or "?"
                receiver = tx.get("to","?") or "?"
                hash_url = tx.get("hash_url","")
                whale_msg += f"• ${int(amt):,} — `{sender}` ➜ `{receiver}`\n  TX: {hash_url}\n"

                if amt > biggest_transfer["amount"]:
                    biggest_transfer = {"amount":amt,"chain":chain,"tx":tx}

                s = sender.lower()
                r = receiver.lower()
                hx = hash_url.lower()
                if any(ex in s or ex in hx for ex in EXCHANGE_KEYWORDS):
                    exchange_outflows += amt
                if any(ex in r or ex in hx for ex in EXCHANGE_KEYWORDS):
                    exchange_inflows += amt
            whale_msg += "\n"

        except Exception as e:
            print(f"[whale] {chain} exception:", e)
            whale_msg += f"**{chain}:** Error fetching data\n\n"

    # summary
    if biggest_transfer["amount"] > 0:
        tx = biggest_transfer["tx"]
        whale_msg += "🏆 **Largest Whale Transfer**\n"
        whale_msg += f"• Chain: {biggest_transfer['chain']}\n"
        whale_msg += f"• Amount: ${int(biggest_transfer['amount']):,}\n"
        whale_msg += f"• From: `{tx.get('from','?')}`\n"
        whale_msg += f"• To: `{tx.get('to','?')}`\n"
        whale_msg += f"• TX: {tx.get('hash_url','')}\n\n"
    else:
        whale_msg += "🏆 **Largest Whale Transfer:** No data\n\n"

    # exchange flows
    whale_msg += "🏦 **Exchange Flow Summary**\n"
    whale_msg += f"• Inflows: ${int(exchange_inflows):,}\n"
    whale_msg += f"• Outflows: ${int(exchange_outflows):,}\n"
    if exchange_inflows > exchange_outflows*1.3:
        whale_msg += "📉 Market Pressure: Bearish\n"
    elif exchange_outflows > exchange_inflows*1.3:
        whale_msg += "📈 Market Pressure: Bullish\n"
    else:
        whale_msg += "⚖️ Market Pressure: Neutral\n"

    if not any_million_found:
        whale_msg += "\n_Note: No $1M+ transfers today._"

    messages.append(whale_msg)

except Exception as e:
    print("Whale section fatal error:", e)
    messages.append("⚠️ Whale section failed.")

# ----------------------------
# 3. Crypto News (Cryptopanic + CoinDesk RSS)
# ----------------------------
try:
    news_msg = "📰 **Crypto News (Top Headlines)**\n\n"
    # Primary: Cryptopanic
    try:
        cp = requests.get("https://cryptopanic.com/api/v1/posts/?auth_token=ef2c4418f36f0ad41f9798f5d9ccf7a8f1a&filter=important", timeout=12)
        news = cp.json() if cp.status_code==200 else {}
        items = news.get("results",[]) if isinstance(news,dict) else []
        if items:
            for n in items[:8]:
                news_msg += f"• **{n.get('title','No title')}**\n{n.get('url','')}\n\n"
        else:
            raise Exception("cryptopanic empty")
    except Exception:
        # Fallback: CoinDesk RSS
        feed = feedparser.parse("https://www.coindesk.com/arc/outboundfeeds/rss/")
        for entry in feed.entries[:8]:
            news_msg += f"• **{entry.title}**\n{entry.link}\n\n"
    messages.append(news_msg)
except Exception as e:
    print("News error:", e)
    messages.append("⚠️ Crypto news unavailable.")

# ----------------------------
# 4. Stablecoin Dominance
# ----------------------------
try:
    params = {"vs_currency":"usd","ids":",".join(STABLECOIN_IDS)}
    r = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=12)
    stable_data = r.json() if r.status_code==200 else []
    stable_total = sum(item.get("market_cap",0) for item in stable_data if isinstance(item,dict))
    r2 = requests.get(COINGECKO_MARKETS_URL, params={"vs_currency":"usd","order":"market_cap_desc","per_page":250,"page":1}, timeout=15)
    top250 = r2.json() if r2.status_code==200 else []
    total_mc = sum(item.get("market_cap",0) for item in top250 if isinstance(item,dict))
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
# 5. Fear & Greed Index
# ----------------------------
try:
    fg = requests.get("https://api.alternative.me/fng/", timeout=8).json()
    if isinstance(fg,dict) and fg.get("data"):
        val = fg["data"][0]["value"]
        lbl = fg["data"][0]["value_classification"]
        messages.append(f"😨 **Fear & Greed Index:** {val} — {lbl}")
    else:
        messages.append("⚠️ F&G index unavailable.")
except Exception as e:
    print("F&G error:", e)
    messages.append("⚠️ F&G index unavailable.")

# ----------------------------
# 6. Final assembly & send
# ----------------------------
try:
    header = f"⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    final_messages = [header] + messages + ["✅ **Crypto Intel Report Complete**"]
    send_batched(final_messages)
except Exception as e:
    print("Final send error:", e)
    send_raw("⚠️ Failed to send final Crypto Intel report.")
