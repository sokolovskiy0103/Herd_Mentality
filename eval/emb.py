"""Embedding + agglomerative clustering. spec: emb:<hf-model>:<threshold>[:<prefix>]
Average-linkage clustering of cosine distance, cut at threshold."""
import numpy as np
from fuzzy import normalize

_cache = {}


def load(name):
    if name not in _cache:
        from sentence_transformers import SentenceTransformer
        _cache[name] = SentenceTransformer(name, device="cpu")
    return _cache[name]


def cluster(sim, thr):
    n = len(sim)
    clusters = [[i] for i in range(n)]
    while len(clusters) > 1:
        best, bi, bj = -1, 0, 0
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                s = np.mean([sim[i][j] for i in clusters[a] for j in clusters[b]])
                if s > best:
                    best, bi, bj = s, a, b
        if best < thr:
            break
        clusters[bi] += clusters.pop(bj)
    lab = [0] * n
    for k, c in enumerate(clusters):
        for i in c:
            lab[i] = k
    return lab


def make(name, thr, prefix=""):
    name = name.replace("__", "/")
    model = load(name)
    thr = float(thr)

    def predict(q, answers):
        texts = [prefix + normalize(a) for a in answers]
        e = model.encode(texts, normalize_embeddings=True)
        return cluster(e @ e.T, thr)
    return predict
