#!/usr/bin/env python3
"""
combined_xrp_intel_report.py
"""

import requests
import pandas as pd
from smartmoneyconcepts import smc
import os
from datetime import datetime, timedelta

CSV_FILE = "xrp_history.csv"

def fetch_xrp_hourly_data() -> pd.DataFrame:
    print("Fetching XRP/USDT hourly from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    params = {"fsym": "XRP", "tsym": "USDT", "limit": 2000}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    json_resp = resp.json()

    if isinstance(json_resp.get("Data"), dict) and "Data" in json_resp["Data"]:
        data = json_resp["Data"]["Data"]
    elif isinstance(json_resp.get("Data"), list):
        data = json_resp["Data"]
    elif "data" in json_resp:
        data = json_resp["data"]
    else:
        raise ValueError(f"Unexpected response: {list(json_resp.keys())}")

    df = pd.DataFrame([d for d in data if d.get("time", 0) > 0])
    if df.empty:
        return df

    df["open_time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"volumeto": "volume"}, inplace=True)
    df.columns = df.columns.str.strip().str.lower()
    return df[["open_time", "open", "high", "low", "close", "volume"]]

def load_csv(file_path: str) -> pd.DataFrame:
    try:
        old_df = pd.read_csv(file_path)
        old_df.columns = old_df.columns.str.strip().str.lower()
        if "open_time" in old_df.columns:
            old_df["open_time"] = pd.to_datetime(old_df["open_time"], errors="coerce")
        return old_df
    except Exception as e:
        print("CSV load failed:", e)
        return pd.DataFrame()

# FINAL WORKING MARKET STRUCTURE — ONLY THIS BLOCK IS DIFFERENT
def compute_market_structure(df):
    try:
        df = df.copy()
        df.rename(columns=str.lower, inplace=True)

        # DO NOT reset_index — this is the ONLY line that fixes the bug
        data = df[["open", "high", "low", "close"]].tail(500)  # ← NO .reset_index(drop=True)

        swing_df = smc.swing_highs_lows(data, swing_length=50)

        if len(swing_df) < 3:
            return "No Clear Structure"

        recent = swing_df.tail(3)
        highs = recent['high'].astype(float)
        lows = recent['low'].astype(float)

        if highs.is_monotonic_increasing and lows.is_monotonic_increasing:
            return "Bullish Structure (HH + HL)"
        elif highs.is_monotonic_decreasing and lows.is_monotonic_decreasing:
            return "Bearish Structure (LH + LL)"
        else:
            return "Ranging / Choppy Structure"

    except Exception as e:
        print("Market structure error:", str(e))
        return "Unavailable"

# Your original placeholders
def send_discord_alert(message: str):
    pass

def check_macd_rsi_alerts(df):
    pass

def detect_chart_patterns(df):
    pass

def main():
    new_df = fetch_xrp_hourly_data()
    if new_df.empty:
        print("No new data.")
        return

    old_df = load_csv(CSV_FILE)
    df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset="open_time")
    df.columns = df.columns.str.strip().str.lower()

    df.to_csv(CSV_FILE, index=False)
    print(f"Saved updated CSV with {len(df)} rows.")

    structure_status = compute_market_structure(df)
    print("Market Structure:", structure_status)

    check_macd_rsi_alerts(df)
    detect_chart_patterns(df)
    send_discord_alert(f"Market Structure: {structure_status}")

if __name__ == "__main__":
    main()
