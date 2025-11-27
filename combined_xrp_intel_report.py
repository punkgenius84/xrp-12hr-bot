#!/usr/bin/env python3
"""
ULTIMATE 7-COIN EMPIRE — FINAL 2025 EDITION + PER-COIN NEWS
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
    "XRP":  {"color": 0x9b59b6, "thumb": "https://cryptologos.cc/logos/xrp-xrp-logo.png", "news_cat": "XRP"},
    "BTC":  {"color": 0xf7931a, "thumb": "https://cryptologos.cc/logos/bitcoin-btc-logo.png", "news_cat": "BTC"},
    "ADA":  {"color": 0x0033ad, "thumb": "https://cryptologos.cc/logos/cardano-ada-logo.png", "news_cat": "ADA"},
    "ZEC":  {"color": 0xf4b728, "thumb": "https://cryptologos.cc/logos/zcash-zec-logo.png", "news_cat": "ZEC"},
    "HBAR": {"color": 0x000000, "thumb": "https://cryptologos.cc/logos/hedera-hashgraph-hbar-logo.png", "news_cat": "HBAR"},
    "ETH":  {"color": 0x627eea, "thumb": "https://cryptologos.cc/logos/ethereum-eth-logo.png", "news_cat": "ETH"},
    "SOL":  {"color": 0x14f195, "thumb": "https://cryptologos.cc/logos/solana-sol-logo.png", "news_cat": "SOL"},
}

# ============================= DATA & INDICATORS (unchanged) =============================
def fetch_data(coin): ...  # ← your exact fetch_data from before
def market_structure(df, timeframe): ...  # ← your exact function
def bollinger_analysis(df_4h): ...  # ← your exact function

# ============================= SEND REPORT + PER-COIN NEWS =============================
def send_report(coin):
    webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{coin}")
    if not webhook_url:
        print(f"{coin} → No webhook found, skipping")
        return

    try:
        hourly, df_4h, df_daily = fetch_data(coin)
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

        # MAIN EMBED
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
        print(f"{coin} → GOD-TIER report sent!")

        # PER-COIN NEWS (CryptoCompare — best free source)
        try:
            cat = COINS[coin]["news_cat"]
            news_url = f"https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories={cat}&excludeCategories=ICO"
            news_data = requests.get(news_url, timeout=10).json()["Data"][:4]  # top 4 fresh articles

            if news_data:
                news_hook = DiscordWebhook(url=webhook_url)
                news_hook.set_content(f"**Latest {coin} News**")

                for item in news_data:
                    title = item['title'][:256]
                    body = (item['body'][:400] + "...") if len(item['body']) > 400 else item['body']
                    e = DiscordEmbed(title=title, description=body, color=COINS[coin]["color"], url=item['url'])
                    if item.get('imageurl'):
                        e.set_image(url=item['imageurl'])
                    e.set_footer(text="Click title → full article")
                    e.timestamp = datetime.utcfromtimestamp(item['published_on']).isoformat()
                    news_hook.add_embed(e)

                news_hook.execute()
                print(f"{coin} → Fresh news delivered!")
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
            print("XRP → Tweeted to X!")

    except Exception as e:
        print(f"{coin} failed: {e}")

# ============================= MAIN =============================
if __name__ == "__main__":
    for coin in ["XRP", "BTC", "ADA", "ZEC", "HBAR", "ETH", "SOL"]:
        send_report(coin)
