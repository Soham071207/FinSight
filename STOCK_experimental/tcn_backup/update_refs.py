import sys

new_refs = """## REFERENCES

[1] E. Chong, C. Han, and F. C. Park, "Deep Learning Networks for Stock Market Analysis and Prediction," *Expert Systems with Applications*, vol. 83, pp. 187-205, 2017.  
[2] G. Ke et al., "LightGBM: A Highly Efficient Gradient Boosting Decision Tree," *NeurIPS*, vol. 30, pp. 3146-3154, 2017.  
[3] T. Bollerslev, "Generalized Autoregressive Conditional Heteroskedasticity," *Journal of Econometrics*, vol. 31, no. 3, pp. 307-327, 1986.  
[4] J. Marcucci, "Forecasting Stock Market Volatility with Regime-Switching GARCH Models," *Journal of Financial Econometrics*, 2005.  
[5] J. Devlin et al., "BERT: Pre-training of Deep Bidirectional Transformers," *NAACL-HLT*, pp. 4171-4186, 2019.  
[6] D. Araci, "FinBERT: Financial Sentiment Analysis with Pre-trained Language Models," *arXiv:1908.10063*, 2019.  
[7] M. Kraus and S. Feuerriegel, "Decision Support from Financial Disclosures with Deep Neural Networks," *Decision Support Systems*, vol. 104, pp. 38-48, 2017.  
[8] I. K. Nti et al., "A Comprehensive Evaluation of Ensemble Learning for Stock-Market Prediction," *Journal of Big Data*, vol. 7, no. 20, 2020.  
[9] Y. Xu and V. Keselj, "Stock Prediction Using Deep Learning and Sentiment Analysis," *IEEE Big Data*, pp. 5573-5580, 2019.  
[10] P. Akioyamen et al., "A Hybrid Learning Approach to Detecting Regime Switches," *ICAIF*, 2020.  
[11] F. Z. Xing et al., "Natural Language Based Financial Forecasting: A Survey," *Artificial Intelligence Review*, 2018.  
[12] S. Bai, J. Z. Kolter, and V. Koltun, "An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling," *arXiv:1803.01271*, 2018.  
[13] Y. Gal and Z. Ghahramani, "Dropout as a Bayesian Approximation: Representing Model Uncertainty in Deep Learning," *ICML*, 2016.  
[14] S. M. Lundberg and S.-I. Lee, "A Unified Approach to Interpreting Model Predictions," *NeurIPS*, 2017.  
[15] N. Bussmann et al., "Explainable Machine Learning in Credit Risk Management," *Computational Economics*, vol. 57, pp. 203-216, 2021.  
[16] S. A. Gyamerah et al., "On Stock Market Movement Prediction via Stacking Ensemble Learning Method," *IEEE*, 2019.  
[17] A. Vaswani et al., "Attention is All You Need," *NeurIPS*, vol. 30, 2017.  
[18] N. Srivastava et al., "Dropout: A Simple Way to Prevent Neural Networks from Overfitting," *JMLR*, vol. 15, pp. 1929-1958, 2014.  
[19] E. F. Fama, "Efficient Capital Markets: A Review of Theory and Empirical Work," *The Journal of Finance*, vol. 25, no. 2, pp. 383-417, 1970.  
[20] M. Al Ridhawi et al., "Adaptive Regime-Aware Stock Price Prediction Using Autoencoder-Gated Dual Node Transformers," *Applied Sciences*, 2023.  
[21] R. C. Cavalcante et al., "Computational Intelligence and Financial Markets: A Survey," *Expert Systems with Applications*, vol. 55, pp. 194-211, 2016.  
[22] O. B. Sezer, M. U. Gudelek, and A. M. Ozbayoglu, "Financial time series forecasting with deep learning: A systematic literature review: 2005-2019," *Applied Soft Computing*, vol. 90, p. 106181, 2020.  
[23] H. Borovykh, S. Bohte, and C. W. Oosterlee, "Conditional Time Series Forecasting with Convolutional Neural Networks," *arXiv:1703.04691*, 2017.  
[24] A. Niculescu-Mizil and R. Caruana, "Predicting Good Probabilities With Supervised Learning," *ICML*, 2005.  
[25] J. Bracke, A. Datta, C. Jung, and S. Sen, "Machine Learning Explainability in Finance: An Application to Default Risk Analysis," *Bank of England Working Paper*, 2019.  
[26] M. Lopez de Prado, "Advances in Financial Machine Learning," *John Wiley & Sons*, 2018.  
[27] C. Cortes and M. Mohri, "AUC Optimization vs. Error Rate Minimization," *NIPS*, 2003.  
[28] S. Li et al., "Enhancing the Locality and Breaking the Memory Bottleneck of Transformer on Time Series Forecasting," *NeurIPS*, 2019.  
[29] L. Rokach, "Ensemble-based classifiers," *Artificial Intelligence Review*, vol. 33, no. 1-2, pp. 1-39, 2010.  
[30] A. Tsantekidis et al., "Forecasting Stock Prices from the Limit Order Book using Convolutional Neural Networks," *CBI*, 2017.  
[31] T. Chen and C. Guestrin, "XGBoost: A Scalable Tree Boosting System," *KDD*, 2016.  
[32] C. J. Huang and P. H. Kuo, "A Deep CNN-Based Model for Financial Market Fluctuation Prediction," *IEEE Access*, 2019.
"""

filepath = r"c:\Users\soham\.gemini\antigravity-ide\brain\86ba3cf2-8602-434b-a611-bf06024a4d8e\IEEE_Paper_Draft.md"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find("## REFERENCES")
if start_idx != -1:
    new_content = content[:start_idx] + new_refs
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully replaced references.")
else:
    print("Could not find references section.")
