#!/usr/bin/env python3
"""
XRP AI BOT — FINAL PERFECTION (2025) + 7-COIN EMPIRE WITH PER-COIN NEWS
+ BULLISH PROBABILITY INDICATOR IS BACK BABY
"""

import requests
import pandas as pd
import os
from datetime import datetime
import pytz
from discord_webhook import DiscordWebhook, DiscordEmbed
import tweepy

CSV_FILE = "xrp_history.csv"

eastern = pytz.timezone('America/New_York')

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

def fetch_data(coin):
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    resp = requests.get(url, params={"fsym": coin, "tsym": "USDT", "limit": 2000}, timeout=20)
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame([d for d in data if d["time"] > 0])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"volumeto": "volume"}, inplace=True)

    hourly = df[["time", "open", "high", "low", "close", "volume"]].set_index("time")
    df_4h = hourly.resample('4h').agg({
        'open':'first','high':'max','low':'min','close':'last','volume':'sum'
    }).dropna()
    df_daily = hourly.resample('1D').agg({
        'open':'first','high':'max','low':'min','close':'last','volume':'sum'
    }).dropna()

    return hourly, df_4h, df_daily

# ================= MARKET STRUCTURE (FIXED SPEED) =================
def market_structure(df, timeframe):
    try:
        window = 10 if timeframe == "Daily" else 8  # <-- FASTER 4H STRUCTURE
        high_roll = df['high'].rolling(window*2+1, center=True).max()
        low_roll = df['low'].rolling(window*2+1, center=True).min()

        highs = df['high'][df['high'] == high_roll].dropna().tail(4)
        lows = df['low'][df['low'] == low_roll].dropna().tail(4)

        if len(highs) < 3 or len(lows) < 3:
            return "Ranging/Choppy"

        if highs.iloc[-1] > highs.iloc[-2] > highs.iloc[-3] and lows.iloc[-1] > lows.iloc[-2] > lows.iloc[-3]:
            return "Bullish (HH+HL)"
        if highs.iloc[-1] < highs.iloc[-2] < highs.iloc[-3] and lows.iloc[-1] < lows.iloc[-2] < lows.iloc[-3]:
            return "Bearish (LH+LL)"

        return "Ranging/Choppy"
    except:
        return "Unavailable"

# ================= BOLLINGER =================
def bollinger_analysis(df_4h):
    df = df_4h.copy()
    df['mid'] = df['close'].rolling(20).mean()
    df['std'] = df['close'].rolling(20).std()
    df['upper'] = df['mid'] + df['std'] * 2
    df['lower'] = df['mid'] - df['std'] * 2
    df['bandwidth'] = (df['upper'] - df['lower']) / df['mid']
    df['distance_from_lower'] = (df['close'] - df['lower']) / (df['upper'] - df['lower'])

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    squeeze_threshold = df['bandwidth'].rolling(100).quantile(0.1).iloc[-1]
    squeeze = "SQUEEZE ACTIVE" if latest['bandwidth'] < squeeze_threshold else "No Squeeze"

    breakout = ""
    if prev['close'] <= prev['upper'] and latest['close'] > latest['upper']:
        breakout = "BULLISH BREAKOUT"
    elif prev['close'] >= prev['lower'] and latest['close'] < latest['lower']:
        breakout = "BEARISH BREAKOUT"

    return {
        "upper": latest['upper'],
        "lower": latest['lower'],
        "mid": latest['mid'],
        "dist_pct": latest['distance_from_lower'] * 100,
        "squeeze": squeeze,
        "breakout": breakout,
    }

# ================= RSI (FIXED: WILDER + PSYCHOLOGY INVERSION) =================
def calculate_rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return int(100 - (100 / (1 + rs.iloc[-1])))

# ================= PROBABILITY =================
def calculate_bullish_probability(bb, rsi, daily_struct, h4_struct):
    score = 50
    score += (bb['dist_pct'] - 50) * 0.6

    # Psychology inversion
    if rsi < 30:
        score += 15
    elif rsi > 70:
        score -= 15
    else:
        score += (50 - rsi) * 0.3

    if "Bullish" in daily_struct: score += 20
    if "Bearish" in daily_struct: score -= 20
    if "Bullish" in h4_struct: score += 15
    if "Bearish" in h4_struct: score -= 15
    if bb['squeeze'] == "SQUEEZE ACTIVE": score += 12
    if "BULLISH" in bb['breakout']: score += 18
    if "BEARISH" in bb['breakout']: score -= 18

    return max(5, min(95, round(score)))

# ================= MAIN PER-COIN LOOP (UNCHANGED) =================
def send_report(coin):
    webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{coin}")
    if not webhook_url:
        return

    hourly, df_4h, df_daily = fetch_data(coin)

    if coin == "XRP":
        hourly_reset = hourly.reset_index().rename(columns={"time": "open_time"})
        try:
            old = pd.read_csv(CSV_FILE)
            old["open_time"] = pd.to_datetime(old["open_time"])
            hourly_reset = pd.concat([old, hourly_reset]).drop_duplicates("open_time")
        except:
            pass
        hourly_reset.to_csv(CSV_FILE, index=False)

    price = df_4h['close'].iloc[-1]
    rsi = calculate_rsi(df_4h['close'])
    daily_struct = market_structure(df_daily, "Daily")
    h4_struct = market_structure(df_4h, "4H")
    bb = bollinger_analysis(df_4h)
    bullish_prob = calculate_bullish_probability(bb, rsi, daily_struct, h4_struct)

    now_est = datetime.now(eastern).strftime("%I:%M %p EST")

    embed = DiscordEmbed(title=f"{coin} Market Report", color=COINS[coin]["color"])
    embed.add_embed_field(name="**Bullish Probability**", value=f"**{bullish_prob}%**", inline=False)
    embed.add_embed_field(name="Market Structure", value=f"Daily: {daily_struct}\n4H: {h4_struct}", inline=False)
    embed.add_embed_field(name="RSI (14)", value=str(rsi), inline=True)
    embed.add_embed_field(name="BB Position", value=f"{bb['dist_pct']:.1f}% from lower", inline=True)
    embed.add_embed_field(name="BB Status", value=f"{bb['squeeze']}\n{bb['breakout']}", inline=False)
    embed.set_thumbnail(url=COINS[coin]["thumb"])
    embed.set_footer(text=f"Updated {now_est}")
    embed.timestamp = datetime.utcnow().isoformat()

    webhook = DiscordWebhook(url=webhook_url)
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    for coin in COINS:
        send_report(coin)
