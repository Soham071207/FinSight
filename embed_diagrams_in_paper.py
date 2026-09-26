import os
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = r"C:\Users\soham\Desktop\final1 asep2"
DOC_PATH = os.path.join(ROOT, "FinSight_SCI_Journal_Paper.docx")
PLOTS_DIR = os.path.join(ROOT, "STOCK_experimental", "plots")

def add_figure(doc, img_name, caption):
    img_path = os.path.join(PLOTS_DIR, img_name)
    if not os.path.exists(img_path):
        print(f"Skipping {img_name}, not found.")
        return
    
    # Add a paragraph for the image
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    r.add_picture(img_path, width=Inches(3.0)) # Fits in a 2-column format well

    # Add caption
    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cp.add_run(caption)
    cr.font.name = "Times New Roman"
    cr.font.size = Pt(9)
    cr.italic = True
    
    doc.add_paragraph() # spacing

def main():
    print(f"Loading {DOC_PATH}...")
    doc = Document(DOC_PATH)
    
    # We will append the Methodological figures under Section III
    # and Results figures under Section V
    # To do this safely without messing up paragraph references, we will find indices
    
    method_idx = -1
    results_idx = -1
    for i, p in enumerate(doc.paragraphs):
        if "III. PROPOSED METHODOLOGY" in p.text:
            method_idx = i
        elif "V. RESULTS AND ANALYSIS" in p.text:
            results_idx = i
            
    # However, python-docx doesn't support inserting images *at* a specific index easily
    # It appends to the end of the document.
    # We can create a new document, or we can use `p.insert_paragraph_before()` which is complex for pictures.
    # Let's just append them to the end of the document in a new 'FIGURES AND VISUALIZATIONS' section 
    # to ensure they don't break the two-column layout unexpectedly.
    
    doc.add_page_break()
    
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hr = h.add_run("APPENDIX A: COMPREHENSIVE DATA VISUALIZATIONS")
    hr.bold = True
    hr.font.size = Pt(14)
    hr.font.name = "Times New Roman"
    
    desc = doc.add_paragraph("The following 14 data visualizations detail the end-to-end methodology, cross-asset correlations, predictive distributions, and experimental results of the proposed FinSight framework.")
    desc.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    figs = [
        ("fig_system_arch.png", "Fig. 1. System Architecture Schematic Flowchart mapping data flow through the TCN-MHA, ST-GCN, and Bayesian Meta-Learner."),
        ("fig_walk_forward.png", "Fig. 2. Walk-Forward Online Learning Methodology for concept drift adaptation using rolling 120-day windows."),
        ("fig_gcn_heatmap.png", "Fig. 3. Spatial-Temporal GCN learned dynamic adjacency weights demonstrating cross-asset correlations."),
        ("fig_tstcc_tsne.png", "Fig. 4. t-SNE projection of TS-TCC contrastive pre-trained embeddings showing distinct Bull/Bear latent state separation."),
        ("fig_sentiment_overlay.png", "Fig. 5. FinBERT sentiment momentum plotted against asset price, illustrating sentiment-driven regime shifts."),
        ("fig_loss_curve.png", "Fig. 6. TCN-MHA Training vs. Validation Loss convergence across 30 epochs."),
        ("fig_scatter_reg.png", "Fig. 7. Scatter plot and regression curve evaluating correlation between predicted bullish probabilities and actual 5-day forward returns."),
        ("fig_bayesian_violin.png", "Fig. 8. Bayesian epistemic uncertainty distribution (Monte Carlo dropout) for correct vs. incorrect predictions."),
        ("fig_bar_trend.png", "Fig. 9. Comparative bar chart with trend lines summarizing Accuracy and AUC-ROC across all baseline models."),
        ("fig_roc.png", "Fig. 10. Receiver Operating Characteristic (ROC) comparative distribution curves."),
        ("fig_pr.png", "Fig. 11. Precision-Recall curves evaluating model performance on imbalanced market data."),
        ("fig_confusion.png", "Fig. 12. Stacking Ensemble Confusion Matrix heatmap."),
        ("fig_shap.png", "Fig. 13. SHAP Feature Importance bar chart detailing the driving variables for LightGBM predictions."),
        ("fig_regime.png", "Fig. 14. Time-series trend of the equity curve overlaid with dynamic market regimes.")
    ]
    
    for fname, caption in figs:
        add_figure(doc, fname, caption)
        
    OUT_DOC = os.path.join(ROOT, "FinSight_SCI_Journal_Paper_Visualized.docx")
    doc.save(OUT_DOC)
    print(f"Successfully embedded 14 figures into {OUT_DOC}")

if __name__ == "__main__":
    main()
