#!/usr/bin/env python3
"""
XRP Combined Intel Report – Discord Embeds + X Auto-Post (OAuth 1.0a User Context)
Multi-timeframe: 15m, 1h, 24h
Smart adaptive levels · Clickable news · Works perfectly on GitHub Actions
November 2025 – EMBED VERSION
"""

import os
import requests
import feedparser
import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, ADXIndicator
from ta.volatility import BollingerBands
from ta.volume import OnBalanceVolumeIndicator
from datetime import datetime
from requests_oauthlib import OAuth1
from smartmoneyconcepts import smc  # For market structure logic

# ========================= CONFIG =========================
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

CSV_FILE = "xrp_history.csv"

# ========================= HELPERS =========================
def fmt(x, decimals=4):
    try:
        return f"{float(x):,.{decimals}f}".rstrip("0").rstrip(".")
    except:
        return str(x)

# ========================= DISCORD EMBEDS =========================
def send_discord_embed(title, fields=None, news=None):
    if not DISCORD_WEBHOOK:
        print("No Discord webhook → skipping send")
        return
    embeds = [{
        "title": title,
        "color": 0x00ff00,
        "fields": fields or [],
        "footer": {"text": "Auto-updated via GitHub Actions"},
        "timestamp": datetime.utcnow().isoformat()
    }]
    if news:
        embeds.append({
            "title": "📰 Latest XRP, Ripple & BTC News",
            "description": news,
            "color": 0x3498db
        })
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"embeds": embeds}, timeout=15)
        if r.status_code in (200, 204):
            print("Embed report sent to Discord")
        else:
            print(f"Discord embed failed ({r.status_code}): {r.text}")
    except Exception as e:
        print("Discord embed send error:", e)

# ========================= X POST =========================
def post_to_x(text):
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        print("Missing X credentials → skipping post")
        return
    url = "https://api.twitter.com/2/tweets"
    auth = OAuth1(X_API_KEY, client_secret=X_API_SECRET,
                  resource_owner_key=X_ACCESS_TOKEN, resource_owner_secret=X_ACCESS_SECRET)
    try:
        r = requests.post(url, json={"text": text}, auth=auth, timeout=10)
        if r.status_code == 201:
            print("Posted to X successfully!")
        else:
            print(f"X post failed ({r.status_code}): {r.text}")
    except Exception as e:
        print("X post error:", e)

# ========================= DATA FETCH =========================
def fetch_xrp_data(timeframe="1h", limit=2000):
    if timeframe == "15m":
        url = "https://min-api.cryptocompare.com/data/v2/histominute"
        params = {"fsym": "XRP", "tsym": "USDT", "limit": limit, "aggregate": 15}
    elif timeframe == "24h":
        url = "https://min-api.cryptocompare.com/data/v2/histoday"
        params = {"fsym": "XRP", "tsym": "USDT", "limit": limit}
    else:
        url = "https://min-api.cryptocompare.com/data/v2/histohour"
        params = {"fsym": "XRP", "tsym": "USDT", "limit": limit}

    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df["open_time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"volumeto": "volume"}, inplace=True)
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    return df

# ========================= INDICATORS =========================
def compute_indicators(df):
    c = df["close"]
    rsi_series = RSIIndicator(c, window=14).rsi()
    macd = MACD(c, window_fast=12, window_slow=26, window_sign=9)
    ema50 = EMAIndicator(c, window=50).ema_indicator().iloc[-1]
    ema200 = EMAIndicator(c, window=200).ema_indicator().iloc[-1]
    bb = BollingerBands(c, window=20, window_dev=2)
    stoch = StochasticOscillator(df["high"], df["low"], c)
    adx_val = ADXIndicator(df["high"], df["low"], c).adx().iloc[-1]
    obv_val = OnBalanceVolumeIndicator(c, df["volume"]).on_balance_volume().iloc[-1]

    return {
        "rsi": rsi_series.iloc[-1],
        "macd": macd.macd().iloc[-1],
        "signal": macd.macd_signal().iloc[-1],
        "ema50": ema50,
        "ema200": ema200,
        "bb_mavg": bb.bollinger_mavg().iloc[-1],
        "bb_signal": ("Overbought 🔴" if c.iloc[-1] > bb.bollinger_hband().iloc[-1]
                      else "Oversold 🟢" if c.iloc[-1] < bb.bollinger_lband().iloc[-1] else "Neutral"),
        "stoch_k": stoch.stoch().iloc[-1],
        "stoch_d": stoch.stoch_signal().iloc[-1],
        "adx": adx_val,
        "obv": obv_val
    }

# ========================= VOLUME =========================
def volume_spike(df):
    ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    if ratio >= 1.5: return f"Extreme Surge {ratio:.2f}x 🔥"
    if ratio >= 1.3: return f"Strong Surge {ratio:.2f}x ⚡"
    if ratio >= 1.15: return f"Elevated {ratio:.2f}x ⚠️"
    return "Normal"

# ========================= MARKET STRUCTURE =========================
def compute_market_structure(df):
    try:
        swings = smc.swing_highs_lows(df, swing_length=50)
        bos_choch = smc.bos_choch(df, swing_highs_lows=swings, close_break=True)
        latest = bos_choch.iloc[-1]
        if latest["BOS"] == 1: return "Bullish BOS 🟢"
        if latest["BOS"] == -1: return "Bearish BOS 🔴"
        if latest["CHOCH"] == 1: return "Bullish CHOCH 🟢"
        if latest["CHOCH"] == -1: return "Bearish CHOCH 🔴"
        return "Ranging"
    except:
        return "Unavailable"

# ========================= DYNAMIC LEVELS =========================
def dynamic_levels(df):
    price = df["close"].iloc[-1]
    recent_high = df["high"].tail(24).max()
    recent_low = df["low"].tail(24).min()
    r = max(recent_high - recent_low, 0.0001)
    return {
        "breakout_strong": recent_low + r * 0.618,
        "breakout_weak": recent_low + r * 0.382,
        "breakdown_strong": recent_low + r * 0.236,
        "breakdown_weak": recent_low + r * 0.118,
        "danger": recent_low
    }

def flips_triggers(price, levels):
    triggers = []
    if price > levels["breakout_strong"]: triggers.append("🚀 Strong Bullish")
    elif price > levels["breakout_weak"]: triggers.append("Bullish (Weak)")
    if price < levels["breakdown_strong"]: triggers.append("💥 Strong Bearish")
    elif price < levels["breakdown_weak"]: triggers.append("Bearish (Weak)")
    if price < levels["danger"]: triggers.append("🚨 Danger Zone")
    return triggers[0] if triggers else "Stable"

# ========================= NEWS =========================
def get_news_section():
    try:
        feed = feedparser.parse("https://cryptonews.com/news/rss/")
        keywords = ["XRP", "Ripple", "BTC", "Bitcoin"]
        filtered = [e for e in feed.entries if any(kw.lower() in (e.title + getattr(e, 'description', '')).lower() for kw in keywords)]
        return "\n".join([f"[{e.title.replace('`','\'')}]({e.link})" for e in filtered[:5]]) or "No relevant news"
    except:
        return "News temporarily unavailable"

# ========================= MAIN =========================
def main():
    timeframes = ["15m", "1h", "24h"]
    embed_fields = []

    for tf in timeframes:
        df = fetch_xrp_data(tf)
        df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce")
        df = df.drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
        price = df["close"].iloc[-1]
        indicators = compute_indicators(df)
        vol_text = volume_spike(df)
        levels = dynamic_levels(df)
        triggers = flips_triggers(price, levels)
        market_struct = compute_market_structure(df)

        embed_fields.extend([
            {"name": f"⏱ {tf} Current Price", "value": f"${fmt(price,3)}", "inline": True},
            {"name": f"⏱ {tf} RSI", "value": f"{fmt(indicators['rsi'],2)}", "inline": True},
            {"name": f"⏱ {tf} MACD", "value": f"{fmt(indicators['macd'],4)} | Signal {fmt(indicators['signal'],4)}", "inline": True},
            {"name": f"⏱ {tf} EMA50/200", "value": f"{fmt(indicators['ema50'],4)} / {fmt(indicators['ema200'],4)}", "inline": True},
            {"name": f"⏱ {tf} Bollinger", "value": f"Middle {fmt(indicators['bb_mavg'],4)} | {indicators['bb_signal']}", "inline": True},
            {"name": f"⏱ {tf} Stoch %K/%D", "value": f"{fmt(indicators['stoch_k'],2)}/{fmt(indicators['stoch_d'],2)}", "inline": True},
            {"name": f"⏱ {tf} Market Structure", "value": market_struct, "inline": True},
            {"name": f"⏱ {tf} Volume", "value": vol_text, "inline": True},
            {"name": f"⏱ {tf} Flips/Triggers", "value": triggers, "inline": True}
        ])

    news = get_news_section()
    send_discord_embed(f"🚨 Combined XRP Intel Report — {datetime.utcnow().strftime('%b %d, %H:%M UTC')}",
                       embed_fields, news)

    # Post teaser to X
    post_to_x(f"🚨 XRP Intel — Price: ${fmt(price,3)} | Vol: {vol_text} | Flips: {triggers} #XRP #Crypto")

if __name__ == "__main__":
    main()
