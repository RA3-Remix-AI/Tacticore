# Full-target path combat mission, independent MCT2 revision

This keeps MCT1 (82b31 DLL /9add wrapper /d07 helper), its successful429-unit
calibration, and its failed2100-unit approach unchanged. MCT2 has a separate DLL,
mapping, message, qualifier and pre-native rejection helper. It needs new field
evidence before any model capability is granted.

The normal Script Move receives the actual currently visible target XYZ. The
game's normal pathfinder chooses its detours. No250-unit interpolated endpoint is
claimed reachable. The supervisor stops movement when actual remaining XY<=125,
then performs the same normal AK preparation, one normal burst Attack, source
damage verification, retreat and native pool return. A moving target can cause a
bounded new path request when the old destination is reached; maximum12 approach
orders and2100 approach frames remain. A250-frame lack of actual own displacement
causes retreat; approaching does not have the old450-frame per-request cutoff.

Every actual>=120-unit movement from the last checkpoint records an own position
event, with32 slots. Retreat requests those actual checkpoints in reverse order,
then the immutable retreat point. Maximum40 retreat orders/1800 retreat frames;
total mission deadline remains4500 frames. Final arrival has its own three-distinct-
frame counter against the immutable retreat point. A nearby checkpoint's arrival
counter cannot substitute for final arrival.

CLI is identical to MCT1, using this directory's `lease.py` and a new output path,
command UUID, task UUID and sequence. The same trusted schema1 mission file may
omit retreat_point to use the actor's actual dispatch origin. Never label this
point absolutely safe. All FOV, owner, lifecycle, pause, thread and cancellation
guards remain active. The model never supplies private XYZ or native pointers.

Native identity: TacticalMissionCombat2.dll /TacticalMissionCombat2Control,
Local\RA3TacticalMissionCombat2_PID_TOKEN, MCT2/version10, WM_APP+0x37c,
14 hooks/restore16383. Compiled layout is Event788/Tactical3228700/events1052.
Qualifier: `mission_combat_v2_qualification.qualify/qualify_path`.
Pre-native refusal: `pre_dispatch_v2_contract.verify_no_dispatch`, exit64 only
before the durable native launch intent. Death reader:
`mission_v2_readonly_disposal.verify_path/collect`, no fake return/completion.
