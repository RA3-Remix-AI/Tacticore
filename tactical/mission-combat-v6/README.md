# MCT6: early AK preparation and bounded native burst

This isolated revision has **no field capability yet**. MCT5, its original
qualifier, qv2, binaries and raw reports remain unchanged. Only the sole game
runner executes this program, after the other native channels are fully inert.

`build-manifest.json` and `revision.json` pin this revision. The protocol is
MCT6/v14, WM_APP+0x382, `TacticalMissionCombat6.dll`, mapping prefix
`RA3TacticalMissionCombat6_`, fourteen original hooks / restoration mask16383.
The real host `--layout` and ctypes both report Event852, Tactical3490916,
events offset1124. The independently extracted timer/pointer RVAs and fourteen
exact executable entry signatures are in `inert-layout.json`.

## Execution

Normal transfer(false), clean Stop, optional exact normal Conscript toggle,
15 logical frames plus three distinct idle-AK samples, another clean Stop,
approach with normal Move, current full-FOV engagement gate at150, clean Stop,
one normal ScriptAttack(source1, INTMAX), bounded native bursts, normal Stop,
actual retreat-origin arrival in three distinct frames and native-pool return.
No ammunition, HP, price, status or weapon-selection fields are written.

Early loadout stages remain publicly `approach`; internal stage11 is the final
`prepare` before `engage`. Public progress retains its original nine fields,
derived solely from immutable published native events. No phase regression.
Current footprint FOV is required to attack. Approach-only memory uses the last
legal same-ID target XYZ/frame for900 frames, with the original2100 approach /
4500 whole-mission bounds. Hidden position or HP is never refreshed.

The configured engagement deadline is180..300 frames, default300. Successful
attributed damage goal is `min(150 HP, .2 * entry-visible target HP)`, or an exact
observed source-lethal transition. Goal, low HP, FOV loss, cancel, watchdog and
absolute deadline can end an order earlier. The actual duration is reported;
the executor does not promise180 frames of firing. Native aiming, LOS, bursts
and reloading determine the real outcome.150 is the audited AK base range policy
input, not a claim that visibility guarantees a firing line.

Event22 observes same-entry ammo decrease;67 observes a same-entry increase to3
with the previous native sampling frame/tick. The qualifier reconstructs the
entire transition chain, actual rounds and observed refills. Polling can miss a
full consume/refill cycle; such an unexplained chain fails qualification rather
than inventing shots. Each accepted HP loss still needs its real source actor,
target Body, matching commit, exact AK/GUN DamageInfo packet and an enclosing
observed ammo-consumption interval. An ammo drop alone is never damage.

For lethal synchronous calls, the hook proves full FOV before the real call and
then pins frame, thread, Thing ID, owner, template and the same Body/vtable before
reading post-call HP, allowing zero/negative HP. It does not refresh hidden XYZ
or require a post-death fog record. Reported amount must still match the actual
HP delta: clamped overkill with unequal packet amount remains unknown.

## Sole-runner command

Use a newly prepared mission JSON containing `schema_version:1` and an absolute
`expires_frame` at most4500 frames ahead; omission of `retreat_point` freezes the
actor's actual late-sampled initial position. Explicit trusted home points keep
their existing provenance checks. No model coordinates are accepted.

```text
python bridge-probe/tactical/mission-combat-v6/lease.py --session SESSION.json --natural NATURAL.json --object-id OWN_ID --mission-file MISSION.json --expires-frame DEADLINE --proof-file FOV_PROOF.json --contact-id CURRENT_CONTACT --command-id UUID --task-id UUID --seq INCREASING --post-frames 30 --execute --output NEW_RAW.json
```

The old `field_combat.py` helper must explicitly allow backend
`mission-combat-v6`; it must not substitute another visible contact, reuse an
old address or load this concurrently with formation/production hooks. Native
admission independently checks exact own Conscript, actual idle16/normalMove1,
positive valid native surface cache, no air/garrison/holder/deferred lock. The
wrapper additionally records the full late admission certificate.

Authoritative pure API is
`mission_combat_v6_qualification.qualify_path(path)` / `qualify(report)`.
Success status stays `continuous_ak_combat_mission_verified`. The result exposes
`sustained_engagement_verified`, `damage_goal_reached`, `engagement_partial`,
`observed_reload_count`, `observed_rounds_consumed`, actual engagement duration,
qualified source hits and independent approach/retreat/return booleans. It does
not call damage economic suppression. Two same-frame hits do not qualify as
sustained: at least two attributed hits over at least15 logical frames are
required. Root's capability-source gate additionally requires real reload,
hidden movement/reacquisition and long retreat from new field raw.

Pre-native rejection uses `pre_dispatch_v6_contract.py`; launched zero-lease
rejection uses `mission_v6_gate_no_lease.py`; actual own-death release uses
`mission_v6_readonly_disposal.py` with new exact layout, timer0, fourteen pristine
entries and two complete advancing-frame ID-absence scans. Release never creates
retreat, return or completion. On real error32 collect immediately with the game
running to measure corpse-removal latency; a much later success cannot prove the
12-second immediate collection path.

Offline tests: `test_mission_combat_v6` and `test_mission6_client`. These include
synthetic raw protocol/negative boundaries, real compiled ctypes ABI, exact
fourteen executable bytes and fake-child/kernel client routes. They do not
constitute actual field effects or unlock model capabilities.
