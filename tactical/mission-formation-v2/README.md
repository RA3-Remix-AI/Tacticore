# Continuous two-role mission — experimental, no live grant yet

This is an isolated MFM1/version1 backend. It does not replace the previously
verified formation-stop-v2 DLL or any production, combat, strategy or host source.
The source was derived from the proven normal ScriptMove/Stop, normal AK command
preparation, exact full-footprint player-3 visibility and current DamageInfo packet
primitives. `primitive-provenance.json` records the predecessor source hashes.

Native scope: a Conscript front and a Flak positional support. Both are borrowed
once, advance over a finite sequence of **actual recorded own positions**, hold and
follow in separate stages, and produce paired same-tick geometry. Only the front
receives a ground attack. A successful direct AK source packet triggers withdrawal
over the completed route in reverse order; the support withdraws first while the
front holds, then the front follows. Both must physically reach their original
known own positions, settle, and return through the normal native AI pool API.
There is no claim that Flak fires at ground targets. Invalid or hidden contacts
never authorize target-position updates or firing.

`mission_route.record_history(memory, session, own_snapshot, frame, history_dir)`
accepts the raw `own_candidates` dictionary containing `candidates` entries with
hex address/owner_address/type_hash, object_id and owner_index_candidate=3. It
revalidates identity, real own XYZ, HP, garrison/immobile status and frame consistency.
The host can pass `formation_history_dir` in its private schema1 mission context.
The wrapper then plans at most 16 legs of 40–170 units over those real points; lack
of a route is a pre-native rejection, not a hidden-enemy fallback. An explicit
route may instead contain `xyz`, `own_source_path`, `own_source_sha256`, and
`own_source_object_id` per point. These are private host inputs, never model fields.
Recorded pass-through by an amphibious scout does not promise another unit can
reach a point; actual arrival remains mandatory and a stalled leg fails honestly.

CLI:

```text
python lease.py --session SESSION --natural NATURAL --front-id CONS_ID
  --support-id FLAK_ID --mission-file PRIVATE_CONTEXT_JSON
  --proof-file CURRENT_SESSION_VISIBILITY_PROOF --contact-id EXPLICIT_CONTACT
  --expires-frame ORIGINAL_DEADLINE --command-id CHILD_COMMAND_UUID
  --task-id CHILD_TASK_UUID --seq MONOTONIC_SEQ --execute --output NEW_REPORT
```

The target must be the high-level task's explicit current visible ground contact;
the backend does not select a different target. A phase5 read-only/paused waiter
may be used outside the backend; normal field execution starts after actual resume.
`field_plan.py` is a read-only calibration planner. It never loads the DLL.

Protocol: `WM_APP+0x37e`, magic `0x4d464d32`,
`Local\RA3TacticalMissionFormation2_<pid>_<token>`,
`TacticalMissionFormation2.dll`, 13 hooks, successful mask 8191. The current offline
ABI is Event820/Tactical6718400/events960. The task deadline remains immutable and
bounded by 4500 frames. Stage transitions issue finite commands, not periodic
command replacement. `retreat_requested` requests physical withdrawal;
`stop_requested` and heartbeat loss request emergency cleanup.

`formation_mission_qualification.py` exports pure `qualify(report)`,
`progress(report, public_mission_id)` and `control_release(report)`. Progress has
exactly the shared nine fields; revision is the last published event sequence,
remaining distance is from the last currently visible front/target sample and
freezes when hidden. The published stages are approach/prepare/engage/retreat/
restored. Progress is never completion evidence. Qualification requires all route
stages, front source damage with support geometry, real long retreat, two clean
normal returns, and actual timer/entry restoration. `control_release` is independent
of goal success and distinguishes two returns from death disposal.

One actor's death enters separate cleanup: only surviving borrowed actors receive
normal Stop and pool return. A dead actor is never marked returned. Native ID
absence requires two distinct advancing-frame complete scans; a separate read-only
sidecar must also establish absence before the pure release verifier accepts it.
This branch has offline matrix tests but still needs a real field fault case.

Build: run `prepare_sources.py`, `build.ps1`, `freeze_build.py`. The generated
`lease.cpp` contains the expanded state machine. Both its hash and all local
`*.cpp.inc`/generator/runtime helper hashes are recorded and frozen. Native and
Python ABI layouts are compared before any field dispatch. Pre-launch rejection
uses the shared `pre_native_launch_v1` attestation/exit64 boundary; a possible native
Popen can never attest that control was never held.

Current validation: 23 offline boundary tests pass, including same-tick geometry,
distinct-frame arrival, role sequencing, hidden-distance freezing, immutable
progress, two-actor release/death matrices and old-primitive rejection. A real
current-menu invocation confirmed actual child exit64 and all nine pre-dispatch
verification checks with zero SDK dispatch. No MFM DLL has yet been loaded into
the game. `build-manifest.json` explicitly records `live_effect_verified=false`.

At the paused 21440/session12e52d25 calibration, `coord-plan01.json` correctly found
no valid pair: free Conscripts and Flaks were more than 400 units apart. That is a
zero-dispatch preparation result; it is not a native mission failure. No thresholds
were relaxed to manufacture a pair.

The origin is the two actors’ current verified owned, independently movable positions with no currently visible enemy within 350. Nearby own base distances are diagnostic only; no arbitrary base-radius gate is used and this does not guarantee hidden-threat safety. Native movement, damage, arrival and restoration thresholds are unchanged.
