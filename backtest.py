import os, csv, pandas as pd
from atr_utils import calculate_atr
from datetime import datetime
try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None
from main import detect_inverse_fvg, detect_liquidity_swing, calc_sl_tp

LOG_FOLDER = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_FOLDER, exist_ok=True)
OUT_CSV = os.path.join(LOG_FOLDER, "backtest_results.csv")

def fetch_ohlc(symbol, timeframe, bars):
    # Use M3 or M5 CSV files for EURUSD and GBPUSD
    m3_csv = f"{symbol}_2025-09-12_M3.csv"
    m5_csv = f"{symbol}_2025-09-12_M5.csv"
    if timeframe == "TIMEFRAME_M5" and os.path.exists(m5_csv):
        df = pd.read_csv(m5_csv, parse_dates=['time'])
        return df.tail(bars).reset_index(drop=True)
    elif os.path.exists(m3_csv):
        df = pd.read_csv(m3_csv, parse_dates=['time'])
        return df.tail(bars).reset_index(drop=True)
    raise RuntimeError("CSV not found for historical data.")

def simulate(symbol, timeframe, bars, swingL, swingR, tol):
    df = fetch_ohlc(symbol, timeframe, bars)
    trades = []
    for i in range(5, len(df)-2):
        window = df.iloc[:i+1].copy().reset_index(drop=True)
        fvg_list = detect_inverse_fvg(window)
        sweep = detect_liquidity_swing(window, swingL=swingL, swingR=swingR, lookback=200, tol=tol)
        last = window.iloc[-1]
        if not fvg_list or not sweep:
            continue
        # ATR calculation for current window
        atr_period = 14
        atr_series = calculate_atr(window, period=atr_period)
        atr_val = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
        atr_mult = 1.2  # ATR multiplier for stop loss
        for fvg in reversed(fvg_list):
            now_utc = pd.Timestamp.now('UTC')
            fvg_time = pd.to_datetime(fvg['time'])
            if fvg_time.tzinfo is None:
                fvg_time = fvg_time.tz_localize('UTC')
            if (now_utc - fvg_time).total_seconds() > 60*60*24:
                continue
            if fvg['type']=='bull' and sweep['type']=='bull_sweep' and last['close'] <= fvg['gap_high']:
                entry_idx = i+1
                if entry_idx >= len(df): break
                entry_open = df.iloc[entry_idx]['open']
                symbol_info = type("S", (), {"point": 0.00001, "digits": 5})()
                sl_pips = {'atr': atr_val, 'mult': atr_mult}
                sl_price, tp_price = calc_sl_tp('buy', entry_open, sl_pips, symbol_info=symbol_info)
                hit=None; exit_price=entry_open
                for j in range(entry_idx, len(df)):
                    row = df.iloc[j]
                    if row['low'] <= sl_price:
                        hit='SL'; exit_price=sl_price; break
                    if row['high'] >= tp_price:
                        hit='TP'; exit_price=tp_price; break
                pips = (exit_price - entry_open) / symbol_info.point * (1 if hit=='TP' else -1)
                trades.append({"time": df.iloc[entry_idx]['time'], "symbol": symbol, "direction":"buy", "entry":entry_open, "exit":exit_price, "exit_type": hit or "NO_EXIT", "pips": pips})
                break
            if fvg['type']=='bear' and sweep['type']=='bear_sweep' and last['close'] >= fvg['gap_low']:
                entry_idx = i+1
                if entry_idx >= len(df): break
                entry_open = df.iloc[entry_idx]['open']
                symbol_info = type("S", (), {"point": 0.00001, "digits": 5})()
                sl_pips = {'atr': atr_val, 'mult': atr_mult}
                sl_price, tp_price = calc_sl_tp('sell', entry_open, sl_pips, symbol_info=symbol_info)
                hit=None; exit_price=entry_open
                for j in range(entry_idx, len(df)):
                    row = df.iloc[j]
                    if row['high'] >= sl_price:
                        hit='SL'; exit_price=sl_price; break
                    if row['low'] <= tp_price:
                        hit='TP'; exit_price=tp_price; break
                pips = (entry_open - exit_price) / symbol_info.point * (1 if hit=='TP' else -1)
                trades.append({"time": df.iloc[entry_idx]['time'], "symbol": symbol, "direction":"sell", "entry":entry_open, "exit":exit_price, "exit_type": hit or "NO_EXIT", "pips": pips})
                break
    if trades:
        keys = trades[0].keys()
        # If file exists, append without header; else, write with header
        write_header = not os.path.exists(OUT_CSV)
        with open(OUT_CSV, "a", newline="") as f:
            import csv as _csv
            writer = _csv.DictWriter(f, keys)
            if write_header:
                writer.writeheader()
            writer.writerows(trades)
    wins = sum(1 for t in trades if t['exit_type']=='TP')
    losses = sum(1 for t in trades if t['exit_type']=='SL')
    total = len(trades); total_pips = sum(t['pips'] for t in trades)
    print(f"Simulated {total} trades: {wins} wins, {losses} losses, pips={total_pips:.1f}")
    return trades

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--timeframe", default="TIMEFRAME_M15")
    p.add_argument("--bars", type=int, default=2000)
    p.add_argument("--swingL", type=int, default=15)
    p.add_argument("--swingR", type=int, default=10)
    p.add_argument("--tol", type=float, default=0.00010)
    args = p.parse_args()
    trades = simulate(args.symbol, args.timeframe, args.bars, args.swingL, args.swingR, args.tol)
    print(f"Appended {args.symbol} backtest results to {OUT_CSV}")