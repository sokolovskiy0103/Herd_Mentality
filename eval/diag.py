import sys, pickle, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
from run_eval import load_cases, score
from ref_pipeline import Judge, cluster, clean
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download
d = sys.argv[1]; cases = load_cases(); J = Judge(d)
# 1. tokenizer parity vs HF (map via vocab strings)
for kind, name, tk in [("embed", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2", J.te), ("nli", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7", J.tn)]:
    hf = Tokenizer.from_file(hf_hub_download(name, "tokenizer.json"))
    inv = {i: p for p, i in tk.piece.items()}
    bad = tot = 0
    for c in cases:
        for a in c["answers"]:
            t = clean(a); mine = [inv[i] for i in tk.encode(t)]
            ref = hf.encode(t, add_special_tokens=False).tokens
            tot += 1
            if mine != ref:
                bad += 1
                if bad <= 4: print(kind, repr(t), mine, ref)
    print(kind, "tokenization mismatches", bad, "/", tot)
# 2. component F1 (ref vs float cache)
M = pickle.load(open("ref_cache.pkl", "rb")); F = pickle.load(open("cache.pkl", "rb"))
idx = {(c["q"], tuple(c["answers"])): i for i, c in enumerate(cases)}
def best(f):
    r = max((score(cases, lambda q, a, t=t: cluster(f(q, a), t), verbose=False) for t in np.arange(0.2, 0.95, 0.05)), key=lambda r: r["F1"]); return r["F1"]
print("emb  ref", best(lambda q, a: M[(q, tuple(a))][0]), " float", best(lambda q, a: F["emb:sentence-transformers/paraphrase-multilingual-mpnet-base-v2"][idx[(q, tuple(a))]]))
print("nli  ref", best(lambda q, a: M[(q, tuple(a))][1]), " float", best(lambda q, a: F["nli:bare"][idx[(q, tuple(a))]]))
