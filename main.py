import os, json, time
from atr_utils import calculate_atr
from datetime import datetime
import pandas as pd
try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None
import requests

BASE_DIR = os.path.dirname(__file__)
with open(os.path.join(BASE_DIR, "config.json"), "r") as f:
    cfg = json.load(f)

SYMBOLS = cfg.get("symbols", ["EURUSD", "GBPUSD", "USDCAD", "AUDUSD"])
TIMEFRAMES = cfg.get("timeframe", ["TIMEFRAME_M15"])
if isinstance(TIMEFRAMES, str):
    TIMEFRAMES = [TIMEFRAMES]
LOT_SIZE = float(cfg.get("lot_size", 0.1))
MAGIC_NUMBER = int(cfg.get("magic_number", 123456))
TELEGRAM = cfg.get("telegram", {})
TELEGRAM_TOKEN = TELEGRAM.get("token", "")
TELEGRAM_CHAT_ID = TELEGRAM.get("chat_id", "")
CHECK_INTERVAL = int(cfg.get("check_interval", 30))
FVG_LOOKBACK = int(cfg.get("fvg_lookback", 400))
RISK_REWARD = float(cfg.get("risk_reward", 2.0))
MAX_SL_PIPS = int(cfg.get("max_sl_pips", 200))
thresholdPer = float(cfg.get("thresholdPer", 0.0))
SWINGL = int(cfg.get("swingL", 15))
SWINGR = int(cfg.get("swingR", 10))
SWEEP_TOL = float(cfg.get("sweep_tolerance", 0.00010))
LOG_FOLDER = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_FOLDER, exist_ok=True)
SIGNALS_CSV = os.path.join(LOG_FOLDER, "signals.csv")
TRADES_CSV = os.path.join(LOG_FOLDER, "trades.csv")

def telegram_notify(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except Exception as e:
        print("Telegram error:", e)

def telegram_trade_open(symbol, direction, entry, sl, tp):
    emoji = "🚀" if direction == "buy" else "🔻"
    msg = f"{emoji} TRADE OPEN: {direction.upper()} {symbol}\nEntry: {entry}\nSL: {sl}\nTP: {tp}"
    telegram_notify(msg)

def telegram_trade_close(symbol, direction, entry, exit, sl, tp, result):
    emoji = "✅" if result == "TP" else "❌"
    msg = f"{emoji} TRADE CLOSED: {direction.upper()} {symbol}\nEntry: {entry}\nExit: {exit}\nSL: {sl}\nTP: {tp}\nResult: {result}"
    telegram_notify(msg)

def get_ohlc_mt5(symbol, timeframe, n):
    from datetime import UTC
    utc_to = datetime.now(UTC)
    rates = mt5.copy_rates_from(symbol, timeframe, utc_to, n)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def detect_inverse_fvg(df):
    fvg_list = []
    if len(df) < 5:
        return fvg_list
    threshold_per = (thresholdPer or 0.0) / 100.0
    for i in range(2, len(df)):
        A = df.iloc[i-2]; B = df.iloc[i-1]; C = df.iloc[i]
        A_high = A['high']; A_low = A['low']; B_close = B['close']; C_low = C['low']; C_high = C['high']
        high2 = A_high; low2 = A_low
        bull_fvg = False; bear_fvg = False
        if (C_low > high2) and (B_close > high2):
            gap_ratio = ((C_low - high2) / high2) if high2 != 0 else 0
            if gap_ratio > threshold_per:
                bull_fvg = True
        if (C_high < low2) and (B_close < low2):
            gap_ratio = ((low2 - C_high) / low2) if low2 != 0 else 0
            if gap_ratio > threshold_per:
                bear_fvg = True
        if bull_fvg:
            gap_low = high2; gap_high = C_low
            fvg_list.append({'type': 'bull', 'start_idx': i-2, 'end_idx': i, 'gap_low': gap_low, 'gap_high': gap_high, 'time': C['time']})
        elif bear_fvg:
            gap_low = C_high; gap_high = low2
            fvg_list.append({'type': 'bear', 'start_idx': i-2, 'end_idx': i, 'gap_low': gap_low, 'gap_high': gap_high, 'time': C['time']})
    return fvg_list

def detect_liquidity_swing(df, swingL=SWINGL, swingR=SWINGR, lookback=50, tol=SWEEP_TOL):
    n = len(df)
    if n < max(swingL, swingR) + 3:
        return None
    pivots_high = []; pivots_low = []
    for i in range(swingL, n - swingR):
        window_high = df['high'].iloc[i - swingL: i + swingR + 1]
        if df['high'].iloc[i] == window_high.max():
            pivots_high.append({'idx': i, 'price': float(df['high'].iloc[i]), 'time': df['time'].iloc[i]})
        window_low = df['low'].iloc[i - swingL: i + swingR + 1]
        if df['low'].iloc[i] == window_low.min():
            pivots_low.append({'idx': i, 'price': float(df['low'].iloc[i]), 'time': df['time'].iloc[i]})
    last = df.iloc[-1]
    for ph in reversed(pivots_high):
        if (n - 1 - ph['idx']) > lookback:
            continue
        if last['high'] > ph['price'] and last['close'] < ph['price']:
            for prev in pivots_high:
                if prev['idx'] < ph['idx'] and abs(prev['price'] - ph['price']) <= tol:
                    return {'type': 'bear_sweep', 'sweep_idx': n-1, 'sweep_wick_price': float(last['high']), 'time': last['time']}
    for pl in reversed(pivots_low):
        if (n - 1 - pl['idx']) > lookback:
            continue
        if last['low'] < pl['price'] and last['close'] > pl['price']:
            for prev in pivots_low:
                if prev['idx'] < pl['idx'] and abs(prev['price'] - pl['price']) <= tol:
                    return {'type': 'bull_sweep', 'sweep_idx': n-1, 'sweep_wick_price': float(last['low']), 'time': last['time']}
    return None

def calc_sl_tp(direction, entry_price, sl_pips=None, rr=RISK_REWARD, symbol_info=None):
    if symbol_info is None:
        class S: pass
        symbol_info = S(); symbol_info.point = 0.00001; symbol_info.digits = 5
    point = symbol_info.point; digits = symbol_info.digits
    if sl_pips is None:
        sl_pips = 50
    # If sl_pips is a float, use as is; if it's a dict with 'atr', use ATR-based logic
    if isinstance(sl_pips, dict) and 'atr' in sl_pips:
        atr_val = sl_pips['atr']
        atr_mult = sl_pips.get('mult', 1.5)
        sl_pips = atr_val * atr_mult / point
    if direction == 'buy':
        sl_price = entry_price - sl_pips * point
        tp_price = entry_price + sl_pips * rr * point
    else:
        sl_price = entry_price + sl_pips * point
        tp_price = entry_price - sl_pips * rr * point
    return round(sl_price, digits), round(tp_price, digits)

def place_order(symbol, direction, volume, sl_price, tp_price):
    if mt5 is None:
        print("MT5 not available (simulation).")
        return {"mock": True}
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol info not found for {symbol}")
        return None
    price = mt5.symbol_info_tick(symbol).ask if direction == 'buy' else mt5.symbol_info_tick(symbol).bid
    request = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": float(volume), "type": mt5.ORDER_TYPE_BUY if direction=='buy' else mt5.ORDER_TYPE_SELL, "price": price, "sl": sl_price, "tp": tp_price, "deviation":20, "magic":MAGIC_NUMBER, "comment":"FVG+Swing Bot", "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_RETURN}
    result = mt5.order_send(request)
    try:
        pd.DataFrame([{"time":datetime.utcnow().isoformat(),"symbol":symbol,"direction":direction,"price":price,"volume":volume,"sl":sl_price,"tp":tp_price,"result":str(result)}]).to_csv(TRADES_CSV, mode='a', header=not os.path.exists(TRADES_CSV), index=False)
    except Exception:
        pass
    return result

def log_signal(row: dict):
    try:
        pd.DataFrame([row]).to_csv(SIGNALS_CSV, mode='a', header=not os.path.exists(SIGNALS_CSV), index=False)
    except Exception as e:
        print("Failed logging signal:", e)

# --- Daily Risk Management Logic ---
daily_stats = {'date': None, 'sl_total': 0.0, 'profit_total': 0.0, 'trades': 0, 'blocked': False}

def reset_daily_stats():
    global daily_stats
    today = datetime.utcnow().date()
    daily_stats['date'] = today
    daily_stats['sl_total'] = 0.0
    daily_stats['profit_total'] = 0.0
    daily_stats['trades'] = 0
    daily_stats['blocked'] = False

def update_daily_stats(exit_type, sl_pips, tp_pips):
    global daily_stats
    if exit_type == 'SL':
        daily_stats['sl_total'] += sl_pips
    elif exit_type == 'TP':
        daily_stats['profit_total'] += tp_pips
    daily_stats['trades'] += 1

def check_daily_block(atr_sl):
    global daily_stats
    # Block trading if daily SL > ATR SL + daily profit
    if daily_stats['sl_total'] > (atr_sl + daily_stats['profit_total']):
        daily_stats['blocked'] = True
        telegram_notify(f"DAILY STOP: Trading blocked for today. SL={daily_stats['sl_total']:.2f}, Profit={daily_stats['profit_total']:.2f}")
        print(f"DAILY STOP: Trading blocked for today. SL={daily_stats['sl_total']:.2f}, Profit={daily_stats['profit_total']:.2f}")

def is_symbol_in_drawdown(symbol):
    if mt5 is None:
        return False  # Simulation: always allow
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return False  # No open position
    # Check if any open position is in drawdown
    for pos in positions:
        if pos.profit < 0:
            return True
    return False

def has_open_position(symbol):
    if mt5 is None:
        return False  # Simulation: always allow
    positions = mt5.positions_get(symbol=symbol)
    return bool(positions)

# --- Main Trading Logic ---
def evaluate_and_trade(symbol, timeframe):
    global daily_stats
    today = datetime.utcnow().date()
    if daily_stats['date'] != today:
        reset_daily_stats()
    if daily_stats['blocked']:
        print(f"Trading blocked for {today}. No trades will be placed.")
        return
    # Only allow one position per symbol and skip if in drawdown
    if has_open_position(symbol):
        if is_symbol_in_drawdown(symbol):
            print(f"Symbol {symbol} is in drawdown. Skipping setup.")
            return
        else:
            print(f"Symbol {symbol} already has an open position. Skipping setup.")
            return
    try:
        df = get_ohlc_mt5(symbol, timeframe, FVG_LOOKBACK) if mt5 else pd.read_csv(f"{symbol}.csv", parse_dates=['time']).tail(FVG_LOOKBACK)
    except Exception as e:
        print("Failed to fetch data:", e); return
    last_candle = df.iloc[-1]
    sweep = detect_liquidity_swing(df, swingL=SWINGL, swingR=SWINGR, lookback=200, tol=SWEEP_TOL)
    if not sweep:
        return
    fvg_list = detect_inverse_fvg(df)
    if not fvg_list:
        return
    # ATR calculation
    atr_period = 14
    atr_series = calculate_atr(df, period=atr_period)
    atr_val = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
    atr_mult = 1.2  # ATR multiplier for stop loss
    atr_sl = atr_val * atr_mult / 0.00001  # pips
    for fvg in reversed(fvg_list):
        if (datetime.utcnow() - pd.to_datetime(fvg['time'])).total_seconds() > 60*60*24:
            continue
        if fvg['type']=='bull' and sweep['type']=='bull_sweep' and last_candle['close'] <= fvg['gap_high']:
            entry_price = mt5.symbol_info_tick(symbol).ask if mt5 else float(last_candle['close'])
            symbol_info = mt5.symbol_info(symbol) if mt5 else None
            sl_pips = {'atr': atr_val, 'mult': atr_mult}
            sl_price, tp_price = calc_sl_tp('buy', entry_price, sl_pips, symbol_info=symbol_info)
            log_signal({"time": datetime.utcnow().isoformat(), "symbol": symbol, "setup": "bull_fvg+bull_sweep", "entry": entry_price, "sl": sl_price, "tp": tp_price})
            res = place_order(symbol, 'buy', LOT_SIZE, sl_price, tp_price)
            if res:
                telegram_trade_open(symbol, 'buy', entry_price, sl_price, tp_price)
                # Simulate trade result for daily stats (live: update after close)
                # For demo, assume SL hit for risk logic
                update_daily_stats('SL', atr_sl, 0)
                check_daily_block(atr_sl)
            return
        if fvg['type']=='bear' and sweep['type']=='bear_sweep' and last_candle['close'] >= fvg['gap_low']:
            entry_price = mt5.symbol_info_tick(symbol).bid if mt5 else float(last_candle['close'])
            symbol_info = mt5.symbol_info(symbol) if mt5 else None
            sl_pips = {'atr': atr_val, 'mult': atr_mult}
            sl_price, tp_price = calc_sl_tp('sell', entry_price, sl_pips, symbol_info=symbol_info)
            log_signal({"time": datetime.utcnow().isoformat(), "symbol": symbol, "setup": "bear_fvg+bear_sweep", "entry": entry_price, "sl": sl_price, "tp": tp_price})
            res = place_order(symbol, 'sell', LOT_SIZE, sl_price, tp_price)
            if res:
                telegram_trade_open(symbol, 'sell', entry_price, sl_price, tp_price)
                update_daily_stats('SL', atr_sl, 0)
                check_daily_block(atr_sl)
            return

def main_loop():
    reset_daily_stats()
    if mt5:
        try:
            if not mt5.initialize():
                print('MT5 connection status: FAILED')
                return
            else:
                print('MT5 connection status: SUCCESS')
        except Exception:
            pass
    try:
        while True:
            for symbol in SYMBOLS:
                for timeframe in TIMEFRAMES:
                    try:
                        evaluate_and_trade(symbol, timeframe)
                    except Exception as e:
                        print(f"Error evaluating {symbol} {timeframe}:", e)
            time.sleep( CHECK_INTERVAL )
    except KeyboardInterrupt:
        print("Stopping...")

if __name__ == "__main__":
    main_loop()