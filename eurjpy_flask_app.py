import os
import json
import logging
import threading
import asyncio
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify
import yfinance as yf
import pandas as pd
import requests

# ================= CONFIG =================
CONFIG_FILE = "config.json"
PAIR = "EURJPY=X"
INTERVAL = "1m"
TZ_OFFSET = timezone(timedelta(hours=7))  # WIB (UTC+7)
LOG_FILE = "/tmp/eurjpy_flask.log"

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ================= TELEGRAM =================
def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Gagal memuat config.json: {e}")
        return None


def send_telegram_message(token, chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(url, data=payload, timeout=10)
        logging.info("Pesan Telegram terkirim.")
    except Exception as e:
        logging.error(f"Gagal kirim pesan Telegram: {e}")


def send_status(token, chat_id, status):
    now_local = datetime.now(timezone.utc).astimezone(TZ_OFFSET)
    msg = f"*Bot Status:* {status}\nTime (WIB): {now_local.strftime('%Y-%m-%d %H:%M:%S')}"
    send_telegram_message(token, chat_id, msg)


# ================= DATA MARKET =================
def get_price_data():
    try:
        df = yf.download(PAIR, period="1d", interval=INTERVAL, progress=False, auto_adjust=True)
        return df if df is not None and len(df) > 20 else None
    except Exception as e:
        logging.error(f"Gagal ambil data harga: {e}")
        return None


# ================= ANALISA =================
def analyze_signal(df):
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema_fast = close.ewm(span=9, adjust=False).mean()
    ema_slow = close.ewm(span=21, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9).mean()
    macd_hist = macd - macd_signal

    std = close.rolling(window=20).std()
    mid = close.rolling(window=20).mean()
    upper = mid + 2 * std
    lower = mid - 2 * std

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    last_close = float(close.iloc[-1])
    last_ema_fast = float(ema_fast.iloc[-1])
    last_ema_slow = float(ema_slow.iloc[-1])
    last_macd_hist = float(macd_hist.iloc[-1])
    last_upper = float(upper.iloc[-1])
    last_lower = float(lower.iloc[-1])
    last_atr = float(atr.iloc[-1])
    avg_rsi = float(rsi.tail(5).mean(skipna=True))

    score = 0
    score += 2 if last_ema_fast > last_ema_slow else -2
    score += 1 if last_macd_hist > 0 else -1
    score += 1.5 if avg_rsi < 35 else -1.5 if avg_rsi > 65 else 0
    score += 0.5 if last_close > last_upper else -0.5 if last_close < last_lower else 0
    score += 0.3 if last_atr > 0.0005 * last_close else 0

    signal = "BUY" if score > 0 else "SELL"
    confidence = min(99, round(abs(score) * 15, 1))
    return signal, last_close, confidence


# ================= LOOP ANALISA =================
async def bot_loop(token, chat_id, stop_flag):
    send_status(token, chat_id, "Started (WebApp Reloaded ✅)")
    logging.info("Loop analisa dimulai (Flask WebApp)")

    last_signal_time = None
    while not stop_flag.is_set():
        try:
            df = get_price_data()
            if df is None:
                await asyncio.sleep(10)
                continue

            signal, price, conf = analyze_signal(df)
            now_utc = datetime.now(timezone.utc)
            now_local = now_utc.astimezone(TZ_OFFSET)
            price_str = f"{price:.3f}"

            if last_signal_time is None:
                msg = (
                    f"📊 *AI EUR/JPY (Prediksi Candle 5m)*\n"
                    f"📈 Arah: {signal}\n"
                    f"💰 Harga: {price_str}\n"
                    f"🤖 Akurasi: {conf}%\n"
                    f"🕒 WIB: {now_local.strftime('%H:%M:%S')} (Sinyal awal)"
                )
                send_telegram_message(token, chat_id, msg)
                last_signal_time = now_utc

            next_min = (now_utc.minute // 5 + 1) * 5
            if next_min >= 60:
                next_time = now_utc.replace(minute=0, second=0) + timedelta(hours=1)
            else:
                next_time = now_utc.replace(minute=next_min, second=0)
            target_time = next_time - timedelta(seconds=10)

            if now_utc >= target_time and now_utc - last_signal_time > timedelta(minutes=4):
                msg = (
                    f"📊 *AI EUR/JPY (Prediksi Candle 5m)*\n"
                    f"📈 Arah: {signal}\n"
                    f"💰 Harga: {price_str}\n"
                    f"🤖 Akurasi: {conf}%\n"
                    f"🕒 WIB: {now_local.strftime('%H:%M:%S')}"
                )
                send_telegram_message(token, chat_id, msg)
                last_signal_time = now_utc
                logging.info(f"Sinyal {signal} dikirim {now_local.strftime('%H:%M:%S')} WIB")

            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error: {e}")
            send_status(token, chat_id, f"Error: {e}. Restart 15s...")
            await asyncio.sleep(15)

    send_status(token, chat_id, "Stopped (WebApp)")
    logging.info("Loop bot dihentikan.")


# ================= FLASK APP =================
app = Flask(__name__)
loop_thread = None
stop_flag = None


def start_background():
    global loop_thread, stop_flag
    if loop_thread and loop_thread.is_alive():
        return
    cfg = load_config()
    if not cfg:
        logging.error("config.json tidak valid.")
        return
    token = cfg["token"]
    chat_id = int(cfg["chat_id"])
    stop_flag = asyncio.Event()

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_loop(token, chat_id, stop_flag))

    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    logging.info("Background bot dimulai.")


@app.route("/health")
def health():
    start_background()
    now = datetime.now(timezone.utc).astimezone(TZ_OFFSET)
    return jsonify({
        "status": "ok",
        "time_wib": now.strftime("%Y-%m-%d %H:%M:%S"),
        "message": "EURJPY Bot aktif ✅"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Back4App akan set PORT otomatis
    app.run(host="0.0.0.0", port=port)

