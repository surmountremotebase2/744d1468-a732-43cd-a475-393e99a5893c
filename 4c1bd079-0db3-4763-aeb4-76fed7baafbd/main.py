# Import necessary components from Surmount
from surmount.base_strategy import Strategy, TargetAllocation
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
                "ema9": EMA(9),
                "ema20": EMA(20),
                "vwap": VWAP()
            }
        # State variable to track active positions per ticker
        self.invested = {ticker: False for ticker in self.tickers}

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
        signals = []

        for ticker in self.tickers:
            # Get OHLCV data for the ticker
            ohlcv = data["ohlcv"].get(ticker)

            # Ensure we have enough data points for indicators (e.g., at least 20 for EMA20)
            if ohlcv is None or len(ohlcv) < 25: # Need buffer for calculation
                log(f"Not enough data for {ticker}")
                allocation_dict[ticker] = 0 # Ensure no position if data is insufficient
                continue # Skip this asset if not enough data

            # Calculate indicator values
            # Use a slice like [-50:] to ensure indicators have enough history but are efficient
            # Adjust slice length based on indicator period + buffer
            historical_data = ohlcv[-50:] # Example slice for calculation
            
            try:
              ema9_val = self.indicators[ticker]["ema9"].calculate(historical_data)
              ema20_val = self.indicators[ticker]["ema20"].calculate(historical_data)
              vwap_val = self.indicators[ticker]["vwap"].calculate(historical_data)
            except Exception as e:
              log(f"Error calculating indicators for {ticker}: {e}")
              allocation_dict[ticker] = 0
              continue # Skip if indicators fail


            # Check if all indicator values are valid numbers
            if ema9_val is None or ema20_val is None or vwap_val is None:
                log(f"Indicator calculation incomplete for {ticker}")
                allocation_dict[ticker] = 0 # Ensure no position if indicators are invalid
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

            # --- Logic for Entering Positions ---
            if not self.invested[ticker]:
                target_stake = 0 # Default to no action
                if is_uptrend_condition and long_pullback:
                    # Enter Long
                    log(f"LONG ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = 0.10 # Allocate 10% of capital
                    self.invested[ticker] = True # Mark as invested
                elif is_downtrend_condition and short_pullback:
                    # Enter Short (Using negative stake for shorting)
                    log(f"SHORT ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = -0.10 # Allocate 10% capital to short
                    self.invested[ticker] = True # Mark as invested
                
                allocation_dict[ticker] = target_stake


            # --- Logic for Exiting Positions ---
            elif self.invested[ticker]:
                current_allocation = data["holdings"].get(ticker, 0) # Get current holding percentage
                exit_signal = False
                
                # Stop Loss Exit (Primary Risk Control)
                if current_allocation > 0 and current_close < ema20_val: # Long position stop loss
                    log(f"STOP LOSS (Long): {ticker} exited at {current_close:.2f}")
                    exit_signal = True
                elif current_allocation < 0 and current_close > ema20_val: # Short position stop loss
                    log(f"STOP LOSS (Short): {ticker} exited at {current_close:.2f}")
                    exit_signal = True

                # Potential Take Profit / Trend Reversal Exit:
                # Exit long if price closes back below EMA9 (after being above on entry trigger region)
                # Exit short if price closes back above EMA9 (after being below on entry trigger region)
                # This is a simple exit logic; can be refined with R:R targets.
                if not exit_signal: # Only check TP if SL not hit
                    if current_allocation > 0 and current_close < ema9_val: 
                       # Let's refine: Exit long if trend conditions break (e.g., price drops below VWAP OR ema9 crosses below ema20)
                       if current_close < vwap_val or ema9_val < ema20_val:
                           log(f"EXIT LONG (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True
                    elif current_allocation < 0 and current_close > ema9_val:
                       # Refine: Exit short if trend conditions break (e.g., price moves above VWAP OR ema9 crosses above ema20)
                       if current_close > vwap_val or ema9_val > ema20_val:
                           log(f"EXIT SHORT (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True

                # If any exit condition is met:
                if exit_signal:
                    allocation_dict[ticker] = 0 # Signal to close position
                    self.invested[ticker] = False # Mark as not invested


            # If no entry/exit signal for an invested asset, maintain position (Surmount handles this by default if not specified)
            # However, explicit 'keep' might be needed depending on platform specifics. Let's ensure we set allocation.
            if ticker not in allocation_dict:
                 # If currently invested and no exit signal, keep the position. Get current allocation.
                 # If not invested and no entry signal, stay flat (0 allocation).
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0)


        # Create TargetAllocation object
        # Check if allocation_dict is empty before creating TargetAllocation
        if not allocation_dict:
            return TargetAllocation({}) # Return empty allocation if no tickers processed
        else:
            # Ensure all assets have an allocation entry (even if 0)
            for ticker in self.tickers:
                if ticker not in allocation_dict:
                    allocation_dict[ticker] = 0 # Default to 0 if not set otherwise
            
            return TargetAllocation(allocation_dict)