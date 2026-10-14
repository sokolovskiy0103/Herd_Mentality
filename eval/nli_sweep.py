import sys, itertools, time, numpy as np, torch
sys.stdout.reconfigure(encoding="utf-8")
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from run_eval import load_cases, score
import emb

name = sys.argv[1]
tok = AutoTokenizer.from_pretrained(name)
model = AutoModelForSequenceClassification.from_pretrained(name).eval()
ent = [i for i, l in model.config.id2label.items() if l.lower().startswith("entail")][0]
print(name, model.config.id2label, "entail idx", ent)
cases = load_cases()
TEMPLATES = {
  "ctx": lambda q, a: f"Питання: {q} Відповідь: {a}.",
  "bare": lambda q, a: a,
}
for tname, T in TEMPLATES.items():
    t0 = time.time()
    S = {}
    for ci, c in enumerate(cases):
        n = len(c["answers"]); P = [(i, j) for i in range(n) for j in range(n) if i != j]
        prem = [T(c["q"], c["answers"][i]) for i, j in P]; hyp = [T(c["q"], c["answers"][j]) for i, j in P]
        probs = []
        for s in range(0, len(P), 64):
            enc = tok(prem[s:s+64], hyp[s:s+64], return_tensors="pt", padding=True, truncation=True)
            with torch.no_grad():
                probs += torch.softmax(model(**enc).logits, -1)[:, ent].tolist()
        m = np.eye(n)
        for (i, j), p in zip(P, probs): m[i][j] = p
        S[ci] = np.minimum(m, m.T)
    print(f"## template={tname} ({time.time()-t0:.0f}s)")
    for thr in [0.3, 0.5, 0.7, 0.8, 0.9, 0.95]:
        key = lambda q, a: next(i for i, c in enumerate(cases) if c["q"] == q and c["answers"] == a)
        r = score(cases, lambda q, a, thr=thr: emb.cluster(S[key(q, a)], thr), verbose=False)
        print(f"  thr={thr:.2f} P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} fp={r['fp']} fn={r['fn']}")
