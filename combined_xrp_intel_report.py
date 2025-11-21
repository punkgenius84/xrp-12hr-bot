#!/usr/bin/env python3
"""
combined_xrp_intel_report.py

Combined Crypto Intel + XRP 12-Hour Report

* Full Discord report with indicators, alerts, patterns, news
* Volume spike and MACD crossover alerts included
* Multi-timeframe confirmations: 15m approx, 1h, 24h
* Updates xrp_history.csv automatically
* Dynamic caution/strong/danger levels fully integrated
  """

import os
import requests
import feedparser
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta

# ----------------------------

# CONFIG

# ----------------------------

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CSV_FILE = "xrp_history.csv"

VOLUME_SPIKE_LEVELS = {"caution": 1.15, "strong": 1.30, "extreme": 1.50}
RSI_WINDOW = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SWING_WINDOW = 24
COMPRESSION_WINDOW = 24
PULSE_STACK_WINDOW = 12
SENTINEL_WINDOW = 24

# ----------------------------

# UTILITY FUNCTIONS

# ----------------------------

def send_discord(content: str, webhook=DISCORD_WEBHOOK):
if not webhook:
print("Webhook not set, skipping Discord send")
return
try:
r = requests.post(webhook, json={"content": content}, timeout=10)
if r.status_code not in (200, 204):
print(f"Discord responded {r.status_code}: {r.text[:300]}")
else:
print("Discord message sent")
except Exception as e:
print("Failed to send to Discord:", e)

def fmt(x):
if isinstance(x, (int, np.integer)):
return f"{x}"
try:
return f"{float(x):,.4f}"
except:
return str(x)

# ----------------------------

# FETCH DATA

# ----------------------------

def fetch_30d_hourly():
url = "[https://api.coingecko.com/api/v3/coins/ripple/market_chart](https://api.coingecko.com/api/v3/coins/ripple/market_chart)"
params = {"vs_currency": "usd", "days": "30"}
try:
data = requests.get(url, params=params, timeout=15).json()
except Exception as e:
print("Fetch error:", e)
return None

```
prices = data.get("prices", [])
vols = data.get("total_volumes", [])
if not prices or not vols:
    print("Invalid market_chart payload")
    return None

df_p = pd.DataFrame(prices, columns=["timestamp", "close"])
df_v = pd.DataFrame(vols, columns=["timestamp", "volume"])
df_p["timestamp"] = pd.to_datetime(df_p["timestamp"], unit="ms", utc=True)
df_v["timestamp"] = pd.to_datetime(df_v["timestamp"], unit="ms", utc=True)
df = pd.merge(df_p, df_v, on="timestamp", how="left").sort_values("timestamp").reset_index(drop=True)
df["high"] = df["close"]
df["low"] = df["close"]
return df
```

def fetch_live_price():
url = "[https://api.coingecko.com/api/v3/simple/price](https://api.coingecko.com/api/v3/simple/price)"
params = {"ids": "ripple", "vs_currencies": "usd", "include_last_updated_at": "true"}
try:
data = requests.get(url, params=params, timeout=10).json()
price = float(data["ripple"]["usd"])
ts = int(data["ripple"].get("last_updated_at", 0))
ts_dt = datetime.fromtimestamp(ts) if ts else datetime.utcnow()
return price, ts_dt
except Exception as e:
print("Live price fetch failed:", e)
return None, None

def fetch_crypto_news(limit=5):
news_msg = ""
try:
feed = feedparser.parse("[https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml](https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml)")
entries = feed.entries[:limit]
for entry in entries:
news_msg += f"• {entry.get('title','No title')}\n{entry.get('link','')}\n\n"
return news_msg.strip()
except Exception as e:
print("News fetch error:", e)
return "No headlines available"

# ----------------------------

# HISTORY MANAGEMENT

# ----------------------------

def update_history_csv(row: dict):
try:
hist = pd.read_csv(CSV_FILE)
hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True)
except FileNotFoundError:
hist = pd.DataFrame(columns=["timestamp","close","high","low","volume"])
if pd.to_datetime(row["timestamp"]) not in hist["timestamp"].values:
hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
cutoff = datetime.utcnow() - timedelta(days=30)
hist = hist[hist["timestamp"] >= cutoff]
hist.to_csv(CSV_FILE, index=False)
return hist

# ----------------------------

# INDICATORS

# ----------------------------

def compute_indicators(df):
result = {}
close = df["close"].astype(float)
try:
rsi = RSIIndicator(close, window=RSI_WINDOW).rsi()
result["rsi_series"] = rsi
result["rsi"] = float(rsi.iloc[-1])
except:
result["rsi_series"] = pd.Series([np.nan]*len(df))
result["rsi"] = np.nan
try:
macd = MACD(close, window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
result["macd_line"] = float(macd.macd().iloc[-1])
result["macd_signal"] = float(macd.macd_signal().iloc[-1])
result["macd_hist_series"] = macd.macd_diff()
result["macd_hist"] = float(macd.macd_diff().iloc[-1])
except:
result.update({"macd_line": np.nan, "macd_signal": np.nan, "macd_hist": np.nan, "macd_hist_series": pd.Series([np.nan]*len(df))})
result["ma50"] = float(close.rolling(50,min_periods=1).mean().iloc[-1])
result["ma200"] = float(close.rolling(200,min_periods=1).mean().iloc[-1])
return result

# ----------------------------

# ALERTS

# ----------------------------

def detect_volume_spike(df):
vol_series = df["volume"].astype(float)
avg = vol_series.tail(24).mean() if len(vol_series)>=24 else vol_series.mean()
last = float(vol_series.iloc[-1])
ratio = (last/avg) if avg>0 else 0
level = None
if ratio >= VOLUME_SPIKE_LEVELS["extreme"]:
level="EXTREME"
elif ratio >= VOLUME_SPIKE_LEVELS["strong"]:
level="STRONG"
elif ratio >= VOLUME_SPIKE_LEVELS["caution"]:
level="CAUTION"
return {"ratio":ratio,"avg":avg,"last":last,"level":level}

def macd_histogram_trend(macd_hist_series):
try:
last = macd_hist_series.iloc[-3:]
if len(last.dropna())<3:
return None
if last.is_monotonic_increasing:
return "increasing"
if last.is_monotonic_decreasing:
return "decreasing"
return "mixed"
except:
return None

def support_resistance(df):
price = df["close"].astype(float)
return {"recent_high":float(price.tail(SWING_WINDOW).max()), "recent_low":float(price.tail(SWING_WINDOW).min()), "last":float(price.iloc[-1])}

def detect_patterns(df, indicators):
patterns=[]
if len(df)>=COMPRESSION_WINDOW+1:
window=df.tail(COMPRESSION_WINDOW)
r=window["high"]-window["low"]
if r.iloc[-1]<r.iloc[0]*0.6 and r.std()<r.mean()*0.6:
patterns.append("Compression Arc")
if len(df)>=PULSE_STACK_WINDOW:
window=df.tail(PULSE_STACK_WINDOW)
closes, vols=window["close"].astype(float), window["volume"].astype(float)
if (closes.pct_change()>0).sum()>=3 and np.polyfit(range(len(vols)),vols,1)[0]>0:
patterns.append("Pulse Stack")
if len(df)>=12:
recent_high=df["close"].tail(24).max()
recent_low=df["close"].tail(24).min()
spike_exists=(df["close"].tail(24)>recent_high*1.02).any()
if spike_exists and df["close"].iloc[-1]<recent_low*0.995:
patterns.append("Trap Funnel")
if len(df)>=SENTINEL_WINDOW:
lows=df.tail(SENTINEL_WINDOW)["low"].astype(float)
rsi_series=indicators.get("rsi_series")
macd_line=indicators.get("macd_line",0)
if lows.std()<lows.mean()*0.01 and rsi_series is not None and rsi_series.iloc[-1]>rsi_series.iloc[-3] and macd_line>0:
patterns.append("Sentinel Base")
return patterns if patterns else ["None detected"]

# ----------------------------

# DYNAMIC LEVELS

# ----------------------------

def compute_dynamic_levels(df):
recent_high=float(df["close"].tail(24).max())
recent_low=float(df["close"].tail(24).min())
return {
"recent_high":recent_high,
"recent_low":recent_low,
"breakout_weak":recent_high*1.02,
"breakout_strong":recent_high*1.06,
"breakdown_weak":recent_low*0.98,
"breakdown_strong":recent_low*0.95,
"danger":recent_low*0.92
}

# ----------------------------

# COMPOSE DISCORD MESSAGE

# ----------------------------

def compose_discord_message(df, live_price):
indicators=compute_indicators(df)
price=float(live_price)
vol=detect_volume_spike(df)
vol_text="No surge"
if vol["level"]=="EXTREME":
vol_text=f"EXTREME volume spike ({vol['ratio']:.2f}x avg)"
elif vol["level"]=="STRONG":
vol_text=f"Strong volume spike ({vol['ratio']:.2f}x avg)"
elif vol["level"]=="CAUTION":
vol_text=f"Caution volume spike ({vol['ratio']:.2f}x avg)"

```
patterns=detect_patterns(df, indicators)
patterns_text=", ".join(patterns)
macd_hist_text=macd_histogram_trend(indicators.get("macd_hist_series")) or "None"

sr=support_resistance(df)
levels=compute_dynamic_levels(df)

# Flips/Triggers
flips=[]
if price>levels["breakout_weak"]:
    flips.append(f"Bullish breakout (weak ≥ ${fmt(levels['breakout_weak'])})")
if price>levels["breakout_strong"]:
    flips.append(f"Bullish breakout (strong ≥ ${fmt(levels['breakout_strong'])})")
if price<levels["breakdown_weak"]:
    flips.append(f"Bearish breakdown (weak ≤ ${fmt(levels['breakdown_weak'])})")
if price<levels["breakdown_strong"]:
    flips.append(f"Bearish breakdown (strong ≤ ${fmt(levels['breakdown_strong'])})")
if price<levels["danger"]:
    flips.append(f"DANGER: below danger level ≤ ${fmt(levels['danger'])}")
flips_text=", ".join(flips) if flips else "None"

# Dynamic Levels Text
dynamic_text=(
    f"🟢 Breakout Weak: ${fmt(levels['breakout_weak'])}\n"
    f"🟢 Breakout Strong: ${fmt(levels['breakout_strong'])}\n"
    f"🔴 Breakdown Weak: ${fmt(levels['breakdown_weak'])}\n"
    f"🔴 Breakdown Strong: ${fmt(levels['breakdown_strong'])}\n"
    f"⚠ Danger Zone: ${fmt(levels['danger'])}"
)

bullish,bearish=50,50
if price>indicators["ma50"]:
    bullish+=15; bearish-=15
else:
    bullish-=15; bearish+=15
if indicators["macd_line"]>indicators["macd_signal"]:
    bullish+=20; bearish-=20
else:
    bullish-=20; bearish+=20
if indicators["rsi"]<30:
    bullish+=10; bearish-=10
elif indicators["rsi"]>70:
    bullish-=10; bearish+=10
if indicators["ma50"]>indicators["ma200"]:
    bullish+=5; bearish-=5
bullish=max(0,min(100,bullish))
bearish=max(0,min(100,bearish))

news=fetch_crypto_news()
message=f"""
```

**🚨 Combined XRP Intelligence Report**

💰 Current Price: ${fmt(price)}
📈 RSI (14): {fmt(indicators['rsi'])}
📉 MACD: {fmt(indicators['macd_line'])} (signal {fmt(indicators['macd_signal'])})
📊 MA50: {fmt(indicators['ma50'])}  MA200: {fmt(indicators['ma200'])}

📈 Bullish Probability: {fmt(bullish)}%
📉 Bearish Probability: {fmt(bearish)}%

🔍 Trend: {"Bullish 🟢" if bullish>bearish else "Bearish 🔴"}

📊 Volume Signals: {vol_text}
⚠ Patterns Detected: {patterns_text}
📊 MACD Histogram Trend: {macd_hist_text}
🧭 Support/Resistance: 24h High: ${fmt(sr['recent_high'])}, 24h Low: ${fmt(sr['recent_low'])}
🔔 Flips/Triggers: {flips_text}

📊 Dynamic Levels:
{dynamic_text}

📰 Top Crypto News:
{news}

---

*Data window: last {len(df)} hourly candles (30-day history).*
"""
return message

# ----------------------------

# MAIN

# ----------------------------

def main():
df=fetch_30d_hourly()
if df is None or df.empty:
print("No data, aborting.")
return
live_price,live_ts=fetch_live_price()
if live_price is None:
print("Live price unavailable; using last close.")
live_price=float(df["close"].iloc[-1])

```
df=df.copy()
df.loc[df.index[-1],"close"]=live_price
df.loc[df.index[-1],"high"]=max(df.loc[df.index[-1],"high"],live_price)
df.loc[df.index[-1],"low"]=min(df.loc[df.index[-1],"low"],live_price)

last_row={
    "timestamp":df.loc[df.index[-1],"timestamp"],
    "close":float(df.loc[df.index[-1],"close"]),
    "high":float(df.loc[df.index[-1],"high"]),
    "low":float(df.loc[df.index[-1],"low"]),
    "volume":float(df.loc[df.index[-1],"volume"])
}
try:
    update_history_csv(last_row)
except Exception as e:
    print("CSV update failed:", e)

message=compose_discord_message(df, live_price)
send_discord(message)
print("Report sent.")
```

if **name**=="**main**":
main()
