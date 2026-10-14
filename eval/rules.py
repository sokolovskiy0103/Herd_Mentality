"""Cheap deterministic rules layered over model similarity. Mirrors what can be ported to Kotlin."""
import re
from fuzzy import normalize, stem, key, same, STOP

NUM = {"нуль": 0, "жодного": 0, "один": 1, "одна": 1, "одного": 1, "два": 2, "двоє": 2, "три": 3, "троє": 3, "чотири": 4,
       "п'ять": 5, "шість": 6, "сім": 7, "вісім": 8, "дев'ять": 9, "десять": 10, "двадцять": 20, "тридцять": 30,
       "сорок": 40, "п'ятдесят": 50, "шістдесят": 60, "сто": 100}


def number(s):
    """Numeric value of an answer ('5', 'п'ять секунд', '5 сек'), else None."""
    low = s.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'")
    toks = "".join(ch if (ch.isalnum() or ch == "'") else " " for ch in low).split()
    for t in toks:
        if t.isdigit():
            return int(t)
        if t in NUM:
            return NUM[t]
    return None


def toks(s):
    t = normalize(s).split()
    return {stem(x) for x in ([x for x in t if x not in STOP] or t)}


def contains(a, b):
    ta, tb = toks(a), toks(b)
    if not ta or not tb or ta == tb:
        return False
    small, big = (ta, tb) if len(ta) < len(tb) else (tb, ta)
    return small <= big and all(len(x) >= 4 for x in small)


def adjust(answers, sim):
    """sim: n×n similarity; returns adjusted copy."""
    s = sim.copy()
    n = len(answers)
    for i in range(n):
        for j in range(i + 1, n):
            ni, nj = number(answers[i]), number(answers[j])
            if ni is not None or nj is not None:
                v = 1.0 if (ni is not None and ni == nj) else 0.0
            elif same(answers[i], answers[j]) or contains(answers[i], answers[j]):
                v = 1.0
            else:
                continue
            s[i][j] = s[j][i] = v
    return s
