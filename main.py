import os
import time
import requests
from breeze_connect import BreezeConnect
from datetime import datetime
import pandas as pd

# Breeze credentials from environment
api_key = os.getenv("BREEZE_API_KEY")
api_secret = os.getenv("BREEZE_API_SECRET")
session_token = os.getenv("BREEZE_SESSION_TOKEN")

# Telegram credentials from environment
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

# Initialize Breeze API
breeze = BreezeConnect(api_key=api_key)
breeze.generate_session(api_secret=api_secret, session_token=session_token)

def send_telegram_alert(bot_message):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "parse_mode": "MarkdownV2",
        "text": bot_message.replace('!', '\\!')
    }
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        print("❌ Failed to send message:", response.text)
    else:
        print("✅ Telegram alert sent")

def mround(x, base=50):
    return int(base * round(float(x) / base))

def analyze_symbol(symbol):
    try:
        option_chain = breeze.get_option_chain_quotes(stock_code=symbol, exchange_code="NFO", product_type="options")

        df = pd.DataFrame(option_chain["Success"])
        df['strike_price'] = pd.to_numeric(df['strike_price'], errors='coerce')
        df['change_oi'] = pd.to_numeric(df['change_oi'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['open_interest'] = pd.to_numeric(df['open_interest'], errors='coerce')
        df = df.dropna()

        spot = float(option_chain['StockPrice'])

        # --- Call Logic ---
        ce = df[(df['option_type'] == 'CE') & (df['strike_price'] < spot)]
        ce_itm = ce[ce['change_oi'] < 0]
        ce_top = ce_itm.loc[ce_itm['open_interest'].idxmax()] if not ce_itm.empty else None

        # --- Put Logic ---
        pe = df[(df['option_type'] == 'PE') & (df['strike_price'] > spot)]
        pe_itm = pe[pe['change_oi'] < 0]
        pe_top = pe_itm.loc[pe_itm['open_interest'].idxmax()] if not pe_itm.empty else None

        message = f"*{symbol} Option Analysis*\nSpot: `{spot}`"

        if ce_top is not None:
            ce_bep = mround(ce_top['strike_price'] + ce_top['high'])
            if ce_bep > spot:
                message += f"\n🟥 *Bearish (CE)*: Sell `{int(ce_top['strike_price'])}` at `{ce_top['high']}`\nBEP: `{ce_bep}`"

        if pe_top is not None:
            pe_bep = mround(pe_top['strike_price'] - pe_top['high'])
            if pe_bep < spot:
                message += f"\n🟩 *Bullish (PE)*: Sell `{int(pe_top['strike_price'])}` at `{pe_top['high']}`\nBEP: `{pe_bep}`"

        send_telegram_alert(message)

    except Exception as e:
        print(f"Error processing {symbol}: {e}")

# Main Loop for NIFTY and BANKNIFTY
if __name__ == "__main__":
    while True:
        print(f"⏰ Running analysis at {datetime.now().strftime('%H:%M:%S')}")
        for sym in ['NIFTY', 'BANKNIFTY']:
            analyze_symbol(sym)
        print("Sleeping for 3 minutes...\n")
        time.sleep(180)
