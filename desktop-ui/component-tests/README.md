# Native workspace interaction preview

`native-workspace-preview.html` mounts the real `NativeApp`, game setup and
connection panels with an in-memory native transport. Use a separate local
origin from normal app development:

```sh
npx vite --host 127.0.0.1 --port 5176 --strictPort
```

Open `/component-tests/native-workspace-preview.html` on that server. The visible
preview toolbar switches between configured, first-use, active-run and pending
configuration scenarios. It also reports start, stop and configuration-query
counts. Preview reload clears only the last-run key on this dedicated origin.

This fixture is not imported by either production entry point. No game, model,
credential store or real native command is accessed. Use dummy values only.
Diagnostics intentionally returns an unavailable result; this fixture does not
simulate a successful diagnostic download.

Interaction checks:

1. First use (`?first_use=1`): the three-step wizard (游戏与 Mod, 模型与 API Key,
   对局模式) cannot finish until each step is done. No start is submitted by
   configuration alone. "稍后再说" skips to the main screen.
2. Settings → AI 风格: edit the style, switch pages and return. The draft survives
   and Start stays blocked ("去保存") until it is saved.
3. 对局: 查找对局 shows the match card (map, mode, teams, model seat), then a
   single 开始 prepares, checks and starts. Exactly one start is submitted; 停止 AI
   stays in the top bar on every page while the run holds the game.
4. Stop enters "停止中" before a later status query proves release. New starts
   and configuration edits stay blocked until that proof arrives.
5. Simulate pending configuration, then 重新读取 in 模型与 API Key. Old readiness
   is revoked; recovering does not restart or reuse it.
6. Switch pages repeatedly. The setup panels stay mounted; navigation does not
   requery configuration or reset the draft.
7. Waiting-model and failed-call scenarios: 详细信息与诊断 shows the latest call
   without guessing an authentication cause or retrying.
8. Active run: the decision feed fills in over time (mock records from
   `src/runtime/decisionFixtures.ts`). After stop and release, 复盘 shows the
   result, counts and the full timeline.
9. "旧版后台" scenario: candidates without `scenario` and an unsupported
   `run.decisions` degrade to the legacy map line and a plain notice.
10. Narrow and wide windows: lobby instructions for each mode are readable and
    never name a fixed map, seat or start position.

The Playwright scripts `configuration-gate-parent-v1.mjs` and
`connection-query-notice-v1.mjs` target the pre-beta.4 labels and Windows-only
paths; they need updating before they can be rerun against this UI.

These checks validate React interactions and presentation only. Windows file
dialogs, DPAPI, packaged native RPC, installation and live-game return must be
tested separately on a new Windows candidate.
