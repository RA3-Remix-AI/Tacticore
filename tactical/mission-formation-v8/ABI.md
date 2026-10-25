# MFM8 native protocol (independent candidate; ABI fixed)

Independent `TacticalMissionFormation8.dll`, `TacticalMissionFormation8Control`, `Local\\RA3TacticalMissionFormation8_<pid>_<token>`, magic `0x4d464d38`, version8, message `WM_APP+0x388`, timer ID `0x52413378`. The original13 hooks/signatures from MFM4 remain, with three additional passive copy/unpack/dispatcher observers; total16 and restore65535. RVAs are extracted only after final compilation. No live installation authorized until the completed native algorithm, wrapper and qualifier are frozen and audited.

Actual 32-bit C++ layout: Breadcrumb104 / MoveLineage568 / Event1616 / Tactical13266172 / events27900. Old Tactical prefix through MFM4 planning fields is unchanged. `shared.h` is the canonical field order. Both Native and wrapper keep `route_count`, `route_ready`, `route_generation` zero: no host planning handshake or externally supplied route exists.

Input uses the prior exact player/AI/UUID/actor/template/button/current-contact identity, fresh complete FOV, origin350, initial HP>=50 and helper2 state1/10/16. The new fixed bounds are memory_ttl_frames900, approach_limit2100, retreat_limit1800, hold_timeout_frames60, combat_frames<=300, same absolute mission_deadline_frame<=4500 remaining. Native copies absolute deadline and lease length privately. Public mission stages remain approach1, prepare/engage2 (lease_stage0/3/4 vs1), retreat3, final-stop4, cleanup5. Native phase7 remains fault cleanup, phase2 returned-post-observation, phase3/4 terminal. No public planning stage is added.

The front leader receives normal source1 Move toward the last completely visible target point. Hidden navigation never refreshes target coordinates or HP; reacquisition is required before prepare/Attack. Flak follows only prior source-positive front breadcrumbs at least80m apart, choosing a point behind the leader's actual travelled distance. The first crumb of each source role/mission stage is its real phase origin: it may be targeted once the leader has moved>=25 and current leader-to-goal XY>=25; subsequent crumbs require path difference>=100 and the same actual25 clearance. The first source crumb can have a nonzero global index in retreat. It completes <=15XY/10Z for three different logical frames and normal Stop3 before accepting another breadcrumb. Normal source1 Move is issued only at a new actual waypoint/state transition, never every poll.

Breadcrumb identity comes from actual native reads: thing, ID, owner, compiled type, update/backref, seven native status words, valid native surface cache bit4/height distance<=.5, holder0, finite XYZ/HP>0, exact known Ground templates. The read is repeated with same logical frame/identity/surface values before acceptance. Ground160 is diagnostic, not positive evidence. Initial admission still requiresHP>=50. Each accepted crumb is immutable; `published_seq` is the raw event80 sequence. `surface_verified` cannot replace independent reconstruction.

New raw events (all contain actual role position/HP/state/path and common order identity):

- 80: accepted actual breadcrumb; role and arg=index; complete Breadcrumb is echoed with its own published_seq. Header crumbs[role][index] is immutable.
- 81: normal follower Move about to be issued, contains the referenced prior complete breadcrumb. Actual facade/private source1 chain follows; follower role is Event.role, source leader role is Breadcrumb.role.
- 82: leader Stop for gap regroup; 83: actual three-distinct-frame idle/source1/path0 gate; 85: bounded normal leader Move resumes.
- 84: follower's third distinct physical arrival to the referenced breadcrumb; 94: its subsequent actual Stop3 gate. No next breadcrumb may be issued before94.
- 86: actual double-Stop approach endpoint/prepare gate and frozen support position; normal AK prepare/order/damage events retain original kinds.
- 87: first hidden navigation observation/memory point freeze; 88: actual reacquisition. Both echo unchanged last_seen_target and target_last_seen_frame, plus target_visible.
- 89: begin retreat; leader role becomes Flak, front follows only Flak's new retreat-phase actual breadcrumbs. Both original physical origins remain frozen.
- 90: actual two-role geometry checkpoint sample/gate; role0/1 same frame/tick, never an aggregate-counter substitute.
- 91: a role's third distinct physical arrival at its exact original safe point.
- 92: bounded normal Move to a previously observed leader hold anchor after real drift; 93: actual return-to-anchor + Stop3 gate.

Gap regroup uses stop at>240 and resumes only after rear closes<=200. Each movement phase permits at most12 regroups and the whole mission at most24; leaderMove<=32, followerMove<=128, holdRepair<=2. Counts are reconstructed by phase from raw82 events, not just the header. Each regroup consumes the original deadline. Hold repair is bounded (maximum2), returns to the recorded actual hold point and rechecks15x3/Stop3; it never changes the anchor to the drifted position. Failure/death/foreign native order/heartbeat/cancel invokes normal survivor Stop/return; force69 remains distinguishable and cannot qualify as normal restoration. Live completion requires both physical retreat origins15x3 and two normal native pool returns, then timer0/all16 pristine bytes.

Role scope is actual Conscript AK source damage with Flak following/holding geometry. No Flak ground firing or economic suppression claim. This backend needs its own real approach/effect/retreat source; neither MFM4 partial movement nor MCT7 success grants MFM8.

Motion states: 0 acquire dualStop3; 1 leader travel/follower substate; 2 leader regroup stopping; 3 leader held waiting; 4 leader returning to frozen hold anchor; 5 repair Stop3; 6 endpoint leader stopping; 7 endpoint held/rear completing; 8 combat preparation/engagement; 9 front final own-origin Move; 10 final dualStop. role_motion_mode: 0 stopped-ready,1 normalMove active,3 normalStop pending,4 held leader. Kind95 is the final front normalMove to its own original physical origin after retreat leaderFlak home91 and Stop3/83.

Safety: actual own motion that jumps beyond20+6*logical-frame-delta units is rejected as unexplained movement, never recorded as a walking trail. Private native crumb arrays and goals are authoritative; the shared arrays are output mirrors. Source scope is nonlethal AK attribution only: the inherited post-visible HP observer does not qualify a lethal hit; no MCT7 lethal proof is borrowed. Pre-install errors without complete actual13-byte restoration remain mask0/fault and may require a fresh process.

## Version6 regroup-wait reanchor

Only motion_state3 (middle-of-navigation regroup wait), in mission_stage1 or3, may abandon its previous wait anchor. Private monotonic wait_reanchor_count is separate from endpoint hold_repair_count and is limited to2 across the mission.

Event96 is emitted BEFORE the leader's new normal Stop. It has motion_state3, arg=1 or2, old leader_hold_xyz and the actual drifted leader XYZ (>15 from old anchor). Only the leader then enters motion11. Existing follower motion may continue toward its already accepted actual breadcrumb; no new leader Move/Attack occurs.

Motion11 waits for three distinct logical frames of the actual normal source1 Stop/idle16/path0 gate. It then repeats actual own-surface sampling in that same frame. Event97 has motion11, the same arg count, leader_hold_xyz equal to the actual new stopped XYZ, and a complete Breadcrumb-shaped actual surface snapshot with published_seq0/index0. This snapshot is not event80, never appended to header crumbs, never used as a follower target and never rewrites old trail records. Motion returns to3 and the existing rear-catching condition resumes. The original home origins/endpoint/combat/support goals remain unchanged.

Unknown surface or unsuccessful Stop within60 frames invokes normal cleanup; count exhaustion in approach invokes actual retreat and in retreat fails safely. Endpoint motion7 still uses the original real92/93 repair back to its fixed anchor (<=2); it cannot reanchor. Public9field phases remain unchanged. Native control-source deviation uses event106 (event96 is now exclusively abandon-anchor).

## Version7 first-retreat departure

The live MFM6 case exposed a circular wait: retreat started at actual gap246.394, the rear leader moved only3.333 before the ordinary240 regroup stop, but the first real breadcrumb could not be assigned until that leader had travelled and cleared25. This revision adds one bounded departure window, without weakening25 source clearance,15x3 arrival, Stop3, or original home points.

After both actual retreat-entry Stop3 gates and the two phase3 origin80 publications, Native captures the immutable first phase3 leader breadcrumb privately. It sets a mission-wide once-only latch, publishes98, and issues the original normal leader85 Move. Events98/99 echo that exact original Breadcrumb, including its true index, published_seq, frame and identity; they do not create80 or modify the trail. Their argument_path is the departure start logical frame, argument_limit the actual initial XY gap, and actual_gap the current physical gap. Event98.arg=0.

While open, the original follower_tick is not invoked, so there is no new81. Only this first departure may defer the ordinary240 regroup stop. It remains bounded by30 logical frames and actual gap<=350. Native publishes99.arg=1 only when both accumulated actual leader path and actual XY clearance from the referenced origin are>=25. Success99 is published before the same tick's ordinary follower_tick/81. The ordinary240-stop/200-resume policy then applies immediately, including a possible same-tick82 followed by real Stop3/83.

Failure99.arg=2 means elapsed>30 or invalid time order,3 means actual gap>350, and4 means the immutable source/role/phase binding is invalid. Each closes the window and invokes normal failed cleanup. No failure, Stop, regroup, or reanchor resets the once-only latch. Generic scene/death/emergency cleanup can terminate an open window without a success99; it cannot count as mission completion.

Each motion phase now permits12 regroups and the whole mission24. Leader Move remains32, follower128, endpoint repair2 and wait reanchor2. Approach2100, retreat1800 and the original4500 deadline remain unchanged. This has65 pure native-function cases and a software2km round trip; neither is field evidence or a capability grant.


## Version8 stored normal-Move lineage

Only a normal opcode0/source1/path0 move with FLT_MAX adapter limit is eligible. Each role has an independent monotonic generation and private ticket frozen by its actual81/85/92/95 publication. A pending credit requires own normal facade/dispatcher input, a real830220 copy (caller787d42) into that same actor Update+310, old opcodeFFFFFFFF and changed full96-byte stored record. The copied92-byte live Command is captured only during its actual stack lifetime.

Consumer830320 (caller7da0b3) must decode that identical96-byte record for the actual same Thing into a fresh92-byte output Command. Consumer dispatch (caller7da0d9) must receive that exact output pointer and payload. Its dynamic thread-local scope permits exactly one private76d9d0 call (caller6d3b7d) with goal pointer equal to decoded Command+8, source1/path0/FLT_MAX and the frozen goal. Original tag0 remains tag0; no caller-only or equal-coordinate exception exists.

Events110 own-facade begin (after50),120 own dispatcher,111/112 actual copy before/after,119 facade end (after51),113/114 unpack before/after,115 consumer dispatcher enter,10 actual private,116 accepted private (private_seq=that10),11 actual private return,117 consumer dispatcher return form the raw chain. Event118 invalidates the same-role ticket. Another role's normal Stop does not invalidate it. Stop/Attack/new facade/Return/owner/deadline/slot mutation/age>250/re-defer/no-private invalidates or rejects the credit. There is no retry credit or added SDK order.

Event.lineage preserves the bridge input, immutable copy-before/copy-after and unpacked output raw words. observed_slot is separately read at each hook. observed_this/observed_thing/observed_command are actual callback arguments, not the ticket's claimed addresses. MoveLineage is568 bytes at Event offset1048; all original Header27900 fields remain fixed. The additional passive entries830220/830320/787500 participate in active-callback lifetime accounting even for untracked actors. Complete cleanup now requires all16 actual original byte entries and timer0.
