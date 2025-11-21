# ----------------------------
# COMPOSE DISCORD MESSAGE (Updated with dynamic caution levels)
# ----------------------------
def compose_discord_message(df, live_price):
    indicators = compute_indicators(df)
    price = float(live_price)
    
    # Volume spike detection
    vol = detect_volume_spike(df)
    vol_text = "No surge"
    if vol["level"] == "EXTREME":
        vol_text = f"EXTREME volume spike ({vol['ratio']:.2f}x avg)"
    elif vol["level"] == "STRONG":
        vol_text = f"Strong volume spike ({vol['ratio']:.2f}x avg)"
    elif vol["level"] == "CAUTION":
        vol_text = f"Caution volume spike ({vol['ratio']:.2f}x avg)"
    
    # Patterns
    patterns = detect_patterns(df, indicators)
    patterns_text = ", ".join(patterns)
    
    # MACD Histogram Trend
    macd_hist_text = macd_histogram_trend(indicators.get("macd_hist_series")) or "None"
    
    # Support/Resistance
    sr = support_resistance(df)
    levels = compute_dynamic_levels(df)
    
    # Flips/Triggers
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
    
    # Bullish/Bearish Probabilities
    bullish, bearish = 50, 50
    if price > indicators["ma50"]:
        bullish += 15; bearish -= 15
    else:
        bullish -= 15; bearish += 15
    if indicators["macd_line"] > indicators["macd_signal"]:
        bullish += 20; bearish -= 20
    else:
        bullish -= 20; bearish += 20
    if indicators["rsi"] < 30:
        bullish += 10; bearish -= 10
    elif indicators["rsi"] > 70:
        bullish -= 10; bearish += 10
    if indicators["ma50"] > indicators["ma200"]:
        bullish += 5; bearish -= 5
    bullish = max(0, min(100, bullish))
    bearish = max(0, min(100, bearish))
    
    # --- Dynamic Caution Levels ---
    caution_levels = []
    # Weak Caution
    if (levels["breakout_weak"] <= price <= levels["breakout_strong"]) or (vol["ratio"] >= 1.15):
        caution_levels.append(f"⚠️ Weak Caution 🟡 - Price/volume approaching warning zone (x{vol['ratio']:.2f})")
    # Strong Caution
    if (levels["breakout_strong"] < price <= levels["breakout_strong"]*1.02) or (vol["ratio"] >= 1.30):
        caution_levels.append(f"⚠️ Strong Caution 🟠 - Price/volume in high-risk zone (x{vol['ratio']:.2f})")
    # Danger Zone
    if price >= levels["breakout_strong"]*1.06 or price <= levels["danger"] or (vol["ratio"] >= 1.50):
        caution_levels.append(f"🚨 Danger Zone 🔴 - Price/volume in danger territory (x{vol['ratio']:.2f})")
    caution_text = "\n".join(caution_levels) if caution_levels else "None"
    
    # Fetch crypto news
    news = fetch_crypto_news()
    
    # Compose final message
    message = f"""
**🚨 Combined XRP Intelligence Report**

💰 Current Price: ${fmt(price)}
📈 RSI (14): {fmt(indicators['rsi'])}
📉 MACD: {fmt(indicators['macd_line'])} (signal {fmt(indicators['macd_signal'])})
📊 MA50: {fmt(indicators['ma50'])}  MA200: {fmt(indicators['ma200'])}

📈 Bullish Probability: {fmt(bullish)}%
📉 Bearish Probability: {fmt(bearish)}%

🔍 Trend: {"Bullish 🟢" if bullish>bearish else "Bearish 🔴"}

📊 Volume Signals: {vol_text}
⚠ Patterns Detected: {patterns_text}
📊 MACD Histogram Trend: {macd_hist_text}
🧭 Support/Resistance: 24h High: ${fmt(sr['recent_high'])}, 24h Low: ${fmt(sr['recent_low'])}
🔔 Flips/Triggers: {flips_text}

🟡🟠🔴 Caution Levels:
{caution_text}

📰 Top Crypto News:
{news}

---

_Data window: last {len(df)} hourly candles (30-day history)._
"""
    return message
