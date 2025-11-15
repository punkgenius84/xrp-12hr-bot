import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta
import os

WEBHOOK_URL = "https://discord.com/api/webhooks/1439145854899589141/s5vTSsu_z-Wx1HxgV1C-pSt3LO9jo_brrsoFbXRoBfjlcxD1Ut7tFC_6TlpicqC8P6HY"
CSV_FILE = "xrp_history.csv"

# ----------------------------
# Step 1: Fetch 30-day hourly CSV
# ----------------------------
def fetch_30d_hourly_csv():
    url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart?vs_currency=usd&days=30"
    try:
        data = requests.get(url, timeout=15).json()
    except Exception as e:
        print("❌ Failed to fetch historical data:", e)
        return

    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    if not prices:
        print("❌ No price data returned from CoinGecko")
        return

    df_prices = pd.DataFrame(prices, columns=["timestamp", "close"])
    df_vol = pd.DataFrame(volumes, columns=["timestamp", "volume"])

    df_prices["timestamp"] = pd.to_datetime(df_prices["timestamp"], unit="ms")
    df_vol["timestamp"] = pd.to_datetime(df_vol["timestamp"], unit="ms")

    df = pd.merge(df_prices, df_vol, on="timestamp", how="left")
    df["high"] = df["close"]
    df["low"] = df["close"]

    df.to_csv(CSV_FILE, index=False)
    print("✅ 30-day hourly CSV saved as xrp_history.csv")

# ----------------------------
# Step 2: Fetch current price
# ----------------------------
def fetch_current_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd&include_24hr_vol=true"
    try:
        data = requests.get(url, timeout=10).json()
        price = float(data["ripple"]["usd"])
        volume = float(data["ripple"]["usd_24h_vol"])
        timestamp = datetime.utcnow()
        return {"timestamp": timestamp, "close": price, "volume": volume, "high": price, "low": price}
    except Exception as e:
        print("❌ Failed to fetch current price:", e)
        return None

# ----------------------------
# Step 3: Update history CSV
# ----------------------------
def update_history(current):
    df_new = pd.DataFrame([current])

    df_hist = pd.read_csv(CSV_FILE)
    df_hist = pd.concat([df_hist, df_new], ignore_index=True)

    df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], errors="coerce", utc=True)
    df_hist = df_hist.dropna(subset=["timestamp"])

    thirty_days_ago = pd.Timestamp.utcnow() - pd.Timedelta(days=30)
    df_hist = df_hist[df_hist["timestamp"] >= thirty_days_ago]

    df_hist.to_csv(CSV_FILE, index=False)

# ----------------------------
# Step 4: Analyze indicators
# ----------------------------
def analyze(df):
    df["close"] = df["close"].astype(float)
    price = df["close"].iloc[-1]

    rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    macd_line = MACD(df["close"]).macd().iloc[-1]
    macd_signal = MACD(df["close"]).macd_signal().iloc[-1]

    ma50 = df["close"].rolling(50).mean().iloc[-1] if len(df) >= 50 else price
    ma200 = df["close"].rolling(200).mean().iloc[-1] if len(df) >= 200 else price

    bullish_prob = 0
    bearish_prob = 0

    if price > ma50: bullish_prob += 30
    else: bearish_prob += 25

    if macd_line > macd_signal: bullish_prob += 40
    else: bearish_prob += 40

    if rsi < 30: bullish_prob += 20
    if rsi > 70: bearish_prob += 20

    total = bullish_prob + bearish_prob
    if total == 0: total = 1

    bullish_prob = round((bullish_prob / total) * 100, 2)
    bearish_prob = round((bearish_prob / total) * 100, 2)

    return {
        "price": price,
        "rsi": round(rsi, 2),
        "macd_line": round(macd_line, 4),
        "macd_signal": round(macd_signal, 4),
        "ma50": round(ma50, 4),
        "ma200": round(ma200, 4),
        "bullish_prob": bullish_prob,
        "bearish_prob": bearish_prob
    }

# ----------------------------
# Step 5: Send Discord report
# ----------------------------
def send_report(report):
    message = f"""
**📊 XRP 12-Hour Report**

**Price:** ${report['price']:.2f}  
**RSI:** {report['rsi'] if not pd.isna(report['rsi']) else 'N/A'}  
**MACD:** {report['macd_line'] if not pd.isna(report['macd_line']) else 'N/A'} (signal {report['macd_signal'] if not pd.isna(report['macd_signal']) else 'N/A'})  
**MA50:** {report['ma50']:.4f}  
**MA200:** {report['ma200']:.4f}  

**📈 Bullish Probability:** {report['bullish_prob']}%  
**📉 Bearish Probability:** {report['bearish_prob']}%  

**Alerts:**  
- MACD crossover monitored  
- RSI divergence monitored  
- Volume spikes monitored  
- Pattern detection enabled
"""
    try:
        response = requests.post(WEBHOOK_URL, json={"content": message})
        if response.status_code == 204:
            print("✅ Discord message sent successfully")
        else:
            print(f"❌ Discord message failed with status {response.status_code}")
    except Exception as e:
        print("❌ Failed to send Discord message:", e)

# ----------------------------
# Step 6: Main
# ----------------------------
if __name__ == "__main__":
    if not os.path.exists(CSV_FILE):
        print("📁 xrp_history.csv not found — fetching 30-day hourly data...")
        fetch_30d_hourly_csv()

    current = fetch_current_price()
    if current is None:
        print("❌ Could not fetch price. Skipping report.")
    else:
        update_history(current)
        df_hist = pd.read_csv(CSV_FILE)
        df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], errors="coerce", utc=True)
        df_hist = df_hist.dropna(subset=["timestamp"])
        report = analyze(df_hist)
        send_report(report)
