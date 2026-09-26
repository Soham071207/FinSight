import os
import sys
sys.path.append(os.path.dirname(__file__))

import numpy as np
import pandas as pd
import tensorflow as tf
from tcn_model import PositionalEncoding
from graph_model import GCNRefinementModule

def main():
    print("Testing PositionalEncoding...")
    pe = PositionalEncoding()
    inputs = tf.ones((2, 60, 32))
    out = pe(inputs)
    print("  PE out shape:", out.shape)
    assert out.shape == inputs.shape
    
    print("\nTesting GAT...")
    tickers = ["AAPL", "MSFT", "TSLA"]
    meta_scores = {"AAPL": 50, "MSFT": 60, "TSLA": 70}
    tcn_probs = {"AAPL": 0.5, "MSFT": 0.6, "TSLA": 0.7}
    lgbm_probs = {"AAPL": 0.5, "MSFT": 0.6, "TSLA": 0.7}
    garch = {"AAPL": 0.1, "MSFT": 0.2, "TSLA": 0.3}
    labels = np.array([0.5, -0.5, 0.0])

    df = pd.DataFrame({
        "AAPL": [0.01, 0.02, -0.01, 0.03],
        "MSFT": [0.01, 0.02, -0.01, 0.03],
        "TSLA": [-0.01, -0.02, 0.01, -0.03]
    })

    gcn = GCNRefinementModule(tickers=tickers, correlation_window=3)
    gcn.fit(df, meta_scores, tcn_probs, lgbm_probs, garch, labels, epochs=10)
    refined = gcn.refine_scores(meta_scores, tcn_probs, lgbm_probs, garch)
    print("GCN Refined Scores:", refined)
    print("\nAll tests passed!")

if __name__ == "__main__":
    main()
