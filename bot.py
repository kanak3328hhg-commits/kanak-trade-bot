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


# Render Port Binding-এর জন্য ফেক সার্ভার
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Kanak AI Bot is scanning charts successfully on 5-Minute Intervals!")
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
    if 4 <= current_hour < 13: sessions.append("Sydney")
    if 6 <= current_hour < 15: sessions.append("Tokyo")
    if 13 <= current_hour < 22: sessions.append("London")
    if current_hour >= 18 or current_hour < 3: sessions.append("New York")
    return ", ".join(sessions) if sessions else "Live Market"

def get_ai_bengali_tip(pair_name, direction, rsi, price):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        prompt = (
            f"Write a short technical commentary in Bengali about {pair_name}. "
            f"Trend is {direction}, RSI is {rsi:.1f}. Explain what this means for a scalper in 1 short sentence."
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            tip_text = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return tip_text.replace('"', '').replace('*', '').replace('<', '').replace('>', '')
    except:
        pass
    return f"{pair_name} পেয়ারের বর্তমান টেকনিক্যাল লেভেলে ক্যান্ডেলস্টিক প্যাটার্ন ফলো করুন।"

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

# 🎯 স্ট্র্যাটেজি ও ক্যান্ডেল ডাটা অ্যানালাইসিস ফাংশন
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

        # ট্রেন্ড স্ট্রেংথ ফিল্টার
        if adx_val < 25: return "NO_SIGNAL" 

        direction = None
        # 🟢 UP সিগন্যাল শর্ত
        if ema_f > ema_s and rsi_val > 53 and latest['High'] >= prev['High']:
            direction = "UP"
            sl, tp1, tp2 = price - (atr_val * 1.5), price + (atr_val * 1.5), price + (atr_val * 3.0)
            quotex_exit = price + (atr_val * 0.4)
            strength = int(min(rsi_val + 20, 98))
        # 🔴 DOWN সিগন্যাল শর্ত
        elif ema_f < ema_s and rsi_val < 47 and latest['Low'] <= prev['Low']:
            direction = "DOWN"
            sl, tp1, tp2 = price + (atr_val * 1.5), price - (atr_val * 1.5), price - (atr_val * 3.0)
            quotex_exit = price - (atr_val * 0.4)
            strength = int(min((100 - rsi_val) + 20, 98))
            
        if not direction: return "NO_SIGNAL"
            
        is_jpy = "JPY" in ticker_symbol
        return {
            "price": round(price, 4 if not is_jpy else 2), "direction": direction, "strength": strength,
            "sl": round(sl, 4 if not is_jpy else 2), "tp1": round(tp1, 4 if not is_jpy else 2),
            "tp2": round(tp2, 4 if not is_jpy else 2), "quotex_exit": round(quotex_exit, 4 if not is_jpy else 2),
            "tip": get_ai_bengali_tip(display_name, direction, rsi_val, price)
        }
    except:
        return "NO_SIGNAL"

# আপনার ট্র্যাকিং পেয়ার লিস্ট (মোট ২০টি গুরুত্বপূর্ণ পেয়ার স্ক্র্যাপ করার স্পিড বাড়ানোর জন্য অপ্টিমাইজড)
pairs_to_track = {
    "EURUSD=X": "EUR-USD", "GBPUSD=X": "GBP-USD", "USDJPY=X": "USD-JPY", "USDCHF=X": "USD-CHF",
    "AUDUSD=X": "AUD-USD", "USDCAD=X": "USD-CAD", "NZDUSD=X": "NZD-USD", "EURGBP=X": "EUR-GBP",
    "EURJPY=X": "EUR-JPY", "EURCHF=X": "EUR-CHF", "EURCAD=X": "EUR-CAD", "EURAUD=X": "EUR-AUD",
    "GBPJPY=X": "GBP-JPY", "GBPCHF=X": "GBP-CHF", "GBPCAD=X": "GBP-CAD", "GBPAUD=X": "GBP-AUD",
    "AUDJPY=X": "AUD-JPY", "AUDCAD=X": "AUD-CAD", "XAUUSD=X": "XAU-USD"
}

# ফেক ওয়েব সার্ভার ব্যাকগ্রাউন্ডে চালু করা
threading.Thread(target=run_fake_server, daemon=True).start()
print("Kanak AI Bot initialized for Mandatory 5-Minute Cycles...")

# ⏱️ মেইন রিয়েল-টাইম ৫ মিনিটের ক্লোজিং লুপ
while True:
    try:
        current_session = get_current_forex_sessions()
        now_bst = datetime.utcnow() + timedelta(hours=6)
        current_time = now_bst.strftime("%I:%M %p")
        
        print(f"\n🔄 5-MIN CYCLE SCANNING STARTED AT {current_time}")
        
        no_signal_pairs = [] 
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        for ticker, display_name in pairs_to_track.items():
            time.sleep(1.2) # আইপি ব্লকিং এড়াতে সেফটি ডিলয়
            result = generate_signal(ticker, display_name)
            
            if isinstance(result, dict): # সিগন্যাল পাওয়া গেলে সাথে সাথে পুশ
                emoji = "🟢" if result['direction'] == "UP" else "🔴"
                
                # ফরেক্স মেসেজ ফরম্যাট
                forex_message = (
                    f"📊 <b>Forex Signal Update - {current_time}</b>\n\n"
                    f"🎯 <b>{display_name}</b> - {emoji} {result['direction']}\n\n"
                    f"⏰ Timeframe: 5M\n📊 Strength: {result['strength']}%\n💰 Entry Price: {result['price']}\n"
                    f"🛑 Stop Loss (SL): {result['sl']}\n✅ Take Profit 1 (TP1): {result['tp1']}\n✅ Take Profit 2 (TP2): {result['tp2']}\n\n"
                    f"💡 <b>AI টিপস:</b> {result['tip']}\n\n#{display_name.replace('-', '_')} #Forex\n🌐 <b>Active Session:</b> <code>{current_session}</code>"
                )
                
                # কোটেক্স মেসেজ ফরম্যাট
                quotex_message = (
                    f"📱 <b>Quotex Fast Binary Signals - {current_time}</b>\n\n"
                    f"📊 <b>Quotex | {display_name}</b>\n\n"
                    f"🎯 Signal Direction: {emoji} <b>{result['direction']}</b>\n"
                    f"💰 Entry Price: <b>{result['price']}</b>\n"
                    f"🏁 Exit Target Price: <b>{result['quotex_exit']}</b>\n"
                    f"⏰ Best Expiry: <b>1 MINUTE</b>\n"
                    f"📈 Signal Accuracy: {result['strength']}%\n"
                    f"🚀 Trade Type: Turbo Scalping\n\n"
                    f"💡 <b>AI টিপস:</b> {result['tip']}\n\n#{display_name.replace('-', '_')} #Quotex1M\n🌐 <b>Active Session:</b> <code>{current_session}</code>"
                )
                
                requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": forex_message, "parse_mode": "HTML"}, timeout=10)
                requests.post(url, json={"chat_id": QUOTEX_CHAT_ID, "text": quotex_message, "parse_mode": "HTML"}, timeout=10)
                print(f"   🔥 Signal sent for {display_name}")
            else:
                # সিগন্যাল না পাওয়া পেয়ারগুলো লিস্টে জমা হবে
                no_signal_pairs.append(display_name)

        # 📊 ৫ মিনিট শেষ হওয়ার বাধ্যতামূলক মার্কেট আপডেট রিপোর্ট (যা আপনি চেইন টাইমে চেয়েছেন)
        report_message = f"🔄 <b>Market Scan Update - {current_time}</b>\n"
        report_message += f"🌐 Active Session: <code>{current_session}</code>\n\n"
        report_message += f"⚠️ <b>নিচের পেয়ারগুলোতে সিগনাল এখনও তৈরি হয় নাই বা পাওয়া যাচ্ছে না:</b>\n"
        
        if no_signal_pairs:
            report_message += f"<code>{', '.join(no_signal_pairs)}</code>\n\n"
        else:
            report_message += "<i>সবগুলো পেয়ারেই সিগন্যাল চলমান!</i>\n\n"
            
        report_message += "🤖 <i>বট পরবর্তী ক্যান্ডেল ক্লোজিং ও ৫ মিনিট পর রি-স্ক্যানের জন্য প্রস্তুত হচ্ছে...</i>"
        
        # রিপোর্ট মেসেজটি চ্যানেলে পাঠানো হচ্ছে (যাতে প্রতি ৫ মিনিট পর পর চ্যানেলে মেসেজ আসেই)
        requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": report_message, "parse_mode": "HTML"}, timeout=10)
        requests.post(url, json={"chat_id": QUOTEX_CHAT_ID, "text": report_message, "parse_mode": "HTML"}, timeout=10)
        print("✅ 5-Minute Mandatory Market Report Pushed successfully!")
                
    except Exception as e:
        print(f"Loop error: {e}")
        
    # ঠিক ৫ মিনিট (৩০০ সেকেন্ড) পর পর লুপটি পুনরায় রান হবে
    time.sleep(300)
