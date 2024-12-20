import MetaTrader5 as mt5
import pandas as pd
import os
from datetime import datetime, timedelta

# Define the base currency pairs (without suffixes)
BASE_CURRENCY_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
    "USDCAD", "EURGBP", "EURJPY", "EURCHF", "GBPJPY", "GBPCHF",
    "AUDJPY", "AUDNZD", "AUDCAD", "AUDCHF", "CADJPY", "CADCHF",
    "CHFJPY", "EURAUD", "EURNZD", "GBPAUD", "GBPNZD", "GBPCAD",
    "NZDJPY", "NZDCAD", "NZDCHF"
]

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1
}

# Update OUTPUT_FOLDER to BiasFX_Data
OUTPUT_FOLDER = "../BiasFX_Data"

def connect_mt5():
    """Connect to MT5."""
    if not mt5.initialize():
        print("Failed to initialize MT5:", mt5.last_error())
        return False
    print("Connected to MT5")
    return True

def get_full_symbol_list():
    """Retrieve all symbols available in the MT5 terminal."""
    symbols = mt5.symbols_get()
    return [symbol.name for symbol in symbols]

def map_symbols(base_pairs, full_symbols):
    """
    Map base currency pairs to their full symbols (with suffixes).
    :param base_pairs: List of base currency pairs
    :param full_symbols: List of all symbols available in the broker
    :return: Dictionary mapping base pairs to full symbols
    """
    mapped_symbols = {}
    for base in base_pairs:
        for full in full_symbols:
            if full.startswith(base):
                mapped_symbols[base] = full
                break
    return mapped_symbols

def fetch_data(symbol, timeframe, days=1):
    """
    Fetch historical OHLC data for a given symbol and timeframe.
    :param symbol: Symbol name (e.g., "EURUSD")
    :param timeframe: MT5 Timeframe constant
    :param days: Number of days of historical data to fetch
    :return: Pandas DataFrame with OHLC and tick volume
    """
    utc_from = datetime.now() - timedelta(days=days)
    utc_to = datetime.now()
    rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)
    if rates is None:
        print(f"Failed to fetch data for {symbol} on {timeframe}: {mt5.last_error()}")
        return None
    df = pd.DataFrame(rates)
    return df

def save_csv(dataframe, filepath):
    """
    Save data to a CSV file.
    :param dataframe: DataFrame to save
    :param filepath: File path to save the data
    """
    dataframe["time"] = pd.to_datetime(dataframe["time"], unit="s")
    dataframe = dataframe[["time", "open", "high", "low", "close", "tick_volume"]]
    dataframe.to_csv(filepath, index=False)

def main():
    """Main function to fetch and save data."""
    if not connect_mt5():
        return

    # Get the list of all available symbols in the broker
    full_symbols = get_full_symbol_list()

    # Map base currency pairs to their full symbols
    mapped_symbols = map_symbols(BASE_CURRENCY_PAIRS, full_symbols)
    print("Mapped Symbols:", mapped_symbols)

    # Create the main output folder if it doesn't exist
    if not os.path.exists(OUTPUT_FOLDER):
        os.mkdir(OUTPUT_FOLDER)

    for base_pair, full_symbol in mapped_symbols.items():
        # Create a folder for each currency pair
        pair_folder = os.path.join(OUTPUT_FOLDER, base_pair)
        if not os.path.exists(pair_folder):
            os.mkdir(pair_folder)

        for tf_name, tf_value in TIMEFRAMES.items():
            # Define file name and path for each timeframe
            filename = f"{tf_name}.csv"
            filepath = os.path.join(pair_folder, filename)

            print(f"Fetching {full_symbol} data for {tf_name}")
            df = fetch_data(full_symbol, tf_value, days=1)  # Fetch last 1 day's data
            if df is not None:
                save_csv(df, filepath)
                print(f"Saved {tf_name} data for {full_symbol} to {filepath}")

    mt5.shutdown()
    print("MT5 connection closed.")

if __name__ == "__main__":
    main()
