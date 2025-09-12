import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import os

# Major pairs
MAJOR_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
TIMEFRAME = mt5.TIMEFRAME_M3
DATE = datetime(2025, 9, 12)
BASE_DIR = os.path.dirname(__file__)

# MT5 must be running and logged in
if not mt5.initialize():
    print("MT5 initialization failed!")
    exit(1)

for symbol in MAJOR_PAIRS:
    print(f"Downloading {symbol} 3-min data for 2025-09-12...")
    # Get all bars for the day
    utc_from = datetime(2025, 9, 12, 0, 0)
    utc_to = datetime(2025, 9, 12, 23, 59)
    rates = mt5.copy_rates_range(symbol, TIMEFRAME, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print(f"No data for {symbol} on 2025-09-12.")
        continue
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    out_csv = os.path.join(BASE_DIR, f"{symbol}_2025-09-12_M3.csv")
    df.to_csv(out_csv, index=False)
    print(f"Saved to {out_csv}")

mt5.shutdown()
print("Download complete.")
