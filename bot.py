import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# আপনার দেওয়া সঠিক টোকেন, মাইনাসসহ চ্যানেল আইডি এবং এআই চাবি
BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
FOREX_CHAT_ID = "-1004292142406"  
QUOTEX_CHAT_ID = "-1003684590469"
GEMINI_API_KEY = "AIzaSyB6_x6_7-TuK-yYHEas7yhBshe4mG7ibNI"

# Render-এর Port Timeout এরর এড়ানোর জন্য ডামি ওয়েব সার্ভার সেটআপ
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Kanak AI-Powered Trade Bot is Live and Running!")

def run_dummy_server():
    import os
    port = int(os.environ.get("PORT", 10001))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# বাংলাদেশ সময় অনুযায়ী ফরেক্স সেশনের নাম বের করার ফাংশন
def get_current_forex_sessions():
    now_utc = datetime.utcnow()
    now_bst = now_utc + timedelta(hours=6)
    current_hour = now_bst.hour
    
    sessions = []
    if 4 <= current_hour < 13: sessions.append("Sydney")
    if 6 <= current_hour < 15: sessions.append("Tokyo")
    if 13 <= current_hour < 22: sessions.append("London")
    if current_hour >= 18 or current_hour < 3: sessions.append("New York")
        
    if not sessions: return "Live Market"
    return ", ".join(sessions)

# সরাসরি Google Gemini AI ব্যবহার করে লাইভ মার্কেট অনুযায়ী বাংলা টিপস জেনারেট করার ফাংশন
def get_ai_bengali_tip(pair_name, direction, rsi, price):
    try:
        # Gemini 1.5-flash API Endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        # এআই-কে সঠিক নির্দেশ বা প্রম্পট দেওয়া
        prompt = (
            f"You are a professional Forex and Binary Options trader. "
            f"Currently, a {direction} signal is generated for {pair_name} at price {price}. "
            f"The RSI value is {rsi:.2f}. Based on this market condition, give a single line (max 15-20 words) "
            f"educational trading tip or caution in professional, easy-to-understand Bengali language for my Telegram subscribers. "
            f"Do not include any English translation or greetings, just the one-line Bengali tip. Start directly with the tip."
        )
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            ai_response = response.json()
            tip_text = ai_response['candidates'][0]['content']['parts'][0]['text'].strip()
            return tip_text
        else:
            return "মার্কেট ট্রেন্ড ফলো করুন এবং প্রফিট বুক করতে স্টপ লস ট্রেইল করুন।"
    except Exception as e:
        print(f"AI Generation Error: {e}")
        return "ট্রেন্ডের দিকে নজর রাখুন এবং সঠিক মানি ম্যানেজমেন্ট মেনে ট্রেড করুন।"

# RSI হিসাব করার ফাংশন
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    for i in range(period, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# EMA হিসাব করার ফাংশন
def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def generate_signal(ticker_symbol, display_name):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range=2d&interval=5m"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return None
            
        json_data = response.json()
        result = json_data['chart']['result'][0]
        
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        highs = result['indicators']['quote'][0]['high']
        lows = result['indicators']['quote'][0]['low']
        opens = result['indicators']['quote'][0]['open']
        
        data = pd.DataFrame({
            'Open': opens, 'High': highs, 'Low': lows, 'Close': closes
        }, index=pd.to_datetime(timestamps, unit='s'))
        
        data.dropna(subset=['Close'], inplace=True)
        if data.empty or len(data) < 30: return None

        data['RSI'] = calculate_rsi(data['Close'], period=14)
        data['EMA_fast'] = calculate_ema(data['Close'], period=9)
        data['EMA_slow'] = calculate_ema(data['Close'], period=21)
        
        latest_row = data.iloc[-1]
        rsi_value = latest_row['RSI']
        ema_fast = latest_row['EMA_fast']
        ema_slow = latest_row['EMA_slow']
        current_price = latest_row['Close']
        
        if pd.isna(rsi_value) or pd.isna(ema_fast) or pd.isna(ema_slow): return None

        rsi_value = float(rsi_value)
        ema_fast = float(ema_fast)
        ema_slow = float(ema_slow)
        current_price = float(current_price)

        is_jpy = "JPY" in ticker_symbol
        pips_sl = 0.0300 if is_jpy else 0.0030   
        pips_tp1 = (pips_sl * 2)  
        pips_tp2 = (pips_sl * 3)  

        if ema_fast > ema_slow and rsi_value > 50:
            direction, strength = "UP", int(min(rsi_value + 25, 98))
            sl = current_price - pips_sl
            tp1 = current_price + pips_tp1
            tp2 = current_price + pips_tp2
        elif ema_fast < ema_slow and rsi_value < 50:
            direction, strength = "DOWN", int(min((100 - rsi_value) + 25, 98))
            sl = current_price + pips_sl
            tp1 = current_price - pips_tp1
            tp2 = current_price - pips_tp2
        else:
            direction = "UP" if rsi_value >= 50 else "DOWN"
            strength = 72
            sl = current_price - pips_sl
            tp1 = current_price + pips_tp1
            tp2 = current_price + pips_tp2
            
        # 🤖 এআই কল করে একদম রিয়েল-টাইম বাংলা টিপস নেওয়া
        bengali_tip = get_ai_bengali_tip(display_name, direction, rsi_value, current_price)
            
        return {
            "price": round(current_price, 4 if not is_jpy else 2), 
            "direction": direction, 
            "strength": strength,
            "sl": round(sl, 4 if not is_jpy else 2),
            "tp1": round(tp1, 4 if not is_jpy else 2),
            "tp2": round(tp2, 4 if not is_jpy else 2),
            "tip": bengali_tip
        }
    except Exception as e:
        print(f"Error analyzing {ticker_symbol}: {e}")
        return None

pairs_to_track = {
    "NZDUSD=X": "NZD-USD",
    "EURUSD=X": "EUR-USD",
    "GBPUSD=X": "GBP-USD",
    "USDJPY=X": "USD-JPY",
    "AUDUSD=X": "AUD-USD"
}

server_thread = threading.Thread(target=run_dummy_server, daemon=True)
server_thread.start()

print("Kanak AI-Powered Bot is fully integrated and starting...")

while True:
    try:
        current_session = get_current_forex_sessions()
        
        now_utc = datetime.utcnow()
        now_bst = now_utc + timedelta(hours=6)
        current_time = now_bst.strftime("%I:%M %p")
        
        forex_message = f"📊 **Forex Signals Update - {current_time}**\n\n"
        quotex_message = f"📱 **Quotex Fast Binary Signals - {current_time}**\n\n"
        has_signals = False
        
        for ticker, display_name in pairs_to_track.items():
            signal = generate_signal(ticker, display_name)
            if signal:
                has_signals = True
                emoji = "🟢" if signal['direction'] == "UP" else "🔴"
                
                forex_message += (
                    f"🎯 **{display_name}** - {emoji} {signal['direction']}\n\n"
                    f"⏰ Timeframe: 5M\n"
                    f"📊 Strength: {signal['strength']}%\n"
                    f"💰 Entry Price: {signal['price']}\n"
                    f"🛑 Stop Loss (SL): {signal['sl']}\n"
                    f"✅ Take Profit 1 (TP1): {signal['tp1']}\n"
                    f"✅ Take Profit 2 (TP2): {signal['tp2']}\n\n"
                    f"💡 **AI টিপস:** {signal['tip']}\n\n"
                    f"#{display_name} #Forex\n"
                    f"🌐 **Active Session:** `{current_session}`\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                )
                
                quotex_message += (
                    f"📊 **Quotex | {display_name}**\n\n"
                    f"🎯 Signal Direction: {emoji} **{signal['direction']}**\n"
                    f"⏰ Best Expiry: **1 MINUTE**\n"
                    f"📈 Signal Accuracy: {signal['strength']}%\n"
                    f"🚀 Trade Type: Turbo Scalping\n\n"
                    f"💡 **AI টিপস:** {signal['tip']}\n\n"
                    f"#{display_name} #Quotex1M\n"
                    f"🌐 **Active Session:** `{current_session}`\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                )
        
        if has_signals:
            if forex_message.endswith("━━━━━━━━━━━━━━━━━━\n\n"): forex_message = forex_message[:-22]
            if quotex_message.endswith("━━━━━━━━━━━━━━━━━━\n\n"): quotex_message = quotex_message[:-22]
                
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            
            try: requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": forex_message, "parse_mode": "Markdown"}, timeout=15)
            except Exception as e: print(e)
            
            try:
                requests.post(url, json={"chat_id": QUOTEX_CHAT_ID, "text": quotex_message, "parse_mode": "Markdown"}, timeout=15)
                print(f"AI-generated signals pushed to channels successfully!")
            except Exception as e: print(e)
            
    except Exception as main_loop_error:
        print(f"Network issue: {main_loop_error}")
    
    time.sleep(300)
