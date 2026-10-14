import sys, numpy as np, time
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from fuzzy import normalize
import emb
from sentence_transformers import SentenceTransformer

cases = load_cases()
models = sys.argv[1:]
for spec in models:
    name, _, prefix = spec.partition("|")
    try:
        m = SentenceTransformer(name, device="cpu", trust_remote_code=True)
    except Exception as e:
        print(f"## {name}: FAILED {str(e)[:100]}"); continue
    t0 = time.time()
    E = {i: m.encode([prefix + normalize(a) for a in c["answers"]], normalize_embeddings=True) for i, c in enumerate(cases)}
    dt = time.time() - t0
    print(f"## {name} (encode {dt:.1f}s total)")
    best = None
    for thr in [0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85]:
        idx = {id(c): i for i, c in enumerate(cases)}
        pred = lambda q, a, thr=thr: emb.cluster(E[next(i for i, c in enumerate(cases) if c["q"] == q and c["answers"] == a)] @ E[next(i for i, c in enumerate(cases) if c["q"] == q and c["answers"] == a)].T, thr)
        r = score(cases, pred, verbose=False)
        print(f"  thr={thr:.2f} P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} fp={r['fp']} fn={r['fn']}")
