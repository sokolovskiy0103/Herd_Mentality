"""Python port of FuzzyMatcher.kt (current offline fallback)."""
import re

STOP = set("""в у на з із зі до по під за біля коло від для про через при над між без к о об і й та а це то ну
мій моя моє мої свій своя своє свої якийсь якась якесь во со с и это мой свой the a an in on at of my""".split())
ENDINGS = ["ами", "ями", "ові", "еві", "єві", "ого", "ому", "ими", "іми", "ях", "ах", "ою", "ею", "єю",
           "ом", "ем", "ам", "ям", "ів", "їв", "ий", "ій", "ій", "ия", "ая", "яя", "ое", "ее", "ые",
           "а", "я", "у", "ю", "і", "и", "е", "є", "о", "ь", "ї", "й", "ы"]


def normalize(raw):
    s = raw.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'").replace("ё", "е")
    s = "".join(ch if ch.isalnum() else " " for ch in s)
    return " ".join(s.split())


def stem(t):
    if t.isdigit():
        return t
    for e in ENDINGS:
        if t.endswith(e) and len(t) - len(e) >= 3:
            return t[: -len(e)]
    return t


def key(raw):
    toks = normalize(raw).split()
    m = [t for t in toks if t not in STOP] or toks
    return " ".join(sorted(stem(t) for t in m))


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return prev[-1]


def same(a, b):
    ka, kb = key(a), key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if any(c.isdigit() for c in ka + kb):
        return False
    m = max(len(ka), len(kb))
    if m < 4:
        return False
    return lev(ka, kb) <= (1 if m <= 5 else 2 if m <= 10 else 3)


def group(answers):
    """Returns a label per answer (equal label = same group)."""
    n = len(answers)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(n):
        for j in range(i + 1, n):
            if same(answers[i], answers[j]):
                parent[find(j)] = find(i)
    return [find(i) for i in range(n)]
