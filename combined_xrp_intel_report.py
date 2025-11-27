#!/usr/bin/env python3
"""
XRP AI BOT — FINAL PERFECTION (2025) + 7-COIN EMPIRE WITH PER-COIN NEWS
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

# ==================== 7 COINS CONFIG ====================
COINS = {
    "XRP":  {"color": 0x9b59b6, "thumb": "https://cryptologos.cc/logos/xrp-xrp-logo.png"},
    "BTC":  {"color": 0xf7931a, "thumb": "https://cryptologos.cc/logos/bitcoin-btc-logo.png"},
    "ADA":  {"color": 0x0033ad, "thumb": "https://cryptologos.cc/logos/cardano-ada-logo.png"},
    "ZEC":  {"color": 0xf4b728, "thumb": "https://cryptologos.cc/logos/zcash-zec-logo.png"},
    "HBAR": {"color": 0x000000, "thumb": "https://cryptologos.cc/logos/hedera-hashgraph-hbar-logo.png"},
    "ETH":  {"color": 0x627eea, "thumb": "https://cryptologos.cc/logos/ethereum-eth-logo.png"},
    "SOL":  {"color": 0x14f195, "thumb": "https://cryptologos.cc/logos/solana-sol-logo.png"},
}
# =======================================================

def fetch_data(coin):
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    resp = requests.get(url, params={"fsym": coin, "tsym": "USDT", "limit": 2000}, timeout=20)
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame([d for d in data if d["time"] > 0])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"volumeto": "volume"}, inplace=True)

    hourly = df[["time", "open", "high", "low", "close", "volume"]].set_index("time")
    df_4h = hourly.resample('4h').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
    df_daily = hourly.resample('1D').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()

    return hourly, df_4h, df_daily

def market_structure(df, timeframe):
    try:
        window = 10 if timeframe == "Daily" else 15
        high_roll = df['high'].rolling(2*window+1, center=True).max()
        low_roll = df['low'].rolling(2*window+1, center=True).min()
        highs = df['high'][df['high'] == high_roll].dropna().tail(4)
        lows = df['low'][df['low'] == low_roll].dropna().tail(4)
        if len(highs) < 3 or len(lows) < 3:
            return "Ranging/Choppy"
        hh_hl = (highs.iloc[-1] > highs.iloc[-2] > highs.iloc[-3] and lows.iloc[-1] > lows.iloc[-2] > lows.iloc[-3])
        lh_ll = (highs.iloc[-1] < highs.iloc[-2] < highs.iloc[-3] and lows.iloc[-1] < lows.iloc[-2] < lows.iloc[-3])
        if hh_hl: return "Bullish (HH+HL)"
        if lh_ll: return "Bearish (LH+LL)"
        return "Ranging/Choppy"
    except:
        return "Unavailable"

def bollinger_analysis(df_4h):
    df = df_4h.copy()
    df['mid'] = df['close'].rolling(20).mean()
    df['std'] = df['close'].rolling(20).std()
    df['upper'] = df['mid'] + (df['std'] * 2)
    df['lower'] = df['mid'] - (df['std'] * 2)
    df['bandwidth'] = (df['upper'] - df['lower']) / df['mid']
    df['distance_from_lower'] = (df['close'] - df['lower']) / (df['upper'] - df['lower'])

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    dist_pct = latest['distance_from_lower'] * 100
    current_bandwidth = latest['bandwidth']
    squeeze_threshold = df['bandwidth'].rolling(100).quantile(0.1).iloc[-1]
    squeeze = "SQUEEZE ACTIVE" if pd.notna(squeeze_threshold) and current_bandwidth < squeeze_threshold else "No Squeeze"

    breakout_dir = ""
    if prev['close'] <= prev['upper'] and latest['close'] > latest['upper']:
        breakout_dir = "BULLISH BREAKOUT"
    elif prev['close'] >= prev['lower'] and latest['close'] < latest['lower']:
        breakout_dir = "BEARISH BREAKOUT"

    return {
        'upper': latest['upper'], 'lower': latest['lower'], 'mid': latest['mid'],
        'dist_pct': dist_pct, 'squeeze': squeeze, 'breakout': breakout_dir
    }

def send_report(coin):
    webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{coin}")
    if not webhook_url:
        print(f"{coin} → No webhook, skipping")
        return

    try:
        hourly, df_4h, df_daily = fetch_data(coin)

        # Save XRP history only
        if coin == "XRP":
            hourly_reset = hourly.reset_index().rename(columns={"time": "open_time"})
            try:
                old = pd.read_csv(CSV_FILE)
                old["open_time"] = pd.to_datetime(old["open_time"])
                combined = pd.concat([old, hourly_reset]).drop_duplicates("open_time")
            except:
                combined = hourly_reset
            combined.to_csv(CSV_FILE, index=False)

        price = df_4h['close'].iloc[-1]
        change_24h = (price / df_4h['close'].iloc[-6] - 1) * 100 if len(df_4h) >= 6 else 0
        now_est = datetime.now(eastern).strftime("%I:%M %p EST")
        bb = bollinger_analysis(df_4h)

        rsi = int(100 - (100 / (1 + (
            df_4h['close'].pct_change().clip(lower=0).rolling(14).mean() /
            abs(df_4h['close'].pct_change()).rolling(14).mean()
        ).replace([0, float('inf')], 1)).iloc[-1]))

        daily_struct = market_structure(df_daily, "Daily")
        h4_struct = market_structure(df_4h, "4H")

        # MAIN REPORT
        embed = DiscordEmbed(title=f"Combined {coin} Intelligence Report", color=COINS[coin]["color"])
        embed.add_embed_field(name="**Market Structure**", value=f"**Daily:** {daily_struct}\n**4-Hour:** {h4_struct}", inline=False)
        embed.add_embed_field(name="**Current Price**", value=f"${price:.4f}", inline=True)
        embed.add_embed_field(name="**24h Change**", value=f"{change_24h:+.2f}%", inline=True)
        embed.add_embed_field(name="**Bollinger Bands (20,2)**", value=f"Upper: ${bb['upper']:.4f}\nMid: ${bb['mid']:.4f}\nLower: ${bb['lower']:.4f}", inline=True)
        embed.add_embed_field(name="**BB Position**", value=f"{bb['dist_pct']:.1f}% from lower", inline=True)
        embed.add_embed_field(name="**BB Status**", value=f"{bb['squeeze']}\n{bb['breakout']}", inline=True)
        embed.add_embed_field(name="**RSI (14)**", value=f"{rsi}", inline=True)
        embed.set_thumbnail(url=COINS[coin]["thumb"])
        embed.set_footer(text=f"Updated {now_est} | 4× Daily Report")
        embed.timestamp = datetime.utcnow().isoformat()

        webhook = DiscordWebhook(url=webhook_url)
        webhook.add_embed(embed)
        webhook.execute()
        print(f"{coin} → Report sent!")

        # PER-COIN NEWS — ONLY RELEVANT ARTICLES
        try:
            news_resp = requests.get(
                f"https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories={coin}",
                timeout=10
            ).json()
            articles = news_resp.get("Data", [])[:4]

            if articles:
                news_hook = DiscordWebhook(url=webhook_url)
                news_hook.set_content(f"**Latest {coin} News**")
                for a in articles:
                    e = DiscordEmbed(
                        title=a['title'][:256],
                        description=(a['body'][:390] + "...") if len(a['body']) > 390 else a['body'],
                        color=COINS[coin]["color"],
                        url=a['url']
                    )
                    if a.get('imageurl'):
                        e.set_image(url=a['imageurl'])
                    e.set_footer(text="Click title → full article")
                    e.timestamp = datetime.utcfromtimestamp(a['published_on']).isoformat()
                    news_hook.add_embed(e)
                news_hook.execute()
                print(f"{coin} → News delivered!")
        except Exception as e:
            print(f"{coin} news failed: {e}")

        # TWEET ONLY XRP
        if coin == "XRP":
            tweet = f"""{coin} • {now_est}
${price:.4f} ({change_24h:+.2f}%)
Daily: {daily_struct} | 4H: {h4_struct}
BB: {bb['squeeze']} {bb['breakout']}
Price {bb['dist_pct']:.0f}% from lower band | RSI {rsi}
#XRP #Crypto"""
            client.create_tweet(text=tweet)
            print("XRP → Tweeted!")

    except Exception as e:
        print(f"{coin} failed: {e}")

# ============================= MAIN =============================
if __name__ == "__main__":
    for coin in ["XRP", "BTC", "ADA", "ZEC", "HBAR", "ETH", "SOL"]:
        send_report(coin)
