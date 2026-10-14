import sys, pickle, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from emb import cluster
cases = load_cases(); C = pickle.load(open("cache.pkl", "rb"))
idx = {(c["q"], tuple(c["answers"])): i for i, c in enumerate(cases)}
f = lambda i: 0.3*C["nli:bare"][i] + 0.7*C["emb:BAAI/bge-m3"][i]
score(cases, lambda q, a: cluster(f(idx[(q, tuple(a))]), 0.55), verbose=True)
