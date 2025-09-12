from flask import Flask, render_template, jsonify
import pandas as pd
import os
import MetaTrader5 as mt5
from datetime import datetime, timedelta

app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)
TRADES_CSV = os.path.join(BASE_DIR, "logs", "trades.csv")

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]

# Helper to get MT5 status
def get_mt5_status():
    if not mt5.initialize():
        return "Disconnected"
    status = "Connected" if mt5.version() else "Unknown"
    mt5.shutdown()
    return status

# Helper to get bot status (simple: running if file exists)
def get_bot_status():
    # You can improve this with a heartbeat file or IPC
    return "Running" if os.path.exists(TRADES_CSV) else "Stopped"

# Helper to get trades
def get_trades():
    if not os.path.exists(TRADES_CSV):
        return [], []
    df = pd.read_csv(TRADES_CSV)
    open_trades = df[df['result'].str.contains('open|pending', case=False, na=False)].to_dict('records')
    closed_trades = df[df['result'].str.contains('closed|tp|sl', case=False, na=False)].to_dict('records')
    return open_trades, closed_trades

# Helper to get PnL summary
def get_pnl_summary():
    if not os.path.exists(TRADES_CSV):
        return {"daily": 0, "weekly": 0}
    df = pd.read_csv(TRADES_CSV)
    df['time'] = pd.to_datetime(df['time'])
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    daily_pnl = df[df['time'].dt.date == today]['result'].apply(lambda x: float(x.split(':')[-1]) if ':' in x else 0).sum()
    weekly_pnl = df[df['time'].dt.date >= week_ago]['result'].apply(lambda x: float(x.split(':')[-1]) if ':' in x else 0).sum()
    return {"daily": daily_pnl, "weekly": weekly_pnl}

@app.route("/")
def dashboard():
    mt5_status = get_mt5_status()
    bot_status = get_bot_status()
    open_trades, closed_trades = get_trades()
    pnl = get_pnl_summary()
    return render_template("dashboard.html", mt5_status=mt5_status, bot_status=bot_status,
                           open_trades=open_trades, closed_trades=closed_trades, pnl=pnl, symbols=SYMBOLS)

@app.route("/api/chart/<symbol>")
def chart_data(symbol):
    # For demo, return last 100 prices from CSV
    csv_path = os.path.join(BASE_DIR, f"{symbol}_2025-09-12_M3.csv")
    if not os.path.exists(csv_path):
        return jsonify({"labels": [], "prices": []})
    df = pd.read_csv(csv_path)
    labels = df['time'].tail(100).tolist()
    prices = df['close'].tail(100).tolist()
    return jsonify({"labels": labels, "prices": prices})

if __name__ == "__main__":
    app.run(debug=True)
