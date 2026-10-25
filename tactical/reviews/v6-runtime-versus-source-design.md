# V6 read-only completion boundary review

No runtime, qualifier, native binary or raw report was changed. The companion
JSON binds the actual first-death raw and two pure synthetic counterexamples;
`replay_v6_completion_boundary.py` reproduces them without accessing the game.

The actual fatal source is **unknown**. Outgoing health events all concern
Refinery774 and source773. The selected actor773 has no recorded incoming Body
DamageInfo packet. Global damage/commit hook counts include unreported calls
and cannot identify them. Own HP95 at1641 and0 at1643 establishes a sharp death
window, not its attacker, weapon or mechanism. Do not infer a Bear, miner or
other nearby object from the scene. Future instrumentation could separately
record the own Body's exact incoming synchronous packet, without using that
numeric private source ID to reveal an unseen enemy to the model; this is not
implemented in frozen V6.

The completion review confirms a real semantic mismatch. Native policy ends
the order after `min(150, .2 * entry-visible target HP)` attributed damage or an
exact source-lethal transition. For a20HP target, one5HP hit reaches the4HP goal.
For a5HP target, an exact5HP→0 source hit is a legal kill. Both pure fixtures
retain full physical retreat and normal return and pass all existing causal
checks, yet return `not_passed` solely because `sustained_source_effect=False`.
Neither naturally needs a refill or a15-frame span between two hits. This would
mislabel a valid short mission as failed at runtime.

The next separately reviewed qualification revision should distinguish:

| Runtime task completion | Capability-source acceptance |
| --- | --- |
| Exact new-order source effect reaches the frozen goal, or proves source-lethal transition | Full runtime chain plus actual multi-hit span, natural refill, required memory loss/reacquisition and long movement/retreat |
| Full binding, current FOV for firing, packet/commit/ammo association, no native interference | Same checks; no synthetic fixture or short kill substitutes for field ability proof |
| Physical retreat and normal native-pool return are still mandatory | The source must demonstrate those outcomes in the same accepted field case |
| Short goal/kill can complete with `sustained_engagement_verified=False` | That case cannot grant sustained/memory capability |

Keep `sustained_engagement_verified`, rounds, refills, actual duration and lethal
observations as factual diagnostics. Do not set sustained true merely because a
short task succeeded. A dedicated `runtime_goal_verified` result and explicit
`capability_source_verified` verifier (or an equivalently strict Root source
gate) make the distinction reviewable. The model cannot select the verifier or
change goal parameters. Source gates remain as strict as now.

The existing first V6 case remains failed under either design:90/150HP goal,
actor death, no physical retreat and no normal return. Its verified disposal
only releases exclusive control; it never supplies runtime completion or a
capability grant. Partial no-goal missions with safe return likewise stay
partial/failed. No MCT7 or qualifier replacement is implemented by this review.
