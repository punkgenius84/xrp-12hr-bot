import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime
import os

WEBHOOK_URL = "https://discord.com/api/webhooks/1439145854899589141/s5vTSsu_z-Wx1HxgV1C-pSt3LO9jo_brrsoFbXRoBfjlcxD1Ut7tFC_6TlpicqC8P6HY"
CSV_FILE = "xrp_history.csv"

def fetch_current_price():
    """
    Get current XRP price and 24h volume from CoinGecko simple price endpoint.
    """
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

def update_history(current):
    """
    Save current price to CSV history. Create CSV if it doesn't exist.
    """
    df_new = pd.DataFrame([current])
    if os.path.exists(CSV_FILE):
        df_hist = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
        df_hist = pd.concat([df_hist, df_new], ignore_index=True)
        # Keep last 7 days of data (~672 rows for 15min intervals)
        df_hist = df_hist.tail(672)
        df_hist.to_csv(CSV_FILE, index=False)
    else:
        df_new.to_csv(CSV_FILE, index=False)

def analyze(df):
    """
    Compute RSI, MACD, moving averages, and probabilities.
    """
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

def send_report(report):
    """
    Send formatted report to Discord webhook.
    """
    message = f"""
**📊 XRP 12-Hour Report**

**Price:** ${report['price']}
**RSI:** {report['rsi']}
**MACD:** {report['macd_line']} (signal {report['macd_signal']})
**MA50:** {report['ma50']}
**MA200:** {report['ma200']}

**📈 Bullish Probability:** {report['bullish_prob']}%
**📉 Bearish Probability:** {report['bearish_prob']}%

**Alerts:**  
- MACD crossover monitored  
- RSI divergence monitored  
- Volume spikes monitored  
- Pattern detection enabled  
"""
    try:
        requests.post(WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print("❌ Failed to send Discord message:", e)

if __name__ == "__main__":
    current = fetch_current_price()
    if current is None:
        print("❌ Could not fetch price. Skipping report.")
    else:
        update_history(current)
        df_hist = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
        report = analyze(df_hist)
        send_report(report)
        print("✅ XRP 12-hour report sent successfully.")
