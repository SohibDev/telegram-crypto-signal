import asyncio
import logging
import sys
import ccxt
import matplotlib.pyplot as plt
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from datetime import datetime

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_TOKEN = "8193453612:AAExyyXMOeHWjx_BeAVsc1WtHYku-wptq2I"
COINS = ["BTC/USDT", "BNB/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "MATIC/USDT", "DOT/USDT"]
TIMEFRAME = '15m'
RISK_REWARD_RATIO = 1.5
USER_ID = 5498281083  # o'zingizning Telegram ID

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

active_signals = {}

def fetch_ohlcv(symbol, timeframe, limit=50):
    exchange = ccxt.binance()
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return ohlcv
    except Exception as e:
        print(f"Error fetching OHLCV for {symbol}: {e}")
        return None

def get_support_resistance(ohlcv):
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    return min(lows), max(highs)

def is_breakout(ohlcv):
    if len(ohlcv) < 2:
        return None, None, None, None
    last = ohlcv[-1]
    close = last[4]
    volume = last[5]
    support, resistance = get_support_resistance(ohlcv[:-1])
    avg_vol = sum(c[5] for c in ohlcv[:-1]) / (len(ohlcv) - 1)
    if close > resistance and volume > avg_vol:
        entry = close
        sl = support
        tp = entry + (entry - sl) * RISK_REWARD_RATIO
        return "BUY", entry, sl, tp
    elif close < support and volume > avg_vol:
        entry = close
        sl = resistance
        tp = entry - (sl - entry) * RISK_REWARD_RATIO
        return "SELL", entry, sl, tp
    return None, None, None, None

def draw_chart(ohlcv, coin):
    timestamps = [datetime.fromtimestamp(c[0] / 1000) for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    plt.figure(figsize=(10, 4))
    plt.plot(timestamps, closes, label="Close Price")
    plt.title(f"{coin} - {TIMEFRAME} Chart")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.grid(True)
    plt.tight_layout()
    plt.legend()
    plt.savefig("chart.png")
    plt.close()

async def check_signals():
    while True:
        any_signal = False

        for coin in COINS:
            ohlcv = fetch_ohlcv(coin, TIMEFRAME)
            if not ohlcv:
                continue

            if coin not in active_signals:
                signal, entry, sl, tp = is_breakout(ohlcv)
                if signal:
                    any_signal = True
                    active_signals[coin] = {
                        "signal": signal,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp
                    }
                    draw_chart(ohlcv, coin)
                    text = (
                        f"📢 {signal} Signal!\n"
                        f"Coin: {coin}\n"
                        f"Entry: {entry:.4f}\n"
                        f"SL: {sl:.4f}\n"
                        f"TP: {tp:.4f}\n"
                        f"Timeframe: {TIMEFRAME}\n"
                        f"Strategy: Breakout + Volume + RR 1:1.5"
                    )
                    await bot.send_message(USER_ID, text)
                    await bot.send_photo(USER_ID, photo=types.FSInputFile("chart.png"))
            else:
                # TP yoki SL tekshirish
                price = ohlcv[-1][4]
                sig = active_signals[coin]
                if sig["signal"] == "BUY":
                    if price >= sig["tp"]:
                        await bot.send_message(USER_ID, f"✅ {coin} BUY signal TP yetdi! Narx: {price:.4f}")
                        del active_signals[coin]
                    elif price <= sig["sl"]:
                        await bot.send_message(USER_ID, f"❌ {coin} BUY signal SL urildi! Narx: {price:.4f}")
                        del active_signals[coin]
                elif sig["signal"] == "SELL":
                    if price <= sig["tp"]:
                        await bot.send_message(USER_ID, f"✅ {coin} SELL signal TP yetdi! Narx: {price:.4f}")
                        del active_signals[coin]
                    elif price >= sig["sl"]:
                        await bot.send_message(USER_ID, f"❌ {coin} SELL signal SL urildi! Narx: {price:.4f}")
                        del active_signals[coin]

        if not any_signal and not active_signals:
            await bot.send_message(USER_ID, "📉 Hozircha signal yo'q. 1 daqiqadan keyin yana tekshiramiz.")
        await asyncio.sleep(60)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Salom! Signal monitoring ishga tushdi!")

async def main():
    dp.message.register(cmd_start, Command("start"))
    asyncio.create_task(check_signals())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
