import requests
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# আপনার একদম সঠিক ও ভেরিফাইড তথ্যসমূহ
BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
FOREX_CHAT_ID = "-1004292142406"  # 🎯 স্ক্রিনশট অনুযায়ী ফরেক্স চ্যানেলের সঠিক আইডি
QUOTEX_CHAT_ID = "-1003684590469" # 🎯 স্ক্রিনশট অনুযায়ী কোটেক্স চ্যানেলের সঠিক আইডি
GEMINI_API_KEY = "AIzaSyB6_x6_7-TuK-yYHEas7yhBshe4mG7ibNI"

# Render-এর পোর্ট ফিক্স করার জন্য ফেক ওয়েব সার্ভার সেটআপ
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Kanak AI Bot is running smoothly with HTML & Anti-Block Loop!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_fake_server():
    import os
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    print(f"Fake server started on port {port}")
    server.serve_forever()

# বাংলাদেশ সময় অনুযায়ী ফরেক্স সেশনের নাম বের করার ফাংশন
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
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        
        if response.status_code == 200:
            ai_response = response.json()
            tip_text = ai_response['candidates'][0]['content']['parts'][0]['text'].strip()
            # HTML ট্যাগ ক্লিনিং (যাতে টেলিগ্রাম মেসেজ রিজেক্ট না করে)
            tip_text = tip_text.replace('"', '').replace('*', '').replace('<', '').replace('>', '')
            return tip_text
        else:
            if "EUR" in pair_name: return "ইউরোর বর্তমান চার্ট প্যাটার্ন অনুযায়ী ব্রেকআউটের জন্য অপেক্ষা করা বুদ্ধিমানের কাজ হবে।"
            if "GBP" in pair_name: return "পাউন্ডের হাই ভোলাটিলিটি জোনে প্রোপার মানি ম্যানেজমেন্ট কঠোরভাবে মেনে চলুন।"
            if "JPY" in pair_name: return "জেপিওয়াই পেয়ারে ট্রেন্ড রিভার্সাল কনফার্মেশনের পর এন্ট্রি নেওয়া নিরাপদ।"
            return f"{pair_name} পেয়ারের বর্তমান টেকনিক্যাল লেভেলে ক্যান্ডেলস্টিক প্যাটার্ন ফলো করুন।"
    except:
        return f"{pair_name} পেয়ারে ট্রেড করার সময় প্রোপার রিস্ক ম্যানেজমেন্ট ফলো করুন।"

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

# ATR (Volatility Calculator) ফাংশন
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=period).mean() 

# 🎯 মেইন সিগন্যাল জেনারেটর (ইনডেক্সিং এবং রেট লিমিট হ্যান্ডেলার সহ)
def generate_signal(ticker_symbol, display_name):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range=7d&interval=5m"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: 
            print(f"Yahoo Fetch Error for {display_name}: Status {response.status_code}")
            return None
            
        json_data = response.json()
        result = json_data['chart']['result'][0]
        
        data = pd.DataFrame({
            'Open': result['indicators']['quote'][0]['open'],
            'High': result['indicators']['quote'][0]['high'],
            'Low': result['indicators']['quote'][0]['low'],
            'Close': result['indicators']['quote'][0]['close']
        }, index=pd.to_datetime(result['timestamp'], unit='s')).dropna()
        
        if len(data) < 50: return None 

        # ১. টেকনিক্যাল ইন্ডিকেটরসমূহ
        data['RSI'] = calculate_rsi(data['Close'], period=14)
        data['EMA_fast'] = calculate_ema(data['Close'], period=9)
        data['EMA_slow'] = calculate_ema(data['Close'], period=21)
        data['ATR'] = calculate_atr(data, period=14)
        
        # ২. 🛡️ ADX ক্যালকুলেশন (টাইমিং ইনডেক্স ফিক্সড)
        plus_dm = data['High'].diff()
        minus_dm = data['Low'].diff()
        
        plus_dm_series = pd.Series(np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0), index=data.index)
        minus_dm_series = pd.Series(np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0), index=data.index)
        
        tr = pd.concat([data['High'] - data['Low'], 
                        np.abs(data['High'] - data['Close'].shift()), 
                        np.abs(data['Low'] - data['Close'].shift())], axis=1).max(axis=1)
                        
        atr_adx = tr.rolling(window=14).mean()
        
        plus_di = 100 * (plus_dm_series.rolling(window=14).mean() / atr_adx)
        minus_di = 100 * (minus_dm_series.rolling(window=14).mean() / atr_adx)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        data['ADX'] = dx.rolling(window=14).mean()

        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        rsi_val = latest['RSI']
        ema_f = latest['EMA_fast']
        ema_s = latest['EMA_slow']
        price = latest['Close']
        atr_val = latest['ATR']
        adx_val = latest['ADX']
        
        if pd.isna(rsi_val) or pd.isna(atr_val) or pd.isna(adx_val): return None

        # 🚨 ADX ফিল্টার: ২৫ এর নিচে মার্কেট সাইডওয়েজ থাকলে কোনো সিগন্যাল জেনারেট হবে না
        if adx_val < 25: 
            return None 

        sl_dist = atr_val * 1.5   
        tp1_dist = atr_val * 1.5  
        tp2_dist = atr_val * 3.0  
        quotex_pips = atr_val * 0.4

        direction = None
        
        # 🟢 UP সিগন্যাল শর্ত
        if ema_f > ema_s and rsi_val > 53 and latest['High'] >= prev['High']:
            direction = "UP"
            strength = int(min(rsi_val + 20, 98))
            sl = price - sl_dist
            tp1 = price + tp1_dist
            tp2 = price + tp2_dist
            quotex_exit = price + quotex_pips
            
        # 🔴 DOWN সিগন্যাল শর্ত
        elif ema_f < ema_s and rsi_val < 47 and latest['Low'] <= prev['Low']:
            direction = "DOWN"
            strength = int(min((100 - rsi_val) + 20, 98))
            sl = price + sl_dist
            tp1 = price - tp1_dist
            tp2 = price - tp2_dist
            quotex_exit = price - quotex_pips
            
        if not direction: return None
            
        bengali_tip = get_ai_bengali_tip(display_name, direction, rsi_val, price)
        is_jpy = "JPY" in ticker_symbol
            
        return {
            "price": round(price, 4 if not is_jpy else 2), 
            "direction": direction, "strength": strength,
            "sl": round(sl, 4 if not is_jpy else 2),
            "tp1": round(tp1, 4 if not is_jpy else 2),
            "tp2": round(tp2, 4 if not is_jpy else 2),
            "quotex_exit": round(quotex_exit, 4 if not is_jpy else
