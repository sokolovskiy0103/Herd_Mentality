"""Export mpnet-multilingual (embeddings) and mDeBERTa-xnli (NLI) to pruned, int8 ONNX + compact vocab files.
Usage: [KINDS=embed,nli] python export_models.py <outdir>
"""
import sys, json, os, pathlib, numpy as np, torch, onnx
from onnx import numpy_helper, helper, TensorProto
from onnxruntime.quantization import quantize_dynamic, QuantType
from transformers import AutoModel, AutoModelForSequenceClassification
from huggingface_hub import hf_hub_download

OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
MODELS = {
    "embed": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "nli": "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
}


def allowed(piece):
    for ch in piece.replace("▁", ""):
        o = ord(ch)
        if not (o < 0x250 or 0x400 <= o <= 0x4FF or o in (0x2019, 0x2018, 0x2013, 0x2014, 0x2026)):
            return False
    return True


def prune(tok_json):
    vocab = tok_json["model"]["vocab"]
    added = {a["id"] for a in tok_json["added_tokens"]}
    keep = [i for i, (p, s) in enumerate(vocab) if i in added or (allowed(p) and not (p.startswith("<0x") and p.endswith(">")))]
    return keep


def quantize_gather(path):
    """Replace the big fp32 word-embedding table by int8 rows + per-row scales."""
    m = onnx.load(str(path))
    inits = {i.name: i for i in m.graph.initializer}
    done = 0
    for node in list(m.graph.node):
        if node.op_type == "Gather" and node.input[0] in inits:
            w = numpy_helper.to_array(inits[node.input[0]])
            if w.ndim != 2 or w.shape[0] < 20000:
                continue
            scale = np.maximum(np.abs(w).max(1, keepdims=True), 1e-8) / 127.0
            q = np.round(w / scale).astype(np.int8)
            n = node.input[0]
            m.graph.initializer.remove(inits[n])
            m.graph.initializer.append(numpy_helper.from_array(q, n + "_q"))
            m.graph.initializer.append(numpy_helper.from_array(scale.astype(np.float32), n + "_s"))
            ids = node.input[1]; out = node.output[0]
            g1, g2, c, mul = n + "_g1", n + "_g2", n + "_c", out
            idx = list(m.graph.node).index(node)
            new = [helper.make_node("Gather", [n + "_q", ids], [g1], axis=0),
                   helper.make_node("Cast", [g1], [c], to=TensorProto.FLOAT),
                   helper.make_node("Gather", [n + "_s", ids], [g2], axis=0),
                   helper.make_node("Mul", [c, g2], [mul])]
            m.graph.node.remove(node)
            for k, nn in enumerate(new): m.graph.node.insert(idx + k, nn)
            done += 1
    assert done == 1, f"expected exactly one embedding gather, got {done}"
    onnx.save(m, str(path))


def fp16_weights(path):
    """Store large fp32 weights as fp16 + Cast back to fp32 (lossless enough, half the size)."""
    m = onnx.load(str(path)); casts = []
    for init in list(m.graph.initializer):
        if init.data_type == TensorProto.FLOAT and int(np.prod(init.dims)) >= 4096 and not init.name.endswith("_s"):
            arr = numpy_helper.to_array(init)
            name = init.name
            m.graph.initializer.remove(init)
            m.graph.initializer.append(numpy_helper.from_array(arr.astype(np.float16), name + "_h16"))
            casts.append(helper.make_node("Cast", [name + "_h16"], [name], to=TensorProto.FLOAT, name="cast_" + name))
    for k, c in enumerate(casts): m.graph.node.insert(k, c)
    onnx.save(m, str(path))
    print("fp16 weights:", len(casts))


for kind, name in [(k, v) for k, v in MODELS.items() if k in os.environ.get("KINDS", "embed,nli").split(",")]:
    print("==", kind, name, flush=True)
    tj = json.load(open(hf_hub_download(name, "tokenizer.json"), encoding="utf-8"))
    keep = prune(tj)
    vocab = tj["model"]["vocab"]
    old2new = {o: n for n, o in enumerate(keep)}
    sp = {a["content"]: a["id"] for a in tj["added_tokens"]}
    print("kept", len(keep), "of", len(vocab))
    if kind == "embed":
        model = AutoModel.from_pretrained(name).eval()
        emb = model.embeddings.word_embeddings
    else:
        model = AutoModelForSequenceClassification.from_pretrained(name).eval()
        emb = model.deberta.embeddings.word_embeddings
    new_emb = torch.nn.Embedding(len(keep), emb.weight.shape[1], padding_idx=old2new.get(emb.padding_idx))
    new_emb.weight.data = emb.weight.data[keep].clone()
    if kind == "embed": model.embeddings.word_embeddings = new_emb
    else: model.deberta.embeddings.word_embeddings = new_emb
    model.config.vocab_size = len(keep); model = model.float()

    class Wrap(torch.nn.Module):
        def __init__(s, m): super().__init__(); s.m = m
        def forward(s, input_ids, attention_mask):
            if kind == "embed":
                h = s.m(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
                mk = attention_mask.unsqueeze(-1).to(h.dtype)
                e = (h * mk).sum(1) / mk.sum(1).clamp(min=1e-9)
                return torch.nn.functional.normalize(e, dim=-1)
            return s.m(input_ids=input_ids, attention_mask=attention_mask).logits
    ids = torch.tensor([[1, 5, 6, 7, 2], [1, 5, 6, 2, 0]]); am = torch.tensor([[1] * 5, [1, 1, 1, 1, 0]])
    raw = OUT / f"{kind}.fp32.onnx"
    torch.onnx.export(Wrap(model), (ids, am), str(raw), input_names=["input_ids", "attention_mask"], output_names=["out"],
                      dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"}, "out": {0: "b"}},
                      opset_version=17, dynamo=False)
    q = OUT / f"{kind}.onnx"
    # embeddings tolerate dynamic int8 (F1 0.616 vs 0.624 fp32); the NLI model does not (0.62 vs 0.72),
    # so its weights are stored as fp16 instead: same ~300 MB, no accuracy loss.
    if kind == "embed":
        quantize_dynamic(str(raw), str(q), weight_type=QuantType.QInt8, op_types_to_quantize=["MatMul"], per_channel=True)
        quantize_gather(q)
    else:
        import shutil; shutil.copy(raw, q)
        quantize_gather(q)
        fp16_weights(q)
    raw.unlink(missing_ok=True)
    for extra in OUT.glob(f"{kind}.fp32*"): extra.unlink()
    print("size MB", q.stat().st_size / 1e6)

    unk = old2new[tj["model"]["unk_id"]]
    cls = old2new[sp.get("<s>", sp.get("[CLS]"))]; sep = old2new[sp.get("</s>", sp.get("[SEP]"))]
    pad = old2new[sp.get("<pad>", sp.get("[PAD]"))]
    with open(OUT / f"{kind}.vocab", "w", encoding="utf-8", newline="\n") as f:
        f.write(f"#unk={unk} cls={cls} sep={sep} pad={pad} pair={1 if kind == 'nli' else 0}\n")
        for o in keep: f.write(f"{vocab[o][0]}\t{vocab[o][1]:.5f}\n")
    if kind == "nli":
        print("labels", model.config.id2label)
        (OUT / "nli.labels.json").write_text(json.dumps(model.config.id2label))
