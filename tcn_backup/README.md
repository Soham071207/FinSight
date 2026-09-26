# TCN Backup — Original Version

This folder contains the **original** `tcn_model.py` (pre-SCI journal upgrade).

## File
| File | Description |
|------|-------------|
| `tcn_model_original.py` | v1 — Dilated TCN with GlobalAveragePooling1D |

## What Changed in v2 (tcn_model.py)

| Aspect | v1 (Original) | v2 (TCN-MHA Hybrid) |
|--------|--------------|----------------------|
| Temporal Aggregation | `GlobalAveragePooling1D` — treats all 60 days equally | `MultiHeadAttention(4 heads)` — learns which days matter most |
| Layer Normalization | `BatchNormalization` (Post-LN in TCN blocks) | `LayerNormalization` (Pre-LN) — more stable for financial data |
| Attention | Claimed in docstring, not implemented | Fully implemented (4-head, key_dim=32) + FFN sublayer |
| Explainability | None | `get_attention_weights()` — exports XAI heatmaps |
| Tuning Search Space | filters, dropout, lr, dense_units | + num_heads, key_dim |
| MC Dropout | `predict_with_uncertainty()` present | Same — preserved |
| EarlyStopping metric | `val_loss` | `val_auc` — more aligned with ranking objective |

## How to Restore
To go back to the original:
```bash
copy tcn_backup\tcn_model_original.py STOCK_experimental\tcn_model.py
```
