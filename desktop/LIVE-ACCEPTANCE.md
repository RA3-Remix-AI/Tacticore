# Desktop live host control v4

Current output: `CommanderDesktop.live.v4.exe` (SHA256 `c6684d252e05f981f4064fe486cd285c0ccea1236917624e9e86068a18e12ab5`). v3 added computer-perspective visibility and tactical evidence to launch, pinned source/binary inputs, and displayed visibility/tactical counters. v4 corrects end-of-match and sidebar copy; it changes no game command or saved configuration. New binaries preserve earlier windows and executables.

The real 20261025-034721 match completed with Iron versus native Oleg, both medium/10000, observer player2. Iron won at the 09:32 statistics screen. This match used CLI arming before start, not a desktop-start end-to-end exercise. See [current acceptance](../acceptance/vision-tactics-status.md). Safe control/continuous lifecycle passed; attack and raid goal completion did not pass.

Visual QA against the actual completed session checked four-page layout, dark drop-downs, two reusable connections, three commander profiles, inherited DeepSeek configuration, and player3 session/UUID/package verification. Read-only observation showed actual request/production/tactical counts. No configuration save, connection test, start or stop was used in this visual check. Earlier tests below describe the v2 foundation; they do not establish tactical effectiveness.

## Earlier control validation

Output: `CommanderDesktop.live.v2.exe`. Existing desktop executables, windows and user configuration were not changed by this build. `CommanderHub` adds a fourth dark-themed page; it does not automatically observe or launch a host.

Click **观察当前真实会话** to read only `../acceptance/active-session.json`, then the derived `<run_directory>/battle-host/host-status.json`. Arbitrary JSON imports remain confined to the simulation page. Refresh runs off the UI thread every three seconds.

The page displays the current single-host binding (player, commander name, Soviet/Allied/Japan role), host state/reason, current plan and budgets, task module/status/reason, latest snapshot and credits, model requests/acceptances/rejections/timeouts, transport counts, memory context builds/compactions/payload bytes and task counts. Current host schema contains one binding; this release does not invent other player bindings.

Independent checks:

- Session UUID; run containment under acceptance/runs; host session/PID/start-time/mod/registry metadata.
- Actual game process creation time, exact image path and supported executable SHA256.
- Actual package SHA256; skudef's single add-big reference; registry package/revision and compiled IDs.
- Collector identity's UUID/connection/player-index/store membership/AIPlayer and registry asset/instance/side correlation.
- Final session bytes unchanged during validation; host status age at most 20 seconds.
- For stop eligibility: live Python PID, creation before status write, WMI command line containing the exact absolute battle_host.py and exact absolute active-session.json --session argument. Missing WMI/process access fails closed.

These are independent process/file consistency checks, not a second native memory collector or cryptographic host attestation. Telemetry reports the host's execution flag but does not authorize execution. Arbitrary status imports cannot enable start.

## Formal host launch (v2)

Choose the saved commander in the live page, then **检查启动条件**. The app invokes the fixed bundled Python interpreter with the absolute integration/battle_host.py, --session acceptance/active-session.json, --commander chosen UUID, --player 3, --library the saved library, --execute, and the fixed run183816 primitive trace and persistent production evidence. The first invocation adds --check. This does not request a model or inject a bridge; the collector creates local snapshot/identity files while reading the game.

Start requires exit 0, can_start=true, computer/package/production evidence verified, reason ready, matching UUID/player/session; it then independently verifies process/exe/mod/skudef/registry/native identity. Latest identity must itself contain the active session/PID/package hash. Unsaved profiles, missing saved model/key, old stop markers or existing live host block start. The check fingerprints the active session, saved library, encrypted credential file, host script, primitive report/stream and persistent status/audit.

**开始指挥** is enabled only after this check, for at most 20 seconds and while the selected profile/configuration remains unchanged. Clicking it repeats the complete formal check, requires the same session and fingerprints, checks for UI closing or new configuration edits, and launches exactly the formal host without --check. It does not open/restart the game. The host owns its player lease, waits for a barracks and its 30-second natural production observation, then handshakes with the persistent executor. The host may make paid real model requests and bounded real production commands; the UI explains that before the click. Arguments use Windows quoting, UseShellExecute=false and a hidden process window. API keys are never passed on the command line or logged.

The old simulation page start button remains disabled. A real host start was not clicked or invoked during this agent's validation. The fixed Python path is `%USERPROFILE%/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`; no WindowsApps alias or installation is used. A consumed process reports fresh_process_required; malformed/fault output fails closed.

**停止宿主派单** is enabled only for fully verified, fresh telemetry from a live initializing/running/paused host. On click it revalidates and matches session, status path, host PID, player, commander UUID and connection UUID against the displayed record. It atomically writes only `{session_id: ...}` to that host's stop.json. It never kills Python, game or unrelated processes. The host is responsible for cancelling model/dispatch work and leaving native AI running. **停止观察** only stops the page timer; closing the app likewise does not stop the external host.

## Validation

Run `./Test.ps1`: 69 passing checks, including filesystem/status/stop isolation and formal start tests. New cases use an isolated fake session, synthetic mod and test-injected process probes/CLI/host launcher; no real host or game command occurs. They cover second check before start, incorrect UUID, unsaved state, consumed process, rejection preventing launch, no shell, and Windows argument quoting. Existing HTTP tests use loopback/fake keys.

Run `./AcceptanceTests.exe --live-readonly`: actual session 00b2ebe2-8de3-4308-ab60-e8bba2fbe838 passed game process/hash, mod and registry/identity chain. The observed status was stopped/host_time_limit, dry-run; freshness false, host alive false, can_stop false. This command reads only and writes no stop file.

The actual formal --check was run once with the fixed runtime and evidence paths against the old session. It returned exit 1, state fault, reason ValueError (no can_start grant); no host was started and no model request or injection occurred. The fresh session's actual readiness remains for parent QA.

Build: `./Build.ps1 -OutputName CommanderDesktop.live.v2.exe`.

Pending parent QA: fourth tab fit/theme/scroll areas; click observe to view stopped historical record; next live host should display its current task/memory counters. No GUI was opened or controlled for this task. An actual stop should only be exercised by the coordinating parent when intended; this agent did not stop the current host.
