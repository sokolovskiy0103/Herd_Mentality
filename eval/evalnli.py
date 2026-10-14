import sys, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from ref_pipeline import Judge, cluster, clean
cases = load_cases(); J = Judge(sys.argv[1])
S = {(c["q"], tuple(c["answers"])): J.nli_sim([clean(a) for a in c["answers"]]) for c in cases}
r = max((score(cases, lambda q, a, t=t: cluster(S[(q, tuple(a))], t), verbose=False) for t in np.arange(0.2, 0.95, 0.05)), key=lambda r: r["F1"])
print(sys.argv[2], "NLI best F1", round(r["F1"], 3))
