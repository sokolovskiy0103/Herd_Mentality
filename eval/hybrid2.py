import sys, pickle, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from rules import adjust
cases = load_cases(); C = pickle.load(open("cache.pkl", "rb"))
idx = {(c["q"], tuple(c["answers"])): i for i, c in enumerate(cases)}

def cluster(sim, thr, link):
    n = len(sim); cl = [[i] for i in range(n)]
    while len(cl) > 1:
        best, bi, bj = -1, 0, 0
        for a in range(len(cl)):
            for b in range(a + 1, len(cl)):
                v = [sim[i][j] for i in cl[a] for j in cl[b]]
                s = {"avg": np.mean, "single": np.max, "complete": np.min}[link](v)
                if s > best: best, bi, bj = s, a, b
        if best < thr: break
        cl[bi] += cl.pop(bj)
    lab = [0]*n
    for k, c in enumerate(cl):
        for i in c: lab[i] = k
    return lab

def best(label, f, thrs, link, rules):
    out = []
    for t in thrs:
        def pred(q, a):
            i = idx[(q, tuple(a))]; s = f(i)
            return cluster(adjust(a, s) if rules else s, t, link)
        out.append((score(cases, pred, verbose=False), t))
    r, t = max(out, key=lambda x: x[0]["F1"])
    print(f"{label:50s} {link:8s} rules={rules!s:5s} thr={t:.2f} P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} fp={r['fp']} fn={r['fn']}", flush=True)

th = np.arange(0.3, 0.9, 0.05)
E = "emb:BAAI/bge-m3"
for name, f in [("bge", lambda i: C[E][i]),
                ("nli bare", lambda i: C["nli:bare"][i]),
                ("0.7 bge + 0.3 nli", lambda i: 0.7*C[E][i] + 0.3*C["nli:bare"][i]),
                ("0.5 bge + 0.5 nli", lambda i: 0.5*C[E][i] + 0.5*C["nli:bare"][i])]:
    for link in ["avg", "single"]:
        for rules in [False, True]:
            best(name, f, th, link, rules)
