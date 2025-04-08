# Import necessary components from Surmount
from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import EMA, VWAP
from surmount.logging import log
import traceback # Import for detailed error logging

# Define the strategy class
class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["SPY"] # Define the assets to trade
        log("Strategy Initialized.")

    @property
    def interval(self):
        # Use a 5-minute timeframe
        return "5min" # Correct interval string

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return []

    def run(self, data):
        allocation_dict = {}
        # Get the main OHLCV data structure (list of time steps)
        ohlcv_list = data.get("ohlcv")

        # Data Sufficiency Check
        if ohlcv_list is None or len(ohlcv_list) < 50: # Need history for indicators
            log(f"Not enough historical steps in ohlcv_list (need ~50)")
            for ticker in self.tickers: allocation_dict[ticker] = 0 # Flatten all positions
            return TargetAllocation(allocation_dict)

        for ticker in self.tickers:
            # Initialize variables for this ticker
            ema9_val, ema20_val, vwap_val = None, None, None
            current_close = None

            # Check if ticker exists in the *latest* data point before processing
            # This prevents KeyError if a ticker has partial data at the end
            if ticker not in ohlcv_list[-1]:
                 log(f"Ticker {ticker} not found in the latest data step: {ohlcv_list[-1]}")
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0) # Hold position
                 continue

            try:
                # Pass the entire ohlcv_list (list[dict[ticker->bar]]) to indicators.
                # Assume they internally extract the series for the specified ticker.
                ema9_raw = EMA(ticker=ticker, data=ohlcv_list, length=9)
                ema20_raw = EMA(ticker=ticker, data=ohlcv_list, length=20)
                vwap_raw = VWAP(ticker=ticker, data=ohlcv_list, length=1) # Using length=1 as placeholder

                # Extract the latest value from indicators
                # Assumes list return; adjust if needed. Check type if errors persist.
                ema9_val = ema9_raw[-1] if isinstance(ema9_raw, list) and ema9_raw else ema9_raw if isinstance(ema9_raw, (int,float)) else None
                ema20_val = ema20_raw[-1] if isinstance(ema20_raw, list) and ema20_raw else ema20_raw if isinstance(ema20_raw, (int,float)) else None
                vwap_val = vwap_raw[-1] if isinstance(vwap_raw, list) and vwap_raw else vwap_raw if isinstance(vwap_raw, (int,float)) else None

                # Get the most recent closing price using the correct structure
                # List[-1] -> Dict[ticker] -> Dict["close"] (lowercase based on template)
                current_close = ohlcv_list[-1][ticker]["close"] # <--- CORRECTED ACCESS & KEY CASE

            except Exception as e:
                log(f"Error during indicator calculation or data access for {ticker}: {e}")
                log(f"DEBUG: Exception Type: {type(e)}")
                log(f"DEBUG: Traceback: {traceback.format_exc()}")
                allocation_dict[ticker] = data["holdings"].get(ticker, 0) # Hold position on error
                continue

            # --- Validity Check ---
            if not all(isinstance(v, (int, float)) for v in [ema9_val, ema20_val, vwap_val, current_close]):
                 log(f"Indicator/Price values invalid after calculation for {ticker}. EMA9: {ema9_val}, EMA20: {ema20_val}, VWAP: {vwap_val}, Close: {current_close}")
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0)
                 continue

            # --- Trading Logic ---
            current_holding = data["holdings"].get(ticker, 0)
            currently_invested = abs(current_holding) > 1e-9

            is_uptrend_condition = current_close > vwap_val and ema9_val > ema20_val
            is_downtrend_condition = current_close < vwap_val and ema9_val < ema20_val
            long_pullback = current_close < ema9_val and current_close > ema20_val
            short_pullback = current_close > ema9_val and current_close < ema20_val

            # --- Entry Logic ---
            if not currently_invested:
                target_stake = 0
                if is_uptrend_condition and long_pullback:
                    log(f"LONG ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = 0.10
                elif is_downtrend_condition and short_pullback:
                    log(f"SHORT ENTRY SIGNAL: {ticker} at {current_close:.2f}")
                    target_stake = -0.10
                allocation_dict[ticker] = target_stake

            # --- Exit Logic ---
            elif currently_invested:
                exit_signal = False
                if current_holding > 0 and current_close < ema20_val: # Long SL
                    log(f"STOP LOSS (Long): {ticker} exit at {current_close:.2f}. Stop level: {ema20_val:.2f}")
                    exit_signal = True
                elif current_holding < 0 and current_close > ema20_val: # Short SL
                    log(f"STOP LOSS (Short): {ticker} exit at {current_close:.2f}. Stop level: {ema20_val:.2f}")
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

            # --- Maintain Allocation ---
            if ticker not in allocation_dict:
                 allocation_dict[ticker] = data["holdings"].get(ticker, 0)

        # --- Return Target Allocation ---
        final_allocation = {ticker: allocation_dict.get(ticker, data["holdings"].get(ticker, 0)) for ticker in self.tickers}
        return TargetAllocation(final_allocation)