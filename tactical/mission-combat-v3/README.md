# Direct-home retreat revision (MCT3)

MCT1's429-unit success and MCT2's2004-unit approach/real damage plus failed
checkpoint retreat remain unchanged. MCT3 only changes the retreat route policy
and adds its bounded replan telemetry. It uses the same14 native entry points.

After source damage / cancellation / FOV loss, normal Stop is followed by one
normal Script Move directly to the immutable original retreat goal. The engine
chooses the complete path. Previously crossed fractional checkpoints are evidence
of the approach, not mandatory places to stop on the return trip.

One optional bounded fallback is available after250 game frames without actual
movement and native idle/path0. It selects the nearest actual checkpoint>=80 away,
at least80 closer to the original goal, excluding the goal itself. Event62 records
the abandoned primary subgoal and selected checkpoint; it does not claim arrival.
After actual displacement>=120, home-distance improvement>=80, or an independently
verified checkpoint arrival, event63 records a replan back to the original goal.
Maximum2 replans /3 return Move orders; no alternative means failure. Repeated
stall means failure. Retreat1800 /mission4500 and final goal<=15 for3 distinct
frames are unchanged. Native AI pool return remains separate from task success.

`mission_combat_v3_qualification` independently reconstructs all movement, actual
checkpoints, bounded replan reasons, source AK damage and final arrival. Lack of
an intermediate event57 is allowed when actual final event60 samples independently
prove arrival. A scalar arrival counter never substitutes for the three positions.

Native identity: TacticalMissionCombat3.dll /TacticalMissionCombat3Control,
Local\RA3TacticalMissionCombat3_PID_TOKEN, MCT3/version11, WM_APP+0x37d,
restore16383. Compiled Event788/Tactical3228728/events1080.
Input CLI is unchanged from MCT2. New output paths and IDs are mandatory.
Pre-native rejection helper: pre_dispatch_v3_contract.py.
Read-only death release: mission_v3_readonly_disposal.py.

Fallback currently has synthetic positive/negative tests only. If the real source
case returns directly, its evidence must explicitly say that the fallback branch
was not exercised in the field. No V1/V2 raw is promoted to V3 capability.
