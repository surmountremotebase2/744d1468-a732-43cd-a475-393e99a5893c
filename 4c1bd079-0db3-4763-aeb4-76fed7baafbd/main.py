# Import necessary components from Surmount
from surmount.base_class import Strategy, TargetAllocation # Correct base class import
from surmount.technical_indicators import EMA, VWAP       # Correct indicator import location
from surmount.logging import log

# Define the strategy class
class TradingStrategy(Strategy):
    def __init__(self):
        # Define the assets to trade
        self.tickers = ["SPY"] # Example: Use SPY ETF (ensure it's a list)
        log("Strategy Initialized.")

    @property
    def interval(self):
        # Use a 5-minute timeframe - CORRECTED STRING
        return "5min" # <--- CORRECTED

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
            ohlcv_data_source = data.get("ohlcv")
            ohlcv = None
            if isinstance(ohlcv_data_source, dict):
                ohlcv = ohlcv_data_source.get(ticker)
            elif isinstance(ohlcv_data_source, list) and len(self.assets) == 1:
                ohlcv = ohlcv_data_source
            else:
                log(f"Warning: Unexpected data structure for ohlcv for {ticker}. Type: {type(ohlcv_data_source)}")

            # --- Data Sufficiency Check ---
            if ohlcv is None or len(ohlcv) < 50: # Need ~50 bars for safety buffer
                log(f"Not enough data or failed to retrieve OHLCV for {ticker} (need ~50 bars)")
                allocation_dict[ticker] = 0
                continue

            # --- Calculate Indicators ---
            historical_data = ohlcv

            ema9_val, ema20_val, vwap_val = None, None, None
            current_close = None

            try:
                # Call indicators directly as functions
                ema9_raw = EMA(ticker=ticker, data=historical_data, length=9)
                ema20_raw = EMA(ticker=ticker, data=historical_data, length=20)
                # Add 'length' argument to VWAP call based on error message
                vwap_raw = VWAP(ticker=ticker, data=historical_data, length=1) # <--- ADDED length=1

                # Extract the latest value
                ema9_val = ema9_raw[-1] if isinstance(ema9_raw, list) and ema9_raw else ema9_raw if isinstance(ema9_raw, (int,float)) else None
                ema20_val = ema20_raw[-1] if isinstance(ema20_raw, list) and ema20_raw else ema20_raw if isinstance(ema20_raw, (int,float)) else None
                vwap_val = vwap_raw[-1] if isinstance(vwap_raw, list) and vwap_raw else vwap_raw if isinstance(vwap_raw, (int,float)) else None

                current_close = historical_data[-1]["close"]

            except Exception as e:
                log(f"Error during indicator calculation or processing for {ticker}: {e}")
                allocation_dict[ticker] = data["holdings"].get(ticker, 0)
                continue

            # --- Validity Check ---
            if not all(isinstance(v, (int, float)) for v in [ema9_val, ema20_val, vwap_val, current_close]):
                 log(f"Indicator/Price values invalid after calculation/extraction for {ticker}. EMA9: {ema9_val}, EMA20: {ema20_val}, VWAP: {vwap_val}, Close: {current_close}")
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