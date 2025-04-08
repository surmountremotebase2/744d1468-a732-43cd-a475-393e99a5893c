# Import necessary components from Surmount
from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import EMA, VWAP # Keep imports
from surmount.logging import log

# Define the strategy class
class TradingStrategy(Strategy):
    def __init__(self):
        # Define the assets to trade
        self.tickers = ["SPY"] # Example: Use SPY ETF
        # NO indicator instantiation here anymore
        # self.indicators = {} # REMOVED
        log("Strategy Initialized") # Added log to confirm __init__ runs

    @property
    def interval(self):
        # Use a 2-minute timeframe
        return "5min"

    @property
    def assets(self):
        # Return the list of assets
        return self.tickers

    @property
    def data(self):
        # No additional data streams needed beyond OHLCV
        return []

    def run(self, data):
        """
        Executes the strategy logic for each data point.
        """
        allocation_dict = {}

        for ticker in self.tickers:
            # --- CORRECTED OHLCV DATA RETRIEVAL ---
            ohlcv_data_source = data.get("ohlcv") # Use .get on the main data dict

            ohlcv = None # Initialize ohlcv to None
            if isinstance(ohlcv_data_source, dict):
                # If it's a dictionary, get data by ticker key
                ohlcv = ohlcv_data_source.get(ticker)
            elif isinstance(ohlcv_data_source, list) and len(self.assets) == 1:
                # If it's a list AND we only requested one asset, assume the list is the data
                ohlcv = ohlcv_data_source
            else:
                # Log unexpected structure if necessary
                log(f"Warning: Unexpected data structure for ohlcv. Type: {type(ohlcv_data_source)}")
            # --- END OF CORRECTION ---

            # Ensure we have enough data points (and ohlcv was successfully retrieved)
            if ohlcv is None or len(ohlcv) < 50:
                log(f"Not enough data or failed to retrieve OHLCV for {ticker} (need ~50 bars)")
                # Ensure allocation is 0 if we can't process data
                allocation_dict[ticker] = 0
                continue # Skip to next ticker

            # Prepare data slice (use sufficient history)
            historical_data = ohlcv # Pass the retrieved ohlcv list

            # ... (rest of your indicator calculation and trading logic) ...
            try:
                # Call indicators directly as functions
                ema9_val = EMA(ticker=ticker, data=historical_data, length=9)
                ema20_val = EMA(ticker=ticker, data=historical_data, length=20)
                vwap_val = VWAP(ticker=ticker, data=historical_data)

                # Extract latest values (assuming list return for now)
                # Add more robust checks if needed based on actual return types
                ema9_val = ema9_val[-1] if isinstance(ema9_val, list) and ema9_val else None
                ema20_val = ema20_val[-1] if isinstance(ema20_val, list) and ema20_val else None
                vwap_val = vwap_val[-1] if isinstance(vwap_val, list) and vwap_val else None

            # ... (rest of try block, except block, logic)

            # Check if indicator values are valid numbers AFTER extraction
            if not all(isinstance(v, (int, float)) for v in [ema9_val, ema20_val, vwap_val]):
                 log(f"Indicator calculation incomplete or invalid after extraction for {ticker}. EMA9: {ema9_val}, EMA20: {ema20_val}, VWAP: {vwap_val}")
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0) # Hold position on error
                 continue

            # Get the most recent closing price
            current_close = ohlcv[-1]["close"] # This assumes ohlcv is a list of dicts

            # ... (rest of your trading logic: conditions, entry, exit) ...


        # Create TargetAllocation object
        final_allocation = {ticker: allocation_dict.get(ticker, 0) for ticker in self.tickers}
        return TargetAllocation(final_allocation)