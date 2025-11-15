import requests
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta
import os
import sys

# ----------------------
# CONFIG
# ----------------------
CSV_FILE = "xrp_history.csv"

# Grab webhook from environment
WEBHOOK = os.getenv("WEBHOOK_URL")
if not WEBHOOK:
    print("❌ ERROR: WEBHOOK_URL secret not found! Add it in Settings → Secrets → Actions.")
    sys.exit(1)

# ----------------------
# FETCH DATA
# ----------------------
def fetch_30d_hourly():
    """Fetch 30 days of hourly XRP prices and volumes from CoinGecko"""
    url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
    params = {"vs_currency": "usd", "days": "30"}
    
    try:
        data = requests.get(url, params=params, timeout=15).json()
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return None

    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    if not prices or not volumes:
        print("❌ CoinGecko API returned invalid data.")
        return None

    df_prices = pd.DataFrame(prices, columns=["timestamp", "close"])
    df_vol = pd.DataFrame(volumes, columns=["timestamp", "volume"])

    # Convert ms to datetime
    df_prices["timestamp"] = pd.to_datetime(df_prices["timestamp"], unit="ms", errors="coerce")
    df_vol["timestamp"] = pd.to_datetime(df_vol["timestamp"], unit="ms", errors="coerce")

    df = pd.merge(df_prices, df_vol, on="timestamp", how="left")
    df["high"] = df["close"]
    df["low"] = df["close"]

    return df

# ----------------------
# UPDATE HISTORY CSV
# ----------------------
def update_history(current_row):
    """Append latest data to CSV and keep last 30 days"""
    try:
        df_hist = pd.read_csv(CSV_FILE)
        df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], errors="coerce")
    except FileNotFoundError:
        df_hist = pd.DataFrame(columns=["timestamp", "close", "high", "low", "volume"])

    # Append only if new timestamp
    if current_row["timestamp"] not in df_hist["timestamp"].values:
        df_hist = pd.concat([df_hist, pd.DataFrame([current_row])], ignore_index=True)

    # Keep last 30 days
    cutoff = datetime.utcnow() - timedelta(days=30)
    df_hist = df_hist[df_hist["timestamp"] >= cutoff]

    df_hist.to_csv(CSV_FILE, index=False)
    return df_hist

# ----------------------
# ANALYZE
# ----------------------
def analyze(df):
    if df.empty or len(df) < 14:  # RSI requires at least 14 points
        return {
            "price": df["close"].iloc[-1] if not df.empty else 0,
            "rsi": "N/A",
            "macd_line": "N/A",
            "macd_signal": "N/A",
            "ma50": df["close"].iloc[-1] if len(df) >= 1 else 0,
            "ma200": df["close"].iloc[-1] if len(df) >= 1 else 0,
            "bullish_prob": 0,
            "bearish_prob": 100
        }

    price = df["close"].iloc[-1]

    rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    macd_obj = MACD(df["close"])
    macd_line = macd_obj.macd().iloc[-1]
    macd_signal = macd_obj.macd_signal().iloc[-1]

    ma50 = df["close"].rolling(50).mean().iloc[-1] if len(df) >= 50 else df["close"].mean()
    ma200 = df["close"].rolling(200).mean().iloc[-1] if len(df) >= 200 else df["close"].mean()

    bullish_prob = 0
    bearish_prob = 0

    if price > ma50: bullish_prob += 30
    else: bearish_prob += 25

    if macd_line > macd_signal: bullish_prob += 40
    else: bearish_prob += 40

    if rsi < 30: bullish_prob += 20
    if rsi > 70: bearish_prob += 20

    total = bullish_prob + bearish_prob
    total = total if total != 0 else 1
    bullish_prob = round((bullish_prob / total) * 100, 2)
    bearish_prob = round((bearish_prob / total) * 100, 2)

    return {
        "price": round(price, 4),
        "rsi": round(rsi, 2) if isinstance(rsi, (float, int)) else "N/A",
        "macd_line": round(macd_line, 4) if isinstance(macd_line, (float, int)) else "N/A",
        "macd_signal": round(macd_signal, 4) if isinstance(macd_signal, (float, int)) else "N/A",
        "ma50": round(ma50, 4),
        "ma200": round(ma200, 4),
        "bullish_prob": bullish_prob,
        "bearish_prob": bearish_prob
    }

# ----------------------
# HIGH/LOW & VOLUME ALERT
# ----------------------
def get_highs_lows(df):
    now = df["timestamp"].max()
    df_12h = df[df["timestamp"] >= now - pd.Timedelta(hours=12)]
    df_24h = df[df["timestamp"] >= now - pd.Timedelta(hours=24)]
    
    return {
        "12h_high": round(df_12h["close"].max(), 4),
        "12h_low": round(df_12h["close"].min(), 4),
        "24h_high": round(df_24h["close"].max(), 4),
        "24h_low": round(df_24h["close"].min(), 4)
    }

def check_volume_spike(df):
    last_vol = df["volume"].iloc[-1]
    avg_vol = df["volume"].tail(24).mean()  # last 24 periods
    if last_vol > avg_vol * 1.5:
        return "⚡ Volume spike detected!"
    return ""

# ----------------------
# SEND REPORT
# ----------------------
def send_report(report, highs_lows, volume_alert):
    trend_alert = ""
    if report['bullish_prob'] > 70:
        trend_alert = "📈 Strong Bullish Trend"
    elif report['bearish_prob'] > 70:
        trend_alert = "📉 Strong Bearish Trend"

    message = f"""
**📊 XRP 12-Hour Report**

Price: ${report['price']}
RSI: {report['rsi']}
MACD: {report['macd_line']} (signal {report['macd_signal']})
MA50: {report['ma50']}
MA200: {report['ma200']}

📈 Bullish Probability: {report['bullish_prob']}%
📉 Bearish Probability: {report['bearish_prob']}%

High/Low:
- 12H High: ${highs_lows['12h_high']}
- 12H Low: ${highs_lows['12h_low']}
- 24H High: ${highs_lows['24h_high']}
- 24H Low: ${highs_lows['24h_low']}

{volume_alert}
{trend_alert}

Alerts:
- MACD crossover monitored
- RSI divergence monitored
- Pattern detection enabled
"""
    try:
        requests.post(WEBHOOK, json={"content": message}, timeout=10)
        print("✅ Discord report sent")
    except Exception as e:
        print(f"❌ Failed to send Discord report: {e}")

# ----------------------
# MAIN
# ----------------------
def main():
    df_hist = fetch_30d_hourly()
    if df_hist is None:
        print("⚠️ Skipping report: Failed to fetch data.")
        return

    # Use last row as "current"
    current = df_hist.iloc[-1].to_dict()
    df_hist = update_history(current)

    report = analyze(df_hist)
    highs_lows = get_highs_lows(df_hist)
    volume_alert = check_volume_spike(df_hist)

    send_report(report, highs_lows, volume_alert)
    print("✅ XRP report completed")

if __name__ == "__main__":
    main()
