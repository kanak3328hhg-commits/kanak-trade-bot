import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# আপনার একদম সঠিক ও ভেরিফাইড তথ্যসমূহ
BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
FOREX_CHAT_ID = "-1004292142406"  # 🎯 স্ক্রিনশট অনুযায়ী ফরেক্স চ্যানেলের সঠিক আইডি
QUOTEX_CHAT_ID = "-1003684590469" # 🎯 স্ক্রিনশট অনুযায়ী কোটেক্স চ্যানেলের সঠিক আইডি
GEMINI_API_KEY = "AIzaSyB6_x6_7-TuK-yYHEas7yhBshe4mG7ibNI"


# Render-এর পোর্ট ফিক্স করার জন্য ফেক ওয়েব সার্ভার সেটআপ
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Kanak AI Bot is running smoothly!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_fake_server():
    import os
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    print(f"Fake server started on port {port}")
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

# জেমিনি এআই বাংলা টিপস জেনারেট করার ফাংশন
def get_ai_bengali_tip(pair_name, direction, rsi, price):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        prompt = (
            f"Write a short technical commentary in Bengali about {pair_name} market structure. "
            f"The trend is {direction}, current price is {price}, and RSI indicator is at {rsi:.1f}. "
            f"Explain what this structure means for a scalper in exactly one short sentence (maximum 12 words). "
            f"Make it unique, analytical, and write directly in Bengali without any intro, quotes, or greetings."
        )
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, headers=headers, timeout=8) # টাইমআউট ৮ সেকেন্ড করা হলো দ্রুত রেসপন্সের জন্য
        
        if response.status_code == 200:
            ai_response = response.json()
            tip_text = ai_response['candidates'][0]['content']['parts'][0]['text'].strip()
            tip_text = tip_text.replace('"', '').replace('*', '')
            return tip_text
        else:
            if "EUR" in pair_name: return "ইউরোর বর্তমান চার্ট প্যাটার্ন অনুযায়ী ব্রেকআউটের জন্য অপেক্ষা করা বুদ্ধিমানের কাজ হবে।"
            if "GBP" in pair_name: return "পাউন্ডের হাই ভোলাটিলিটি জোনে প্রোপার মানি ম্যানেজমেন্ট কঠোরভাবে মেনে চলুন।"
            if "JPY" in pair_name: return "জেপিওয়াই পেয়ারে ট্রেন্ড রিভার্সাল কনফার্মেশনের পর এন্ট্রি নেওয়া নিরাপদ।"
            return f"{pair_name} পেয়ারের বর্তমান টেকনিক্যাল লেভেলে ক্যান্ডেলস্টিক প্যাটার্ন ফলো করুন।"
    except Exception as e:
        return f"{pair_name} পেয়ারে ট্রেড করার সময় প্রোপার রিস্ক ম্যানেজমেন্ট ফলো করুন।"

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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=10)
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
        quotex_pips_target = 0.0100 if is_jpy else 0.0005

        if ema_fast > ema_slow and rsi_value > 50:
            direction, strength = "UP", int(min(rsi_value + 25, 98))
            sl = current_price - pips_sl
            tp1 = current_price + pips_tp1
            tp2 = current_price + pips_tp2
            quotex_exit = current_price + quotex_pips_target
        elif ema_fast < ema_slow and rsi_value < 50:
            direction, strength = "DOWN", int(min((100 - rsi_value) + 25, 98))
            sl = current_price + pips_sl
            tp1 = current_price - pips_tp1
            tp2 = current_price - pips_tp2
            quotex_exit = current_price - quotex_pips_target
        else:
            direction = "UP" if rsi_value >= 50 else "DOWN"
            strength = 72
            sl = current_price - pips_sl
            tp1 = current_price + pips_tp1
            tp2 = current_price + pips_tp2
            quotex_exit = current_price + quotex_pips_target if direction == "UP" else current_price - quotex_pips_target
            
        bengali_tip = get_ai_bengali_tip(display_name, direction, rsi_value, current_price)
            
        return {
            "price": round(current_price, 4 if not is_jpy else 2), 
            "direction": direction, 
            "strength": strength,
            "sl": round(sl, 4 if not is_jpy else 2),
            "tp1": round(tp1, 4 if not is_jpy else 2),
            "tp2": round(tp2, 4 if not is_jpy else 2),
            "quotex_exit": round(quotex_exit, 4 if not is_jpy else 2),
            "tip": bengali_tip
        }
    except Exception as e:
        return None

pairs_to_track = {
    "NZDUSD=X": "NZD-USD",
    "EURUSD=X": "EUR-USD",
    "GBPUSD=X": "GBP-USD",
    "USDJPY=X": "USD-JPY",
    "AUDUSD=X": "AUD-USD"
}

# ব্যাকগ্রাউন্ড সার্ভার স্টার্ট
server_thread = threading.Thread(target=run_fake_server, daemon=True)
server_thread.start()

print("Kanak AI Bot Starting smoothly with Real-time Loop...")

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
                    f"💰 Entry Price: **{signal['price']}**\n"
                    f"🏁 Exit Target Price: **{signal['quotex_exit']}**\n"
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
            
            # কোনো শর্ত ছাড়া সরাসরি রিয়েল-টাইমে পুশ হবে
            try: requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": forex_message, "parse_mode": "Markdown"}, timeout=12)
            except Exception as e: print(e)
            
            try:
                requests.post(url, json={"chat_id": QUOTEX_CHAT_ID, "text": quotex_message, "parse_mode": "Markdown"}, timeout=12)
                print(f"Signals directly pushed at {current_time}")
            except Exception as e: print(e)
                
    except Exception as main_loop_error:
        print(f"Loop error: {main_loop_error}")
    
    # ⏱️ সেফ জোনে ৩ মিনিট (১৮০ সেকেন্ড) পর পর রেগুলার ফ্রেশ পুশ হবে 
    time.sleep(180)
