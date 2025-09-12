# ATR calculation utility for main.py
import pandas as pd

def calculate_atr(df, period=14):
    """
    Calculate the Average True Range (ATR) for a given DataFrame.
    df: DataFrame with columns ['high', 'low', 'close']
    period: ATR period (default 14)
    Returns a pandas Series of ATR values.
    """
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean()
    return atr
