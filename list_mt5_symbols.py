import MetaTrader5 as mt5

if not mt5.initialize():
    print("MT5 initialization failed!")
    exit(1)

symbols = mt5.symbols_get()
print("Available MT5 symbols:")
for s in symbols:
    print(s.name)

mt5.shutdown()
