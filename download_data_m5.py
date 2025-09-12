import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

# Settings
symbols = ["GBPUSD"]
timeframe = mt5.TIMEFRAME_M5
start_date = datetime(2025, 9, 12)
end_date = start_date + timedelta(days=1)

mt5.initialize()
for symbol in symbols:
    rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    out_file = f"{symbol}_2025-09-12_M5.csv"
    df.to_csv(out_file, index=False)
    print(f"Saved {out_file} ({len(df)} rows)")
mt5.shutdown()
