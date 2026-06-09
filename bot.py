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
GEMINI_API_KEY = "AIzaSyB6_x6_7-TuK-yYHEas7yhBshe4mG7ibNI"


class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Kanak AI Bot: Running Dedicatedly for Forex Channel Only!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_fake_server():
    import os
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

def get_current_forex_sessions():
    now_utc = datetime.utcnow()
    now_bst = now_utc + timedelta(hours=6)
    current_hour = now_bst.hour
    sessions = []
    if 4 <= current_hour < 13: sessions.append("Sydney 🇦🇺")
    if 6 <= current_hour < 15: sessions.append("Tokyo 🇯🇵")
    if 13 <= current_hour < 22: sessions.append("London 🇬🇧")
    if current_hour >= 18 or current_hour < 3: sessions.append("New York 🇺🇸")
    return ", ".join(sessions) if sessions else "Live Market"

def get_ai_bengali_tip(pair_name, direction, rsi, price):
    for attempt in range(3):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            prompt = (
                f"You are a passionate, elite human day-trader speaking to your community on Telegram. "
                f"Write a 1-sentence quick chart observation or action advice in Bengali for {pair_name}. "
                f"Current price is {price}, trend is {direction}, and RSI is {rsi:.1f}. "
                f"Act like you just opened the chart and noticed this. Do not sound like a machine or robot. "
                f"Write fully in Bengali using Bengali script. Keep it short and high-impact. No intros."
            )
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            response = requests.post(url, json=payload, headers=headers, timeout=12)
            if response.status_code == 200:
                tip_text = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                clean_tip = tip_text.replace('"', '').replace('*', '').replace('<', '').replace('>', '')
                if clean_tip: return clean_tip
        except:
            time.sleep(1)
    action = "বাই (Buy)" if direction == "UP" else "সেল (Sell)"
    return f"চার্ট অনুযায়ী {pair_name}-এ এখন ক্লিয়ার {action} প্রেশার দেখা যাচ্ছে, প্রফিট বুক করার ভালো সুযোগ এটি।"

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    for i in range(period, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(window=period).mean()

def generate_signal(ticker_symbol, display_name):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range=5d&interval=5m"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return "NO_SIGNAL"
            
        result = response.json()['chart']['result'][0]
        data = pd.DataFrame({
            'Open': result['indicators']['quote'][0]['open'],
            'High': result['indicators']['quote'][0]['high'],
            'Low': result['indicators']['quote'][0]['low'],
            'Close': result['indicators']['quote'][0]['close']
        }, index=pd.to_datetime(result['timestamp'], unit='s')).dropna()
        
        if len(data) < 50: return "NO_SIGNAL"

        data['RSI'] = calculate_rsi(data['Close'])
        data['EMA_fast'] = calculate_ema(data['Close'], 9)
        data['EMA_slow'] = calculate_ema(data['Close'], 21)
        data['ATR'] = calculate_atr(data)
        
        # ADX ক্যালকুলেশন
        plus_dm = data['High'].diff()
        minus_dm = data['Low'].diff()
        plus_dm_series = pd.Series(np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0), index=data.index)
        minus_dm_series = pd.Series(np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0), index=data.index)
        tr = pd.concat([data['High'] - data['Low'], np.abs(data['High'] - data['Close'].shift()), np.abs(data['Low'] - data['Close'].shift())], axis=1).max(axis=1)
        atr_adx = tr.rolling(window=14).mean()
        plus_di = 100 * (plus_dm_series.rolling(window=14).mean() / atr_adx)
        minus_di = 100 * (minus_dm_series.rolling(window=14).mean() / atr_adx)
        data['ADX'] = (100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)).rolling(window=14).mean()

        latest, prev = data.iloc[-1], data.iloc[-2]
        rsi_val, ema_f, ema_s, price, atr_val, adx_val = latest['RSI'], latest['EMA_fast'], latest['EMA_slow'], latest['Close'], latest['ATR'], latest['ADX']
        
        if pd.isna(rsi_val) or pd.isna(atr_val) or pd.isna(adx_val): return "NO_SIGNAL"

        if adx_val < 20: return "NO_SIGNAL" 

        direction = None
        if ema_f > ema_s and rsi_val > 50: direction = "UP"
        elif ema_f < ema_s and rsi_val < 50: direction = "DOWN"
            
        if not direction: return "NO_SIGNAL"
            
        is_jpy = "JPY" in ticker_symbol
        dec_places = 4 if not is_jpy else 2
        
        risk_dist = atr_val * 1.5
        sl = price - risk_dist if direction == "UP" else price + risk_dist
        strength = int(min(rsi_val + 20, 98)) if direction == "UP" else int(min((100 - rsi_val) + 20, 98))
        
        # 🎯 ১:২ থেকে শুরু হওয়া হিউম্যানাইজড ডাইনামিক টিপি
        tp_list = []
        tp1_val = price + (risk_dist * 2) if direction == "UP" else price - (risk_dist * 2)
        tp_list.append(f"🎯 <b>Target 1 (1:2 ratio):</b> {round(tp1_val, dec_places)}")
        
        if 20 <= adx_val < 30:
            tp2_val = price + (risk_dist * 3) if direction == "UP" else price - (risk_dist * 3)
            tp_list.append(f"🎯 <b>Target 2 (1:3 ratio):</b> {round(tp2_val, dec_places)}")
        elif 30 <= adx_val < 40:
            tp2_val = price + (risk_dist * 3) if direction == "UP" else price - (risk_dist * 3)
            tp3_val = price + (risk_dist * 4) if direction == "UP" else price - (risk_dist * 4)
            tp_list.append(f"🎯 <b>Target 2 (1:3 ratio):</b> {round(tp2_val, dec_places)}")
            tp_list.append(f"🎯 <b>Target 3 (1:4 ratio):</b> {round(tp3_val, dec_places)}")
        else:
            tp2_val = price + (risk_dist * 3) if direction == "UP" else price - (risk_dist * 3)
            tp3_val = price + (risk_dist * 4) if direction == "UP" else price - (risk_dist * 4)
            tp4_val = price + (risk_dist * 5) if direction == "UP" else price - (risk_dist * 5)
            tp_list.append(f"🎯 <b>Target 2 (1:3 ratio):</b> {round(tp2_val, dec_places)}")
            tp_list.append(f"🎯 <b>Target 3 (1:4 ratio):</b> {round(tp3_val, dec_places)}")
            tp_list.append(f"🎯 <b>Target 4 (1:5 Extended):</b> {round(tp4_val, dec_places)}")
            
        tp_text_block = "\n".join(tp_list)
        ai_tip = get_ai_bengali_tip(display_name, direction, rsi_val, price)
        
        return {
            "price": round(price, dec_places), "direction": direction, "strength": strength,
            "sl": round(sl, dec_places), "tp_block": tp_text_block, "tip": ai_tip
        }
    except:
        return "NO_SIGNAL"

pairs_to_track = {
    "EURUSD=X": "EUR-USD", "GBPUSD=X": "GBP-USD", "USDJPY=X": "USD-JPY", "USDCHF=X": "USD-CHF",
    "AUDUSD=X": "AUD-USD", "USDCAD=X": "USD-CAD", "NZDUSD=X": "NZD-USD", "EURGBP=X": "EUR-GBP",
    "EURJPY=X": "EUR-JPY", "EURCHF=X": "EUR-CHF", "EURCAD=X": "EUR-CAD", "EURAUD=X": "EUR-AUD",
    "GBPJPY=X": "GBP-JPY", "GBPCHF=X": "GBP-CHF", "GBPCAD=X": "GBP-CAD", "GBPAUD=X": "GBP-AUD",
    "AUDJPY=X": "AUD-JPY", "AUDCAD=X": "AUD-CAD", "XAUUSD=X": "XAU-USD"
}

threading.Thread(target=run_fake_server, daemon=True).start()
print("Kanak AI Bot: Running Dedicated Forex Mode (3-Min Cycles)...")

# ⏱️ মেইন রিয়েল-টাইম ৫ মিনিটের কন্টিনিউয়াস ফরেক্স লুপ (আগের পারফেক্ট টাইমিং)
while True:
    try:
        current_session = get_current_forex_sessions()
        now_bst = datetime.utcnow() + timedelta(hours=6)
        current_time = now_bst.strftime("%I:%M %p")
        
        print(f"\n🔄 SCANNING STARTED AT {current_time} (Dedicated 5M Interval)")
        
        no_signal_pairs = [] 
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        for ticker, display_name in pairs_to_track.items():
            time.sleep(1.2) # এপিআই সেফটি ডিলে
            result = generate_signal(ticker, display_name)
            
            if isinstance(result, dict): 
                action_text = "🟢 BUY SETUP" if result['direction'] == "UP" else "🔴 SELL SETUP"
                
                # 📊 নিখুঁত হিউম্যান-স্টাইল ফরেক্স মেসেজ
                forex_message = (
                    f"⚡ <b>Live Chart Analysis | {current_time}</b>\n\n"
                    f"🔥 <b>{display_name}</b> → <b>{action_text}</b>\n"
                    f"───────────────────\n"
                    f"📈 <b>Market View:</b> 5-Min Chart Scan\n"
                    f"💪 <b>Conviction:</b> {result['strength']}% Trade Strength\n\n"
                    f"💵 <b>Entry Price:</b> {result['price']}\n"
                    f"🛡️ <b>Invalidation (SL):</b> {result['sl']}\n"
                    f"{result['tp_block']}\n\n"
                    f"📝 <b>My Personal Note:</b> {result['tip']}\n\n"
                    f"<i>⚠️ প্রপার মানি ম্যানেজমেন্ট মেনে এন্ট্রি নিবেন। হ্যাপি ট্রেডিং!</i>\n\n"
                    f"#{display_name.replace('-', '_')} #LiveTrade"
                )
                
                requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": forex_message, "parse_mode": "HTML"}, timeout=10)
                print(f"   🔥 Signal sent to Forex Channel for {display_name}")
            else:
                no_signal_pairs.append(display_name)

        # 📊 ৫ মিনিটের হিউম্যানাইজড মার্কেট সামারি আপডেট
        report_message = (
            f"🔄 <b>Quick Market Snapshot | {current_time}</b>\n"
            f"🌐 <b>Active Session:</b> {current_session}\n"
            f"───────────────────\n"
            f"👁️‍🗨️ <b>অপেক্ষা করছি (No Setup Yet):</b>\n"
        )
        if no_signal_pairs:
            report_message += f"<code>{', '.join(no_signal_pairs)}</code>\n\n"
            report_message += f"<i>বাকি এই পেয়ারগুলোতে আমাদের কন্ডিশন এখনও ফুলফিল হয় নাই। জোর করে এন্ট্রি নেওয়ার দরকার নেই, আমরা পারফেক্ট মুভমেন্টের জন্য ওয়েট করছি।</i>\n"
        else:
            report_message += "<i>সবগুলো পেয়ারেই অলরেডি লাইভ মুভমেন্ট বা সিগন্যাল রানিং আছে!</i>\n"
            
        report_message += "\n⏱️ <i>পরবর্তী ৫ মিনিট পর আমি আবার চার্ট চেক করে নতুন আপডেট দিচ্ছি...</i>"
        
        requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": report_message, "parse_mode": "HTML"}, timeout=10)
        print("✅ 5-Minute Forex Summary Pushed Successfully!")
                
    except Exception as e:
        print(f"Loop error: {e}")
        
    # ⏱️ ঠিক ৫ মিনিট (৩০০ সেকেন্ড) পর পর মেইন লুপটি পুনরায় রান হবে
    time.sleep(300)
