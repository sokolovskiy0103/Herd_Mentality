import sys, pickle, numpy as np, time
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from ref_pipeline import Judge, cluster
from rules import adjust
d = sys.argv[1]
cases = load_cases(); J = Judge(d)
t0 = time.time(); M = {}
for c in cases: M[(c["q"], tuple(c["answers"]))] = J.matrices(c["answers"])
print(f"matrices {time.time()-t0:.1f}s on CPU ({sum(len(c['answers']) for c in cases)} answers)")
pickle.dump(M, open("ref_cache.pkl", "wb"))
for rules in [False, True]:
    for w in [0.3, 0.4, 0.5, 0.6, 0.7]:
        res = []
        for thr in np.arange(0.3, 0.8, 0.025):
            def pred(q, a):
                E, N = M[(q, tuple(a))]; s = w * N + (1 - w) * E
                return cluster(adjust(a, s) if rules else s, thr)
            res.append((score(cases, pred, verbose=False), thr))
        r, thr = max(res, key=lambda x: x[0]["F1"])
        print(f"rules={rules!s:5} w_nli={w} thr={thr:.3f} P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} fp={r['fp']} fn={r['fn']}")
