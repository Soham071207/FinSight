import os
import sys

from main import StockPredictionSystem

if __name__ == "__main__":
    system = StockPredictionSystem(["RELIANCE.NS"])
    system.run()
