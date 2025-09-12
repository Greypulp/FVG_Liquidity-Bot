import os
import subprocess
import pandas as pd

# List of major pairs (update as needed)
MAJOR_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
LOT_SIZE = 1  # Standard lot
PIP_VALUE = {
    "USDJPY": 9.1,  # Approximate pip value for USDJPY per lot
    "EURUSD": 10,
    "GBPUSD": 10,
    "AUDUSD": 10,
    "USDCAD": 10,
    "USDCHF": 10,
    "NZDUSD": 10
}

results = []
for symbol in MAJOR_PAIRS:
    print(f"Running backtest for {symbol}...")
    try:
        # Run backtest.py for each symbol
        output = subprocess.check_output([
            "python", "backtest.py",
            "--symbol", symbol,
            "--timeframe", "TIMEFRAME_M3",
            "--bars", "500",
            "--swingL", "15",
            "--swingR", "10",
            "--tol", "0.00010"
        ], stderr=subprocess.STDOUT, text=True)
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Error running backtest for {symbol}: {e.output}")

# Read results from CSV
csv_path = os.path.join("logs", "backtest_results.csv")
df = pd.read_csv(csv_path)

summary = {}
for symbol in MAJOR_PAIRS:
    df_symbol = df[df['symbol'] == symbol]
    wins = (df_symbol['exit_type'] == 'TP').sum()
    losses = (df_symbol['exit_type'] == 'SL').sum()
    net_pips = df_symbol['pips'].sum()
    pip_value = PIP_VALUE.get(symbol, 10)
    usd_result = net_pips * pip_value * LOT_SIZE / 100  # For JPY pairs, pip is 0.01
    summary[symbol] = {
        'trades': len(df_symbol),
        'wins': wins,
        'losses': losses,
        'net_pips': net_pips,
        'usd': usd_result
    }

print("\n--- Backtest USD Summary ---")
for symbol, stats in summary.items():
    print(f"{symbol}: Trades={stats['trades']}, Wins={stats['wins']}, Losses={stats['losses']}, Net Pips={stats['net_pips']:.1f}, USD={stats['usd']:.2f}")
