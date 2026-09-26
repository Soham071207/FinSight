# PROVISIONAL PATENT APPLICATION DRAFT (LSTM Variant)
(Prepared for submission to the Institutional IPR Cell — pre-filing internal review copy)

## 1. TITLE OF THE INVENTION
“FinSight: An Artificial Intelligence-Powered Unified Personal Finance Management Ecosystem with an Attention-LSTM Stock Prediction Engine”

## 2. INVENTOR AND APPLICANT PARTICULARS
The following individuals are named as inventors based on their contribution to the conception and technical design of the system. Names, addresses and contribution descriptions marked in red require confirmation by all listed persons before filing, and the ownership/assignee position must be confirmed against the institution's IP policy (student vs. institution-owned IP).

## 3. FIELD OF THE INVENTION
The present invention relates generally to the field of financial technology (FinTech), and more particularly to a computer-implemented artificial intelligence (AI) and machine learning (ML) based system and method for unified personal finance management. The invention specifically pertains to (a) a multi-stage stacking-ensemble architecture for predictive stock market signal generation that combines attention-augmented Long Short-Term Memory (LSTM) networks, gradient-boosted tree classifiers, econometric volatility models, and natural language processing (NLP) based sentiment analysis with a calibrated meta-learner; (b) an on-device natural-language/regex based transaction extraction system for private expense tracking; (c) a multi-criteria risk-adjusted mutual fund ranking and simulation engine; and (d) a deterministic, explainable credit-score estimation module.

## 4. BACKGROUND OF THE INVENTION
In the current digital era, retail investors and everyday individuals rely on a fragmented ecosystem of standalone applications to manage personal finances. Existing stock-prediction tools available to retail users typically rely on a single model family evaluated non-deterministically. Such systems frequently fail to jointly account for complex sequence dynamics and weight informative time-steps in price sequences, regime-dependent behaviour of technical indicators, volatility clustering, and concurrent market sentiment. There is a need for a unified system that improves technical accuracy and reproducibility of AI-based stock-trend prediction through a multi-model stacking architecture utilizing attention-augmented Long Short-Term Memory (LSTM) networks.

## 5. OBJECTS OF THE INVENTION
*   To provide a unified, cross-platform personal finance application that integrates AI-based stock prediction, private expense tracking, mutual fund analysis, and credit scoring.
*   To provide a stock-trend prediction module that utilizes an attention-augmented Long Short-Term Memory (LSTM) network for sequence modelling, a global LightGBM classifier that uses market regime as a categorical feature, and a GARCH-family volatility model, combined by a calibrated stacking meta-learner.
*   To improve probability calibration and decision-threshold selection using isotonic regression calibration and a Youden's-J-statistic-optimized classification threshold.
*   To incorporate macroeconomic context and dual-pipeline natural-language-processing sentiment layer.
*   To provide an intelligent, privacy-preserving expense tracker that parses financial SMS notifications entirely on-device.
*   To provide a mutual-fund recommendation engine and a deterministic, explainable credit-score estimation module.

## 6. SUMMARY OF THE INVENTION
**Module 1 — Stacking-Ensemble AI Stock Prediction Engine**
A multi-stage ensemble that generates BUY / SELL / HOLD signals. Base learners comprise an attention-augmented LSTM for sequence/pattern modelling, a single global LightGBM classifier that treats detected market regime as a categorical input feature, and a GARCH-family model for volatility estimation. A dual sentiment pipeline scores aggregated financial news. Base-learner outputs and macro/sector features are combined by a stacking meta-learner.

**Module 2 — Privacy-Preserving On-Device Expense Tracker**
A five-stage regular-expression parsing pipeline that intercepts financial SMS notifications on-device, extracting transaction details with no transmission of message content off-device.

**Module 3 & 4**
A multi-criteria mutual fund recommendation engine using a weighted composite score (XIRR, Risk, Sortino Ratio, Maximum Drawdown), and a deterministic explainable credit score calculator.

## 7. BRIEF DESCRIPTION OF THE ACCOMPANYING DRAWINGS
*   FIG. 1: Overall system architecture.
*   FIG. 2: Data-flow block diagram of the stock prediction pipeline, showing the attention-LSTM, global LightGBM, GARCH branch, sentiment pipeline, and meta-learner.
*   FIG. 3-5: Flowcharts for on-device expense extraction, mutual fund ranking, and credit score calculation.

## 8. DETAILED DESCRIPTION OF THE INVENTION
**8.2 Module 1: Stacking-Ensemble Stock Prediction Engine**
This module implements a multi-stage architecture:
*   **Sequence-modelling base learner:** an attention-augmented LSTM network, trained on historical price/technical-indicator sequences to capture temporal dependencies and to weight the most informative time-steps via the attention mechanism.
*   **Regime-aware tree-based base learner:** a single global LightGBM gradient-boosted classifier trained across all detected market regimes.
*   **Volatility modelling & Sentiment analysis:** GARCH model estimates conditional volatility, and a dual-pipeline NLP subsystem scores financial news.
*   **Meta-learning and calibration:** a stacking meta-learner ingests all outputs, which are then isotonic-calibrated and thresholded using a Youden's-J-statistic-optimized cut-off.

## 9. CLAIMS
**We claim:**
1.  An artificial-intelligence-powered unified personal finance management system comprising an AI-based stock-trend prediction module, an on-device expense-tracking module, a mutual-fund evaluation module, and a credit-score calculation module.
2.  The system as claimed in claim 1, wherein the stock-trend prediction module comprises: an attention-augmented Long Short-Term Memory (LSTM) network as a sequence-modelling base learner; a single global LightGBM classifier; a GARCH volatility model; and a stacking meta-learner.
3.  [Include claims for expense tracking, mutual funds, and credit scoring as originally drafted.]
10. A computer-implemented method for generating a stock-market trend prediction signal comprising: processing sequence data using an attention-augmented Long Short-Term Memory (LSTM) network; classifying market conditions using a global LightGBM classifier; estimating market volatility; generating a sentiment score; and combining outputs via a stacking meta-learner.

## 10. ABSTRACT
A unified personal finance management system (“FinSight”) is disclosed. A stock-trend prediction module combines an attention-augmented LSTM network with a regime-aware global LightGBM classifier, a GARCH volatility model, NLP sentiment analysis, and macroeconomic features, fused via a stacking meta-learner. Additional modules include a privacy-preserving on-device expense tracker, a multi-criteria risk-adjusted mutual fund recommender, and an explainable credit-score module.
