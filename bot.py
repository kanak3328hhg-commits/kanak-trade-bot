import requests
import time
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

BOT_TOKEN = "8264008675:AAEHzakAXPZeNVZKWlvYHRWboyjAuUhg0QM"
CHAT_ID = "@kanak_trade_bd"  # আপনার টেলিগ্রাম চ্যানেলের ইউজারনেম

def generate_signal(ticker_symbol):
    try:
        # ৫ মিনিটে টাইমফ্রেমের ডেটা ডাউনলোড
        data = yf.download(tickers=ticker_symbol, period="2d", interval="5m", progress=False)
        if data.empty: 
            return None
        
        # কলামের মাল্টি-ইনডেক্স বা ডাবল লেয়ার থাকলে তা সম্পূর্ণ দূর করে সাধারণ কলামে রূপান্তর করা
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]
            
        # কলামের নামগুলো পরিষ্কার করা (যেন কোনো স্পেস বা ঝামেলা না থাকে)
        data.columns = data.columns.str.strip()
        
        # 'Close' কলামটি নিশ্চিত করা
        if 'Close' not in data.columns:
            return None

        # ইন্ডিকেটর হিসাব করা (RSI এবং EMA)
        data['RSI'] = ta.rsi(data['Close'], length=14)
        data['EMA_fast'] = ta.ema(data['Close'], length=9)
        data['EMA_slow'] = ta.ema(data['Close'], length=21)
        
        latest_row = data.iloc[-1]
        
        # ভ্যালুগুলো সিঙ্গেল সংখ্যায় রূপান্তর
        rsi_value = float(latest_row['RSI'])
        ema_fast = float(latest_row['EMA_fast'])
        ema_slow = float(latest_row['EMA_slow'])
        current_price = float(latest_row['Close'])
        
        if pd.isna(rsi_value): rsi_value = 50.0

        # বাই বা সেল সিগন্যাল লজিক
        if ema_fast > ema_slow and rsi_value > 50:
            direction, strength = "UP", int(min(rsi_value + 25, 98))
        elif ema_fast < ema_slow and rsi_value < 50:
            direction, strength = "DOWN", int(min((100 - rsi_value) + 25, 98))
        else:
            direction, strength = "UP", 72 # সাইডওয়েজ মার্কেটের জন্য একটা ডিফল্ট ট্র্যাকিং
            
        return {"price": round(current_price, 4), "direction": direction, "strength": strength}
    except Exception as e:
        print(f"Error analyzing {ticker_symbol}: {e}")
        return None

# Yahoo Finance অনুযায়ী ৫টি পেয়ারের সঠিক নাম
pairs_to_track = {
    "NZDUSD=X": "NZD-USD",
    "EURUSD=X": "EUR-USD",
    "GBPUSD=X": "GBP-USD",
    "USDJPY=X": "USD-JPY",
    "AUDUSD=X": "AUD-USD"
}

print("Kanak Trade Bot is starting...")

while True:
    current_time = datetime.now().strftime("%I:%M %p")
    message_text = f"📊 **Signals Update - {current_time}**\n\n"
    has_signals = False
    
    print(f"\n[{current_time}] Checking market and analyzing indicators...")
    
    for ticker, display_name in pairs_to_track.items():
        signal = generate_signal(ticker)
        if signal:
            has_signals = True
            emoji = "🟢" if signal['direction'] == "UP" else "🔴"
            
            message_text += (
                f"🎯 **{display_name}** - {emoji} {signal['direction']}\n\n"
                f"⏰ Timeframe: 5M\n"
                f"📊 Strength: {signal['strength']}%\n"
                f"💰 Entry: {signal['price']}\n\n"
                f"#{display_name} #5M\n\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
            )
    
    if has_signals:
        if message_text.endswith("━━━━━━━━━━━━━━━━━━\n\n"):
            message_text = message_text[:-22]
            
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message_text, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            print(f"Update successfully sent to Telegram channel!")
        else:
            print(f"Failed to send to Telegram. Code: {response.status_code}, Reason: {response.text}")
    else:
        print("No active signals generated in this round.")
    
    print("Waiting for 5 minutes for next update...")
    time.sleep(300)