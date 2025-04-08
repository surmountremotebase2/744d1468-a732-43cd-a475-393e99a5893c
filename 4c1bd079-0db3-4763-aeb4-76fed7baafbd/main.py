from surmount.base_strategy import Strategy, TargetAllocation
from surmount.logging import log

class TradingStrategy(Strategy):
    @property
    def interval(self):
        return "1day"
    @property
    def assets(self):
        return ["SPY"]
    def run(self, data):
        return TargetAllocation({"SPY": 1.0}) # Just allocate 100% to SPY