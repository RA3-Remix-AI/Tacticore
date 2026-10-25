# Continuous Conscript combat mission

This is a new independent backend. It never replaces archived combo/formation bins.

Normal Script Stop -> normal Script Move approach in bounded pathfinding segments ->
current player3 full-footprint FOV confirmation -> Stop / optional exact normal
Conscript toggle / 15 game-frame pack + three distinct idle AK frames -> fresh Stop ->
one Script Attack with normal native burst -> source-bound AK/GUN HP submission ->
Stop / retreat through actual reached checkpoints and a trusted own retreat point ->
three distinct arrival positions -> Stop / normal AI pool return.

`mission_protocol=continuous_tactical_v1`; total maximum4500 logical frames (15fps).
Approach2100, engagement300, retreat1800; per movement request <=250 XY units,
no progress for250 frames or450-frame segment cap causes retreat/failure. Maximum
12 approach orders and24 retreat orders. These are pathfinding requests; the code
does not claim interpolated endpoints are already reachable. FOV loss ends pursuit
and retreats without reading hidden target coordinates. HP<=40% initial triggers
retreat. Every native SDK call executes on the naturally witnessed window thread.

No model-generated coordinates. `mission-file` schema1 has an absolute
`expires_frame`, optional bounded `approach_frames/engage_frames/retreat_frames`,
`retreat_hp_fraction`, and `retreat_point={xyz,observed_frame,source,anchor_object_id}`.
`own_home_base` requires exact own Soviet ConstructionYard anchor and a sampled
own point80..300 away from its center. `own_actor_history` can only bind the current
selected actor's actual dispatch origin (within15). Neither label promises the
location is free of enemies. An absent point falls back to that actor's origin.

CLI (sole runner, only after Root Go):

    python mission-combat/lease.py --session SESSION --natural NATURAL --object-id OWN_CONSCRIPT --proof-file PROOF --contact-id CONTACT --mission-file MISSION.json --expires-frame ABSOLUTE_GAME_FRAME --command-id UUID --task-id UUID --seq NEW_SEQ --post-frames 30 --execute --output NEW_REPORT.json

Fresh contact/object/session guards are rechecked by the wrapper and native code.
Do not reuse an existing report, task, command, sequence, or stale actor address.

Native: `TacticalMissionCombat.dll`, WH_GETMESSAGE export
`TacticalMissionCombatControl`, message WM_APP+0x37a, magicMCT1/version9,
mapping `Local\RA3TacticalMissionCombat_PID_TOKEN`,14 hooks/restore16383.
`stop_requested` is emergency Stop/return; `retreat_requested` requests the bounded
retreat state without cancelling the executor or releasing its reservation.
Pause forbids SDK calls; cancelled/expired/failed approach never counts completed.
Death is error32/terminal hook removal; unknown disposal remains reserved until an
independent read-only ID注销 proof exists. No field disposal claim is made here.

`mission_combat_qualification.qualify/qualify_path` independently reconstructs
normal call chains, timing, three-frame Stop/arrival geometry, current FOV, exact
AK DamageInfo/source/target/HP/near-tick ammo, retreat and pool return. Success is
`continuous_ak_combat_mission_verified`; source capability additionally requires
`long_approach_verified` (initial>=300, actual advance>=120). Runtime near attacks
may succeed without being used as evidence that far approach works.

`progress` is only published after actual issued_frame. Its revision is the last
published native event sequence; all nine fields derive from published events or
the immutable deadline. A progress update is never a completed task.

The progress `approach_distance` is remaining actor-to-explicit-target XY distance
at the last current-visible sample, frozen if visibility is lost. It is not route
length. Actual approach advance is independently reconstructed for qualification.

Pre-native rejection uses `pre_native_launch_v1` and child exit64. The wrapper
must atomically publish `native_launch_intent_persisted=true` before it can launch
the native host. After that boundary it can never issue a no-dispatch attestation.
Only a bound exit64 report with no launch intent, no native state/events and exact
session/actor/command/task/sequence/source hashes releases a never-held reservation.
Any possible native launch with missing evidence remains unknown. Existing raw
reports are never replaced by a new invocation.

First live calibration: `acceptance/runs/20261025-095141-commander/main-mission04.json`.
Actor830 approached the currently visible exact Refinery774 from429 units, issued
at3392, made one normal Attack at3527, produced a source-bound direct AK HP-5 event
at3531, showed ammo drop at3532, and actually returned to its origin and native
pool by3656. Both long approach and long retreat passed the raw verifier. A separate
read-only terminal file checked the pinned timer0, native header, and all14 restored
EXE entry bytes. This was a40000-credit/easy-opponent calibration, not the formal
10000-credit/medium match and not evidence of model tactical quality by itself.
