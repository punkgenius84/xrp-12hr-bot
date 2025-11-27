#!/usr/bin/env python3
"""
ULTIMATE 7-COIN EMPIRE — FINAL VERSION (works with your current secrets)
XRP uses your old DISCORD_WEBHOOK · Others use the new ones you just added
"""

import requests
import pandas as pd
import os
from datetime import datetime
import pytz
from discord_webhook import DiscordWebhook, DiscordEmbed
import tweepy

# =============================
# TIME
# =============================
eastern = pytz.timezone('America/New_York')

# =============================
# WEBHOOKS — BACKWARD COMPATIBLE + FUTURE-PROOF
# =============================
WEBHOOKS = {
    "XRP":  os.environ.get("DISCORD_WEBHOOK_XRP") or os.environ["DISCORD_WEBHOOK"],  # ← works with both!
    "BTC":  os.environ.get("DISCORD_WEBHOOK_BTC"),
    "ADA":  os.environ.get("DISCORD_WEBHOOK_ADA"),
    "ZEC":  os.environ.get("DISCORD_WEBHOOK_ZEC"),
    "HBAR": os.environ.get("DISCORD_WEBHOOK_HBAR"),
    "ETH":  os.environ.get("DISCORD_WEBHOOK_ETH"),
    "SOL":  os.environ.get("DISCORD_WEBHOOK_SOL"),
}

# Coin styling
COINS = {
    "XRP":  {"color": 0x9b59b6, "thumb": "https://cryptologos.cc/logos/xrp-xrp-logo.png",       "symbol": "XRP"},
    "BTC":  {"color": 0xf7931a, "thumb": "https://cryptologos.cc/logos/bitcoin-btc-logo.png",   "symbol": "BTC"},
    "ADA":  {"color": 0x0033ad, "thumb": "https://cryptologos.cc/logos/cardano-ada-logo.png",   "symbol": "ADA"},
    "ZEC":  {"color": 0xf4b728, "thumb": "https://cryptologos.cc/logos/zcash-zec-logo.png",     "symbol": "ZEC"},
    "HBAR": {"color": 0x000000, "thumb": "https://cryptologos.cc/logos/hedera-hashgraph-hbar-logo.png", "symbol": "HBAR"},
    "ETH":  {"color": 0x627eea, "thumb": "https://cryptologos.cc/logos/ethereum-eth-logo.png", "symbol": "ETH"},
    "SOL":  {"color": 0x14f195, "thumb": "https://cryptologos.cc/logos/solana-sol-logo.png",   "symbol": "SOL"},
}

client = tweepy.Client(
    bearer_token=os.environ["X_BEARER_TOKEN"],
    consumer_key=os.environ["X_API_KEY"],
    consumer_secret=os.environ["X_API_SECRET"],
    access_token=os.environ["X_ACCESS_TOKEN"],
    access_token_secret=os.environ["X_ACCESS_SECRET"]
)

# =============================
# Fetch Data
# =============================
def fetch_data(coin):
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    resp = requests.get(url, params={"fsym": coin, "tsym": "USDT", "limit": 2000}, timeout=30)
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame([d for d in data if d["time"] > 0])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    hourly = df[["time", "open", "high", "low", "close"]].set_index("time")
    df_4h = hourly.resample('4h').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    df_daily = hourly.resample('1D').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    return df_4h, df_daily

# =============================
# Indicators (exactly like your original perfect version)
# =============================
def market_structure(df, timeframe):
    try:
        window = 10 if timeframe == "Daily" else 15
        highs = df['high'][df['high'] == df['high'].rolling(2*window+1, center=True).max()].dropna().tail(4)
        lows  = df['low'][df['low']   == df['low'].rolling(2*window+1, center=True).min()].dropna().tail(4)
        if len(highs) < 3 or len(lows) < 3: return "Ranging/Choppy"
        hh_hl = highs.iloc[-1] > highs.iloc[-2] > highs.iloc[-3] and lows.iloc[-1] > lows.iloc[-2] > lows.iloc[-3]
        lh_ll = highs.iloc[-1] < highs.iloc[-2] < highs.iloc[-3] and lows.iloc[-1] < lows.iloc[-2] < lows.iloc[-3]
        return "Bullish (HH+HL)" if hh_hl else "Bearish (LH+LL)" if lh_ll else "Ranging/Choppy"
    except:
        return "Ranging/Choppy"

def bollinger_analysis(df_4h):
    df = df_4h.copy()
    df['mid'] = df['close'].rolling(20).mean()
    df['std'] = df['close'].rolling(20).std()
    df['upper'] = df['mid'] + df['std']*2
    df['lower'] = df['mid'] - df['std']*2
    df['bw'] = (df['upper'] - df['lower']) / df['mid']
    df['pct_b'] = (df['close'] - df['lower']) / (df['upper'] - df['lower']) * 100

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    squeeze = "SQUEEZE ACTIVE" if latest['bw'] < df['bw'].rolling(100).quantile(0.1).iloc[-1] else "No Squeeze"
    breakout = ("BULLISH BREAKOUT" if prev['close'] <= prev['upper'] and latest['close'] > latest['upper']
               else "BEARISH BREAKOUT" if prev['close'] >= prev['lower'] and latest['close'] < latest['lower'] else "")

    return {
        "upper": latest['upper'], "mid": latest['mid'], "lower": latest['lower'],
        "dist_pct": latest['pct_b'], "squeeze": squeeze, "breakout": breakout
    }

# =============================
# SEND REPORT
# =============================
def send_report(coin):
    # Skip if webhook missing (except XRP which has fallback)
    if coin != "XRP" and not WEBHOOKS[coin]:
        print(f"{coin} webhook missing — skipping")
        return

    df_4h, df_daily = fetch_data(coin)
    price = df_4h['close'].iloc[-1]
    change_24h = (price / df_4h['close'].iloc[-6] - 1)*100 if len(df_4h) >= 6 else 0
    now_est = datetime.now(eastern).strftime("%I:%M %p EST")
    bb = bollinger_analysis(df_4h)
    rsi = int(100 - (100 / (1 + (
        df_4h['close'].pct_change().clip(lower=0).rolling(14).mean() /
        abs(df_4h['close'].pct_change()).rolling(14).mean()
    ).replace([0, float('inf')], 1)).iloc[-1]))

    daily_struct = market_structure(df_daily, "Daily")
    h4_struct = market_structure(df_4h, "4H")

    embed = DiscordEmbed(title=f"Combined {coin} Intelligence Report", color=COINS[coin]["color"])
    embed.add_embed_field(name="**Market Structure**", value=f"**Daily:** {daily_struct}\n**4-Hour:** {h4_struct}", inline=False)
    embed.add_embed_field(name="**Price**", value=f"${price:,.4f}", inline=True)
    embed.add_embed_field(name="**24h**", value=f"{change_24h:+.2f}%", inline=True)
    embed.add_embed_field(name="**BB (20,2)**", value=f"U: ${bb['upper']:,.4f}\nM: ${bb['mid']:,.4f}\nL: ${bb['lower']:,.4f}", inline=True)
    embed.add_embed_field(name="**BB Position**", value=f"{bb['dist_pct']:.1f}% from lower", inline=True)
    embed.add_embed_field(name="**BB Status**", value=f"{bb['squeeze']}\n{bb['breakout']}", inline=True)
    embed.add_embed_field(name="**RSI (14)**", value=f"{rsi}", inline=True)
    embed.set_thumbnail(url=COINS[coin]["thumb"])
    embed.set_footer(text=f"Updated {now_est} | 4× Daily Report")
    embed.timestamp = datetime.utcnow().isoformat()

    webhook = DiscordWebhook(url=WEBHOOKS[coin])
    webhook.add_embed(embed)
    webhook.execute()
    print(f"{coin} → Sent")

    if coin == "XRP":
        try:
            tweet = f"""XRP • {now_est}
${price:.4f} ({change_24h:+.2f}%)
Daily: {daily_struct} | 4H: {h4_struct}
BB: {bb['squeeze']} {bb['breakout']}
Price {bb['dist_pct']:.0f}% from lower band | RSI {rsi}
#XRP #Crypto"""
            client.create_tweet(text=tweet)
            print("XRP → Tweeted")
        except Exception as e:
            print("Tweet failed:", e)

# =============================
# MAIN
# =============================
def main():
    for coin in ["XRP", "BTC", "ADA", "ZEC", "HBAR", "ETH", "SOL"]:
        try:
            send_report(coin)
        except Exception as e:
            print(f"{coin} crashed:", e)

if __name__ == "__main__":
    main()
