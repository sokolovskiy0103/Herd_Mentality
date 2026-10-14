"""Reference implementation of the on-device judge (mirror of Judge.kt): pruned-vocab Unigram tokenizer + ONNX int8
(embeddings + NLI) + rules + average-linkage clustering. Used to pick weights/threshold and to generate Kotlin test fixtures."""
import sys, math, unicodedata, numpy as np, onnxruntime as ort, pathlib
from rules import adjust

MAXLEN = 32


class Unigram:
    def __init__(self, path):
        lines = pathlib.Path(path).read_text(encoding="utf-8").split("\n")
        hdr = dict(kv.split("=") for kv in lines[0][1:].split())
        self.unk, self.cls, self.sep, self.pad = (int(hdr[k]) for k in ("unk", "cls", "sep", "pad"))
        self.pair = hdr["pair"] == "1"
        self.piece, self.score = {}, []
        for i, l in enumerate(l for l in lines[1:] if l):
            p, s = l.rsplit("\t", 1)
            self.piece[p] = i; self.score.append(float(s))
        self.maxlen = max(len(p) for p in self.piece)
        self.unk_score = min(self.score) - 10.0

    def word(self, w):
        n = len(w); best = [-1e18] * (n + 1); back = [None] * (n + 1); best[0] = 0.0
        for i in range(n):
            if best[i] <= -1e17: continue
            matched = False
            for j in range(i + 1, min(n, i + self.maxlen) + 1):
                idx = self.piece.get(w[i:j])
                if idx is not None and not (idx in (self.unk, self.cls, self.sep, self.pad)):
                    matched = True
                    sc = best[i] + self.score[idx]
                    if sc > best[j]: best[j] = sc; back[j] = (i, idx)
            if not matched or True:
                sc = best[i] + self.unk_score
                if sc > best[i + 1]: best[i + 1] = sc; back[i + 1] = (i, self.unk)
        out, p = [], n
        while p > 0:
            i, idx = back[p]; out.append(idx); p = i
        out.reverse()
        # fuse consecutive unk
        res = []
        for t in out:
            if t == self.unk and res and res[-1] == self.unk: continue
            res.append(t)
        return res

    def encode(self, text):
        ids = []
        for w in unicodedata.normalize("NFKC", text).split():
            ids += self.word("▁" + w)
        return ids[:MAXLEN]


def clean(raw):
    """Model-facing text: lowercase, letters/digits/apostrophes only."""
    s = raw.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'").replace("ё", "е")
    s = "".join(ch if (ch.isalnum() or ch == "'") else " " for ch in s)
    return " ".join(s.split())


def cluster(sim, thr):
    n = len(sim); cl = [[i] for i in range(n)]
    while len(cl) > 1:
        best, bi, bj = -1.0, 0, 0
        for a in range(len(cl)):
            for b in range(a + 1, len(cl)):
                s = sum(sim[i][j] for i in cl[a] for j in cl[b]) / (len(cl[a]) * len(cl[b]))
                if s > best: best, bi, bj = s, a, b
        if best < thr: break
        cl[bi] += cl.pop(bj)
    lab = [0] * n
    for k, c in enumerate(cl):
        for i in c: lab[i] = k
    return lab


class Judge:
    def __init__(self, d):
        d = pathlib.Path(d)
        self.te, self.tn = Unigram(d / "embed.vocab"), Unigram(d / "nli.vocab")
        so = ort.SessionOptions(); so.log_severity_level = 3
        self.se = ort.InferenceSession(str(d / "embed.onnx"), so, providers=["CPUExecutionProvider"])
        self.sn = ort.InferenceSession(str(d / "nli.onnx"), so, providers=["CPUExecutionProvider"])

    @staticmethod
    def batch(seqs, pad):
        L = max(len(s) for s in seqs)
        ids = np.full((len(seqs), L), pad, dtype=np.int64); am = np.zeros((len(seqs), L), dtype=np.int64)
        for i, s in enumerate(seqs): ids[i, :len(s)] = s; am[i, :len(s)] = 1
        return ids, am

    def embed_sim(self, texts):
        seqs = [[self.te.cls] + self.te.encode(t) + [self.te.sep] for t in texts]
        ids, am = self.batch(seqs, self.te.pad)
        e = self.se.run(None, {"input_ids": ids, "attention_mask": am})[0]
        return e @ e.T

    def nli_sim(self, texts, floor_mask=None):
        n = len(texts); enc = [self.tn.encode(t) for t in texts]; P = []
        seqs = []
        for i in range(n):
            for j in range(n):
                if i != j and (floor_mask is None or floor_mask[i][j]):
                    P.append((i, j)); seqs.append([self.tn.cls] + enc[i] + [self.tn.sep] + enc[j] + [self.tn.sep])
        m = np.eye(n)
        if seqs:
            ids, am = self.batch(seqs, self.tn.pad)
            lg = self.sn.run(None, {"input_ids": ids, "attention_mask": am})[0]
            pr = np.exp(lg - lg.max(1, keepdims=True)); pr /= pr.sum(1, keepdims=True)
            for (i, j), p in zip(P, pr[:, 0]): m[i][j] = p     # label 0 = entailment
        return np.minimum(m, m.T)

    def matrices(self, answers, floor=None):
        t = [clean(a) for a in answers]
        E = self.embed_sim(t)
        mask = None if floor is None else (E >= floor)
        return E, self.nli_sim(t, mask)
