"""
graph_model.py — Spatial-Temporal Graph Convolutional Network (ST-GCN) for Inter-Stock Correlation.

Architecture Overview:
  ┌──────────────────────────────────────────────────────────────┐
  │  N Stocks × 4 node features                                  │
  │    [meta_score, tcn_prob, lgbm_bull_prob, garch_vol]        │
  │                   ↓                                          │
  │  Adjacency Matrix A (N×N)  — edge weights                   │
  │    Rolling 252-day Pearson correlation + Sector Prior Blend  │
  │    Kipf & Welling (2017) symmetric normalization             │
  │                   ↓                                          │
  │  GCN Layer 1: ReLU(A_hat · H · W1)                          │
  │                   ↓  Inverted Dropout                        │
  │  GCN Layer 2: Linear(A_hat · H1 · W2)                       │
  │                   ↓                                          │
  │  Readout: Dense(out_dim → 1) → tanh → Δ ∈ [-1, 1]          │
  │                   ↓                                          │
  │  Final Score = clip(MetaScore + Δ × MAX_ADJ, 0, 100)        │
  └──────────────────────────────────────────────────────────────┘

Key Design Decisions (v2 — Refined):
  1. PURE NUMPY ADAM OPTIMIZER — Replaces vanilla SGD with Adam (momentum-based),
     significantly improving convergence in small-N financial graph settings.
  2. SAFE NORMALIZATION — Isolated nodes (degree=0) are handled with safe
     reciprocal computation to prevent inf/nan in D^(-1/2).
  3. 4 NODE FEATURES — Adds lgbm_bull_prob alongside meta_score, tcn_prob,
     and garch_vol for richer per-node embedding.
  4. SECTOR-AWARE SOFT PRIORS — Sector co-membership matrix blended as prior,
     giving stronger initial edges between same-sector stocks.
  5. ROLLING CORRELATION GRAPH — 252-day Pearson window. Only correlations
     above the threshold (default: 0.4) form edges.
  6. INTEGRATION — GCN is a POST-HOC REFINEMENT layer, not a replacement:
       MetaLearner score (0-100)  +  GCN adjustment Δ  =  Refined score (0-100)

Paper Citation Context:
  Based on: Kipf & Welling (2017) "Semi-Supervised Classification with GCNs" — ICLR.
  And:      Feng et al. (2019) "Temporal Relational Ranking for Stock Prediction" — ACM TOIS.
  And:      Zhao et al. (2020) "Temporal GCN for Dynamic Network Prediction" — IEEE TNNLS.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Graph Construction ────────────────────────────────────────────────────────

class StockCorrelationGraph:
    """
    Builds and maintains a dynamic stock correlation graph.

    Nodes  : Each ticker is one node.
    Edges  : Pearson correlation of rolling daily returns (252-day window).
    Weights: r ∈ [threshold, 1.0]. Negative correlations form no edges —
             negative adjacency values destabilise GCN message-passing.

    Usage:
        graph = StockCorrelationGraph(tickers)
        graph.fit(returns_df)
        A_hat = graph.adjacency_matrix    # Kipf-normalized (N × N)
        C_raw = graph.raw_correlation     # Raw Pearson matrix (N × N)
    """

    def __init__(
        self,
        tickers: list,
        correlation_window: int = 252,
        edge_threshold: float = 0.4,
        sector_map: Optional[dict] = None,
        sector_prior_weight: float = 0.15,
    ):
        """
        Args:
            tickers            : List of ticker symbols (defines node ordering).
            correlation_window : Rolling window in trading days for edge weights.
            edge_threshold     : Minimum Pearson r to form an edge. Edges below
                                 this threshold are pruned (set to 0).
            sector_map         : Optional {ticker: sector_name}. Co-sector pairs
                                 receive a bonus edge weight as a soft prior.
            sector_prior_weight: How much the sector prior is blended in [0, 1].
                                 0 = no prior, 1 = fully sector-based.
        """
        self.tickers             = list(tickers)
        self.n                   = len(tickers)
        self.ticker_idx          = {t: i for i, t in enumerate(tickers)}
        self.correlation_window  = correlation_window
        self.edge_threshold      = edge_threshold
        self.sector_map          = sector_map or {}
        self.sector_prior_weight = sector_prior_weight

        self.raw_correlation: Optional[np.ndarray] = None
        self.adjacency_matrix: Optional[np.ndarray] = None
        self.is_fitted: bool = False

    # ── Private Helpers ───────────────────────────────────────────────────

    def _build_sector_prior(self) -> np.ndarray:
        """
        Build an N×N binary sector co-membership matrix S.
        S[i,j] = 1.0 if stock i and stock j share the same sector, else 0.
        Diagonal (self-loops) excluded — they are added in normalization.
        """
        S = np.zeros((self.n, self.n), dtype=np.float32)
        for i, ti in enumerate(self.tickers):
            for j, tj in enumerate(self.tickers):
                if i != j:
                    si = self.sector_map.get(ti)
                    sj = self.sector_map.get(tj)
                    if si and sj and si == sj:
                        S[i, j] = 1.0
        return S

    def _normalize_adjacency(self, A: np.ndarray) -> np.ndarray:
        """
        Kipf & Welling (2017) symmetric normalization:
            Â = D^(-1/2) · (A + I) · D^(-1/2)

        Adds self-loops (I) before normalization. Isolated nodes (degree=0)
        are handled safely: D^(-1/2) is set to 0 for zero-degree nodes
        instead of producing inf.

        Args:
            A: Raw adjacency matrix (N × N), no self-loops.

        Returns:
            A_hat: Normalized adjacency (N × N), float32.
        """
        A_tilde = A + np.eye(self.n, dtype=np.float32)          # Add self-loops: Ã
        degree  = np.sum(A_tilde, axis=1)                         # Row sums: d_i
        # Safe reciprocal: 1/sqrt(d) = 0 where d=0 (isolated nodes)
        d_inv_sqrt = np.where(degree > 0, np.power(degree, -0.5), 0.0)
        D_inv_sqrt = np.diag(d_inv_sqrt)
        A_hat = D_inv_sqrt @ A_tilde @ D_inv_sqrt
        return A_hat.astype(np.float32)

    # ── Public API ────────────────────────────────────────────────────────

    def fit(self, returns_df: pd.DataFrame) -> "StockCorrelationGraph":
        """
        Compute the rolling Pearson correlation matrix and build the graph.

        Args:
            returns_df: pd.DataFrame — columns = tickers, rows = trading days,
                        values = daily returns (pct_change). Missing tickers
                        get only a self-loop (identity row) in the graph.

        Returns:
            self (fitted)
        """
        available = [t for t in self.tickers if t in returns_df.columns]
        missing   = [t for t in self.tickers if t not in returns_df.columns]

        if missing:
            logger.warning(f"  [GCN] No return data for: {missing}. They get identity rows.")

        # Step 1: Pearson correlation on the last `correlation_window` rows
        recent       = returns_df[available].tail(self.correlation_window).dropna(how="all")
        corr_partial = recent.corr().values.astype(np.float32)  # (|available| × |available|)

        # Step 2: Build full N×N correlation matrix, identity for missing tickers
        C_full    = np.eye(self.n, dtype=np.float32)
        avail_idx = [self.ticker_idx[t] for t in available]
        for ii, gi in enumerate(avail_idx):
            for jj, gj in enumerate(avail_idx):
                val = corr_partial[ii, jj]
                C_full[gi, gj] = val if np.isfinite(val) else (1.0 if ii == jj else 0.0)

        # Store raw (not modified in place later)
        self.raw_correlation = C_full.copy()

        # Step 3: Threshold — keep only strong positive correlations as edges
        A = np.where(C_full >= self.edge_threshold, C_full, 0.0).astype(np.float32)
        np.fill_diagonal(A, 0.0)  # Self-loops excluded before normalization

        # Step 4: Blend with sector prior (soft structural knowledge)
        if self.sector_map:
            S = self._build_sector_prior()
            A = (1.0 - self.sector_prior_weight) * A + self.sector_prior_weight * S
            A = np.clip(A, 0.0, 1.0)

        # Step 5: Symmetric Kipf normalization
        self.adjacency_matrix = self._normalize_adjacency(A)
        self.is_fitted = True

        edge_count = int(np.sum(A > 0))
        density    = edge_count / max(self.n * (self.n - 1), 1)
        logger.info(
            f"  [GCN] Graph: {self.n} nodes | {edge_count} edges | "
            f"density={density:.3f} | threshold={self.edge_threshold}"
        )
        print(
            f"  [GCN] Graph: {self.n} nodes | {edge_count} edges | "
            f"density={density:.3f} | threshold={self.edge_threshold}"
        )
        return self

    def get_correlation_heatmap_data(self) -> tuple:
        """
        Returns (tickers, raw_correlation_matrix) for plotting a heatmap figure.
        The returned matrix is a COPY — safe to modify for plotting.
        """
        if self.raw_correlation is None:
            return self.tickers, None
        return self.tickers, self.raw_correlation.copy()


# ── GCN Layer (Pure NumPy) ────────────────────────────────────────────────────

def gcn_layer(
    H: np.ndarray,
    A_hat: np.ndarray,
    W: np.ndarray,
    b: np.ndarray,
    activation: str = "relu",
) -> np.ndarray:
    """
    One Graph Convolutional Layer (Kipf & Welling, 2017) with bias.

    Computes: H_out = activation(A_hat · H · W + b)

    Message-passing step (A_hat · H) aggregates each node's feature vector
    with a weighted sum of its neighbours' features, scaled by correlation
    strength. This is what allows each stock to "hear" its correlated peers.

    Args:
        H         : (N, in_dim)   — node feature matrix
        A_hat     : (N, N)        — Kipf-normalized adjacency
        W         : (in_dim, out_dim) — weight matrix
        b         : (out_dim,)    — bias vector
        activation: 'relu' or 'linear'

    Returns:
        H_out: (N, out_dim) — updated node features
    """
    support = H @ W + b              # (N, out_dim) — linear transform + bias
    H_out   = A_hat @ support        # (N, out_dim) — graph message-passing

    if activation == "relu":
        H_out = np.maximum(0.0, H_out)

    return H_out.astype(np.float32), support.astype(np.float32)


# ── Adam Optimizer State ──────────────────────────────────────────────────────

class AdamState:
    """
    Lightweight Adam optimizer state for a single weight tensor.
    Replaces vanilla SGD — significantly improves convergence on small graphs
    where the gradient signal is noisy.

    Implements: Kingma & Ba (2015) — "Adam: A Method for Stochastic Optimization"
    """

    def __init__(self, shape: tuple, lr: float = 0.01, beta1: float = 0.9,
                 beta2: float = 0.999, eps: float = 1e-8):
        self.lr    = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps   = eps
        self.m     = np.zeros(shape, dtype=np.float32)  # 1st moment (mean)
        self.v     = np.zeros(shape, dtype=np.float32)  # 2nd moment (variance)
        self.t     = 0                                    # Timestep

    def step(self, W: np.ndarray, grad: np.ndarray) -> np.ndarray:
        """Apply one Adam update to weight W given gradient grad. Returns updated W."""
        self.t  += 1
        self.m   = self.beta1 * self.m + (1 - self.beta1) * grad
        self.v   = self.beta2 * self.v + (1 - self.beta2) * (grad ** 2)
        m_hat    = self.m / (1 - self.beta1 ** self.t)   # Bias correction
        v_hat    = self.v / (1 - self.beta2 ** self.t)
        return W - self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


# ── GCN Encoder (2-Layer with Adam) ──────────────────────────────────────────

class GCNEncoder:
    """
    Lightweight 2-layer GCN encoder with Adam optimiser.

    Takes node features for ALL stocks simultaneously, runs two rounds of
    message-passing, and outputs a scalar adjustment Δ ∈ [-1, 1] per node.

    This is a TRANSDUCTIVE model — it must see all nodes at once.
    Training is supervised: it minimises MSE between Δ and the true
    normalised next-day return for each stock.

    Paper description:
        "GCN-Augmented Ensemble: A 2-layer GCN propagates peer-stock signals
         through the dynamic correlation graph, allowing each stock's prediction
         to benefit from simultaneous cross-market context."
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 32,
        out_dim: int = 16,
        dropout: float = 0.2,
        lr: float = 0.01,
    ):
        self.in_dim     = in_dim
        self.hidden_dim = hidden_dim
        self.out_dim    = out_dim
        self.dropout    = dropout
        self.lr         = lr
        self.is_fitted  = False

        # Xavier (Glorot) uniform initialization
        self.W1 = self._xavier(in_dim, hidden_dim)
        self.b1 = np.zeros((hidden_dim,), dtype=np.float32)
        self.W2 = self._xavier(hidden_dim, out_dim)
        self.b2 = np.zeros((out_dim,), dtype=np.float32)
        self.W_readout = self._xavier(out_dim, 1)
        self.b_readout = np.zeros((1,), dtype=np.float32)
        
        # GAT Attention Weights
        self.W_attn = self._xavier(in_dim, in_dim)

        # Adam optimizer states — one per parameter tensor
        self._adam_W1        = AdamState(self.W1.shape,        lr=lr)
        self._adam_b1        = AdamState(self.b1.shape,        lr=lr)
        self._adam_W2        = AdamState(self.W2.shape,        lr=lr)
        self._adam_b2        = AdamState(self.b2.shape,        lr=lr)
        self._adam_Wr        = AdamState(self.W_readout.shape, lr=lr)
        self._adam_br        = AdamState(self.b_readout.shape, lr=lr)
        self._adam_Wa        = AdamState(self.W_attn.shape,    lr=lr)

    @staticmethod
    def _xavier(fan_in: int, fan_out: int) -> np.ndarray:
        """Xavier uniform init: ensures activations have unit variance at init."""
        limit = np.sqrt(6.0 / (fan_in + fan_out))
        return np.random.uniform(-limit, limit, (fan_in, fan_out)).astype(np.float32)

    # ── Forward Pass ──────────────────────────────────────────────────────

    def _forward(self, A_hat: np.ndarray, H: np.ndarray, training: bool = False):
        """
        Full forward pass. Returns (out, cache).
        All intermediate tensors stored for use in backward pass.

        Args:
            A_hat   : (N, N) normalized adjacency
            H       : (N, in_dim) node feature matrix
            training: If True, applies inverted Bernoulli dropout on H1

        Returns:
            out: (N,) predictions in [-1, 1]
            cache: dict of intermediates for backward pass
        """
        # ── Graph Attention (GAT) Mechanism ──
        # Computes dynamic attention weights masked by the correlation graph.
        S = H @ self.W_attn @ H.T                               # (N, N)
        sigma = 1.0 / (1.0 + np.exp(-S))                        # Sigmoid activation
        Alpha = A_hat * sigma                                   # Mask with A_hat

        # Layer 1
        H1, support1 = gcn_layer(H, Alpha, self.W1, self.b1, activation="relu")

        # Inverted dropout
        mask = np.ones_like(H1)
        if training and self.dropout > 0:
            mask    = (np.random.rand(*H1.shape) > self.dropout).astype(np.float32)
            H1_drop = H1 * mask / (1.0 - self.dropout + 1e-9)
        else:
            H1_drop = H1

        # Layer 2
        H2, support2  = gcn_layer(H1_drop, Alpha, self.W2, self.b2, activation="linear")
        raw = H2 @ self.W_readout + self.b_readout                                 # (N, 1)
        out = np.tanh(raw).flatten()                                                # (N,)

        cache = dict(
            H=H, Alpha=Alpha, sigma=sigma, S=S,
            H1=H1, support1=support1, H1_drop=H1_drop, mask=mask,
            H2=H2, support2=support2, raw=raw, out=out
        )
        return out, cache

    # ── Training ──────────────────────────────────────────────────────────

    def fit(
        self,
        A_hat: np.ndarray,
        H: np.ndarray,
        labels: np.ndarray,
        epochs: int = 150,
    ) -> "GCNEncoder":
        """
        Supervised GCN training using Adam optimiser and MSE loss.

        Args:
            A_hat  : (N, N) normalized adjacency matrix
            H      : (N, in_dim) node feature matrix
            labels : (N,) normalised next-day returns in [-1, 1]
            epochs : Training iterations

        Returns:
            self (fitted)
        """
        logger.info(f"  [GCN] Training 2-layer GCN with Adam ({epochs} epochs)...")
        N = len(labels)

        for epoch in range(epochs):
            # ── Forward ────────────────────────────────────────────────
            out, cache = self._forward(A_hat, H, training=True)
            H1, H1_drop, mask, H2 = cache["H1"], cache["H1_drop"], cache["mask"], cache["H2"]
            support1, support2 = cache["support1"], cache["support2"]
            Alpha, sigma, S = cache["Alpha"], cache["sigma"], cache["S"]

            loss = float(np.mean((out - labels) ** 2))

            # ── Backward (analytical chain rule) ───────────────────────
            # dL/d_out
            d_out     = 2.0 * (out - labels) / N                    # (N,)
            # Through tanh: d(tanh)/dx = 1 - tanh^2
            d_raw     = (1.0 - out ** 2) * d_out                    # (N,)
            d_raw_mat = d_raw.reshape(-1, 1)                         # (N, 1)

            # Readout layer
            dW_r = H2.T @ d_raw_mat                                  # (out, 1)
            db_r = d_raw_mat.sum(axis=0)                             # (1,)
            dH2  = d_raw_mat @ self.W_readout.T                      # (N, out)

            # Layer 2 (linear)
            dSupport2 = Alpha.T @ dH2                                # (N, out)
            dW2       = H1_drop.T @ dSupport2                        # (hidden, out)
            db2       = dSupport2.sum(axis=0)                        # (out,)

            # Back through dropout
            dH1_drop  = dSupport2 @ self.W2.T                        # (N, hidden)
            dH1_no_dp = dH1_drop * mask / (1.0 - self.dropout + 1e-9)

            # Back through ReLU
            dH1_relu  = dH1_no_dp * (H1 > 0).astype(np.float32)

            # Layer 1
            dSupport1 = Alpha.T @ dH1_relu                           # (N, hidden)
            dW1       = H.T @ dSupport1                              # (in, hidden)
            db1       = dSupport1.sum(axis=0)                        # (hidden,)
            
            # ── GAT Attention Backward ──────────────────────────────────
            # Alpha is used in both layers: H1 = Alpha @ support1 and H2 = Alpha @ support2
            dAlpha = dH2 @ support2.T + dH1_relu @ support1.T        # (N, N)
            
            dSigma = dAlpha * A_hat                                  # (N, N)
            dS     = dSigma * sigma * (1.0 - sigma)                  # (N, N)
            dW_attn = H.T @ dS @ H                                   # (in_dim, in_dim)

            # ── Adam updates ───────────────────────────────────────────
            self.W1        = self._adam_W1.step(self.W1,        dW1)
            self.b1        = self._adam_b1.step(self.b1,        db1)
            self.W2        = self._adam_W2.step(self.W2,        dW2)
            self.b2        = self._adam_b2.step(self.b2,        db2)
            self.W_readout = self._adam_Wr.step(self.W_readout, dW_r)
            self.b_readout = self._adam_br.step(self.b_readout, db_r)
            self.W_attn    = self._adam_Wa.step(self.W_attn,    dW_attn)

            if epoch % 30 == 0:
                logger.info(f"    [GCN] Epoch {epoch:3d} | MSE: {loss:.5f}")

        self.is_fitted = True
        logger.info(f"  [GCN] Training complete. Final MSE: {loss:.5f}")
        return self

    def forward(self, A_hat: np.ndarray, H: np.ndarray, training: bool = False) -> np.ndarray:
        """
        Inference forward pass. Returns per-node adjustment Δ ∈ [-1, 1].

        Args:
            A_hat   : (N, N) normalized adjacency
            H       : (N, in_dim) node feature matrix
            training: Set True for MC inference (dropout stays on)

        Returns:
            adjustments: (N,) float array
        """
        out, _ = self._forward(A_hat, H, training=training)
        return out


# ── GCN Refinement Module ─────────────────────────────────────────────────────

class GCNRefinementModule:
    """
    High-level interface: wraps StockCorrelationGraph + GCNEncoder.

    Provides a clean `refine_scores()` API consumed by main.py.

        refined = gcn_module.refine_scores(meta_scores, tcn_probs,
                                           lgbm_bull_probs, garch_vols)

    Architecture (paper Section IV-E):
        Stage 8 — GCN-Augmented Ensemble Refinement
          Input : {ticker: meta_score(0-100)} + node features
          Output: {ticker: gcn_refined_score(0-100)}

    Usage:
        gcn = GCNRefinementModule(tickers, sector_map)
        gcn.fit(returns_df, meta_scores, tcn_probs, lgbm_bull_probs, garch_vols, labels)
        refined = gcn.refine_scores(meta_scores, tcn_probs, lgbm_bull_probs, garch_vols)
    """

    MAX_ADJUSTMENT = 10.0   # Max ±Δ the GCN can apply to the MetaLearner score

    def __init__(
        self,
        tickers: list,
        sector_map: Optional[dict] = None,
        correlation_window: int = 252,
        edge_threshold: float = 0.4,
        hidden_dim: int = 32,
        out_dim: int = 16,
        dropout: float = 0.2,
        lr: float = 0.01,
    ):
        self.tickers = list(tickers)
        self.n       = len(tickers)

        self.graph = StockCorrelationGraph(
            tickers=tickers,
            correlation_window=correlation_window,
            edge_threshold=edge_threshold,
            sector_map=sector_map,
        )
        self.encoder    = None
        self.hidden_dim = hidden_dim
        self.out_dim    = out_dim
        self.dropout    = dropout
        self.lr         = lr
        self.is_fitted  = False

    # ── Node Feature Construction ─────────────────────────────────────────

    def build_node_features(
        self,
        meta_scores:     dict,
        tcn_probs:       dict,
        lgbm_bull_probs: dict,
        garch_vols:      dict,
    ) -> np.ndarray:
        """
        Build the (N, 4) node feature matrix H.

        4 node features per stock:
            [0] meta_score_norm    : MetaLearner score normalised to [0, 1]
            [1] tcn_prob           : TCN bullish probability [0, 1]
            [2] lgbm_bull_prob     : LightGBM Strong Buy + Buy probability [0, 1]
            [3] garch_vol_norm     : GARCH conditional volatility, normalised [0, 1]

        Args:
            meta_scores    : {ticker: float (0-100)}
            tcn_probs      : {ticker: float (0-1)}
            lgbm_bull_probs: {ticker: float (0-1)}
            garch_vols     : {ticker: float (raw conditional volatility)}

        Returns:
            H: np.ndarray shape (N, 4), float32
        """
        max_vol = max((v for v in garch_vols.values() if np.isfinite(v)), default=1.0) or 1.0
        H = np.zeros((self.n, 4), dtype=np.float32)

        for i, ticker in enumerate(self.tickers):
            H[i, 0] = np.clip(meta_scores.get(ticker,     50.0) / 100.0, 0.0, 1.0)
            H[i, 1] = np.clip(tcn_probs.get(ticker,       0.5),           0.0, 1.0)
            H[i, 2] = np.clip(lgbm_bull_probs.get(ticker, 0.5),           0.0, 1.0)
            H[i, 3] = np.clip(garch_vols.get(ticker,      0.0) / max_vol, 0.0, 1.0)

        return H

    # ── Fit ───────────────────────────────────────────────────────────────

    def fit(
        self,
        returns_df:      pd.DataFrame,
        meta_scores:     dict,
        tcn_probs:       dict,
        lgbm_bull_probs: dict,
        garch_vols:      dict,
        labels:          np.ndarray,
        epochs:          int = 150,
    ) -> "GCNRefinementModule":
        """
        Build the correlation graph and train the GCN encoder.

        Args:
            returns_df      : Daily returns DataFrame (columns = tickers)
            meta_scores     : {ticker: float (0-100)}
            tcn_probs       : {ticker: float (0-1)}
            lgbm_bull_probs : {ticker: float (0-1)}
            garch_vols      : {ticker: float}
            labels          : (N,) true next-day returns normalised to [-1, 1]
            epochs          : GCN training epochs

        Returns:
            self (fitted)
        """
        print("\n  [GCN] Building Correlation Graph...")
        self.graph.fit(returns_df)

        H = self.build_node_features(meta_scores, tcn_probs, lgbm_bull_probs, garch_vols)
        in_dim = H.shape[1]   # 4

        self.encoder = GCNEncoder(
            in_dim=in_dim,
            hidden_dim=self.hidden_dim,
            out_dim=self.out_dim,
            dropout=self.dropout,
            lr=self.lr,
        )

        print(f"  [GCN] Training Encoder ({epochs} epochs, Adam, lr={self.lr})...")
        self.encoder.fit(
            A_hat=self.graph.adjacency_matrix,
            H=H,
            labels=labels,
            epochs=epochs,
        )

        self.is_fitted = True
        return self

    # ── Inference ─────────────────────────────────────────────────────────

    def refine_scores(
        self,
        meta_scores:     dict,
        tcn_probs:       dict,
        lgbm_bull_probs: dict,
        garch_vols:      dict,
        mc_passes:       int = 1,
    ) -> dict:
        """
        Apply GCN-based refinement to MetaLearner scores.

        Single pass (mc_passes=1): deterministic refinement.
        Multiple passes (mc_passes>1): MC inference — returns (mean, std) tuples.

        Args:
            meta_scores    : {ticker: float (0-100)}
            tcn_probs      : {ticker: float (0-1)}
            lgbm_bull_probs: {ticker: float (0-1)}
            garch_vols     : {ticker: float}
            mc_passes      : Number of MC dropout passes (>1 for uncertainty)

        Returns:
            If mc_passes == 1: {ticker: refined_score (float, 0-100)}
            If mc_passes  > 1: {ticker: (mean_score, uncertainty_std)}
        """
        if not self.is_fitted:
            logger.warning("  [GCN] Not fitted — returning original scores.")
            return dict(meta_scores)

        H     = self.build_node_features(meta_scores, tcn_probs, lgbm_bull_probs, garch_vols)
        A_hat = self.graph.adjacency_matrix

        if mc_passes <= 1:
            adjustments = self.encoder.forward(A_hat, H, training=False)
            refined = {}
            for i, ticker in enumerate(self.tickers):
                if ticker in meta_scores:
                    delta = float(adjustments[i]) * self.MAX_ADJUSTMENT
                    new   = float(np.clip(meta_scores[ticker] + delta, 0.0, 100.0))
                    refined[ticker] = new
                    logger.info(f"  [GCN] {ticker}: {meta_scores[ticker]:.1f} → {new:.1f} (Δ={delta:+.2f})")
            return refined
        else:
            # MC inference — stack N passes into one array
            all_adj = np.stack(
                [self.encoder.forward(A_hat, H, training=True) for _ in range(mc_passes)],
                axis=0,
            )  # (mc_passes, N)
            refined = {}
            for i, ticker in enumerate(self.tickers):
                if ticker in meta_scores:
                    mc_sc = np.clip(
                        meta_scores[ticker] + all_adj[:, i] * self.MAX_ADJUSTMENT,
                        0.0, 100.0,
                    )
                    refined[ticker] = (float(np.mean(mc_sc)), float(np.std(mc_sc)))
            return refined

    # ── Diagnostics ───────────────────────────────────────────────────────

    def get_graph_summary(self) -> dict:
        """
        Return summary statistics of the fitted graph.
        Safe to call after fit(). Does NOT modify stored matrices.
        """
        if not self.is_fitted:
            return {"status": "not_fitted"}

        A = self.graph.adjacency_matrix
        C = self.graph.raw_correlation.copy()   # Copy — do NOT modify in place
        np.fill_diagonal(C, np.nan)             # Exclude self-correlations

        return {
            "num_nodes":          self.n,
            "num_edges":          int(np.sum(A > 0)),
            "avg_degree":         float(np.mean(np.sum(A > 0, axis=1))),
            "mean_abs_corr":      float(np.nanmean(np.abs(C))),
            "max_abs_corr":       float(np.nanmax(np.abs(C))),
            "graph_density":      float(np.sum(A > 0)) / max(self.n * (self.n - 1), 1),
            "edge_threshold":     self.graph.edge_threshold,
            "correlation_window": self.graph.correlation_window,
        }


# ── Convenience Functions ─────────────────────────────────────────────────────

def build_returns_df(data_dict: dict) -> pd.DataFrame:
    """
    Build a daily returns DataFrame from the pipeline's data dict.

    Args:
        data_dict: {ticker: pd.DataFrame with 'Close' column}

    Returns:
        returns_df: pd.DataFrame — columns = tickers, values = pct_change.
                    Inner-joined by date; rows with all-NaN dropped.
    """
    series = {}
    for ticker, df in data_dict.items():
        if "Close" in df.columns:
            series[ticker] = df["Close"].pct_change()

    if not series:
        return pd.DataFrame()

    return pd.DataFrame(series).dropna(how="all")


def get_nse_sector_map() -> dict:
    """
    Sector map for all NSE training tickers defined in config.py.
    Used as the structural prior for the GCN graph construction.
    Foreign tickers (US/UK/EU) not present here receive no sector prior.

    Returns:
        {ticker: sector_name}
    """
    return {
        # IT
        "TCS.NS":       "IT",      "INFY.NS":      "IT",
        "HCLTECH.NS":   "IT",      "TECHM.NS":     "IT",
        "WIPRO.NS":     "IT",
        # Banking
        "HDFCBANK.NS":  "Banking", "ICICIBANK.NS": "Banking",
        "SBIN.NS":      "Banking", "AXISBANK.NS":  "Banking",
        "KOTAKBANK.NS": "Banking", "INDUSINDBK.NS":"Banking",
        # NBFC / Insurance
        "BAJFINANCE.NS":"NBFC",    "BAJAJFINSV.NS":"NBFC",
        "HDFCLIFE.NS":  "Insurance","SBILIFE.NS":  "Insurance",
        # Energy
        "RELIANCE.NS":  "Energy",  "ONGC.NS":      "Energy",
        "BPCL.NS":      "Energy",
        # Automobiles
        "M&M.NS":       "Auto",    "MARUTI.NS":    "Auto",
        "EICHERMOT.NS": "Auto",    "HEROMOTOCO.NS":"Auto",
        "BAJAJ-AUTO.NS":"Auto",
        # Pharmaceuticals
        "SUNPHARMA.NS": "Pharma",  "CIPLA.NS":     "Pharma",
        "DRREDDY.NS":   "Pharma",  "DIVISLAB.NS":  "Pharma",
        "APOLLOHOSP.NS":"Pharma",
        # FMCG
        "ITC.NS":       "FMCG",    "HINDUNILVR.NS":"FMCG",
        "NESTLEIND.NS": "FMCG",    "BRITANNIA.NS": "FMCG",
        "TATACONSUM.NS":"FMCG",
        # Metals
        "TATASTEEL.NS": "Metals",  "HINDALCO.NS":  "Metals",
        "JSWSTEEL.NS":  "Metals",
        # Infrastructure / Utilities
        "LT.NS":        "Infra",   "NTPC.NS":      "Utilities",
        "POWERGRID.NS": "Utilities","COALINDIA.NS": "Utilities",
        # Cement
        "ULTRACEMCO.NS":"Cement",  "GRASIM.NS":    "Cement",
        "SHREECEM.NS":  "Cement",
        # Telecom / Conglomerates
        "BHARTIARTL.NS":"Telecom", "ADANIENT.NS":  "Conglomerate",
        "ADANIPORTS.NS":"Ports",   "UPL.NS":       "Chemicals",
        # Consumer Discretionary
        "ASIANPAINT.NS":"Consumer","TITAN.NS":     "Consumer",
    }
