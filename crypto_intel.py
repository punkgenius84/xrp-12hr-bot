#!/usr/bin/env python3
return buf


# ---- Main scheduled run


def run_scheduled():
now = datetime.now(timezone.utc).isoformat()


# Market prices
prices = coin_gecko_price(["bitcoin","ethereum","xrp"])
btc = prices.get('bitcoin',{})
eth = prices.get('ethereum',{})
xrp = prices.get('xrp',{})


market_text = f"**BTC:** ${btc.get('usd','?'):,} ({btc.get('usd_24h_change',0):.2f}% 24H)\n" \
f"**ETH:** ${eth.get('usd','?'):,} ({eth.get('usd_24h_change',0):.2f}% 24H)\n" \
f"**XRP:** ${xrp.get('usd','?'):,} ({xrp.get('usd_24h_change',0):.2f}% 24H)\n"


# Global news
global_news = fetch_cryptopanic(filter_q='important', limit=10)
news_lines = []
total_sent = 0.0
for item in global_news:
title = item.get('title','')
url = item.get('url','')
s = sentiment_score(title)
total_sent += s
label = label_impact(title, item.get('source',{}).get('title',''), s, mentions=1)
emoji = '🔴' if s < -0.2 else '🟢' if s > 0.2 else '🟡'
news_lines.append(f"{emoji} **{title}**\n{url}\nImpact: {label}\n")


avg_sent = total_sent / max(1, len(global_news))
market_sent = 'Bullish' if avg_sent > 0.15 else 'Bearish' if avg_sent < -0.15 else 'Neutral'


# Gainers/losers
gainers, losers = get_top_gainers_losers()
gain_text = '\n'.join([f"🟢 {g['name']}: {g['price_change_percentage_24h']:.2f}%" for g in gainers])
lose_text = '\n'.join([f"🔴 {l['name']}: {l['price_change_percentage_24h']:.2f}%" for l in losers])


# Whale alerts (if key present)
whales = fetch_whale_alerts(5)
whale_lines = []
for w in whales:
whale_lines.append(f"🐋 {w.get('amount')} {w.get('symbol')} moved: {w.get('transaction_hash','')}\n")


# XRP sentiment heat
xrp_heat = xrp_sentiment_heat()


# TA + chart for XRP (1H)
try:
df = fetch_binance_ohlcv('XRPUSDT', interval='1h', limit=200)
ta_df = compute_ta(df)
chart_buf = generate_xrp_chart(ta_df)
except Exception as e:
print('ohlcv/ta/chart error', e)
chart_buf = None


# Build main embed
embed_main = {
'title': '📊 Crypto Intelligence — 12H Report',
'description': market_text + f"\n**Market Sentiment:** {market_sent}\n**XRP Heat:** {xrp_heat['heat']} (n={xrp_heat['count']})",
'timestamp': now,
'fields': [
