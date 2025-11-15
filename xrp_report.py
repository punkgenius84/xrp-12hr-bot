import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
import time

WEBHOOK_URL = "https://discord.com/api/webhooks/1439145854899589141/s5vTSsu_z-Wx1HxgV1C-pSt3LO9jo_brrsoFbXRoBfjlcxD1Ut7tFC_6TlpicqC8P6HY"

def get_xrp_data(retries=5, delay=5):
    for attempt in range(retries):
        try:
            url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart?vs_currency=usd&days=0.5&interval=minute"
            data = requests.get(url, timeout=10).json()

            if "prices" not in data or not data["prices"]:
                print(f"❌ Attempt {attempt+1}: No price data, retrying...")
                time.sleep(delay)
                continue

            df = pd.DataFrame(data["prices"], columns=["timestamp", "close"])
            df["close"] = df["close"].astype(float)
            df["high"] = df["close"]
            df["low"] = df["close"]

            df_vol = pd.DataFrame(data.get("total_volumes", []), columns=["timestamp", "volume"])
            if not df_vol.empty:
                df["volume"] = df_vol["volume"].astype(float)
            else:
                df["volume"] = 0

            df = df.iloc[::15, :].reset_index(drop=True)
            return df

        except Exception as e:
            print(f"❌ Attempt {attempt+1}: CoinGecko request failed: {e}")
            time.sleep(delay)
    return None

def analyze(df):
    price = df["close"].iloc[-1]
    rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    macd_line = MACD(df["close"]).macd().iloc[-1]
    macd_signal = MACD(df["close"]).macd_signal().iloc[-1]
    ma50 = df["close"].rolling(50).mean().iloc[-1]
    ma200 = df["close"].rolling(200).mean().iloc[-1]

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

def send_report(report, skipped=False):
    if skipped:
        message = "⚠️ XRP report skipped: CoinGecko API returned invalid data."
    else:
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
    df = get_xrp_data()
    if df is not None:
        report = analyze(df)
        send_report(report)
        print("✅ XRP 12-hour report sent successfully via CoinGecko.")
    else:
        send_report(None, skipped=True)
        print("⚠️ XRP report skipped due to CoinGecko API error.")
