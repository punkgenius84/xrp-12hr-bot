#!/usr/bin/env python3
"""
XRP Combined Intel Report – Discord Embeds + X Auto-Post
Full Multi-Timeframe + Robust Market Structure + Volume, Indicators, News
November 2025 – Full Rewrite
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

# ========================= HELPERS =========================
def log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S UTC')}] {msg}")

def fmt(x, decimals=4):
    if isinstance(x, (int, float)):
        formatted = f"{float(x):,.{decimals}f}".rstrip("0").rstrip(".")
        return formatted if '.' in formatted or 'e' in formatted.lower() else formatted + '.0' if decimals > 0 else formatted
    return str(x)

# ========================= DISCORD =========================
def send_discord_embed(title, fields=None, news=None):
    if not DISCORD_WEBHOOK:
        log("No Discord webhook → skipping send")
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
            "title": "📰 Latest XRP & Crypto News",
            "description": news,
            "color": 0x3498db
        })
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"embeds": embeds}, timeout=15)
        log(f"Discord status: {r.status_code}")
    except Exception as e:
        log(f"Discord error: {e}")

# ========================= X POST =========================
def post_to_x(text):
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        log("Missing X credentials → skipping post")
        return
    url = "https://api.twitter.com/2/tweets"
    auth = OAuth1(
        X_API_KEY, client_secret=X_API_SECRET,
        resource_owner_key=X_ACCESS_TOKEN,
        resource_owner_secret=X_ACCESS_SECRET
    )
    try:
        r = requests.post(url, json={"text": text}, auth=auth, timeout=10)
        log(f"X post status: {r.status_code}")
    except Exception as e:
        log(f"X post error: {e}")

# ========================= DATA FETCH =========================
def fetch_xrp_data(limit=2000, timeframe='hour'):
    """Fetch XRP historical OHLCV data"""
    log(f"Fetching XRP/{timeframe}")
    url = f"https://min-api.cryptocompare.com/data/v2/histo{timeframe}"
    params = {"fsym":"XRP","tsym":"USDT","limit":limit}
    df = pd.DataFrame()
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()["Data"]["Data"]
        df = pd.DataFrame(data)
        df["open_time"] = pd.to_datetime(df["time"], unit='s', errors='coerce')
        for col in ["open","high","low","close","volumeto"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.rename(columns={"volumeto":"volume"})
        df = df[["open_time","open","high","low","close","volume"]]
        log(f"Fetched {len(df)} candles")
    except Exception as e:
        log(f"Data fetch failed: {e}")
    return df

# ========================= INDICATORS =========================
def compute_indicators(df):
    c = df["close"].astype(float)
    if len(c) < 3:
        return {}
    # RSI
    rsi_series = RSIIndicator(c, window=14).rsi()
    rsi = rsi_series.iloc[-1]
    # MACD
    macd = MACD(c, window_fast=12, window_slow=26, window_sign=9)
    try:
        macd_val = macd.macd().iloc[-1]
        macd_signal = macd.macd_signal().iloc[-1]
        hist_diff = macd.macd_diff()
        hist_trend = "Increasing 🟢" if len(hist_diff)>1 and hist_diff.iloc[-1] > hist_diff.iloc[-2] else "Decreasing 🔴"
    except Exception:
        macd_val, macd_signal, hist_trend = float("nan"), float("nan"), "Neutral"
    # EMAs
    ema50 = EMAIndicator(c, window=min(50,len(c))).ema_indicator().iloc[-1]
    ema200 = EMAIndicator(c, window=min(200,len(c))).ema_indicator().iloc[-1]
    # Bollinger
    bb = BollingerBands(c, window=20, window_dev=2)
    try:
        bb_mavg = bb.bollinger_mavg().iloc[-1]
        bb_h = bb.bollinger_hband().iloc[-1]
        bb_l = bb.bollinger_lband().iloc[-1]
        bb_width = (bb_h - bb_l)/bb_mavg if bb_mavg else 0
        bb_pct = (c.iloc[-1]-bb_l)/(bb_h-bb_l) if (bb_h-bb_l)!=0 else 0
        bb_signal = "Overbought 🔴" if bb_pct>0.8 else "Oversold 🟢" if bb_pct<0.2 else "Neutral"
    except Exception:
        bb_mavg, bb_signal, bb_width = float("nan"), "Neutral", 0
    # Stochastic
    stoch = StochasticOscillator(df["high"].astype(float), df["low"].astype(float), c, window=14, smooth_window=3)
    stoch_k, stoch_d = stoch.stoch().iloc[-1], stoch.stoch_signal().iloc[-1]
    stoch_signal = "Bullish 🟢" if stoch_k>stoch_d and stoch_k<30 else "Bearish 🔴" if stoch_k<stoch_d and stoch_k>70 else "Neutral"
    # OBV
    obv_series = OnBalanceVolumeIndicator(c, df["volume"].astype(float)).on_balance_volume()
    obv, obv_trend = obv_series.iloc[-1], "Rising 🟢" if obv_series.iloc[-1]>obv_series.iloc[-2] else "Falling 🔴"
    # ADX
    adx = ADXIndicator(df["high"].astype(float), df["low"].astype(float), c, window=14)
    adx_val = adx.adx().iloc[-1]
    adx_signal = "Strong 🟢" if adx_val>25 else "Weak 🔴" if adx_val<20 else "Neutral"

    return {
        "rsi": rsi,
        "macd": macd_val,
        "signal": macd_signal,
        "hist_trend": hist_trend,
        "ema50": ema50,
        "ema200": ema200,
        "bb_mavg": bb_mavg,
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

# ========================= VOLUME =========================
def volume_spike(df):
    try:
        rolling = df["volume"].rolling(24).mean().iloc[-1]
    except Exception:
        rolling = df["volume"].iloc[-1] if len(df["volume"])>0 else 1
    if rolling==0 or pd.isna(rolling): rolling=1
    ratio = df["volume"].iloc[-1]/rolling
    ratio = round(float(ratio),2)
    if ratio>=1.5: return f"Extreme Surge {ratio}x 🔥"
    if ratio>=1.3: return f"Strong Surge {ratio}x ⚡"
    if ratio>=1.15: return f"Elevated {ratio}x ⚠️"
    return "Normal"

# ========================= MARKET STRUCTURE =========================
def compute_market_structure(df):
    try:
        df_local = df.copy()
        for c in ["high","low","close"]:
            if c in df_local.columns:
                df_local[c]=pd.to_numeric(df_local[c],errors='coerce')
            else: return "Unavailable"
        df_clean = df_local.dropna(subset=["high","low","close"]).reset_index(drop=True)
        if len(df_clean)<50: return "Insufficient Data"
        swings = smc.swing_highs_lows(df_clean,swing_length=50)
        bos = smc.bos_choch(df_clean,swing_highs_lows=swings,close_break=True)
        if len(bos)==0: return "Unavailable"
        latest = bos.iloc[-1]
        if latest.get('BOS')==1: return "Bullish BOS 🟢"
        if latest.get('BOS')==-1: return "Bearish BOS 🔴"
        if latest.get('CHOCH')==1: return "Bullish CHOCH 🟢"
        if latest.get('CHOCH')==-1: return "Bearish CHOCH 🔴"
        return "Ranging Structure ⚪"
    except Exception as e:
        log(f"Market structure error: {e}")
        return "Unavailable"

# ========================= NEWS =========================
def get_news():
    try:
        feed = feedparser.parse("https://cryptonews.com/news/rss/")
        keywords = ["XRP","Ripple","BTC","Bitcoin"]
        filtered = [e for e in feed.entries if any(kw.lower() in (e.title+getattr(e,'description','')).lower() for kw in keywords)]
        return "\n".join([f"[{e.title}]({e.link})" for e in filtered[:5]]) or "No relevant news"
    except Exception as e:
        log(f"News fetch error: {e}")
        return "News unavailable"

# ========================= DYNAMIC LEVELS =========================
def dynamic_levels(df):
    price = df["close"].iloc[-1]
    recent_high, recent_low = df["high"].tail(24).max(), df["low"].tail(24).min()
    weekly_high, weekly_low = df["high"].tail(168).max(), df["low"].tail(168).min()
    drop = (weekly_high-price)/weekly_high if weekly_high else 0
    high, low = (recent_high, recent_low) if drop>0.1 else (weekly_high, weekly_low)
    r = max(high-low,0.0001)
    return {
        "breakout_weak": low+r*0.382,
        "breakout_strong": low+r*0.618,
        "breakdown_weak": low+r*0.236,
        "breakdown_strong": low+r*0.118,
        "danger": low
    }

def flips(price,levels):
    triggers=[]
    if price>levels["breakout_strong"]: triggers.append("🚀 Strong Bullish Breakout")
    elif price>levels["breakout_weak"]: triggers.append("Bullish Breakout (Weak)")
    if price<levels["breakdown_strong"]: triggers.append("💥 Strong Bearish Breakdown")
    elif price<levels["breakdown_weak"]: triggers.append("Bearish Breakdown (Weak)")
    if price<levels["danger"]: triggers.append("🚨 Danger Zone")
    return triggers[0] if triggers else "Stable"

# ========================= MAIN =========================
def main():
    df = fetch_xrp_data(limit=2000,timeframe='hour')
    if os.path.exists(CSV_FILE):
        try:
            old = pd.read_csv(CSV_FILE)
            for col in ["open","high","low","close","volume"]:
                if col in old.columns: old[col]=pd.to_numeric(old[col],errors='coerce')
            old["open_time"] = pd.to_datetime(old["open_time"], errors='coerce')
            df = pd.concat([old,df]).drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
        except Exception as e:
            log(f"CSV load error: {e}")
    df.to_csv(CSV_FILE,index=False)
    if len(df)<100: 
        log("Not enough data yet")
        return

    price = df["close"].iloc[-1]
    indicators = compute_indicators(df)
    vol_text = volume_spike(df)
    levels = dynamic_levels(df)
    triggers = flips(price,levels)
    market_struct = compute_market_structure(df)
    news = get_news()
    high24, low24 = df["high"].tail(24).max(), df["low"].tail(24).min()

    fields = [
        {"name":"💰 Price","value":f"${fmt(price,3)}","inline":True},
        {"name":"📈 RSI (14)","value":fmt(indicators.get("rsi","N/A"),2),"inline":True},
        {"name":"📉 MACD","value":fmt(indicators.get("macd","N/A"),4),"inline":True},
        {"name":"📊 EMA50/EMA200","value":f"{fmt(indicators.get('ema50','N/A'))}/{fmt(indicators.get('ema200','N/A'))}","inline":True},
        {"name":"📊 Bollinger","value":f"{fmt(indicators.get('bb_mavg','N/A'))} | {indicators.get('bb_signal','N/A')}","inline":True},
        {"name":"🔍 Market Structure","value":market_struct,"inline":True},
        {"name":"📊 Volume","value":vol_text,"inline":True},
        {"name":"🔔 Flips/Triggers","value":triggers,"inline":True},
        {"name":"🧭 24h High/Low","value":f"{fmt(high24)}/{fmt(low24)}","inline":True},
    ]

    send_discord_embed(f"🚨 XRP Intel — {datetime.utcnow().strftime('%b %d, %H:%M UTC')}", fields, news)
    post_to_x(f"🚨 XRP Intel — Price: ${fmt(price,3)} | {vol_text} | Triggers: {triggers} #XRP #Crypto")

if __name__=="__main__":
    main()
