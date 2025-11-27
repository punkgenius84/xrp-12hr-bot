#!/usr/bin/env python3
"""
XRP AI BOT — 4× Daily Report (8AM, 12PM, 4PM, 9PM EST)
Daily + 4H Market Structure + Pro Alerts + News + X Post
"""

import requests
import pandas as pd
import os
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed
import tweepy

CSV_FILE = "xrp_history.csv"
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

client = tweepy.Client(
    bearer_token=os.environ["X_BEARER_TOKEN"],
    consumer_key=os.environ["X_API_KEY"],
    consumer_secret=os.environ["X_API_SECRET"],
    access_token=os.environ["X_ACCESS_TOKEN"],
    access_token_secret=os.environ["X_ACCESS_SECRET"]
)

# =============================
# Data: Hourly → 4H + Daily
# =============================
def fetch_data():
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    resp = requests.get(url, params={"fsym": "XRP", "tsym": "USDT", "limit": 2000}, timeout=20)
    data = resp.json()["Data"]["Data"]
    df = pd.DataFrame([d for d in data if d["time"] > 0])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"volumeto": "volume"}, inplace=True)

    hourly = df[["time", "open", "high", "low", "close", "volume"]].set_index("time")
    df_4h = hourly.resample('4H').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
    df_daily = hourly.resample('1D').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()

    return hourly, df_4h, df_daily

# =============================
# Market Structure (Swing Highs/Lows)
# =============================
def market_structure(df, tf):
    try:
        window = 10 if tf == "Daily" else 15
        high_roll = df['high'].rolling(2*window+1, center=True).max()
        low_roll = df['low'].rolling(2*window+1, center=True).min()

        swings_high = df['high'][df['high'] == high_roll].dropna().tail(4)
        swings_low = df['low'][df['low'] == low_roll].dropna().tail(4)

        if len(swings_high) < 3 or len(swings_low) < 3:
            return "Ranging"

        # HH + HL = Bullish
        if (swings_high.iloc[-1] > swings_high.iloc[-2] > swings_high.iloc[-3] and
            swings_low.iloc[-1] > swings_low.iloc[-2] > swings_low.iloc[-3]):
            return "Bullish (HH+HL)"
        # LH + LL = Bearish
        elif (swings_high.iloc[-1] < swings_high.iloc[-2] < swings_high.iloc[-3] and
              swings_low.iloc[-1] < swings_low.iloc[-2] < swings_low.iloc[-3]):
            return "Bearish (LH+LL)"
        else:
            return "Ranging/Choppy"
    except:
        return "Unavailable"

# =============================
# Alerts (4H)
# =============================
def get_alerts(df_4h):
    df = df_4h.copy()
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['signal'] = df['macd'].ewm(span=9).mean()
    df['rsi'] = 100 - (100 / (1 + df['close'].pct_change().clip(lower=0).rolling(14).mean() /
                                 abs(df['close'].pct_change()).rolling(14).mean()))

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    alerts = []

    if prev['macd'] < prev['signal'] and latest['macd'] > latest['signal']:
        alerts.append("MACD BULLISH CROSS")
    if prev['macd'] > prev['signal'] and latest['macd'] < latest['signal']:
        alerts.append("MACD BEARISH CROSS")
    if latest['rsi'] > 70: alerts.append("RSI OVERBOUGHT")
    if latest['rsi'] < 30: alerts.append("RSI OVERSOLD")
    if latest['volume'] > df['volume'].tail(20).mean() * 2.5:
        alerts.append("VOLUME SPIKE")

    return " • ".join(alerts) if alerts else "No Active Alerts"

# =============================
# Send Report + News + X
# =============================
def send_report(daily_struct, h4_struct, alerts):
    price = df_4h['close'].iloc[-1]
    change_24h = (price / df_4h['close'].iloc[-6] - 1) * 100 if len(df_4h) >= 6 else 0

    # Discord Embed
    embed = DiscordEmbed(title="XRP Intelligence Report", color=0x9b59b6)
    embed.add_embed_field(name="Market Structure", 
                         value=f"**Daily:** {daily_struct}\n**4-Hour:** {h4_struct}", inline=False)
    embed.add_embed_field(name="Price", value=f"${price:.4f}", inline=True)
    embed.add_embed_field(name="24h Change", value=f"{change_24h:+.2f}%", inline=True)
    embed.add_embed_field(name="Alerts", value=alerts, inline=False)
    embed.set_thumbnail(url="https://cryptologos.cc/logos/xrp-xrp-logo.png")
    embed.set_footer(text=f"Updated {datetime.now().strftime('%Y-%m-%d %I:%M %p EST')} | 4× Daily Report")
    embed.timestamp = datetime.utcnow().isoformat()

    webhook = DiscordWebhook(url=DISCORD_WEBHOOK)
    webhook.add_embed(embed)
    webhook.execute()
    print("Main report sent!")

    # News Cards
    try:
        news = requests.get("https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=XRP,BTC,SEC", timeout=10).json()["Data"][:5]
        news_hook = DiscordWebhook(url=DISCORD_WEBHOOK)
        for a in news:
            e = DiscordEmbed(title=a['title'][:250], description=a['body'][:190]+"...", color=0x9b59b6, url=a['url'])
            if a.get('imageurl'): e.set_image(url=a['imageurl'])
            e.set_footer(text="Click title for full article")
            news_hook.add_embed(e)
        news_hook.execute()
        print("News cards sent!")
    except Exception as e:
        print("News failed:", e)

    # X Post
    try:
        tweet = f"""XRP Update
${price:.4f} ({change_24h:+.2f}%)
Daily: {daily_struct}
4H: {h4_struct}
{alerts}
#XRP #Crypto"""
        client.create_tweet(text=tweet)
        print(f"X posted ({len(tweet)} chars)")
    except Exception as e:
        print("X post failed:", e)

# =============================
# Main
# =============================
def main():
    global df_4h, df_daily
    hourly, df_4h, df_daily = fetch_data()

    # Save CSV
    hourly_reset = hourly.reset_index().rename(columns={"time": "open_time"})
    try:
        old = pd.read_csv(CSV_FILE)
        old["open_time"] = pd.to_datetime(old["open_time"])
        combined = pd.concat([old, hourly_reset]).drop_duplicates("open_time")
    except:
        combined = hourly_reset
    combined.to_csv(CSV_FILE, index=False)
    print(f"CSV saved — {len(combined)} rows")

    daily_struct = market_structure(df_daily, "Daily")
    h4_struct = market_structure(df_4h, "4H")
    alerts = get_alerts(df_4h)

    print(f"Daily: {daily_struct} | 4H: {h4_struct} | Alerts: {alerts}")
    send_report(daily_struct, h4_struct, alerts)

if __name__ == "__main__":
    main()
