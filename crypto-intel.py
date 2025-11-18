#!/usr/bin/env python3
"""
crypto-intel.py (v2.0) - Advanced Crypto Intel for GitHub Actions

Features:
- Market movers (top coins)
- Million+ on-chain whale transfers for multiple chains
- Biggest whale transfer in last 24h
- Exchange inflow/outflow summary and market pressure signal
- Stablecoin dominance (CoinGecko)
- News + Fear & Greed
- Batching for Discord message length safety
- No API keys required (public endpoints)
"""

import os
import time
import math
import requests
import pandas as pd
from datetime import datetime, timedelta

# ----------------------------
# CONFIG
# ----------------------------
WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not WEBHOOK:
    raise Exception("Missing DISCORD_WEBHOOK environment variable (repository secret).")

# chains and their bitinfocharts slug (public)
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

# Exchanges keywords to detect in `from` / `to` fields (lowercase)
EXCHANGE_KEYWORDS = [
    "binance", "coinbase", "kraken", "bitfinex", "huobi", "kucoin",
    "okx", "mexc", "gateio", "bitstamp", "bittrex", "bitso", "gemini"
]

# thresholds
MIN_TRANSFER_USD = 1_000_000  # $1,000,000
DISCORD_CHUNK_LIMIT = 1800    # safe chunk size to avoid hitting 2000 char limit

# stablecoins for dominance check (CoinGecko ids)
STABLECOIN_IDS = ["tether", "usd-coin", "binance-usd", "dai", "true-usd", "tether-gold"]  # tgld included rarely
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

# utility
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

# formatting helpers
def fmt_usd(x):
    try:
        return f"${int(round(x)):,}"
    except Exception:
        return str(x)

def safe_get(d, k, default=""):
    return d.get(k, default) if isinstance(d, dict) else default

# ----------------------------
# 0. Intro
# ----------------------------
send_raw("📡 **Crypto Intel Report – Starting Scan…**")

# collect message parts for batching
messages = []

# ----------------------------
# 1. Market Movers (Top 12 by market cap via CoinGecko)
# ----------------------------
try:
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 12, "page": 1, "sparkline": "false"}
    r = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=15)
    markets = r.json() if r.status_code == 200 else []
    mm = "📊 **Top Market Movers (24h)**\n\n"
    for coin in markets:
        name = coin.get("name", "N/A")
        price = coin.get("current_price", "N/A")
        change24 = coin.get("price_change_percentage_24h", "N/A")
        mm += f"• **{name}** — ${price:.2f} ({change24:.2f}%)\n"
    messages.append(mm)
except Exception as e:
    print("Market movers error:", e)
    messages.append("⚠️ Market overview unavailable.")

# ----------------------------
# 2. Whale Alerts – On-Chain (robust: debug + fallback to 100k)
# ----------------------------
try:
    msg = "🐋 **On-Chain Whale Tracker (Million+ USD Transfers)**\n\n"

    datasets = {
        "Bitcoin": "https://bitinfocharts.com/api/v1/large-transactions/btc",
        "Ethereum": "https://bitinfocharts.com/api/v1/large-transactions/eth",
        "XRP": "https://bitinfocharts.com/api/v1/large-transactions/xrp",
        "Solana": "https://bitinfocharts.com/api/v1/large-transactions/sol",
        "TRON": "https://bitinfocharts.com/api/v1/large-transactions/trx",
        "Cardano": "https://bitinfocharts.com/api/v1/large-transactions/ada",
        "Polygon": "https://bitinfocharts.com/api/v1/large-transactions/matic",
        "Tether USDT": "https://bitinfocharts.com/api/v1/large-transactions/usdt",
    }

    biggest_transfer = {"amount": 0, "chain": None, "tx": None}
    exchange_inflows = 0.0
    exchange_outflows = 0.0

    exchanges = [
        "binance", "coinbase", "kraken", "bitfinex",
        "huobi", "kucoin", "okx", "mexc", "bitstamp", "gateio", "gemini"
    ]

    MIN_USD = 1_000_000  # primary threshold
    FALLBACK_MIN_USD = 100_000  # fallback threshold if no million+ transfers found

    any_million_found = False

    for chain, url in datasets.items():
        try:
            res = requests.get(url, timeout=12)
            status = res.status_code
            # Print debug info to Actions log so you can inspect responses:
            print(f"[whale] {chain} {url} => status {status}")
            try:
                data = res.json() if status == 200 else []
            except Exception as e:
                # sometimes endpoint returns HTML/text; log a small sample
                text_sample = res.text[:400].replace("\n"," ")
                print(f"[whale] {chain} json parse failed, sample: {text_sample}")
                data = []

        except Exception as e:
            print(f"[whale] fetch error for {chain}: {e}")
            data = []

        if not isinstance(data, list) or len(data) == 0:
            msg += f"**{chain}:** No $1,000,000+ transfers in feed (or feed empty)\n\n"
            continue

        # filter actual million+ transfers
        transfers = []
        for t in data:
            try:
                amt = float(t.get("amount_usd", 0))
            except Exception:
                amt = 0.0
            # optional timestamp filtering (if feed provides 'time' or 'timestamp')
            ts = None
            if isinstance(t.get("time"), (int, float)):
                try:
                    ts = datetime.utcfromtimestamp(int(t.get("time")))
                except Exception:
                    ts = None

            if amt >= MIN_USD:
                transfers.append((amt, t))
                any_million_found = True

        if not transfers:
            # Fallback: show >= FALLBACK_MIN_USD so we can confirm feed is live
            small_transfers = []
            for t in data:
                try:
                    amt = float(t.get("amount_usd", 0))
                except Exception:
                    amt = 0.0
                if amt >= FALLBACK_MIN_USD:
                    small_transfers.append((amt, t))
            if small_transfers:
                msg += f"**{chain}:** No $1,000,000+ transfers, showing >= ${FALLBACK_MIN_USD:,} instead\n"
                transfers = sorted(small_transfers, key=lambda x: -x[0])
            else:
                msg += f"**{chain}:** No $100k+ transfers in feed\n\n"
                continue

        # report top 5 transfers for this chain
        msg += f"**{chain} – Top Transfers**\n"
        for amt, tx in transfers[:5]:
            sender = str(tx.get("from", tx.get("sender", "Unknown")))
            receiver = str(tx.get("to", tx.get("receiver", "Unknown")))
            hash_url = tx.get("hash_url", tx.get("tx_url", "")) or ""
            time_str = ""
            if tx.get("time"):
                try:
                    time_str = datetime.utcfromtimestamp(int(tx.get("time"))).strftime("%Y-%m-%d %H:%M UTC")
                except Exception:
                    time_str = ""
            msg += f"• ${int(amt):,} — From `{sender}` ➜ `{receiver}`\n  TX: {hash_url} {time_str}\n"

            # update biggest transfer
            if amt > biggest_transfer["amount"]:
                biggest_transfer = {"amount": amt, "chain": chain, "tx": tx}

            s_lower = sender.lower()
            r_lower = receiver.lower()
            # improved exchange detection:
            s_ex = any(ex in s_lower for ex in exchanges) or any(ex in (hash_url or "").lower() for ex in exchanges)
            r_ex = any(ex in r_lower for ex in exchanges) or any(ex in (hash_url or "").lower() for ex in exchanges)
            if r_ex:
                exchange_inflows += amt
            if s_ex:
                exchange_outflows += amt

        msg += "\n"

    # summary for largest whale
    if biggest_transfer["amount"] > 0:
        tx = biggest_transfer["tx"]
        msg += "🏆 **Largest Whale Transfer (From feeds, ~24h)**\n"
        msg += f"• Chain: **{biggest_transfer['chain']}**\n"
        msg += f"• Amount: **${int(biggest_transfer['amount']):,}**\n"
        msg += f"• From: `{tx.get('from', tx.get('sender','?'))}`\n"
        msg += f"• To: `{tx.get('to', tx.get('receiver','?'))}`\n"
        msg += f"• TX: {tx.get('hash_url', tx.get('tx_url',''))}\n\n"
    else:
        msg += "🏆 **Largest Whale Transfer:** No data found in the feeds.\n\n"

    # exchange flow summary
    msg += "🏦 **Exchange Flow Summary (approx, USD)**\n"
    msg += f"• **Exchange Inflows:** ${int(exchange_inflows):,}\n"
    msg += f"• **Exchange Outflows:** ${int(exchange_outflows):,}\n"
    if exchange_inflows > exchange_outflows * 1.3:
        msg += "📉 **Market Pressure:** Bearish (More flowing INTO exchanges)\n"
    elif exchange_outflows > exchange_inflows * 1.3:
        msg += "📈 **Market Pressure:** Bullish (More flowing OUT of exchanges)\n"
    else:
        msg += "⚖️ **Market Pressure:** Neutral\n"

    # if no million found, add note
    if not any_million_found:
        msg += "\n_Note: No $1M+ transfers were found in primary feeds; displayed smaller transfers (>= $100k) where available._\n"

    send(msg)

except Exception as e:
    print("Whale section fatal error:", e)
    send("⚠️ Whale section failed.")


# ----------------------------
# 3. Crypto News (Cryptopanic fallback) - may be rate limited
# ----------------------------
try:
    news_msg = "📰 **Crypto News (Top Headlines)**\n\n"
    # Cryptopanic requires key for some endpoints; use GDELT as fallback headlines
    try:
        cp = requests.get("https://cryptopanic.com/api/v1/posts/?auth_token=ef2c4418f36f0ad41f9798f5d9ccf7a8f1a&filter=important", timeout=12)
        news = cp.json() if cp.status_code == 200 else {}
        items = news.get("results", []) if isinstance(news, dict) else []
        if not items:
            raise Exception("cryptopanic empty")
        for n in items[:8]:
            news_msg += f"• **{n.get('title','No title')}**\n{n.get('url','')}\n\n"
    except Exception:
        # fallback: GDELT artlist on crypto topic
        gd = requests.get("https://api.gdeltproject.org/api/v2/doc/doc?query=cryptocurrency&mode=artlist&maxrecords=8&format=json", timeout=12)
        gdj = gd.json() if gd.status_code == 200 else {}
        arts = gdj.get("articles", []) if isinstance(gdj, dict) else []
        if arts:
            for a in arts[:8]:
                news_msg += f"• **{a.get('title','No title')}**\n{a.get('url','')}\n\n"
        else:
            news_msg += "No headlines available.\n"
    messages.append(news_msg)
except Exception as e:
    print("News error:", e)
    messages.append("⚠️ Crypto news unavailable.")

# ----------------------------
# 4. Stablecoin Dominance (CoinGecko market caps)
# ----------------------------
try:
    params = {"vs_currency": "usd", "ids": ",".join(STABLECOIN_IDS)}
    r = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=12)
    stable_data = r.json() if r.status_code == 200 else []
    stable_total = sum(item.get("market_cap", 0) for item in stable_data if isinstance(item, dict))
    # also fetch top total market cap (approx top 250 coins)
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
# 5. Fear & Greed Index (alternative.me)
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
# 6. Final assembly & sends (batched)
# ----------------------------
try:
    # prefix with timestamp
    header = f"⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    # build final message chunks
    final_messages = [header] + messages + ["✅ **Crypto Intel Report Complete**"]
    send_batched(final_messages)
except Exception as e:
    print("Final send error:", e)
    send_raw("⚠️ Failed to send final Crypto Intel report.")
