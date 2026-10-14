import sys, pickle, numpy as np, itertools
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from emb import cluster
cases = load_cases(); C = pickle.load(open("cache.pkl", "rb"))
idx = {(c["q"], tuple(c["answers"])): i for i, c in enumerate(cases)}
def run(f, thr):
    return score(cases, lambda q, a: cluster(f(idx[(q, tuple(a))]), thr), verbose=False)
def best(label, f, thrs):
    rs = [(run(f, t), t) for t in thrs]
    r, t = max(rs, key=lambda x: x[0]["F1"])
    print(f"{label:55s} thr={t:.2f} P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} fp={r['fp']} fn={r['fn']}")
th = np.arange(0.1, 0.96, 0.05)
for n in ["nli:ctx", "nli:bare"]:
    best(n, lambda i, n=n: C[n][i], th)
for e in ["emb:BAAI/bge-m3", "emb:sentence-transformers/paraphrase-multilingual-mpnet-base-v2"]:
    best(e, lambda i, e=e: C[e][i], th)
    for n in ["nli:ctx", "nli:bare"]:
        for w in [0.3, 0.5, 0.7]:
            best(f"{e[4:20]}+{n} avg w_nli={w}", lambda i, e=e, n=n, w=w: w * C[n][i] + (1 - w) * C[e][i], th)
        best(f"{e[4:20]}*{n} (geo mean)", lambda i, e=e, n=n: np.sqrt(np.clip(C[e][i], 0, 1) * C[n][i]), th)
        best(f"{e[4:20]}|{n} max", lambda i, e=e, n=n: np.maximum(C[e][i], C[n][i]), th)
