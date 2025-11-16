import requests
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta
import os

# ----------------------
# CONFIG
# ----------------------
CSV_FILE = "xrp_history.csv"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Pull from GitHub secret

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
    if df.empty or len(df) < 14:
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
# ALERTS
# ----------------------
def generate_alerts(price, df):
    alerts = []
    # Update these thresholds as needed
    if price < 2.25:
        alerts.append("🟥 XRP below $2.25 — danger level")
    elif price < 2.28:
        alerts.append("⚠ XRP retraced near $2.28 — caution")

    macd_obj = MACD(df["close"])
    macd_line = macd_obj.macd().iloc[-1]
    macd_signal = macd_obj.macd_signal().iloc[-1]
    if macd_line > macd_signal:
        alerts.append("🟢 MACD Bullish Crossover")
    else:
        alerts.append("🔴 MACD Bearish Crossover")

    return alerts

# ----------------------
# SEND REPORT
# ----------------------
def send_report(df, report):
    last_row = df.iloc[-1]
    high_12h = df["close"].tail(12).max()
    low_12h = df["close"].tail(12).min()
    high_24h = df["close"].tail(24).max()
    low_24h = df["close"].tail(24).min()

    alerts = generate_alerts(report["price"], df)
    trend = "Bullish" if report["bullish_prob"] > report["bearish_prob"] else "Bearish"

    message = f"""
**💹 XRP 12-Hour Report**

💰 Current Price: ${report['price']}

⏱ 12-Hour Range
• High: ${round(high_12h,4)}
• Low: ${round(low_12h,4)}

⏱ 24-Hour Range
• High: ${round(high_24h,4)}
• Low: ${round(low_24h,4)}

📈 RSI (14): {report['rsi']}
📉 MACD: {report['macd_line']}
📉 Signal: {report['macd_signal']}

📈 Bullish Probability: {report['bullish_prob']}%
📉 Bearish Probability: {report['bearish_prob']}%

🔍 Trend: {trend}

⚡ Alerts
""" + "\n".join([f"• {a}" for a in alerts])

    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
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
    send_report(df_hist, report)
    print("✅ XRP report completed")

if __name__ == "__main__":
    main()
