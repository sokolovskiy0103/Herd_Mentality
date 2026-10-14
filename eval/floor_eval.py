import sys, numpy as np, time
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from ref_pipeline import Judge, cluster
from rules import adjust
cases = load_cases(); J = Judge(sys.argv[1])
for floor in [None, 0.2, 0.3, 0.4]:
    t0 = time.time(); M = {(c["q"], tuple(c["answers"])): J.matrices(c["answers"], floor) for c in cases}; dt = time.time() - t0
    best = None
    for w in [0.4, 0.5, 0.6]:
        for thr in np.arange(0.4, 0.7, 0.025):
            r = score(cases, lambda q, a: cluster(adjust(a, w * M[(q, tuple(a))][1] + (1 - w) * M[(q, tuple(a))][0]), thr), verbose=False)
            if best is None or r["F1"] > best[0]["F1"]: best = (r, w, thr)
    r, w, thr = best
    print(f"floor={floor} {dt:.0f}s w={w} thr={thr:.3f} P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} fp={r['fp']} fn={r['fn']}", flush=True)
