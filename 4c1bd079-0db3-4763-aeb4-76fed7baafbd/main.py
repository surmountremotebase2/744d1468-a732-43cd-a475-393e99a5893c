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

        for ticker in self.tickers:
            # Get OHLCV data for the ticker
            ohlcv = data["ohlcv"].get(ticker)

            # Ensure we have enough data points
            # EMA might need length + ~length points to be stable? Use 50 for safety.
            if ohlcv is None or len(ohlcv) < 50:
                log(f"Not enough data for {ticker} (need ~50 bars)")
                allocation_dict[ticker] = 0
                continue

            # Prepare data slice (use sufficient history)
            historical_data = ohlcv # Pass the full available slice for calculation

            try:
                # Call indicators directly as functions
                # Using keyword arguments based on previous errors
                ema9_val = EMA(ticker=ticker, data=historical_data, length=9)
                ema20_val = EMA(ticker=ticker, data=historical_data, length=20)
                # Assuming VWAP might just need data, maybe ticker too? Start with data.
                # If VWAP fails, the next error will guide us.
                vwap_val = VWAP(ticker=ticker, data=historical_data)

                # --- Important Check: What do these functions return? ---
                # Technical indicators often return a list/series or a dict.
                # We need the *latest* value. Let's assume they return a list
                # and the last element is the most recent value.
                # If they return a dict like {'SPY': [values...]}, adjust accordingly.
                # Check the type and content if errors occur later.
                if isinstance(ema9_val, list) and len(ema9_val) > 0:
                    ema9_val = ema9_val[-1]
                elif isinstance(ema9_val, dict):
                     ema9_val = ema9_val.get(ticker, [None])[-1] # Example if dict format {ticker: [vals]}
                # Add similar checks/extraction logic for ema20_val and vwap_val
                if isinstance(ema20_val, list) and len(ema20_val) > 0:
                     ema20_val = ema20_val[-1]
                elif isinstance(ema20_val, dict):
                     ema20_val = ema20_val.get(ticker, [None])[-1]
                if isinstance(vwap_val, list) and len(vwap_val) > 0:
                     vwap_val = vwap_val[-1]
                elif isinstance(vwap_val, dict):
                     vwap_val = vwap_val.get(ticker, [None])[-1]


            except Exception as e:
                log(f"Error calculating/processing indicators for {ticker}: {e}")
                log(f"Returned types - EMA9: {type(ema9_val)}, EMA20: {type(ema20_val)}, VWAP: {type(vwap_val)}")
                allocation_dict[ticker] = data["holdings"].get(ticker, 0) # Hold position on error
                continue

            # Check if indicator values are valid numbers AFTER extraction
            if not all(isinstance(v, (int, float)) for v in [ema9_val, ema20_val, vwap_val]):
                log(f"Indicator calculation incomplete or invalid after extraction for {ticker}. EMA9: {ema9_val}, EMA20: {ema20_val}, VWAP: {vwap_val}")
                allocation_dict[ticker] = data["holdings"].get(ticker, 0) # Hold position on error
                continue

            # Get the most recent closing price
            current_close = ohlcv[-1]["close"]

            # --- Define Entry and Exit Conditions ---
            is_uptrend_condition = current_close > vwap_val and ema9_val > ema20_val
            is_downtrend_condition = current_close < vwap_val and ema9_val < ema20_val
            long_pullback = current_close < ema9_val and current_close > ema20_val
            short_pullback = current_close > ema9_val and current_close < ema20_val

            # --- Get Current Holdings ---
            current_holding = data["holdings"].get(ticker, 0)
            currently_invested = abs(current_holding) > 1e-9

            # --- Logic for Entering Positions ---
            if not currently_invested:
                target_stake = 0
                if is_uptrend_condition and long_pullback:
                    log(f"LONG ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = 0.10
                elif is_downtrend_condition and short_pullback:
                    log(f"SHORT ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = -0.10
                allocation_dict[ticker] = target_stake

            # --- Logic for Exiting Positions ---
            elif currently_invested:
                exit_signal = False
                if current_holding > 0 and current_close < ema20_val: # Long SL
                    log(f"STOP LOSS (Long): {ticker} exited at {current_close:.2f}. Stop: {ema20_val:.2f}")
                    exit_signal = True
                elif current_holding < 0 and current_close > ema20_val: # Short SL
                    log(f"STOP LOSS (Short): {ticker} exited at {current_close:.2f}. Stop: {ema20_val:.2f}")
                    exit_signal = True

                if not exit_signal: # Trend Exit Check
                    if current_holding > 0 and (current_close < vwap_val or ema9_val < ema20_val):
                           log(f"EXIT LONG (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True
                    elif current_holding < 0 and (current_close > vwap_val or ema9_val > ema20_val):
                           log(f"EXIT SHORT (Trend Break): {ticker} at {current_close:.2f}")
                           exit_signal = True

                if exit_signal:
                    allocation_dict[ticker] = 0 # Close position
                else:
                    allocation_dict[ticker] = current_holding # Maintain position

            # Ensure allocation is set if no action taken
            if ticker not in allocation_dict:
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0)

        # Create TargetAllocation object
        final_allocation = {ticker: allocation_dict.get(ticker, 0) for ticker in self.tickers}
        return TargetAllocation(final_allocation)