"""Evaluate answer-grouping methods against eval/cases.json.

Usage: python eval/run_eval.py fuzzy [emb:<model>:<threshold>] [llm:<model>] ...
Metric: pairwise P/R/F1 over all answer pairs (same group vs not), plus exact-partition accuracy.
 - precision drops on FALSE merges (unfair), recall drops on MISSED merges (host can fix by hand).
"""
import json, random, sys, time, itertools, pathlib

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).parent


def load_cases(seed=1):
    rnd = random.Random(seed)
    cases = []
    for c in json.loads((HERE / "cases.json").read_text(encoding="utf-8")):
        items = [(a, gi) for gi, g in enumerate(c["groups"]) for a in g]
        rnd.shuffle(items)
        cases.append({"q": c["q"], "answers": [a for a, _ in items], "gold": [g for _, g in items]})
    return cases


def pairs_of(labels):
    return {(i, j) for i, j in itertools.combinations(range(len(labels)), 2) if labels[i] == labels[j]}


def score(cases, predict, verbose=True):
    tp = fp = fn = exact = 0
    t0 = time.time()
    bad = []
    for c in cases:
        pred = predict(c["q"], c["answers"])
        g, p = pairs_of(c["gold"]), pairs_of(pred)
        tp += len(g & p); fp += len(p - g); fn += len(g - p)
        if g == p:
            exact += 1
        else:
            bad.append((c, g, p))
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    dt = time.time() - t0
    if verbose:
        for c, g, p in bad:
            print(f"  ✗ {c['q']}")
            for i, j in sorted(p - g):
                print(f"      FALSE MERGE : {c['answers'][i]!r} + {c['answers'][j]!r}")
            for i, j in sorted(g - p):
                print(f"      MISSED      : {c['answers'][i]!r} + {c['answers'][j]!r}")
    return dict(P=prec, R=rec, F1=f1, exact=exact / len(cases), fp=fp, fn=fn, sec=dt / len(cases))


# ---------------- methods ----------------

def uf_labels(n, merges):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j in merges:
        parent[find(j)] = find(i)
    return [find(i) for i in range(n)]


def make_method(spec):
    kind, *rest = spec.split(":")
    if kind == "fuzzy":
        import fuzzy
        return lambda q, a: fuzzy.group(a)
    if kind == "emb":
        import emb
        return emb.make(*rest)
    if kind == "llm":
        import llm
        return llm.make(*rest)
    if kind == "hybrid":
        import hybrid
        return hybrid.make(*rest)
    raise SystemExit(f"unknown method {spec}")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    cases = load_cases()
    print(f"{len(cases)} cases, {sum(len(c['answers']) for c in cases)} answers")
    quiet = "-q" in sys.argv
    for spec in [a for a in sys.argv[1:] if a != "-q"]:
        print(f"\n=== {spec}")
        r = score(cases, make_method(spec), verbose=not quiet)
        print(f"  P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} exact={r['exact']:.2f} "
              f"falseMerges={r['fp']} missed={r['fn']} {r['sec']:.2f}s/case")
