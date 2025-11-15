import requests
import time
import os
import numpy as np

WEBHOOK = os.getenv("WEBHOOK_URL")

# -------------------------------------------------------------------
# TIME WINDOWS
# -------------------------------------------------------------------
now = int(time.time())
t12 = now - 12 * 3600
t24 = now - 24 * 3600


# -------------------------------------------------------------------
# FETCH PRICE RANGE
# -------------------------------------------------------------------
def fetch_range(start, end):
    url = (
        "https://api.coingecko.com/api/v3/coins/ripple/market_chart/range"
        f"?vs_currency=usd&from={start}&to={end}"
    )
    data = requests.get(url).json()

    prices = [p[1] for p in data.get("prices", [])]
    volumes = [v[1] for v in data.get("total_volumes", [])]

    return prices, volumes


prices12, vol12 = fetch_range(t12, now)
prices24, vol24 = fetch_range(t24, now)

if not prices12 or not prices24:
    requests.post(WEBHOOK, json={"content": "❌ XRP bot error: Failed to fetch data."})
    raise SystemExit()


current = prices12[-1]

high12 = max(prices12)
low12 = min(prices12)

high24 = max(prices24)
low24 = min(prices24)


# -------------------------------------------------------------------
# RSI (14)
# -------------------------------------------------------------------
def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


rsi = calc_rsi(prices24)


# -------------------------------------------------------------------
# MACD (12, 26, 9)
# -------------------------------------------------------------------
def ema(values, period):
    alpha = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(out[-1] * (1 - alpha) + alpha * v)
    return out


ema12 = ema(prices24, 12)
ema26 = ema(prices24, 26)[-len(ema12):]

macd_line = np.array(ema12) - np.array(ema26)
signal_line = ema(macd_line, 9)[-1]
macd_current = macd_line[-1]
macd_prev = macd_line[-2]


# -------------------------------------------------------------------
# VOLUME SPIKE DETECTION
# -------------------------------------------------------------------
vol_avg = np.mean(vol12)
vol_last = vol12[-1]
volume_spike = vol_last > vol_avg * 2.2


# -------------------------------------------------------------------
# TREND SCORE (simple)
# -------------------------------------------------------------------
trend = (
    ("Bullish" if current > high12 * 0.97 else
     "Bearish" if current < low12 * 1.03 else
     "Neutral")
)


# -------------------------------------------------------------------
# ALERTS
# -------------------------------------------------------------------
alerts = []

if macd_current > signal_line and macd_prev < signal_line:
    alerts.append("🔵 **MACD Bullish Crossover**")

if macd_current < signal_line and macd_prev > signal_line:
    alerts.append("🔴 **MACD Bearish Crossover**")

if volume_spike:
    alerts.append("📈 **VOLUME SPIKE DETECTED**")

if current > 2.70:
    alerts.append("🚀 XRP broke **$2.70**")

if current < 2.30:
    alerts.append("⚠ XRP broke **$2.30** (bearish)")

if current < 2.25:
    alerts.append("🟥 XRP under **$2.25 danger level**")

if current > 2.80:
    alerts.append("🔥 XRP passed **$2.80 breakout**")

if current <= 2.35:
    alerts.append("🔻 XRP retraced near **$2.35**")


# -------------------------------------------------------------------
# REPORT MESSAGE
# -------------------------------------------------------------------
alert_text = "\n".join(alerts) if alerts else "No new alerts."

message = f"""
📊 **XRP 12-Hour Report**

💰 **Current Price:** ${current:.4f}

⏱ **12-Hour Range**
• High: ${high12:.4f}
• Low: ${low12:.4f}

⏱ **24-Hour Range**
• High: ${high24:.4f}
• Low: ${low24:.4f}

📈 **RSI (14):** {rsi}
📉 **MACD:** {macd_current:.4f}
📉 **Signal:** {signal_line:.4f}

🔍 **Trend:** {trend}

⚡ **Alerts**
{alert_text}
"""

requests.post(WEBHOOK, json={"content": message})
