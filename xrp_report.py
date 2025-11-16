import requests
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta

# ----------------------
# CONFIG
# ----------------------
CSV_FILE = "xrp_history.csv"
WEBHOOK_URL = "https://discord.com/api/webhooks/1439145854899589141/s5vTSsu_z-Wx1HxgV1C-pSt3LO9jo_brrsoFbXRoBfjlcxD1Ut7tFC_6TlpicqC8P6HY"  # Replace with your actual webhook

# Percentage thresholds
DANGER_DROP_PCT = 0.02   # 2% drop from current price triggers danger
CAUTION_DROP_PCT = 0.01  # 1% drop from current price triggers caution

# ----------------------
# FETCH DATA
# ----------------------
def fetch_30d_hourly():
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
    try:
        df_hist = pd.read_csv(CSV_FILE)
        df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], errors="coerce")
    except FileNotFoundError:
        df_hist = pd.DataFrame(columns=["timestamp", "close", "high", "low", "volume"])

    if current_row["timestamp"] not in df_hist["timestamp"].values:
        df_hist = pd.concat([df_hist, pd.DataFrame([current_row])], ignore_index=True)

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

    bullish_prob = 50
    bearish_prob = 50

    if price > ma50:
        bullish_prob += 15
        bearish_prob -= 15
    else:
        bullish_prob -= 15
        bearish_prob += 15

    if macd_line > macd_signal:
        bullish_prob += 20
        bearish_prob -= 20
    else:
        bullish_prob -= 20
        bearish_prob += 20

    if rsi < 30:
        bullish_prob += 10
        bearish_prob -= 10
    elif rsi > 70:
        bullish_prob -= 10
        bearish_prob += 10

    bullish_prob = max(0, min(100, bullish_prob))
    bearish_prob = max(0, min(100, bearish_prob))

    return {
        "price": round(price, 4),
        "rsi": round(rsi, 2) if isinstance(rsi, (float, int)) else "N/A",
        "macd_line": round(macd_line, 4) if isinstance(macd_line, (float, int)) else "N/A",
        "macd_signal": round(macd_signal, 4) if isinstance(macd_signal, (float, int)) else "N/A",
        "ma50": round(ma50, 4),
        "ma200": round(ma200, 4),
        "bullish_prob": round(bullish_prob, 2),
        "bearish_prob": round(bearish_prob, 2)
    }

# ----------------------
# SEND REPORT
# ----------------------
def send_report(report, df_hist):
    last_12h = df_hist["close"].tail(12)
    last_24h = df_hist["close"].tail(24)

    trend = "Bullish" if report["bullish_prob"] > report["bearish_prob"] else "Bearish"

    # Dynamic thresholds based on last price
    danger_price = report["price"] * (1 - DANGER_DROP_PCT)
    caution_price = report["price"] * (1 - CAUTION_DROP_PCT)

    alerts = []
    if report["price"] < danger_price:
        alerts.append(f"🟥 XRP below ${danger_price:.4f} — danger level")
    elif report["price"] < caution_price:
        alerts.append(f"⚠ XRP retraced near ${caution_price:.4f} — caution")

    if report["macd_line"] < report["macd_signal"]:
        alerts.append("🔴 MACD Bearish Crossover")
    elif report["macd_line"] > report["macd_signal"]:
        alerts.append("🔵 MACD Bullish Crossover")

    message = f"""**XRP 12-Hour Report**

💰 Current Price: ${report['price']}

⏱ 12-Hour Range
• High: ${last_12h.max():.4f}
• Low: ${last_12h.min():.4f}

⏱ 24-Hour Range
• High: ${last_24h.max():.4f}
• Low: ${last_24h.min():.4f}

📈 RSI (14): {report['rsi']}
📉 MACD: {report['macd_line']} (signal {report['macd_signal']})

📈 Bullish Probability: {report['bullish_prob']}%
📉 Bearish Probability: {report['bearish_prob']}%

🔍 Trend: {trend}

⚡ Alerts
• {"\n• ".join(alerts) if alerts else 'No alerts at this time'}
"""

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

    current = df_hist.iloc[-1].to_dict()
    df_hist = update_history(current)

    report = analyze(df_hist)
    send_report(report, df_hist)
    print("✅ XRP report completed")

if __name__ == "__main__":
    main()
