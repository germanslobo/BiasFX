import MetaTrader5 as mt5
import time

# Constants for lot size calculation
ATR_HEDGE_DISTANCE = 1.0  # Percentage of ATR distance for hedging
PERCENTAGE_MAXIMUM_CAPACITY = 100  # Percentage of maximum capacity

# Trading parameters
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

def maximum_capacity_lot_size(symbol):
    """Calculate the maximum capacity lot size for the given symbol."""
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account information")
        return 0
    account_leverage = account_info.leverage

    current_price = mt5.symbol_info_tick(symbol).ask
    cost_per_lot_current = 1000000 * current_price

    atr = get_daily_atr(symbol)
    hedge_distance = (atr * ATR_HEDGE_DISTANCE / 100)
    hedge_price = current_price - hedge_distance
    cost_per_lot_hedge = 1000000 * hedge_price

    point = mt5.symbol_info(symbol).point
    pip_value = (point * 1000000) / current_price
    equity_loss_at_hedge = hedge_distance * pip_value
    initial_equity = account_info.equity
    equity_at_hedge = initial_equity - equity_loss_at_hedge

    margin_req_buy = cost_per_lot_current / account_leverage
    margin_req_hedge = (cost_per_lot_hedge / account_leverage) / 2
    total_margin_req = margin_req_buy + margin_req_hedge

    max_combined_lots = equity_at_hedge / total_margin_req
    max_lots_each_position = max_combined_lots / 2
    imax_lots_each_position = max_lots_each_position * (PERCENTAGE_MAXIMUM_CAPACITY / 100)

    max_allowed_lot_size = mt5.symbol_info(symbol).volume_max
    min_allowed_lot_size = mt5.symbol_info(symbol).volume_min
    volume_step = mt5.symbol_info(symbol).volume_step

    if imax_lots_each_position > max_allowed_lot_size:
        imax_lots_each_position = max_allowed_lot_size
    if imax_lots_each_position < min_allowed_lot_size:
        imax_lots_each_position = min_allowed_lot_size

    imax_lots_each_position = round(imax_lots_each_position / volume_step) * volume_step

    print(f"Final adjusted lot size to be used: {imax_lots_each_position:.2f}")
    return imax_lots_each_position

def place_market_order(symbol, action):
    """Place a market order with calculated lot size."""
    lot_size = maximum_capacity_lot_size(symbol)
    print(f"Attempting to place a market order with lot size: {lot_size:.2f}")
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

def place_pending_order(symbol, action, price):
    """Place a pending order with calculated lot size."""
    lot_size = maximum_capacity_lot_size(symbol)
    print(f"Attempting to place a pending {action} order with lot size: {lot_size:.2f}")
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
        print(f"No active positions or orders for symbol '{symbol}'.")
        return False
    return True

def trend_following_buy_strategy(symbol, bias):
    """Execute trend-following buy strategy when Bias is 0."""
    if bias != 0:
        print("Bias is not 0. Exiting strategy.")
        return
    
    print("Starting trend-following buy strategy...")

    atr = get_daily_atr(symbol)
    if atr is None:
        print("Failed to calculate ATR. Exiting strategy.")
        return
    spread = mt5.symbol_info(symbol).spread * mt5.symbol_info(symbol).point
    distance = atr + spread

    while True:
        positions = mt5.positions_get(symbol=symbol)
        
        if len(positions) == 0:
            print("No open Buy positions. Exiting strategy.")
            break

        if len(positions) > 1:
            latest_position = positions[-1]
            new_buy_stop_price = mt5.symbol_info_tick(symbol).ask + distance
            new_buy_stop = place_pending_order(symbol, "BUY_STOP", new_buy_stop_price)
            
            while True:
                current_price = mt5.symbol_info_tick(symbol).ask
                trailing_stop_price = latest_position.price_open + 0.0001
                
                if current_price >= latest_position.price_open + 0.0001:
                    trailing_stop_price = latest_position.price_open
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": latest_position.ticket,
                        "sl": trailing_stop_price
                    })
                    print(f"Trailing stop moved to break-even at {trailing_stop_price}")
                
                if current_price >= trailing_stop_price + 0.0001:
                    trailing_stop_price += 0.0001
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": latest_position.ticket,
                        "sl": trailing_stop_price
                    })
                    print(f"Trailing stop moved up to {trailing_stop_price}")

                if new_buy_stop and current_price >= new_buy_stop_price:
                    break

                time.sleep(1)

        if not check_orders_exist(symbol):
            print("All positions closed. Exiting strategy.")
            break

        time.sleep(1)

    print("Trend-following buy strategy completed.")

def monitor_pending_orders(symbol, bias):
    """Monitor pending orders and handle hit orders."""
    print("Monitoring orders created. Waiting for one of the orders to be triggered...")
    while True:
        if not check_orders_exist(symbol):
            break

        positions = mt5.positions_get(symbol=symbol)
        orders = mt5.orders_get(symbol=symbol)

        if len(positions) > 1:
            if any(pos.type == mt5.ORDER_TYPE_BUY for pos in positions):
                print("Buy Stop hit, closing Sell Stop and initiating trend-following strategy.")
                for order in orders:
                    if order.type == mt5.ORDER_TYPE_SELL_STOP:
                        mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket})
                trend_following_buy_strategy(symbol, bias)
                break

        time.sleep(1)
    print("Monitoring completed. Exiting.")

def hedging_logic():
    """Main hedging logic."""
    initialize_mt5()
    symbol = input("Enter the trading symbol (e.g., EURUSD, BTCUSD): ").strip().upper()
    if not validate_symbol(symbol):
        print("Exiting the program due to invalid symbol.")
        mt5.shutdown()
        return

    atr = get_daily_atr(symbol)
    if atr is None:
        print("ATR calculation failed.")
        mt5.shutdown()
        return
    
    spread = mt5.symbol_info(symbol).spread * mt5.symbol_info(symbol).point
    distance = atr + spread

    # Step 3: Open Buy Position
    buy_order = place_market_order(symbol, "BUY")
    if not buy_order:
        print("Failed to place initial Buy order.")
        mt5.shutdown()
        return

    # Step 4: Place Pending Sell Stop
    sell_stop_price = mt5.symbol_info_tick(symbol).bid - distance
    sell_stop_order = place_pending_order(symbol, "SELL_STOP", sell_stop_price)
    if not sell_stop_order:
        print("Failed to place Pending Sell Stop.")
        mt5.shutdown()
        return

    # Step 5: Place Pending Buy Stop
    buy_stop_price = mt5.symbol_info_tick(symbol).ask + distance
    buy_stop_order = place_pending_order(symbol, "BUY_STOP", buy_stop_price)
    if not buy_stop_order:
        print("Failed to place Pending Buy Stop.")
        mt5.shutdown()
        return

    # Step 8: Monitor Orders until conditions in Point 6 or 7 are met
    monitor_pending_orders(symbol, bias=0)
    mt5.shutdown()

if __name__ == "__main__":
    hedging_logic()
    mt5.shutdown()
