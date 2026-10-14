"""Precompute per-case score matrices (embedding cosine + NLI entailment) into cache.npz."""
import sys, time, numpy as np, torch, pickle
sys.stdout.reconfigure(encoding="utf-8")
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer
from run_eval import load_cases
from fuzzy import normalize

cases = load_cases(); out = {}
for name in ["BAAI/bge-m3", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"]:
    m = SentenceTransformer(name, device="cuda"); t = time.time()
    out["emb:" + name] = [ (lambda e: e @ e.T)(m.encode([normalize(a) for a in c["answers"]], normalize_embeddings=True)) for c in cases]
    print(name, f"{time.time()-t:.1f}s", flush=True); del m
NLI = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
tok = AutoTokenizer.from_pretrained(NLI); model = AutoModelForSequenceClassification.from_pretrained(NLI).eval().cuda().half()
ent = [i for i, l in model.config.id2label.items() if l.lower().startswith("entail")][0]
T = {"ctx": lambda q, a: f"Питання: {q} Відповідь: {a}.", "bare": lambda q, a: a}
for tn, f in T.items():
    t = time.time(); res = []
    for c in cases:
        n = len(c["answers"]); P = [(i, j) for i in range(n) for j in range(n) if i != j]
        prem = [f(c["q"], c["answers"][i]) for i, j in P]; hyp = [f(c["q"], c["answers"][j]) for i, j in P]
        probs = []
        for s in range(0, len(P), 128):
            enc = tok(prem[s:s+128], hyp[s:s+128], return_tensors="pt", padding=True, truncation=True).to("cuda")
            with torch.no_grad(): probs += torch.softmax(model(**enc).logits.float(), -1)[:, ent].tolist()
        m_ = np.eye(n)
        for (i, j), p in zip(P, probs): m_[i][j] = p
        res.append(np.minimum(m_, m_.T))
    out["nli:" + tn] = res; print("nli", tn, f"{time.time()-t:.1f}s", flush=True)
pickle.dump(out, open("cache.pkl", "wb"))
