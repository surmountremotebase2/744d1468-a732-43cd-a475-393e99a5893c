# Import necessary components from Surmount
from surmount.base_class import Strategy, TargetAllocation # Correct base class import
from surmount.technical_indicators import EMA, VWAP       # Correct indicator import location
from surmount.logging import log

# Define the strategy class
class TradingStrategy(Strategy):
    def __init__(self):
        # Define the assets to trade
        self.tickers = ["SPY"] # Example: Use SPY ETF (ensure it's a list)
        # No indicator instantiation needed here based on previous errors
        log("Strategy Initialized.")

    @property
    def interval(self):
        # Use a 5-minute timeframe (as "2m" caused KeyError)
        # Ensure this interval is supported by Surmount documentation/platform
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
            # --- Retrieve OHLCV Data ---
            # Handle potential dictionary or list structure for data["ohlcv"]
            ohlcv_data_source = data.get("ohlcv") # Safely get the ohlcv part of data

            ohlcv = None # Initialize ohlcv to None
            if isinstance(ohlcv_data_source, dict):
                # If it's a dictionary, get data by ticker key
                ohlcv = ohlcv_data_source.get(ticker)
            elif isinstance(ohlcv_data_source, list) and len(self.assets) == 1:
                # If it's a list AND we only requested one asset, assume the list is the data
                ohlcv = ohlcv_data_source
            else:
                # Log unexpected structure if necessary
                log(f"Warning: Unexpected data structure for ohlcv for {ticker}. Type: {type(ohlcv_data_source)}")

            # --- Data Sufficiency Check ---
            # Need enough bars for indicator calculation (e.g., 20 period EMA + buffer)
            # Let's use 50 bars as a safe minimum buffer.
            if ohlcv is None or len(ohlcv) < 50:
                log(f"Not enough data or failed to retrieve OHLCV for {ticker} (need ~50 bars)")
                allocation_dict[ticker] = 0 # Ensure flat if data is insufficient
                continue # Skip to next ticker

            # --- Calculate Indicators ---
            historical_data = ohlcv # Use the retrieved list of OHLCV bars

            # Initialize variables before the try block
            ema9_val, ema20_val, vwap_val = None, None, None
            current_close = None

            try:
                # Call indicators directly as functions based on previous errors
                # Passing necessary arguments: ticker, data, length
                ema9_raw = EMA(ticker=ticker, data=historical_data, length=9)
                ema20_raw = EMA(ticker=ticker, data=historical_data, length=20)
                vwap_raw = VWAP(ticker=ticker, data=historical_data) # Assuming VWAP needs ticker & data too

                # Extract the latest value
                # Assumes functions return a list; adjust if they return single values or dicts
                ema9_val = ema9_raw[-1] if isinstance(ema9_raw, list) and ema9_raw else ema9_raw if isinstance(ema9_raw, (int,float)) else None
                ema20_val = ema20_raw[-1] if isinstance(ema20_raw, list) and ema20_raw else ema20_raw if isinstance(ema20_raw, (int,float)) else None
                vwap_val = vwap_raw[-1] if isinstance(vwap_raw, list) and vwap_raw else vwap_raw if isinstance(vwap_raw, (int,float)) else None

                # Get the most recent closing price from the data
                current_close = historical_data[-1]["close"]

            except Exception as e:
                # --- Added except BLOCK ---
                log(f"Error during indicator calculation or processing for {ticker}: {e}")
                # Values remain None as initialized before try block
                # Hold current position and skip rest of logic for this ticker
                allocation_dict[ticker] = data["holdings"].get(ticker, 0)
                continue # Move to the next ticker

            # --- Validity Check for Indicators and Price ---
            # Check if all necessary values were successfully calculated/retrieved
            if not all(isinstance(v, (int, float)) for v in [ema9_val, ema20_val, vwap_val, current_close]):
                 log(f"Indicator/Price values invalid after calculation/extraction for {ticker}. EMA9: {ema9_val}, EMA20: {ema20_val}, VWAP: {vwap_val}, Close: {current_close}")
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0) # Hold position
                 continue # Skip trading logic if values invalid

            # --- Trading Logic ---
            current_holding = data["holdings"].get(ticker, 0)
            currently_invested = abs(current_holding) > 1e-9 # Check if holding is non-zero

            # --- Define Entry and Exit Conditions ---
            is_uptrend_condition = current_close > vwap_val and ema9_val > ema20_val
            is_downtrend_condition = current_close < vwap_val and ema9_val < ema20_val

            # Pullback condition for Long: Price dips near/below EMA9 but stays above EMA20
            long_pullback = current_close < ema9_val and current_close > ema20_val

            # Pullback condition for Short: Price pops near/above EMA9 but stays below EMA20
            short_pullback = current_close > ema9_val and current_close < ema20_val

            # --- Logic for Entering Positions ---
            if not currently_invested:
                target_stake = 0 # Default to no action
                if is_uptrend_condition and long_pullback:
                    # Enter Long
                    log(f"LONG ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = 0.10 # Allocate 10% of capital
                elif is_downtrend_condition and short_pullback:
                    # Enter Short (Using negative stake for shorting)
                    log(f"SHORT ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = -0.10 # Allocate 10% capital to short

                allocation_dict[ticker] = target_stake

            # --- Logic for Exiting Positions ---
            elif currently_invested:
                exit_signal = False

                # Stop Loss Exit (Primary Risk Control based on EMA20)
                if current_holding > 0 and current_close < ema20_val: # Long position stop loss
                    log(f"STOP LOSS (Long): {ticker} exit at {current_close:.2f}. Stop level: {ema20_val:.2f}")
                    exit_signal = True
                elif current_holding < 0 and current_close > ema20_val: # Short position stop loss
                    log(f"STOP LOSS (Short): {ticker} exit at {current_close:.2f}. Stop level: {ema20_val:.2f}")
                    exit_signal = True

                # Trend Reversal Exit (Secondary Exit Condition)
                if not exit_signal:
                    if current_holding > 0: # Currently Long
                       # Exit long if trend conditions break (price < VWAP OR EMA9 < EMA20)
                       if current_close < vwap_val or ema9_val < ema20_val:
                           log(f"EXIT LONG (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True
                    elif current_holding < 0: # Currently Short
                       # Exit short if trend conditions break (price > VWAP OR EMA9 > EMA20)
                       if current_close > vwap_val or ema9_val > ema20_val:
                           log(f"EXIT SHORT (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True

                # Apply exit signal if triggered
                if exit_signal:
                    allocation_dict[ticker] = 0 # Signal to close position
                else:
                    # No exit signal, maintain current holding
                    allocation_dict[ticker] = current_holding

            # --- Maintain Allocation if No Signal ---
            # Ensure allocation is set if no entry/exit logic above triggered it
            # (e.g., already invested and no exit signal, or not invested and no entry signal)
            if ticker not in allocation_dict:
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0)

        # --- Return Target Allocation ---
        # Ensure all assets defined in self.tickers have an allocation entry (even if 0)
        final_allocation = {ticker: allocation_dict.get(ticker, data["holdings"].get(ticker, 0)) for ticker in self.tickers}

        return TargetAllocation(final_allocation)