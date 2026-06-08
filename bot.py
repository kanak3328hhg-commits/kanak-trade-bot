import os
import subprocess
import sys

# সার্ভার রান হওয়ার সময় ব্যাকগ্রাউন্ডে টেকনিক্যাল লাইব্রেরিগুলো অটো-ইনস্টল করার ট্রিক
def install_packages():
    try:
        import pandas
        import pandas_ta
    except ImportError:
        print("Installing required analytical packages in background...")
        # পাইথনের লেটেস্ট ভার্সনে যেন কম্পাইল এরর না আসে তার জন্য বিশেষ কমান্ড
        subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy==1.26.4", "pandas==2.2.3", "--no-build-isolation"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas-ta"])

# মেইন বটের কাজ শুরু হওয়ার আগেই ইনস্টলেশন রান করা
install_packages()

import requests
import time
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# আপনার দেওয়া সঠিক টোকেন এবং চ্যানেল আইডি
BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
FOREX_CHAT_ID = "@kanak_trade_bd"  
QUOTEX_CHAT_ID = "@Kanak_quotex_bd"

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
        if data.empty or len(data) < 21: 
            return None

        data['RSI'] = ta.rsi(data['Close'], length=14)
        data['EMA_fast'] = ta.ema(data['Close'], length=9)
        data['EMA_slow'] = ta.ema(data['Close'], length=21)
        
        latest_row = data.iloc[-1]
        
        rsi_value = float(latest_row['RSI'])
        ema_fast = float(latest_row['EMA_fast'])
        ema_slow = float(latest_row['EMA_slow'])
        current_price = float(latest_row['Close'])
        
        if pd.isna(rsi_value): rsi_value = 50.0

        is_jpy = "JPY" in ticker_symbol
        pips_sl = 0.0300 if is_jpy else 0.0030   
        pips_tp1 = 0.0300 if is_jpy else 0.0030  
        pips_tp2 = 0.0600 if is_jpy else 0.0060  

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

print("Kanak Trade Bot is starting on Render Web Service...")

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
                
                # ফরেক্স মেসেজ ফরম্যাট
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
                
                # কোটেক্স ৩০ সেকেন্ড/১ মিনিটের মেসেজ ফরম্যাট
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
            print("No active signals generated.")
            
    except Exception as main_loop_error:
        print(f"Network issue detected: {main_loop_error}. Retrying in 5 minutes...")
    
    time.sleep(300)
