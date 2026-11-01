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

1. First use: select both game inputs, prepare, initialize a model connection,
   then navigate to operations. No start is submitted by configuration alone.
2. Edit commander text, switch workspaces and return. The draft survives and
   starting remains blocked until it is saved.
3. Discover, prepare, check and start. Exactly one start is submitted; the stop
   action remains reachable while browsing every workspace.
4. Stop enters `stopping` before a subsequent status query proves release. New
   starts and configuration edits remain blocked until that proof arrives.
5. Simulate pending configuration, then requery on the connections page. Old
   readiness is revoked; recovering does not automatically restart or reuse it.
6. Switch workspaces repeatedly. The configuration panel stays mounted, and
   navigation does not requery configuration or reset its draft.

These checks validate React interactions and presentation only. Windows file
dialogs, DPAPI, packaged native RPC, installation and live-game return must be
tested separately on a new Windows candidate.
