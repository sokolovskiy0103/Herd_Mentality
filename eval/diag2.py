import sys, numpy as np, torch
sys.stdout.reconfigure(encoding="utf-8")
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from run_eval import load_cases, score
from ref_pipeline import cluster, clean
N = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
tok = AutoTokenizer.from_pretrained(N); m = AutoModelForSequenceClassification.from_pretrained(N).float().eval().cuda()
cases = load_cases()
def mat(texts):
    n = len(texts); P = [(i, j) for i in range(n) for j in range(n) if i != j]
    enc = tok([texts[i] for i, j in P], [texts[j] for i, j in P], return_tensors="pt", padding=True).to("cuda")
    with torch.no_grad(): p = torch.softmax(m(**enc).logits, -1)[:, 0].cpu().numpy()
    M = np.eye(n)
    for (i, j), v in zip(P, p): M[i][j] = v
    return np.minimum(M, M.T)
for name, f in [("raw", lambda a: a), ("clean-lower", clean)]:
    S = {(c["q"], tuple(c["answers"])): mat([f(a) for a in c["answers"]]) for c in cases}
    r = max((score(cases, lambda q, a, t=t: cluster(S[(q, tuple(a))], t), verbose=False) for t in np.arange(0.2, 0.95, 0.05)), key=lambda r: r["F1"])
    print("float", name, round(r["F1"], 3))
