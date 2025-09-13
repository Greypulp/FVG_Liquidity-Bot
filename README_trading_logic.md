# Trading Bot Logic Overview

This README describes the core trading logic implemented in the FVG Liquidity Bot project.

## Overview
The bot is designed to trade forex pairs using MetaTrader5 (MT5) and Python. It features live monitoring via a Flask dashboard, candlestick chart visualization, and trade logging. The bot supports both live trading and backtesting.

## Main Trading Logic
- **Symbols Traded:** EURUSD, GBPUSD, AUDUSD, USDCAD (configurable)
- **Data Source:** MT5 live data (with CSV fallback for backtesting)
- **Strategy:**
  - The bot scans for fair value gap (FVG) and liquidity sweep patterns.
  - Entry signals are generated when price action matches FVG or sweep criteria.
  - Trades are executed with risk management (TP/SL levels).
  - All trades are logged to `logs/trades.csv`.

## Trade Execution
- **Entry:**
  - Buy/Sell signals are generated based on detected patterns.
  - Orders are placed via MT5 API.
- **Exit:**
  - Trades are closed on TP (Take Profit), SL (Stop Loss), or custom exit logic.
  - Results are logged with timestamps and PnL.

## Backtesting
- Historical data is loaded from CSV files for each symbol.
- The bot simulates trades using the same logic as live trading.
- Backtest results are saved to `logs/backtest_results.csv` and visualized on the dashboard.

## Dashboard Features
- Live candlestick charts for each symbol
- Trade markers for entries/exits (TP/SL/Closed)
- Open/closed trades tables
- MT5 account status and PnL summary

## Risk Management
- Each trade includes TP/SL levels
- Position sizing and risk parameters are configurable
- Daily stop loss logic is enforced:
  - The bot tracks total stop loss (SL) and profit for the day.
  - If daily SL exceeds the allowed threshold (ATR SL + daily profit), trading is blocked for the rest of the day.
  - No new trades are activated once the daily stop is triggered.
- The bot will not activate a new trade for a symbol if an open position for that symbol is in drawdown.
- Only one position per symbol is allowed at a time.

**Relevant functions:**
- `check_daily_block`: Blocks trading for the day if SL threshold is exceeded.
- `is_symbol_in_drawdown`: Prevents new trades for symbols in drawdown.

## Files
- `main.py`: Main bot logic and trade execution
- `dashboard_app.py`: Flask backend for dashboard
- `backtest.py`: Backtesting logic
- `logs/trades.csv`: Trade log
- `logs/backtest_results.csv`: Backtest results
- `templates/dashboard.html`: Dashboard UI

## How to Run
1. Activate the Python virtual environment:
   ```powershell
   & .venv\Scripts\Activate.ps1
   ```
2. Start the bot:
   ```powershell
   python main.py
   ```
3. Start the dashboard:
   ```powershell
   python dashboard_app.py
   ```
4. Open the dashboard in your browser at `http://127.0.0.1:5000/`

## Customization
- Symbols, risk parameters, and strategy logic can be modified in `main.py` and config files.

## Disclaimer
This bot is for educational and research purposes. Use at your own risk in live trading environments.
