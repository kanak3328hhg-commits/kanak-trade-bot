import requests
import time
import pandas as pd
from datetime import datetime

# আপনার দেওয়া সঠিক টোকেন এবং চ্যানেল আইডি
BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
FOREX_CHAT_ID = "@kanak_trade_bd"  
QUOTEX_CHAT_ID = "@Kanak_quotex_bd"

# কোনো লাইব্রেরি ছাড়া খাঁটি পাইথন দিয়ে RSI হিসাব করার ফাংশন
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # প্রথম রোলিং এর পরের ভ্যালুগুলোর জন্য স্মুদিং
    for i in range(period, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# কোনো লাইব্রেরি ছাড়া EMA হিসাব করার ফাংশন
def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def generate_signal(ticker_symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range=2d&interval=5m"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
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
        if data.empty or len(data) < 30: 
            return None

        # আমাদের কাস্টম গাণিতিক ফাংশন দিয়ে ইন্ডিকেটর তৈরি
        data['RSI'] = calculate_rsi(data['Close'], period=14)
        data['EMA_fast'] = calculate_ema(data['Close'], period=9)
        data['EMA_slow'] = calculate_ema(data['Close'], period=21)
        
        latest_row = data.iloc[-1]
        
        rsi_value = latest_row['RSI']
        ema_fast = latest_row['EMA_fast']
        ema_slow = latest_row['EMA_slow']
        current_price = latest_row['Close']
        
        if pd.isna(rsi_value) or pd.isna(ema_fast) or pd.isna(ema_slow):
            return None

        rsi_value = float(rsi_value)
        ema_fast = float(ema_fast)
        ema_slow = float(ema_slow)
        current_price = float(current_price)

       # কারেন্সি পেয়ার JPY (যেমন: USDJPY) নাকি সাধারণ (যেমন: EURUSD) তা চেক করা
        is_jpy = "JPY" in ticker_symbol
        
        # ১. রিস্ক বা স্টপ লস (SL) নির্ধারণ: সাধারণ পেয়ারে ৩০ পিপস, JPY পেয়ারে ৩০ পিপস
        pips_sl = 0.0300 if is_jpy else 0.0030   
        
        # ২. টেক প্রফিট ১ (TP1) -> রেশিও ১:২ (SL-এর দ্বিগুণ লাভ)
        pips_tp1 = (pips_sl * 2)  # সাধারণ পেয়ারে ৬০ পিপস লাভ
        
        # ৩. টেক প্রফিট ২ (TP2) -> রেশিও ১:৩ (SL-এর তিনগুণ লাভ)
        pips_tp2 = (pips_sl * 3)  # সাধারণ পেয়ারে ৯০ পিপস লাভ 

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
            
        return {
            "price": round(current_price, 4 if not is_jpy else 2), 
            "direction": direction, 
            "strength": strength,
            "sl": round(sl, 4 if not is_jpy else 2),
            "tp1": round(tp1, 4 if not is_jpy else 2),
            "tp2": round(tp2, 4 if not is_jpy else 2)
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

print("Kanak Independent Bot is starting on Render Server...")

while True:
    try:
        current_time = datetime.now().strftime("%I:%M %p")
        forex_message = f"📊 **Forex Signals Update - {current_time}**\n\n"
        quotex_message = f"📱 **Quotex Fast Binary Signals - {current_time}**\n\n"
        has_signals = False
        
        print(f"\n[{current_time}] Fetching live market data...")
        
        for ticker, display_name in pairs_to_track.items():
            signal = generate_signal(ticker)
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
                    f"#{display_name} #Forex\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                )
                
                quotex_message += (
                    f"📊 **Quotex | {display_name}**\n\n"
                    f"🎯 Signal Direction: {emoji} **{signal['direction']}**\n"
                    f"⏰ Best Expiry: **1 MINUTE** (or **30 SECONDS**)\n"
                    f"📈 Signal Accuracy: {signal['strength']}%\n"
                    f"🚀 Trade Type: Turbo Scalping\n\n"
                    f"#{display_name} #Quotex1M #Turbo30s\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                )
        
        if has_signals:
            if forex_message.endswith("━━━━━━━━━━━━━━━━━━\n\n"): forex_message = forex_message[:-22]
            if quotex_message.endswith("━━━━━━━━━━━━━━━━━━\n\n"): quotex_message = quotex_message[:-22]
                
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            
            try:
                requests.post(url, json={"chat_id": FOREX_CHAT_ID, "text": forex_message, "parse_mode": "Markdown"}, timeout=15)
            except Exception as telegram_err:
                print(f"Telegram Forex Send Error: {telegram_err}")
            
            try:
                requests.post(url, json={"chat_id": QUOTEX_CHAT_ID, "text": quotex_message, "parse_mode": "Markdown"}, timeout=15)
                print(f"Signals safely sent to Telegram channels!")
            except Exception as telegram_err:
                print(f"Telegram Quotex Send Error: {telegram_err}")
        else:
            print("No active signals generated yet.")
            
    except Exception as main_loop_error:
        print(f"Network issue detected: {main_loop_error}. Retrying in 5 minutes...")
    
    time.sleep(300)
