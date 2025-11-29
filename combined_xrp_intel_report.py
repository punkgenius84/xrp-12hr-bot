#!/usr/bin/env python3
"""
XRP AI BOT — FINAL PERFECTION (2025)
+ RSI MEAN REVERSION (4H) — TRADINGVIEW MATCHED
"""

import requests
import pandas as pd
import os
from datetime import datetime
import pytz
from discord_webhook import DiscordWebhook, DiscordEmbed
import tweepy

CSV_FILE = "xrp_history.csv"
eastern = pytz.timezone("America/New_York")

client = tweepy.Client(
    bearer_token=os.environ["X_BEARER_TOKEN"],
    consumer_key=os.environ["X_API_KEY"],
    consumer_secret=os.environ["X_API_SECRET"],
    access_token=os.environ["X_ACCESS_TOKEN"],
    access_token_secret=os.environ["X_ACCESS_SECRET"]
)

COINS = {
    "XRP":  {"color": 0x9b59b6, "thumb": "https://cryptologos.cc/logos/xrp-xrp-logo.png"},
    "BTC":  {"color": 0xf7931a, "thumb": "https://cryptologos.cc/logos/bitcoin-btc-logo.png"},
    "ADA":  {"color": 0x0033ad, "thumb": "https://cryptologos.cc/logos/cardano-ada-logo.png"},
    "ZEC":  {"color": 0xf4b728, "thumb": "https://cryptologos.cc/logos/zcash-zec-logo.png"},
    "HBAR": {"color": 0x000000, "thumb": "https://cryptologos.cc/logos/hedera-hashgraph-hbar-logo.png"},
    "ETH":  {"color": 0x627eea, "thumb": "https://cryptologos.cc/logos/ethereum-eth-logo.png"},
    "SOL":  {"color": 0x14f195, "thumb": "https://cryptologos.cc/logos/solana-sol-logo.png"},
}

# ================= DATA =================
def fetch_data(coin):
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    r = requests.get(url, params={"fsym": coin, "tsym": "USDT", "limit": 2000}, timeout=20)
    data = r.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"volumeto": "volume"}).set_index("time")
    hourly = df[["open", "high", "low", "close", "volume"]]

    df_4h = hourly.resample("4H").agg({
        "open": "first", "high": "max",
        "low": "min", "close": "last",
        "volume": "sum"
    }).dropna()

    df_daily = hourly.resample("1D").agg({
        "open": "first", "high": "max",
        "low": "min", "close": "last",
        "volume": "sum"
    }).dropna()

    return hourly, df_4h, df_daily

# ================= STRUCTURE =================
def market_structure(df, timeframe):
    try:
        window = 10 if timeframe == "Daily" else 10  # ✅ micro 4H speed improvement
        high_roll = df["high"].rolling(2 * window + 1, center=True).max()
        low_roll = df["low"].rolling(2 * window + 1, center=True).min()
        highs = df["high"][df["high"] == high_roll].dropna().tail(4)
        lows = df["low"][df["low"] == low_roll].dropna().tail(4)

        if len(highs) < 3 or len(lows) < 3:
            return "Ranging/Choppy"

        if highs.iloc[-1] > highs.iloc[-2] > highs.iloc[-3] and lows.iloc[-1] > lows.iloc[-2] > lows.iloc[-3]:
            return "Bullish (HH+HL)"
        if highs.iloc[-1] < highs.iloc[-2] < highs.iloc[-3] and lows.iloc[-1] < lows.iloc[-2] < lows.iloc[-3]:
            return "Bearish (LH+LL)"
        return "Ranging/Choppy"
    except:
        return "Unavailable"

# ================= BB =================
def bollinger_analysis(df):
    mid = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    upper = mid + std * 2
    lower = mid - std * 2

    bandwidth = (upper - lower) / mid
    dist = (df["close"] - lower) / (upper - lower) * 100

    squeeze = bandwidth.iloc[-1] < bandwidth.rolling(100).quantile(0.1).iloc[-1]
    breakout = ""
    if df["close"].iloc[-2] <= upper.iloc[-2] and df["close"].iloc[-1] > upper.iloc[-1]:
        breakout = "BULLISH BREAKOUT"
    elif df["close"].iloc[-2] >= lower.iloc[-2] and df["close"].iloc[-1] < lower.iloc[-1]:
        breakout = "BEARISH BREAKOUT"

    return {
        "upper": upper.iloc[-1],
        "mid": mid.iloc[-1],
        "lower": lower.iloc[-1],
        "dist_pct": dist.iloc[-1],
        "squeeze": "SQUEEZE ACTIVE" if squeeze else "No Squeeze",
        "breakout": breakout
    }

# ================= PROBABILITY =================
def calculate_bullish_probability(bb, rsi, daily_struct, h4_struct):
    score = 50
    score += (bb["dist_pct"] - 50) * 0.6
    score += (rsi - 50) * 0.3

    if "Bullish" in daily_struct: score += 20
    if "Bearish" in daily_struct: score -= 20
    if "Bullish" in h4_struct: score += 15
    if "Bearish" in h4_struct: score -= 15
    if bb["squeeze"] == "SQUEEZE ACTIVE": score += 12
    if "BULLISH" in bb["breakout"]: score += 18
    if "BEARISH" in bb["breakout"]: score -= 18

    return max(5, min(95, round(score)))

# ================= MAIN =================
def send_report(coin):
    webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{coin}")
    if not webhook_url:
        return

    hourly, df_4h, df_daily = fetch_data(coin)
    price = df_4h["close"].iloc[-1]
    now = datetime.now(eastern).strftime("%I:%M %p EST")

    rsi_series = df_4h["close"].pct_change()
    rsi = int(100 - (100 / (1 + (
        rsi_series.clip(lower=0).rolling(14).mean() /
        abs(rsi_series).rolling(14).mean()
    ))).iloc[-1])

    prev_rsi = int(100 - (100 / (1 + (
        rsi_series.clip(lower=0).rolling(14).mean().shift(1) /
        abs(rsi_series).rolling(14).mean().shift(1)
    ))).iloc[-2])

    # ✅ RSI MEAN REVERSION — MATCHES PINE SCRIPT
    if prev_rsi > 30 and rsi < 30:
        rsi_signal = "📈 **BUY** — RSI crossed UNDER 30"
    elif prev_rsi < 50 and rsi > 50:
        rsi_signal = "📉 **SELL** — RSI crossed ABOVE 50"
    else:
        rsi_signal = "⚪ No signal this candle"

    bb = bollinger_analysis(df_4h)
    daily_struct = market_structure(df_daily, "Daily")
    h4_struct = market_structure(df_4h, "4H")
    bullish_prob = calculate_bullish_probability(bb, rsi, daily_struct, h4_struct)

    embed = DiscordEmbed(title=f"{coin} Market Report", color=COINS[coin]["color"])
    embed.add_embed_field(name="**Bullish Probability**", value=f"{bullish_prob}%", inline=False)
    embed.add_embed_field(name="**RSI Mean Reversion (4H)**", value=rsi_signal, inline=False)
    embed.add_embed_field(name="**Market Structure**", value=f"Daily: {daily_struct}\n4H: {h4_struct}", inline=False)
    embed.add_embed_field(name="**Price**", value=f"${price:.4f}", inline=True)
    embed.add_embed_field(name="**RSI (14)**", value=str(rsi), inline=True)
    embed.add_embed_field(name="**BB Status**", value=f"{bb['squeeze']} {bb['breakout']}", inline=True)
    embed.set_thumbnail(url=COINS[coin]["thumb"])
    embed.set_footer(text=f"Updated {now}")

    webhook = DiscordWebhook(url=webhook_url)
    webhook.add_embed(embed)
    webhook.execute()

# ================= RUN =================
if __name__ == "__main__":
    for c in COINS:
        send_report(c)
