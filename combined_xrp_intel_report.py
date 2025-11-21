#!/usr/bin/env python3
"""
combined_xrp_intel_report.py

Combined Crypto Intel + XRP 12-Hour Report
- Full Discord report with indicators, alerts, patterns, news
- Volume spike and MACD crossover alerts
- Multi-timeframe confirmations
- Updates xrp_history.csv automatically
- Dynamic caution/strong/danger levels
"""
import os
import time
import requests
import feedparser
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta, timezone

print("DISCORD_WEBHOOK:", DISCORD_WEBHOOK) 

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
# UTILITIES
# ----------------------------
def send_discord(content: str, webhook: str = DISCORD_WEBHOOK):
    """Post a plain message to Discord webhook (content only)."""
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
    """Format numbers consistently for display."""
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    try:
        return f"{float(x):,.4f}"
    except:
        return str(x)


# ----------------------------
# FETCH DATA
# ----------------------------
def fetch_30d_hourly():
    """Fetch 30-day hourly XRP data from CoinGecko. Falls back to CSV if API fails."""
    url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
    params = {"vs_currency": "usd", "days": "30", "interval": "hourly"}
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        prices = data.get("prices", [])
        vols = data.get("total_volumes", [])
        if not prices or not vols:
            raise ValueError("Empty data from CoinGecko")
        
        df_p = pd.DataFrame(prices, columns=["timestamp_ms", "close"])
        df_v = pd.DataFrame(vols, columns=["timestamp_ms", "volume"])
        df_p["timestamp"] = pd.to_datetime(df_p["timestamp_ms"], unit="ms", utc=True)
        df_v["timestamp"] = pd.to_datetime(df_v["timestamp_ms"], unit="ms", utc=True)
        df = pd.merge(df_p[["timestamp", "close"]], df_v[["timestamp", "volume"]], on="timestamp", how="left")
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["high"] = df["close"]
        df["low"] = df["close"]
        return df

    except Exception as e:
        print("Fetch error (30d hourly):", e)
        print("Falling back to CSV history...")
        # fallback
        try:
            hist = pd.read_csv(CSV_FILE)
            hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True)
            return hist
        except Exception as e2:
            print("CSV fallback failed:", e2)
            # As a last resort, return a minimal fake DF
            now = datetime.utcnow()
            return pd.DataFrame({
                "timestamp": [now],
                "close": [1.0],
                "high": [1.0],
                "low": [1.0],
                "volume": [0]
            })



def fetch_live_price():
    """Return (price, timestamp(datetime tz-aware UTC)) using CoinGecko simple/price."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "ripple", "vs_currencies": "usd", "include_last_updated_at": "true"}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        price = float(data["ripple"]["usd"])
        ts = int(data["ripple"].get("last_updated_at", 0))
        ts_dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(tz=timezone.utc)
        return price, ts_dt
    except Exception as e:
        print("Live price fetch failed:", e)
        return None, None


def fetch_crypto_news(limit: int = 5) -> str:
    """Fetch a short list of headlines (RSS). Falls back gracefully."""
    feed_url = "https://crypto.news/feed/"
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries[:limit]
        lines = []
        for entry in entries:
            title = entry.get("title", "No title")
            link = entry.get("link", "")
            lines.append(f"• {title}\n{link}\n")
        return "\n".join(lines).strip()
    except Exception as e:
        print("News fetch error:", e)
        return "No headlines available"


# ----------------------------
# HISTORY MANAGEMENT
# ----------------------------
def update_history_csv(row: dict):
    """Append a row to CSV history if timestamp is new; keep last 30 days."""
    new_row = pd.DataFrame([row])
    new_row["timestamp"] = pd.to_datetime(new_row["timestamp"], utc=True)

    try:
        hist = pd.read_csv(CSV_FILE)
        hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True)
    except FileNotFoundError:
        hist = pd.DataFrame(columns=["timestamp", "close", "high", "low", "volume"])

    # Avoid duplicates
    if new_row["timestamp"].iloc[0] not in hist["timestamp"].values:
        hist = pd.concat([hist, new_row], ignore_index=True)

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
    hist = hist[hist["timestamp"] >= cutoff]
    hist.to_csv(CSV_FILE, index=False)
    return hist


# ----------------------------
# INDICATORS
# ----------------------------
def compute_indicators(df: pd.DataFrame) -> dict:
    """Compute RSI, MACD, MA50 and MA200 and return as dict."""
    result = {}
    close = df["close"].astype(float)

    # RSI
    try:
        rsi = RSIIndicator(close, window=RSI_WINDOW).rsi()
        result["rsi_series"] = rsi
        result["rsi"] = float(rsi.iloc[-1])
    except Exception:
        result["rsi_series"] = pd.Series([np.nan] * len(df))
        result["rsi"] = np.nan

    # MACD
    try:
        macd = MACD(close, window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
        result["macd_line"] = float(macd.macd().iloc[-1])
        result["macd_signal"] = float(macd.macd_signal().iloc[-1])
        result["macd_hist_series"] = macd.macd_diff()
        result["macd_hist"] = float(macd.macd_diff().iloc[-1])    # FIXED
    except Exception:
        result.update({
            "macd_line": np.nan, "macd_signal": np.nan,
            "macd_hist": np.nan, "macd_hist_series": pd.Series([np.nan] * len(df))
        })

    # Moving averages
    result["ma50"] = float(close.rolling(50, min_periods=1).mean().iloc[-1])
    result["ma200"] = float(close.rolling(200, min_periods=1).mean().iloc[-1])
    return result


# ----------------------------
# ALERTS & PATTERNS
# ----------------------------
def detect_volume_spike(df: pd.DataFrame) -> dict:
    vol_series = df["volume"].astype(float).replace(0, np.nan)
    tail = vol_series.tail(24)
    avg = tail.mean() if len(tail.dropna()) > 0 else vol_series.mean()
    last = float(vol_series.iloc[-1])
    ratio = last / avg if avg and avg > 0 else 0

    level = None
    if ratio >= VOLUME_SPIKE_LEVELS["extreme"]:
        level = "EXTREME"
    elif ratio >= VOLUME_SPIKE_LEVELS["strong"]:
        level = "STRONG"
    elif ratio >= VOLUME_SPIKE_LEVELS["caution"]:
        level = "CAUTION"

    return {"ratio": ratio, "avg": avg, "last": last, "level": level}


def macd_histogram_trend(hist_series: pd.Series):
    if hist_series is None or len(hist_series.dropna()) < 3:
        return None
    recent = hist_series.dropna().tail(3)
    if len(recent) < 3:
        return None
    slope = np.polyfit(range(len(recent)), recent.values, 1)[0]
    if slope > 0.00001:
        return "increasing"
    elif slope < -0.00001:
        return "decreasing"
    return "flat/mixed"


def support_resistance(df: pd.DataFrame) -> dict:
    price = df["close"].astype(float)
    return {
        "recent_high": float(price.tail(SWING_WINDOW).max()),
        "recent_low": float(price.tail(SWING_WINDOW).min()),
        "last": float(price.iloc[-1])
    }


def detect_patterns(df: pd.DataFrame, indicators: dict) -> list:
    patterns = []
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    # Compression Arc
    if len(df) >= COMPRESSION_WINDOW:
        r = high - low
        if r.iloc[-1] < r.iloc[0] * 0.6 and r.std() < r.mean() * 0.6:
            patterns.append("Compression Arc")

    # Pulse Stack (stricter)
    if len(df) >= PULSE_STACK_WINDOW:
        window = df.tail(PULSE_STACK_WINDOW)
        closes = window["close"].astype(float)
        vols = window["volume"].astype(float)
        up_count = (closes.pct_change() > 0).sum()
        vol_trend = np.polyfit(range(len(vols)), vols, 1)[0]
        if up_count >= 9 and vol_trend > 0:
            patterns.append("Pulse Stack")

    # Trap Funnel
    if len(df) >= 24:
        recent_high = close.tail(24).max()
        recent_low = close.tail(24).min()
        spike_exists = (close.tail(24) > recent_high * 1.02).any()
        if spike_exists and close.iloc[-1] < recent_low * 0.995:
            patterns.append("Trap Funnel")

    # Sentinel Base
    if len(df) >= SENTINEL_WINDOW:
        recent_lows = low.tail(SENTINEL_WINDOW)
        rsi_series = indicators.get("rsi_series")
        macd_line = indicators.get("macd_line", 0)
        if (recent_lows.std() < recent_lows.mean() * 0.01 and
                rsi_series is not None and
                len(rsi_series.dropna()) >= 3 and
                rsi_series.iloc[-1] > rsi_series.iloc[-3] and
                macd_line > 0):
            patterns.append("Sentinel Base")

    return patterns if patterns else ["None detected"]


# ----------------------------
# DYNAMIC LEVELS
# ----------------------------
def compute_dynamic_levels(df: pd.DataFrame) -> dict:
    recent_high = float(df["close"].tail(24).max())
    recent_low = float(df["close"].tail(24).min())
    return {
        "recent_high": recent_high,
        "recent_low": recent_low,
        "breakout_weak": recent_high * 1.02,
        "breakout_strong": recent_high * 1.06,
        "breakdown_weak": recent_low * 0.98,
        "breakdown_strong": recent_low * 0.95,
        "danger": recent_low * 0.92
    }


# ----------------------------
# COMPOSE DISCORD MESSAGE
# ----------------------------
def compose_discord_message(df: pd.DataFrame, live_price: float) -> str:
    indicators = compute_indicators(df)
    price = float(live_price)
    vol = detect_volume_spike(df)
    sr = support_resistance(df)
    levels = compute_dynamic_levels(df)
    patterns = detect_patterns(df, indicators)
    macd_hist_trend = macd_histogram_trend(indicators.get("macd_hist_series")) or "unknown"

    # Volume text
    if vol["level"] == "EXTREME":
        vol_text = f"**EXTREME** volume spike ({vol['ratio']:.2f}x avg)"
    elif vol["level"] == "STRONG":
        vol_text = f"**Strong** volume spike ({vol['ratio']:.2f}x avg)"
    elif vol["level"] == "CAUTION":
        vol_text = f"Caution volume spike ({vol['ratio']:.2f}x avg)"
    else:
        vol_text = "No surge"

    # Flips / Triggers
    flips = []
    if price >= levels["breakout_weak"]:
        flips.append(f"Bullish breakout (weak ≥ ${fmt(levels['breakout_weak'])})")
    if price >= levels["breakout_strong"]:
        flips.append(f"Bullish breakout (strong ≥ ${fmt(levels['breakout_strong'])})")
    if price <= levels["breakdown_weak"]:
        flips.append(f"Bearish breakdown (weak ≤ ${fmt(levels['breakdown_weak'])})")
    if price <= levels["breakdown_strong"]:
        flips.append(f"Bearish breakdown (strong ≤ ${fmt(levels['breakdown_strong'])})")
    if price <= levels["danger"]:
        flips.append(f"**DANGER**: below danger level ≤ ${fmt(levels['danger'])}")
    flips_text = ", ".join(flips) if flips else "None"

    # Bullish/Bearish probability
    bullish = 50
    bearish = 50
    if price > indicators["ma50"]:
        bullish += 15
        bearish -= 15
    else:
        bullish -= 15
        bearish += 15

    if indicators["macd_line"] > indicators["macd_signal"]:
        bullish += 20
        bearish -= 20
    else:
        bullish -= 20
        bearish += 20

    if indicators["rsi"] < 30:
        bullish += 10
        bearish -= 10
    elif indicators["rsi"] > 70:
        bullish -= 10
        bearish += 10

    if indicators["ma50"] > indicators["ma200"]:
        bullish += 5
        bearish -= 5

    bullish = max(0, min(100, bullish))
    bearish = max(0, min(100, bearish))

    news = fetch_crypto_news()

    message = f"""
🚨 **Combined XRP Intelligence Report** 🚨

💰 **Current Price**: ${fmt(price)}
📈 RSI (14): {fmt(indicators['rsi'])}
📉 MACD: {fmt(indicators['macd_line'])} | Signal: {fmt(indicators['macd_signal'])}
📊 MA50: ${fmt(indicators['ma50'])} | MA200: ${fmt(indicators['ma200'])}

📈 **Bullish Probability**: {bullish}%
📉 **Bearish Probability**: {bearish}%
🔍 **Trend**: {"Bullish 🟢" if bullish > bearish else "Bearish 🔴"}

📊 **Volume Signals**: {vol_text}
⚠ **Patterns Detected**: {', '.join(patterns)}
📊 MACD Histogram: {macd_hist_trend}
🧭 24h High: ${fmt(sr['recent_high'])} | Low: ${fmt(sr['recent_low'])}

🔔 **Flips/Triggers**: {flips_text}

**Dynamic Levels**
🟢 Breakout Weak: ${fmt(levels['breakout_weak'])}
🟢 Breakout Strong: ${fmt(levels['breakout_strong'])}
🔴 Breakdown Weak: ${fmt(levels['breakdown_weak'])}
🔴 Breakdown Strong: ${fmt(levels['breakdown_strong'])}
⚠ Danger Zone: ${fmt(levels['danger'])}

📰 **Latest Crypto News**
{news}

---
Data: last {len(df)} hourly candles (30-day history) | Updated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
""".strip()

    return message


# ----------------------------
# MAIN
# ----------------------------
def main():
    time.sleep(1)  # gentle rate limit
    df = fetch_30d_hourly()
    if df is None or df.empty:
        print("No historical data, aborting.")
        return

    live_price, live_ts = fetch_live_price()
    if live_price is None:
        print("Live price unavailable; using last close from history.")
        live_price = float(df["close"].iloc[-1])

    # Update latest candle with live price
    df = df.copy()
    last_idx = df.index[-1]
    df.loc[last_idx, "close"] = live_price
    df.loc[last_idx, "high"] = max(df.loc[last_idx, "high"], live_price)
    df.loc[last_idx, "low"] = min(df.loc[last_idx, "low"], live_price)

    # Save to CSV history
    last_row = {
        "timestamp": df.loc[last_idx, "timestamp"],
        "close": float(df.loc[last_idx, "close"]),
        "high": float(df.loc[last_idx, "high"]),
        "low": float(df.loc[last_idx, "low"]),
        "volume": float(df.loc[last_idx, "volume"])
    }
    try:
        update_history_csv(last_row)
    except Exception as e:
        print("CSV update failed:", e)

    message = compose_discord_message(df, live_price)
    send_discord(message)
    print("XRP Report sent to Discord successfully.")


if __name__ == "__main__":
    main()
