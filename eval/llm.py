"""Current production approach (Gemma labels each answer) replicated through Ollama."""
import json, re, pathlib, requests
from fuzzy import key, normalize

SRC = (pathlib.Path(__file__).parent.parent / "app/src/main/java/com/sokolovskiy/herd/JudgePrompt.kt").read_text(encoding="utf-8")
SYSTEM = re.search(r'SYSTEM = """(.*?)"""', SRC, re.S).group(1)


def user_msg(q, answers):
    s = f"Question: {q}\nAnswers:\n" + "".join(f"{i+1}. {a}\n" for i, a in enumerate(answers))
    return s + f'\nReturn {{"labels": [...]}} with exactly {len(answers)} labels.'


EX = [
    ("Де найнезручніше займатися сексом?", ["в машині", "Тачка", "на пляжі", "в авто", "у ванній", "душ", "пляж!!"],
     ["машина", "машина", "пляж", "машина", "ванна", "душ", "пляж"]),
    ("Що найчастіше вдають у ліжку?", ["оргазм", "що кінчив", "сплю", "що спить", "втому", "Оргазм"],
     ["оргазм", "оргазм", "сон", "сон", "втома", "оргазм"]),
    ("Назви напій для романтичного вечора", ["вино", "червоне вино", "шампанське", "ігристе", "пиво", "коньяк"],
     ["вино", "вино", "шампанське", "шампанське", "пиво", "коньяк"]),
    ("Скільки має тривати перший поцілунок? (у секундах)", ["5", "п'ять", "10", "5-10", "десять"],
     ["5", "5", "10", "5-10", "10"]),
]


def chat(model, messages, host="http://localhost:11434"):
    r = requests.post(f"{host}/api/chat", json={
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": 0, "top_k": 1, "num_ctx": 4096}}, timeout=300)
    r.raise_for_status()
    return r.json()["message"]["content"]


def make(*parts):
    model = ":".join(parts)
    def predict(q, answers):
        msgs = [{"role": "system", "content": SYSTEM}]
        for eq, ea, el in EX:
            msgs += [{"role": "user", "content": user_msg(eq, ea)},
                     {"role": "assistant", "content": json.dumps({"labels": el}, ensure_ascii=False)}]
        msgs.append({"role": "user", "content": user_msg(q, answers)})
        out = chat(model, msgs)
        try:
            arr = json.loads(out[out.index("{"): out.rindex("}") + 1])["labels"]
        except Exception:
            return list(range(len(answers)))
        labels = []
        for i in range(len(answers)):
            raw = normalize(arr[i]) if i < len(arr) else ""
            labels.append(key(raw) or f"#{i}" if raw else f"#{i}")
        return labels
    return predict
