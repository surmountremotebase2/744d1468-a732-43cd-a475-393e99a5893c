# Import necessary components from Surmount (CORRECTED IMPORT)
from surmount.base_class import Strategy, TargetAllocation # <--- CORRECTED
from surmount.technical_indicators import EMA, VWAP
from surmount.logging import log

# Define the strategy class
class TradingStrategy(Strategy):
    def __init__(self):
        # Define the assets to trade
        self.tickers = ["SPY"] # Example: Use SPY ETF
        # Initialize indicators for each ticker
        self.indicators = {}
        for ticker in self.tickers:
            self.indicators[ticker] = {
                # Use keyword argument 'length' for clarity and correctness
                "ema9": EMA(length=9),     # <--- CORRECTED
                "ema20": EMA(length=20),   # <--- CORRECTED
                "vwap": VWAP()             # <--- VWAP typically needs no args here
            }
        # State variable (removed as we use data["holdings"])
        # self.invested = {ticker: False for ticker in self.tickers} # Not needed

    @property
    def interval(self):
        # Use a 2-minute timeframe
        return "2m"

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
        # Removed the 'signals = []' line as it wasn't used

        for ticker in self.tickers:
            # Get OHLCV data for the ticker
            ohlcv = data["ohlcv"].get(ticker)

            # Ensure we have enough data points for indicators (e.g., at least 20 for EMA20)
            if ohlcv is None or len(ohlcv) < 25: # Need buffer for calculation
                log(f"Not enough data for {ticker}")
                allocation_dict[ticker] = 0 # Ensure no position if data is insufficient
                continue # Skip this asset if not enough data

            # Calculate indicator values
            historical_data = ohlcv[-50:] # Example slice for calculation
            
            try:
              # Check if indicators return dictionary (for multi-value indicators) or single value
              ema9_data = self.indicators[ticker]["ema9"].calculate(historical_data)
              ema20_data = self.indicators[ticker]["ema20"].calculate(historical_data)
              vwap_data = self.indicators[ticker]["vwap"].calculate(historical_data)
              
              # Assuming these indicators return a single value. Adjust if they return dicts.
              ema9_val = ema9_data if isinstance(ema9_data, (int, float)) else None 
              ema20_val = ema20_data if isinstance(ema20_data, (int, float)) else None
              vwap_val = vwap_data if isinstance(vwap_data, (int, float)) else None

            except Exception as e:
              log(f"Error calculating indicators for {ticker}: {e}")
              allocation_dict[ticker] = 0
              continue # Skip if indicators fail


            # Check if all indicator values are valid numbers
            # Use check for None explicitly as 0 is a valid value
            if ema9_val is None or ema20_val is None or vwap_val is None:
                log(f"Indicator calculation incomplete or invalid for {ticker}. EMA9: {ema9_val}, EMA20: {ema20_val}, VWAP: {vwap_val}")
                # If already invested, maybe apply exit logic or hold? For now, prevent new entries.
                # If we want to ensure exit on bad data, we'd set allocation_dict[ticker] = 0 here.
                # Let's prevent entry/modification if data is bad. If holding, default keeps holding.
                if ticker not in allocation_dict: # Avoid overwriting exit signals already set
                     allocation_dict[ticker] = data["holdings"].get(ticker, 0) 
                continue

            # Get the most recent closing price
            current_close = ohlcv[-1]["close"]

            # --- Define Entry and Exit Conditions ---
            is_uptrend_condition = current_close > vwap_val and ema9_val > ema20_val
            is_downtrend_condition = current_close < vwap_val and ema9_val < ema20_val

            # Pullback condition for Long: Price dips near/below EMA9 but stays above EMA20
            long_pullback = current_close < ema9_val and current_close > ema20_val

            # Pullback condition for Short: Price pops near/above EMA9 but stays below EMA20
            short_pullback = current_close > ema9_val and current_close < ema20_val

            # --- Get Current Holdings ---
            # Use data["holdings"] for current position status instead of self.invested flag
            current_holding = data["holdings"].get(ticker, 0)
            currently_invested = abs(current_holding) > 1e-9 # Check if holding is non-zero

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
                
                # Stop Loss Exit (Primary Risk Control)
                if current_holding > 0 and current_close < ema20_val: # Long position stop loss
                    log(f"STOP LOSS (Long): {ticker} exited at {current_close:.2f}. Stop: {ema20_val:.2f}")
                    exit_signal = True
                elif current_holding < 0 and current_close > ema20_val: # Short position stop loss
                    log(f"STOP LOSS (Short): {ticker} exited at {current_close:.2f}. Stop: {ema20_val:.2f}")
                    exit_signal = True

                # Trend Reversal Exit:
                if not exit_signal: # Only check TP if SL not hit
                    if current_holding > 0: # Currently Long
                       # Exit long if trend conditions break (e.g., price drops below VWAP OR ema9 crosses below ema20)
                       if current_close < vwap_val or ema9_val < ema20_val:
                           log(f"EXIT LONG (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True
                    elif current_holding < 0: # Currently Short
                       # Exit short if trend conditions break (e.g., price moves above VWAP OR ema9 crosses above ema20)
                       if current_close > vwap_val or ema9_val > ema20_val:
                           log(f"EXIT SHORT (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True

                # If any exit condition is met:
                if exit_signal:
                    allocation_dict[ticker] = 0 # Signal to close position
                else:
                    # No exit signal, maintain current holding
                    allocation_dict[ticker] = current_holding


            # If no entry/exit signal triggered for this ticker, ensure its allocation is defined
            # If not invested and no entry, or invested and no exit, maintain state.
            if ticker not in allocation_dict:
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0)


        # Create TargetAllocation object
        # Ensure all assets defined in self.tickers have an allocation entry (even if 0)
        final_allocation = {ticker: allocation_dict.get(ticker, 0) for ticker in self.tickers}
            
        return TargetAllocation(final_allocation)