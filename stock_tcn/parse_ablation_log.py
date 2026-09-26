import re, json

log_path = r"C:\Users\soham\.gemini\antigravity-ide\brain\87fb4cd4-40cd-4a10-aee3-ab1713ecd375\.system_generated\tasks\task-1509.log"

results = {"full": [], "no_gcn": [], "no_sentiment": []}

with open(log_path, "r") as f:
    for line in f:
        m_full = re.search(r"full\s+:\s+([0-9.]+)", line)
        if m_full: results["full"].append(float(m_full.group(1)))
        
        m_gcn = re.search(r"no_gcn\s+:\s+([0-9.]+)", line)
        if m_gcn: results["no_gcn"].append(float(m_gcn.group(1)))
        
        m_sent = re.search(r"no_sentiment\s+:\s+([0-9.]+)", line)
        if m_sent: results["no_sentiment"].append(float(m_sent.group(1)))

final_results = {}
for k, v in results.items():
    if v:
        final_results[k] = {"auc": sum(v) / len(v)}
        print(f"{k}: {sum(v)/len(v):.4f} (N={len(v)})")

# Calculate delta
for k in ["no_gcn", "no_sentiment"]:
    if k in final_results and "full" in final_results:
        final_results[k]["delta"] = final_results[k]["auc"] - final_results["full"]["auc"]
final_results["full"]["delta"] = 0.0

# Load existing ablation_results.json and update it
try:
    with open("ablation_results.json", "r") as f:
        existing = json.load(f)
except:
    existing = {}

existing.update(final_results)

with open("ablation_results.json", "w") as f:
    json.dump(existing, f, indent=4)
    
print("Updated ablation_results.json")
