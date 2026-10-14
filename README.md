# Стадо (Herd Mentality)

Party game for a group of friends. The host's Android phone runs everything; players join from any phone browser by scanning a QR code — no app, no account, no internet.

## How it works

- **Host app (APK)** starts a small web server on the phone and shows a QR code with `http://<phone-ip>:8080/`.
- **Players** must be on the same Wi-Fi as the host, or connected to the host phone's hotspot. They scan once and stay connected for the whole game.
- Everyone answers the same question. The single biggest group gets a cow each; a tie for biggest scores nobody. If exactly one player is alone with their answer, they take the **pink cow** and can't win while holding it. First to N cows (default 8) without the pink cow wins.
- **Auto-grouping (optional):** a tick-box on the host screen. Two small ONNX models run on the host phone (a multilingual sentence encoder + an NLI cross-encoder, ~430 MB downloaded once from the `judge-v1` release) and group answers that mean the same thing ("тачка" = "машина", "вбиральня" = "туалет"). Without it, a conservative fuzzy matcher groups obvious matches. Either way the host can move any answer between groups before scoring.
- Three question levels: light, spicy, 18+. The host can also type a custom question.

## Build

Every push to `main` builds a signed APK in GitHub Actions and publishes it as the latest release:
`https://github.com/sokolovskiy0103/Herd_Mentality/releases/latest/download/HerdMentality.apk`

The signing key is committed on purpose (hobby app) so each new APK installs over the previous one.

## Code map

- `app/src/main/java/.../Game.kt` — rules and state
- `FuzzyMatcher.kt`, `AnswerRules.kt`, `Unigram.kt`, `Judge.kt` — answer grouping (fuzzy fallback, rules + clustering, tokenizer, ONNX models)
- `eval/` — grouping benchmark (`cases.json`), reference pipeline and `export_models.py` that builds the model archive
- `GameServer.kt` — Ktor HTTP + WebSocket server
- `GameService.kt` — foreground service keeping the server alive
- `app/src/main/assets/web/` — host and player pages, question pack

## Grouping model archive

`Judge.kt` downloads `herd-judge-v1.zip` from the `judge-v1` (pre-)release of this repo. It is built by `eval/export_models.py` (pruned vocabularies, int8 encoder, fp16 NLI) and contains `embed.onnx`, `embed.vocab`, `nli.onnx`, `nli.vocab`. Benchmark: `python eval/run_eval.py ...`, reference pipeline `eval/ref_pipeline.py` (pairwise F1 ≈ 0.76 on `eval/cases.json`, vs ≈ 0.40 for the previous Gemma judge).
