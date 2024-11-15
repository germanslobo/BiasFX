import MetaTrader5 as mt5
import time


# Replace these variables with your trading parameters
LOT_SIZE = 0.1  # Lot size for positions
SLIPPAGE = 10  # Slippage in points
MAGIC_NUMBER = 123456  # Magic number for identifying trades
ATR_MULTIPLIER = 1.0  # Multiplier for ATR-based distances


def initialize_mt5():
    """Initialize MetaTrader 5 connection."""
    if not mt5.initialize():
        print("Failed to initialize MetaTrader 5")
        quit()


def validate_symbol(symbol):
    """Validate if the trading symbol exists and is visible."""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol '{symbol}' not found.")
        return False
    if not symbol_info.visible:
        print(f"Symbol '{symbol}' is not visible in the market watch. Adding symbol...")
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to add symbol '{symbol}' to the market watch.")
            return False
    print(f"Symbol '{symbol}' is valid and ready for trading.")
    return True


def get_daily_atr(symbol):
    """Calculate ATR for the daily timeframe."""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 14)
    if rates is None or len(rates) < 14:
        print("Error fetching rates for ATR calculation")
        return None
    highs = [rate['high'] for rate in rates]
    lows = [rate['low'] for rate in rates]
    atr = sum([h - l for h, l in zip(highs, lows)]) / len(highs)
    return atr


def place_market_order(symbol, action, lot_size):
    """Place a market order."""
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": mt5.symbol_info_tick(symbol).ask if action == "BUY" else mt5.symbol_info_tick(symbol).bid,
        "slippage": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Hedging Logic",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to place market order: {result.comment}")
    else:
        print(f"Market order placed: {result}")
    return result


def place_pending_order(symbol, action, lot_size, price):
    """Place a pending order."""
    order_type = mt5.ORDER_TYPE_BUY_STOP if action == "BUY_STOP" else mt5.ORDER_TYPE_SELL_STOP
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "slippage": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Hedging Logic",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to place pending order: {result.comment}")
    else:
        print(f"Pending order placed: {result}")
    return result


def check_orders_exist(symbol):
    """Check if there are any open orders or positions for the given symbol."""
    positions = mt5.positions_get(symbol=symbol)
    orders = mt5.orders_get(symbol=symbol)
    if not positions and not orders:
        print("No active positions or orders. Stopping the script.")
        return False
    return True


def monitor_pending_orders(symbol):
    """Monitor pending orders and handle hit orders."""
    while True:
        if not check_orders_exist(symbol):
            break

        positions = mt5.positions_get(symbol=symbol)
        orders = mt5.orders_get(symbol=symbol)

        if len(positions) > 1:
            # Check which pending order was hit
            if any(pos.type == mt5.ORDER_TYPE_SELL for pos in positions):
                print("Sell Stop hit, closing Buy Stop")
                for order in orders:
                    if order.type == mt5.ORDER_TYPE_BUY_STOP:
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": order.ticket,
                        })
                break
            elif any(pos.type == mt5.ORDER_TYPE_BUY for pos in positions):
                print("Buy Stop hit, closing Sell Stop")
                for order in orders:
                    if order.type == mt5.ORDER_TYPE_SELL_STOP:
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": order.ticket,
                        })
                break
        time.sleep(1)
    print("Monitoring completed. Exiting.")


def hedging_logic():
    """Main hedging logic."""
    initialize_mt5()

    # User input for symbol selection
    symbol = input("Enter the trading symbol (e.g., EURUSD, BTCUSD): ").strip().upper()

    # Validate the symbol
    if not validate_symbol(symbol):
        print("Exiting the program due to invalid symbol.")
        mt5.shutdown()
        return

    # Calculate ATR
    atr = get_daily_atr(symbol)
    if atr is None:
        print("ATR calculation failed")
        mt5.shutdown()
        return

    spread = mt5.symbol_info(symbol).spread * mt5.symbol_info(symbol).point
    distance = ATR_MULTIPLIER * atr + spread

    # Set Bias to 0 directly
    Bias = 0
    print(f"Bias: {Bias}")

    if Bias == 0:
        # Step 3: Open Buy Position
        place_market_order(symbol, "BUY", LOT_SIZE)

        # Step 4 & 5: Place Pending Orders
        tick = mt5.symbol_info_tick(symbol)
        buy_stop_price = tick.ask + distance
        sell_stop_price = tick.bid - distance

        buy_stop = place_pending_order(symbol, "BUY_STOP", LOT_SIZE, buy_stop_price)
        sell_stop = place_pending_order(symbol, "SELL_STOP", LOT_SIZE, sell_stop_price)

        if not buy_stop or not sell_stop:
            print("Failed to place pending orders")
            mt5.shutdown()
            return

        print("Pending orders placed, monitoring...")
        monitor_pending_orders(symbol)

    mt5.shutdown()


if __name__ == "__main__":
    hedging_logic()
