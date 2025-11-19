#!/usr/bin/env python3
"""
xrp_report.py — Advanced XRP 12-hour intelligence report
- Top-level features:
  * Uses 30-day hourly history from CoinGecko
  * Injects live price from CoinGecko simple/price
  * Calculates RSI, MACD, MACD histogram, MA50/MA200
  * Volume surge alerts (15%, 30%, 50% thresholds)
  * RSI divergence detection (simple heuristic)
  * MACD histogram strength and zero-line cross alerts
  * Support/resistance flips (local swings)
  * Heuristic detection for user patterns:
      Compression Arc, Pulse Stack, Trap Funnel, Sentinel Base
  * Multi-timeframe confirmations for 15m (approx), 1h, 24h
  * Dynamic breakout & breakdown thresholds derived from recent ranges
  * Nicely formatted Discord message
Notes:
- 15-minute timeframe is approximated using live price vs last hour candle (CoinGecko hourly data)
- This is heuristic / best-effort. No external paid APIs required.
"""

import requests
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta
import math

# ----------------------
# CONFIG
# ----------------------
CSV_FILE = "xrp_history.csv"
WEBHOOK_URL = "https://discord.com/api/webhooks/1439145854899589141/s5vTSsu_z-Wx1HxgV1C-pSt3LO9jo_brrsoFbXRoBfjlcxD1Ut7tFC_6TlpicqC8P6HY"

# detection parameters
VOLUME_SPIKE_LEVELS = {"caution": 1.15, "strong": 1.30, "extreme": 1.50}  # multiples of avg
RSI_WINDOW = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# pattern detection windows
SWING_WINDOW = 24  # hours used to compute local swings
COMPRESSION_WINDOW = 24  # hours to check tightening range
PULSE_STACK_WINDOW = 12
SENTINEL_WINDOW = 24

# ----------------------
# UTILS
# ----------------------
def send_discord(content: str):
    try:
        r = requests.post(WEBHOOK_URL, json={"content": content}, timeout=10)
        if r.status_code not in (200, 204):
            print("Discord responded:", r.status_code, r.text[:300])
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

# ----------------------
# FETCH DATA
# ----------------------
def fetch_30d_hourly():
    url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
    params = {"vs_currency": "usd", "days": "30"}
    try:
        data = requests.get(url, params=params, timeout=15).json()
    except Exception as e:
        print("Fetch error:", e)
        return None

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

    # use close as open/high/low for hourly (CoinGecko doesn't provide OHLC in this endpoint)
    df["high"] = df["close"]
    df["low"] = df["close"]
    return df

def fetch_live_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "ripple", "vs_currencies": "usd", "include_last_updated_at": "true"}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        price = float(data["ripple"]["usd"])
        ts = int(data["ripple"].get("last_updated_at", 0))
        ts_dt = datetime.fromtimestamp(ts, tz=None) if ts else datetime.utcnow()
        return price, ts_dt
    except Exception as e:
        print("Live price fetch failed:", e)
        return None, None

# ----------------------
# HISTORY MANAGEMENT
# ----------------------
def update_history_csv(row: dict):
    try:
        hist = pd.read_csv(CSV_FILE)
        hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True)
    except FileNotFoundError:
        hist = pd.DataFrame(columns=["timestamp", "close", "high", "low", "volume"])

    # prevent duplicates
    if pd.to_datetime(row["timestamp"]) not in hist["timestamp"].values:
        hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    cutoff = datetime.utcnow() - timedelta(days=30)
    hist = hist[hist["timestamp"] >= cutoff]
    hist.to_csv(CSV_FILE, index=False)
    return hist

# ----------------------
# INDICATORS
# ----------------------
def compute_indicators(df: pd.DataFrame):
    result = {}
    close = df["close"].astype(float)
    # RSI
    try:
        rsi = RSIIndicator(close, window=RSI_WINDOW).rsi()
        result["rsi_series"] = rsi
        result["rsi"] = float(rsi.iloc[-1])
    except Exception:
        result["rsi_series"] = pd.Series([np.nan]*len(df))
        result["rsi"] = np.nan

    # MACD
    try:
        macd = MACD(close, window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
        macd_line = macd.macd()
        macd_signal = macd.macd_signal()
        macd_hist = macd.macd_diff()
        result["macd_line"] = float(macd_line.iloc[-1])
        result["macd_signal"] = float(macd_signal.iloc[-1])
        result["macd_hist"] = float(macd_hist.iloc[-1])
        result["macd_hist_series"] = macd_hist
    except Exception:
        result.update({"macd_line": np.nan, "macd_signal": np.nan, "macd_hist": np.nan, "macd_hist_series": pd.Series([np.nan]*len(df))})

    # Moving averages
    result["ma50"] = float(close.rolling(50, min_periods=1).mean().iloc[-1])
    result["ma200"] = float(close.rolling(200, min_periods=1).mean().iloc[-1])

    return result

# ----------------------
# VOLUME SURGE
# ----------------------
def detect_volume_spike(df: pd.DataFrame):
    # compare last hour volume vs rolling 24-hour mean (or available)
    vol_series = df["volume"].astype(float)
    if len(vol_series) < 24:
        avg = vol_series.mean() if len(vol_series)>0 else 0
    else:
        avg = vol_series.tail(24).mean()
    last = float(vol_series.iloc[-1])
    ratio = (last / avg) if avg>0 else 0
    level = None
    if ratio >= VOLUME_SPIKE_LEVELS["extreme"]:
        level = "EXTREME"
    elif ratio >= VOLUME_SPIKE_LEVELS["strong"]:
        level = "STRONG"
    elif ratio >= VOLUME_SPIKE_LEVELS["caution"]:
        level = "CAUTION"
    return {"ratio": ratio, "avg": avg, "last": last, "level": level}

# ----------------------
# RSI DIVERGENCE (heuristic)
# ----------------------
def detect_rsi_divergence(df: pd.DataFrame, rsi_series: pd.Series):
    # find two recent price lows and their RSI values (simple local minima detection)
    price = df["close"].astype(float)
    length = len(price)
    if length < 8:
        return None  # not enough data

    # local minima detection using simple window
    lows_idx = []
    window = 3
    for i in range(window, length-window):
        if price.iloc[i] < price.iloc[i-1] and price.iloc[i] < price.iloc[i+1]:
            lows_idx.append(i)
    # need at least two lows
    if len(lows_idx) < 2:
        return None

    # use the last two minima
    i1, i2 = lows_idx[-2], lows_idx[-1]
    p1, p2 = price.iloc[i1], price.iloc[i2]
    r1, r2 = rsi_series.iloc[i1], rsi_series.iloc[i2]
    # bullish divergence: price lower low, RSI higher low
    if p2 < p1 and r2 > r1:
        return {"type": "bullish", "p1": p1, "p2": p2, "r1": r1, "r2": r2, "idx": (i1,i2)}
    # bearish divergence: price higher high + RSI lower high (check local maxima)
    highs_idx = []
    for i in range(window, length-window):
        if price.iloc[i] > price.iloc[i-1] and price.iloc[i] > price.iloc[i+1]:
            highs_idx.append(i)
    if len(highs_idx) >= 2:
        j1, j2 = highs_idx[-2], highs_idx[-1]
        ph1, ph2 = price.iloc[j1], price.iloc[j2]
        rh1, rh2 = rsi_series.iloc[j1], rsi_series.iloc[j2]
        if ph2 > ph1 and rh2 < rh1:
            return {"type": "bearish", "ph1": ph1, "ph2": ph2, "rh1": rh1, "rh2": rh2, "idx": (j1,j2)}
    return None

# ----------------------
# MACD HISTOGRAM STRENGTH
# ----------------------
def macd_histogram_trend(macd_hist_series: pd.Series):
    # take last 3 bars
    try:
        last = macd_hist_series.iloc[-3:]
        if len(last.dropna()) < 3:
            return None
        if last.is_monotonic_increasing:
            return "increasing"
        if last.is_monotonic_decreasing:
            return "decreasing"
        return "mixed"
    except Exception:
        return None

# ----------------------
# SUPPORT / RESISTANCE (simple)
# ----------------------
def support_resistance(df: pd.DataFrame):
    price = df["close"].astype(float)
    # recent swing high/low using rolling windows
    recent_high = price.tail(SWING_WINDOW).max()
    recent_low = price.tail(SWING_WINDOW).min()
    last = float(price.iloc[-1])
    return {"recent_high": float(recent_high), "recent_low": float(recent_low), "last": last}

# ----------------------
# PATTERN DETECTION (heuristic)
# ----------------------
def detect_compression_arc(df: pd.DataFrame):
    # compression = progressively narrowing range over COMPRESSION_WINDOW
    if len(df) < COMPRESSION_WINDOW + 1:
        return False
    window = df.tail(COMPRESSION_WINDOW)
    highs = window["high"].astype(float)
    lows = window["low"].astype(float)
    ranges = highs - lows
    # check decreasing range (last range < first range * 0.6) and low volatility
    if ranges.iloc[-1] < ranges.iloc[0] * 0.6 and ranges.std() < (ranges.mean()*0.6):
        return True
    return False

def detect_pulse_stack(df: pd.DataFrame):
    # pulse stack: consecutive bullish hourly closes with rising volume
    if len(df) < PULSE_STACK_WINDOW:
        return False
    window = df.tail(PULSE_STACK_WINDOW)
    closes = window["close"].astype(float)
    vols = window["volume"].astype(float)
    # check >3 consecutive bullish closes and positive slope in volume
    bullish_streak = (closes.pct_change() > 0).sum()
    vol_slope = np.polyfit(range(len(vols)), vols, 1)[0]
    if bullish_streak >= 3 and vol_slope > 0:
        return True
    return False

def detect_trap_funnel(df: pd.DataFrame):
    # trap funnel: brief fake breakout above recent high then drop below support
    if len(df) < 12:
        return False
    recent_high = df["close"].tail(24).max()
    last = df["close"].iloc[-1]
    # simplistic check: if there was a spike > recent_high * 1.02 and now price < recent_low * 0.995
    recent_low = df["close"].tail(24).min()
    spike_exists = (df["close"].tail(24) > recent_high * 1.02).any()
    if spike_exists and last < recent_low * 0.995:
        return True
    return False

def detect_sentinel_base(df: pd.DataFrame, indicators):
    # sentinel base: flat support (low volatility) + rising RSI and MACD positive
    if len(df) < SENTINEL_WINDOW:
        return False
    window = df.tail(SENTINEL_WINDOW)
    lows = window["low"].astype(float)
    if lows.std() < (lows.mean() * 0.01):  # very flat
        rsi_series = indicators.get("rsi_series")
        macd_line = indicators.get("macd_line", 0)
        if rsi_series is not None and len(rsi_series) >= 2:
            if rsi_series.iloc[-1] > rsi_series.iloc[-3] and macd_line > 0:
                return True
    return False

# ----------------------
# MULTI-TIMEFRAME CONFIRMATIONS (15m approx, 1h, 24h)
# ----------------------
def multi_timeframe_confirmations(df: pd.DataFrame, live_price: float, indicators):
    confirmations = {}
    # 1H: current hourly candle is last row
    current = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else current
    # MACD crossover on 1H
    macd_line = indicators.get("macd_line", np.nan)
    macd_signal = indicators.get("macd_signal", np.nan)
    confirmations["1h_macd_cross"] = "bull" if macd_line > macd_signal else ("bear" if macd_line < macd_signal else "none")
    # RSI trend 1h (compare last 3)
    rsi = indicators.get("rsi")
    confirmations["1h_rsi"] = "up" if indicators.get("rsi_series").iloc[-1] > indicators.get("rsi_series").iloc[-3] else "down"
    # 24h: use last 24 rows
    last24 = df["close"].tail(24).astype(float)
    confirmations["24h_price_trend"] = "up" if last24.iloc[-1] > last24.iloc[0] else "down"
    # 15m approx: compare live price to last hourly open/close
    approx_15m = "up" if live_price > current["close"] else "down"
    confirmations["15m_approx"] = approx_15m
    return confirmations

# ----------------------
# DYNAMIC BREAKOUT / BREAKDOWN THRESHOLDS
# ----------------------
def compute_dynamic_levels(df: pd.DataFrame, report_price: float):
    # Use recent 24h high/low to compute dynamic thresholds
    recent_high = float(df["close"].tail(24).max())
    recent_low = float(df["close"].tail(24).min())
    # breakout weak/strong
    breakout_weak = recent_high * 1.02
    breakout_strong = recent_high * 1.06
    # breakdown weak/strong
    breakdown_weak = recent_low * 0.98
    breakdown_strong = recent_low * 0.95
    danger = recent_low * 0.92
    return {
        "recent_high": recent_high, "recent_low": recent_low,
        "breakout_weak": breakout_weak, "breakout_strong": breakout_strong,
        "breakdown_weak": breakdown_weak, "breakdown_strong": breakdown_strong,
        "danger": danger
    }

# ----------------------
# COMPOSE REPORT
# ----------------------
def compose_and_send_report(df: pd.DataFrame, live_price: float):
    indicators = compute_indicators(df)
    # Inject live price into last candle for display and thresholds
    df = df.copy()
    df.loc[df.index[-1], "close"] = live_price
    price = float(live_price)

    # probabilities similar to previous logic but include MA50/200 and timeframe confirmations
    bullish = 50
    bearish = 50
    if price > indicators["ma50"]:
        bullish += 15; bearish -= 15
    else:
        bullish -=15; bearish +=15
    if indicators["macd_line"] > indicators["macd_signal"]:
        bullish += 20; bearish -=20
    else:
        bullish -=20; bearish +=20
    if indicators["rsi"] < 30:
        bullish += 10; bearish -=10
    elif indicators["rsi"] > 70:
        bullish -=10; bearish +=10
    # add small boost if MA50 > MA200
    if indicators["ma50"] > indicators["ma200"]:
        bullish += 5; bearish -=5
    # clamp
    bullish = max(0, min(100, bullish))
    bearish = max(0, min(100, bearish))

    # volume surge
    vol = detect_volume_spike(df)
    vol_text = "No surge"
    if vol["level"] == "EXTREME":
        vol_text = f"EXTREME volume spike ({vol['ratio']:.2f}x avg)"
    elif vol["level"] == "STRONG":
        vol_text = f"Strong volume spike ({vol['ratio']:.2f}x avg)"
    elif vol["level"] == "CAUTION":
        vol_text = f"Caution volume spike ({vol['ratio']:.2f}x avg)"

    # divergence
    div = detect_rsi_divergence(df, indicators.get("rsi_series"))
    div_text = "None"
    if div:
        if div["type"] == "bullish":
            div_text = f"Bullish divergence (price {fmt(div['p1'])} -> {fmt(div['p2'])}, RSI {fmt(div['r1'])} -> {fmt(div['r2'])})"
        elif div["type"] == "bearish":
            div_text = f"Bearish divergence (price {fmt(div['ph1'])} -> {fmt(div['ph2'])}, RSI {fmt(div['rh1'])} -> {fmt(div['rh2'])})"

    # MACD histogram trend
    macd_hist_trend = macd_histogram_trend(indicators.get("macd_hist_series"))
    macd_hist_text = macd_hist_trend if macd_hist_trend else "None"

    # support/resistance
    sr = support_resistance(df)
    sr_text = f"24h High: ${fmt(sr['recent_high'])}, 24h Low: ${fmt(sr['recent_low'])}"

    # patterns
    patterns = []
    if detect_compression_arc(df):
        patterns.append("Compression Arc")
    if detect_pulse_stack(df):
        patterns.append("Pulse Stack")
    if detect_trap_funnel(df):
        patterns.append("Trap Funnel")
    if detect_sentinel_base(df, indicators):
        patterns.append("Sentinel Base")
    patterns_text = ", ".join(patterns) if patterns else "None detected"

    # multi-timeframe confirmations
    mt = multi_timeframe_confirmations(df, live_price, indicators)
    mt_text = f"15m(approx): {mt['15m_approx']}, 1h MACD: {mt['1h_macd_cross']}, 1h RSI: {mt['1h_rsi']}, 24h trend: {mt['24h_price_trend']}"

    # dynamic levels
    levels = compute_dynamic_levels(df, price)
    level_text = (
        f"Breakout weak: ${fmt(levels['breakout_weak'])}, strong: ${fmt(levels['breakout_strong'])}\n"
        f"Breakdown weak: ${fmt(levels['breakdown_weak'])}, strong: ${fmt(levels['breakdown_strong'])}\n"
        f"Danger level: ${fmt(levels['danger'])}"
    )

    # flips
    flips = []
    if price > levels["breakout_weak"]:
        flips.append("Bullish breakout (weak)")
    if price > levels["breakout_strong"]:
        flips.append("Bullish breakout (strong)")
    if price < levels["breakdown_weak"]:
        flips.append("Bearish breakdown (weak)")
    if price < levels["breakdown_strong"]:
        flips.append("Bearish breakdown (strong)")
    if price < levels["danger"]:
        flips.append("DANGER: price below danger level")

    flips_text = ", ".join(flips) if flips else "None"

    # assemble message
    message = f"""
**🚨 XRP 12-Hour Intelligence Report**

💰 Current Price: ${fmt(price)}
📈 RSI (14): {fmt(indicators.get('rsi'))}
📉 MACD: {fmt(indicators.get('macd_line'))} (signal {fmt(indicators.get('macd_signal'))})
📊 MA50: {fmt(indicators.get('ma50'))}  MA200: {fmt(indicators.get('ma200'))}

📈 Bullish Probability: {fmt(bullish)}%
📉 Bearish Probability: {fmt(bearish)}%

🔍 Trend: {"Bullish 🟢" if bullish>bearish else "Bearish 🔴"}

📊 Volume Signals: {vol_text}
🔁 RSI Divergence: {div_text}
📊 MACD Histogram Trend: {macd_hist_text}
🧭 Support/Resistance: {sr_text}
⚠ Patterns Detected: {patterns_text}

🧾 Multi-timeframe confirmations: {mt_text}

📌 Dynamic Levels:
{level_text}

🔔 Flips/Triggers: {flips_text}

⚡ Alerts Summary:
• Volume: {vol_text}
• RSI Divergence: {div_text}
• MACD: {macd_hist_text}
• Patterns: {patterns_text}

---

_Data window used: last {len(df)} hourly candles (30-day history, hourly)._"""

    send_discord(message.strip())

# ----------------------
# MAIN
# ----------------------
def main():
    df = fetch_30d_hourly()
    if df is None or df.empty:
        print("No data, aborting.")
        return

    live_price, live_ts = fetch_live_price()
    if live_price is None:
        # fallback: use last close
        print("Live price unavailable; using last hourly close.")
        live_price = float(df["close"].iloc[-1])

    # inject live price into last row for analysis display (do NOT alter history permanently here)
    df = df.copy()
    df.loc[df.index[-1], "close"] = live_price
    df.loc[df.index[-1], "high"] = max(df.loc[df.index[-1], "high"], live_price)
    df.loc[df.index[-1], "low"] = min(df.loc[df.index[-1], "low"], live_price)

    # persist the last (timestamped) row into CSV history (keeps 30-day history)
    last_row = {
        "timestamp": df.loc[df.index[-1], "timestamp"],
        "close": float(df.loc[df.index[-1], "close"]),
        "high": float(df.loc[df.index[-1], "high"]),
        "low": float(df.loc[df.index[-1], "low"]),
        "volume": float(df.loc[df.index[-1], "volume"])
    }
    try:
        update_history_csv(last_row)
    except Exception as e:
        print("Failed updating history CSV:", e)

    # compose and send report
    compose_and_send_report(df, live_price)
    print("Report sent.")

if __name__ == "__main__":
    main()
