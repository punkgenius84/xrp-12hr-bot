#!/usr/bin/env python3
"""
XRP Combined Intel Report – Discord (Embed) + X Auto-Post
Alert-gated execution · Smart Money Concepts fixed
Production-safe for GitHub Actions
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
from smartmoneyconcepts import smc

# ========================= CONFIG =========================
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

CSV_FILE = "xrp_history.csv"

# ========================= FORMAT =========================
def fmt(x, d=4):
    try:
        return f"{float(x):,.{d}f}".rstrip("0").rstrip(".")
    except:
        return str(x)

# ========================= DISCORD =========================
def send_discord(report_text):
    if not DISCORD_WEBHOOK:
        print("No Discord webhook set")
        return

    chunks = [report_text[i:i+3900] for i in range(0, len(report_text), 3900)]
    embeds = []

    for i, chunk in enumerate(chunks):
        embeds.append({
            "title": "🚨 XRP Combined Intelligence Report" + ("" if i == 0 else f" (cont. {i+1})"),
            "description": chunk,
            "color": 0x1ABC9C,
            "footer": {"text": "Auto-updated via GitHub Actions"}
        })

    try:
        r = requests.post(DISCORD_WEBHOOK, json={"embeds": embeds}, timeout=15)
        r.raise_for_status()
        print(f"✅ Discord delivered ({len(embeds)} embed(s))")
    except Exception as e:
        print("❌ Discord send failed:", e)

# ========================= X =========================
def post_to_x(text):
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        print("X creds missing — skipping")
        return

    auth = OAuth1(
        X_API_KEY,
        client_secret=X_API_SECRET,
        resource_owner_key=X_ACCESS_TOKEN,
        resource_owner_secret=X_ACCESS_SECRET,
    )

    r = requests.post(
        "https://api.twitter.com/2/tweets",
        json={"text": text},
        auth=auth,
        timeout=10,
    )

    if r.status_code == 201:
        print("✅ Posted to X")
    else:
        print("❌ X post failed:", r.text)

# ========================= DATA =========================
def fetch_xrp_hourly_data():
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    params = {"fsym": "XRP", "tsym": "USDT", "limit": 2000}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    data = r.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df["open_time"] = pd.to_datetime(df["time"], unit="s")

    df.rename(columns={"volumeto": "volume"}, inplace=True)
    return df[["open_time", "open", "high", "low", "close", "volume"]]

# ========================= INDICATORS =========================
def compute_indicators(df):
    c = df["close"]

    rsi_series = RSIIndicator(c, 14).rsi()
    macd = MACD(c)

    bb = BollingerBands(c)
    stoch = StochasticOscillator(df["high"], df["low"], c)

    obv_series = OnBalanceVolumeIndicator(c, df["volume"]).on_balance_volume()
    adx = ADXIndicator(df["high"], df["low"], c)

    return {
        "price": c.iloc[-1],
        "rsi": rsi_series.iloc[-1],
        "macd": macd.macd().iloc[-1],
        "signal": macd.macd_signal().iloc[-1],
        "hist_trend": "Increasing 🟢" if macd.macd_diff().iloc[-1] >
                        macd.macd_diff().iloc[-2] else "Decreasing 🔴",
        "ema50": EMAIndicator(c, 50).ema_indicator().iloc[-1],
        "ema200": EMAIndicator(c, 200).ema_indicator().iloc[-1],
        "bb_mid": bb.bollinger_mavg().iloc[-1],
        "bb_width": (bb.bollinger_hband().iloc[-1] -
                     bb.bollinger_lband().iloc[-1]) / bb.bollinger_mavg().iloc[-1],
        "stoch_k": stoch.stoch().iloc[-1],
        "stoch_d": stoch.stoch_signal().iloc[-1],
        "obv_trend": "Rising 🟢" if obv_series.iloc[-1] >
                      obv_series.iloc[-2] else "Falling 🔴",
        "adx": adx.adx().iloc[-1],
    }

# ========================= MARKET STRUCTURE (FIXED) =========================
def compute_market_structure(df):
    try:
        df = df.copy().reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)

        sdf = df.tail(300).reset_index(drop=True)

        swings = smc.swing_highs_lows(sdf, swing_length=50)
        bos = smc.bos_choch(sdf, swings, close_break=True)

        last = bos.iloc[-1]
        if last.get("BOS") == 1:
            return "Bullish BOS 🟢"
        if last.get("BOS") == -1:
            return "Bearish BOS 🔴"
        if last.get("CHOCH") == 1:
            return "Bullish CHOCH 🟢"
        if last.get("CHOCH") == -1:
            return "Bearish CHOCH 🔴"

        return "Ranging ⚪"
    except Exception as e:
        print("⚠️ Market structure skipped:", e)
        return "Unavailable"

# ========================= LEVELS =========================
def dynamic_levels(df):
    high = df["high"].tail(168).max()
    low = df["low"].tail(168).min()
    r = high - low or 0.0001

    return {
        "breakout_strong": low + r * 0.618,
        "breakdown_strong": low + r * 0.118,
        "danger": low,
    }

# ========================= ALERT GATE =========================
def should_alert(price, levels, vol_ratio, price_change_1h):
    if price > levels["breakout_strong"]:
        return True
    if price < levels["breakdown_strong"]:
        return True
    if price < levels["danger"]:
        return True
    if abs(price_change_1h) >= 5:
        return True
    if vol_ratio >= 1.5:
        return True
    return False

# ========================= REPORT =========================
def build_discord_message(df):
    i = compute_indicators(df)
    levels = dynamic_levels(df)
    price_change_1h = ((i["price"] / df["close"].iloc[-2]) - 1) * 100
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]

    struct = compute_market_structure(df)

    return f"""
💰 **Price:** `${fmt(i['price'], 3)}`
⏱ **1h Change:** `{price_change_1h:+.2f}%`
📈 **RSI:** `{fmt(i['rsi'],2)}`
📉 **MACD / Signal:** `{fmt(i['macd'],4)} / {fmt(i['signal'],4)}`
📊 **EMA50 / EMA200:** `{fmt(i['ema50'],4)}` / `{fmt(i['ema200'],4)}`
📊 **BB Width:** `{fmt(i['bb_width']*100,2)}%`
📈 **OBV Trend:** `{i['obv_trend']}`
🔍 **ADX:** `{fmt(i['adx'],2)}`

🛡 **Market Structure:** {struct}

🚀 **Strong Breakout:** `{fmt(levels['breakout_strong'],4)}`
💥 **Strong Breakdown:** `{fmt(levels['breakdown_strong'],4)}`
🚨 **Danger:** `{fmt(levels['danger'],4)}`

📊 **Volume Ratio:** `{fmt(vol_ratio,2)}x`

🕒 `{datetime.utcnow().strftime('%b %d, %H:%M UTC')}`
""".strip()

# ========================= X TEASER =========================
def build_x_teaser(df):
    price = df["close"].iloc[-1]
    change_1h = ((price / df["close"].iloc[-2]) - 1) * 100
    return f"🚨 XRP Alert | ${fmt(price,3)} | 1h {change_1h:+.1f}% #XRP #Crypto"

# ========================= MAIN =========================
def main():
    fresh = fetch_xrp_hourly_data()
    old = pd.read_csv(CSV_FILE) if os.path.exists(CSV_FILE) else pd.DataFrame()

    df = pd.concat([old, fresh]).drop_duplicates("open_time").sort_values("open_time")
    df.to_csv(CSV_FILE, index=False)
    print(f"Data rows: {len(df)}")

    if len(df) < 300:
        print("Not enough data")
        return

    levels = dynamic_levels(df)
    price = df["close"].iloc[-1]
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(24).mean().iloc[-1]
    price_change_1h = ((price / df["close"].iloc[-2]) - 1) * 100

    if should_alert(price, levels, vol_ratio, price_change_1h):
        print("🚨 Alert triggered")
        send_discord(build_discord_message(df))
        post_to_x(build_x_teaser(df))
    else:
        print("ℹ️ No alert — skipping post")

if __name__ == "__main__":
    main()
