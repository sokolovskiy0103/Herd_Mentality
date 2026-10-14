# Стадо (Herd Mentality)

Party game for a group of friends. The host's Android phone runs everything; players join from any phone browser by scanning a QR code — no app, no account, no internet.

## How it works

- **Host app (APK)** starts a small web server on the phone and shows a QR code with `http://<phone-ip>:8080/`.
- **Players** must be on the same Wi-Fi as the host, or connected to the host phone's hotspot. They scan once and stay connected for the whole game.
- Everyone answers the same question. The single biggest group gets a cow each; a tie for biggest scores nobody. If exactly one player is alone with their answer, they take the **pink cow** and can't win while holding it. First to N cows (default 8) without the pink cow wins.
- **Judge:** Gemma 4 E2B runs on the host phone (LiteRT-LM, GPU with CPU fallback) and groups answers that mean the same thing. It is downloaded once from Hugging Face (~2.6 GB) from the host screen. Without it, a conservative fuzzy matcher groups obvious matches. Either way the host can move any answer between groups before scoring.
- Three question levels: light, spicy, 18+. The host can also type a custom question.

## Build

Every push to `main` builds a signed APK in GitHub Actions and publishes it as the latest release:
`https://github.com/sokolovskiy0103/Herd_Mentality/releases/latest/download/HerdMentality.apk`

The signing key is committed on purpose (hobby app) so each new APK installs over the previous one.

## Code map

- `app/src/main/java/.../Game.kt` — rules and state
- `FuzzyMatcher.kt`, `JudgePrompt.kt`, `Judge.kt` — answer grouping
- `GameServer.kt` — Ktor HTTP + WebSocket server
- `GameService.kt` — foreground service keeping the server alive
- `app/src/main/assets/web/` — host and player pages, question pack
