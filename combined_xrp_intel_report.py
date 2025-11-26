#!/usr/bin/env python3
"""
XRP Combined Intel Report – Discord Embeds + X Auto-Post (OAuth 1.0a User Context)
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
    if isinstance(x, (int, float)):
        formatted = f"{float(x):,.{decimals}f}".rstrip("0").rstrip(".")
        return formatted if '.' in formatted or 'e' in formatted.lower() else formatted + '.0' if decimals > 0 else formatted
    return str(x)

# ========================= DISCORD EMBEDS =========================
def send_discord_embed(title, fields=None, news=None):
    """
    Sends a Discord embed with multiple fields.
    fields: list of dicts with {"name": str, "value": str, "inline": bool}
    news: str with clickable links (optional)
    """
    if not DISCORD_WEBHOOK:
        print("No Discord webhook set → skipping Discord send")
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

# ========================= X POST (OAuth 1.0a User Context) =========================
def post_to_x(text):
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        print("Missing X credentials → skipping X post")
        return

    url = "https://api.twitter.com/2/tweets"
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

# ========================= DIVERGENCE DETECTION =========================
def detect_divergence(price_series, ind_series, lookback=20):
    price_lows = price_series.rolling(lookback).min()
    price_highs = price_series.rolling(lookback).max()
    ind_lows = ind_series.rolling(lookback).min()
    ind_highs = ind_series.rolling(lookback).max()
    if price_lows.iloc[-1] < price_lows.iloc[-2] and ind_lows.iloc[-1] > ind_lows.iloc[-2]:
        return "Bullish Divergence 🟢"
    if price_highs.iloc[-1] > price_highs.iloc[-2] and ind_highs.iloc[-1] < ind_highs.iloc[-2]:
        return "Bearish Divergence 🔴"
    return "No Divergence"

# ========================= INDICATORS =========================
def compute_indicators(df):
    c = df["close"]
    rsi_series = RSIIndicator(c, window=14).rsi()
    rsi = rsi_series.iloc[-1]
    macd = MACD(c, window_fast=12, window_slow=26, window_sign=9)
    hist = macd.macd_diff()
    trend = "Increasing 🟢" if len(hist) > 1 and hist.iloc[-1] > hist.iloc[-2] else "Decreasing 🔴"
    ema50 = EMAIndicator(c, window=50).ema_indicator().iloc[-1]
    ema200 = EMAIndicator(c, window=200).ema_indicator().iloc[-1]
    bb = BollingerBands(c, window=20, window_dev=2)
    bb_pct = (c.iloc[-1] - bb.bollinger_lband().iloc[-1]) / (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) if (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) != 0 else 0
    bb_signal = "Overbought 🔴" if bb_pct > 0.8 else "Oversold 🟢" if bb_pct < 0.2 else "Neutral"
    bb_width = (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) / bb.bollinger_mavg().iloc[-1]
    stoch = StochasticOscillator(high=df["high"], low=df["low"], close=c, window=14, smooth_window=3)
    stoch_k = stoch.stoch().iloc[-1]
    stoch_d = stoch.stoch_signal().iloc[-1]
    stoch_signal = "Bullish Cross 🟢" if stoch_k > stoch_d and stoch_k < 30 else "Bearish Cross 🔴" if stoch_k < stoch_d and stoch_k > 70 else "Neutral"
    obv_series = OnBalanceVolumeIndicator(c, df["volume"]).on_balance_volume()
    obv = obv_series.iloc[-1]
    obv_trend = "Rising 🟢" if obv > obv_series.iloc[-2] else "Falling 🔴"
    adx = ADXIndicator(df["high"], df["low"], c, window=14)
    adx_val = adx.adx().iloc[-1]
    adx_signal = "Strong Trend 🟢" if adx_val > 25 else "Weak Trend 🔴" if adx_val < 20 else "Neutral"
    rsi_div = detect_divergence(c, rsi_series)
    macd_div = detect_divergence(c, macd.macd())
    return {
        "rsi": rsi,
        "rsi_div": rsi_div,
        "macd": macd.macd().iloc[-1],
        "signal": macd.macd_signal().iloc[-1],
        "macd_div": macd_div,
        "hist_trend": trend,
        "ema50": ema50,
        "ema200": ema200,
        "bb_mavg": bb.bollinger_mavg().iloc[-1],
        "bb_signal": bb_signal,
        "bb_width": bb_width,
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
        "stoch_signal": stoch_signal,
        "obv": obv,
        "obv_trend": obv_trend,
        "adx": adx_val,
        "adx_signal": adx_signal,
    }

# ========================= VOLUME SPIKES =========================
def volume_spike(df):
    ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    ratio = round(ratio, 2)
    if ratio >= 1.5: return f"Extreme Surge {ratio}x 🔥"
    if ratio >= 1.3: return f"Strong Surge {ratio}x ⚡"
    if ratio >= 1.15: return f"Elevated {ratio}x ⚠️"
    return "Normal"

# ========================= MARKET STRUCTURE =========================
def compute_market_structure(df):
    try:
        swing_df = smc.swing_highs_lows(df, swing_length=50)
        bos_choch_df = smc.bos_choch(df, swing_highs_lows=swing_df, close_break=True)
        latest = bos_choch_df.iloc[-1]
        if latest['BOS'] == 1: return "Bullish BOS 🟢"
        elif latest['BOS'] == -1: return "Bearish BOS 🔴"
        elif latest['CHOCH'] == 1: return "Bullish CHOCH 🟢"
        elif latest['CHOCH'] == -1: return "Bearish CHOCH 🔴"
        recent_swings = swing_df.tail(3)
        if len(recent_swings) >= 3:
            highs = recent_swings['high']
            lows = recent_swings['low']
            if highs.iloc[-1] > highs.iloc[-2] > highs.iloc[-3] and lows.iloc[-1] > lows.iloc[-2] > lows.iloc[-3]:
                return "Bullish Structure 🟢"
            elif highs.iloc[-1] < highs.iloc[-2] < highs.iloc[-3] and lows.iloc[-1] < lows.iloc[-2] < lows.iloc[-3]:
                return "Bearish Structure 🔴"
            else:
                return "Ranging Structure ⚪"
        return "No Clear Structure"
    except Exception as e:
        print("Market structure computation failed:", e)
        return "Unavailable"

# ========================= DYNAMIC LEVELS =========================
def dynamic_levels(df):
    price = df["close"].iloc[-1]
    recent_high = df["high"].tail(24).max()
    recent_low = df["low"].tail(24).min()
    weekly_high = df["high"].tail(168).max()
    weekly_low = df["low"].tail(168).min()
    drop_from_week = (weekly_high - price) / weekly_high if weekly_high > 0 else 0
    range_mode = "7-day"
    if drop_from_week > 0.10:
        high = recent_high
        low = recent_low
        range_mode = "24h crash mode"
    else:
        high = weekly_high
        low = weekly_low
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

def caution_level(price, vol_ratio, levels, price_change_1h, bb_width):
    if vol_ratio >= 1.5 or price < levels["danger"] or abs(price_change_1h) >= 5 or bb_width > 0.05:  
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
            lines.append(f"[{title}]({link})")
        return "\n".join(lines) or "No relevant news"
    except Exception as e:
        print("News error:", e)
        return "News temporarily unavailable"

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

    df = pd.concat([old_df, fresh_df], ignore_index=True)
    df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce")
    df = df.drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"Updated CSV → {len(df)} rows")

    if len(df) < 300:
        print("Not enough data yet")
        return

    price = df["close"].iloc[-1]
    i = compute_indicators(df)
    vol_text = volume_spike(df)
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    levels = dynamic_levels(df)
    triggers = flips_triggers(price, levels)
    price_change_1h = ((price / df["close"].iloc[-2]) - 1) * 100 if len(df) > 1 else 0
    caution = caution_level(price, vol_ratio, levels, price_change_1h, i["bb_width"])
    market_struct = compute_market_structure(df)
    high24 = df["high"].tail(24).max()
    low24 = df["low"].tail(24).min()
    news = get_news_section()

    # Build fields for Discord embed
    fields = [
        {"name": "💰 Current Price", "value": f"${fmt(price,3)}", "inline": True},
        {"name": "📈 RSI (14)", "value": f"{fmt(i['rsi'],2)} ({i['rsi_div']})", "inline": True},
        {"name": "📉 MACD", "value": f"{fmt(i['macd'],4)} (signal {fmt(i['signal'],4)}) ({i['macd_div']})", "inline": True},
        {"name": "📊 EMA50 / EMA200", "value": f"{fmt(i['ema50'],4)} / {fmt(i['ema200'],4)}", "inline": True},
        {"name": "📊 Bollinger", "value": f"Middle: {fmt(i['bb_mavg'],4)} | Signal: {i['bb_signal']}", "inline": True},
        {"name": "📈 Stochastic", "value": f"%K {fmt(i['stoch_k'],2)} | %D {fmt(i['stoch_d'],2)} | {i['stoch_signal']}", "inline": True},
        {"name": "🔍 ADX", "value": f"{fmt(i['adx'],2)} | {i['adx_signal']}", "inline": True},
        {"name": "🛡️ Market Structure", "value": market_struct, "inline": True},
        {"name": "📊 Volume Signals", "value": f"{vol_text} | OBV Trend: {i['obv_trend']} ({fmt(i['obv']/1e6,2)}M)", "inline": True},
        {"name": "🔔 Flips / Triggers", "value": triggers, "inline": True},
        {"name": "⚠️ Caution Level", "value": caution, "inline": True},
        {"name": "🧭 24h High / Low", "value": f"{fmt(high24,4)} / {fmt(low24,4)}", "inline": True},
    ]

    send_discord_embed(f"🚨 Combined XRP Intelligence Report — {datetime.utcnow().strftime('%b %d, %H:%M UTC')}", fields, news)

    # Post teaser to X
    post_to_x(f"🚨 XRP Intel Drop — Price: ${fmt(price,3)} | Vol: {vol_text} | Flips/Triggers: {triggers} #XRP #Crypto")

if __name__ == "__main__":
    main()
