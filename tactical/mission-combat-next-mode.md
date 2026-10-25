# Sustained combat follow-up (design only)

Recorded 2026-10-25. MCT5 remains frozen and must first produce its real
memory-navigation / contact / retreat evidence. This document grants no ability
and changes no runtime. MCT1–MCT5 source damage is a single-hit verification
mechanism; 5 HP against a refinery does not establish economic disruption.

## Small independent change after the MCT5 field chain

Use a separate directory, DLL, message, mapping, qualifier, pre-dispatch helper,
gate reader and death-reader profile. Keep the existing fourteen normal hooks,
normal APIs and exactly one ScriptAttack(source=1, INTMAX). Do not repeatedly
attack, write ammunition, change prices, force targeting bits or bypass FOV.

Change only the engagement exit policy and its raw observations:

The next revision also moves the already reviewed normal AK preparation into
the first clean Stop, before approach. Internally it may have loadout substages,
but published progress remains `approach` until the normal visible engagement
transition; it must not publish `prepare` and then regress to `approach`.
The exact Molotov button is used at most once, only when the actual weapon
getter requires it. Keep the existing pack-time, three distinct idle-AK samples
and subsequent clean Stop gates. Never use a status-bit or ammo write. Later
approach and pre-Attack checks still require the exact AK entry/asset; a mode
change is a bounded failure, not permission to retoggle or broaden scope.

Use the audited AK AttackRange 150 as the documented engagement policy input,
rather than presenting the old 125 approach threshold as an engine limit.
Current full FOV alone does not prove line of sight. The sole normal Attack
must perform native range/LOS handling, and actual source damage is the effect
test. Range modifiers and obstructed shots remain observable outcomes, not
reasons to change range or fabricate a successful attack. Keep the frozen
memory TTL and absolute approach/mission deadlines unchanged.

1. After normal preparation and the final clean Stop, revalidate full FOV and
   record actual target HP from this frame. Freeze the trusted policy and its
   target amount before the sole Attack: proposed attributed-damage goal is
   `min(150 HP, 20% of this observed target HP)`. These are provisional parameters,
   not claims that this damage necessarily suppresses mining or production.
2. Keep the original order alive until the damage goal or the bounded engagement
   window (180–300 logical frames) ends. Native unit behavior handles aiming,
   bursts and reloading. Low own HP, FOV loss, cancellation, heartbeat failure and
   the original mission deadline retain priority over achieving the damage goal.
3. Always perform the independent Stop / physical retreat / final three distinct
   goal samples / native-pool return sequence. A short partial engagement or a
   dead actor must never be promoted to completed or block safe cleanup.

The SDK AK47 definition in
`E:/RA3Modding/SDK/SAGEXML/GlobalData/Weapon.xml` has ClipSize 3, pre-attack delay
0.1 s, firing duration 0.1–0.3 s and normal clip reload 0.3–0.5 s. Its damage
nugget is GUN, DelayTimeSeconds 0 and has no projectile nugget. Do not assume
one clip equals the whole engagement or change the actual weapon mode directly.

## Additional passive records and independent qualification

`sample_weapon()` currently records only ammo decreases and silently advances
`last_ammo` on increases. Add a distinct, read-only reload/ammo-increase event
with the same AK entry and immutable template/asset identity. Preserve the
complete transition chain, including observed before/after ammo, frame, tick,
entry, asset and order stage. Reject unexplained entry/mode changes. Do not call
an increase a confirmed refill from an invented counter or a reset.

Qualification must reconstruct the ordered chain from the Attack through the
post-engagement Stop. Every attributed HP loss still needs the real
SourceActorID-to-target Body event, matching commit and raw DamageInfo packet,
GUN / exact AK asset, and an appropriate observed ammo-consumption interval.
One timer poll can observe more than one consumed round; do not require every
hit to have a different poll, or count one drop as an arbitrary number of hits.
Shots may miss, so ammunition consumption does not itself prove damage. Normal
reload boundaries must be explicit, never patched into the report after a
monotonic-ammo checker fails.

The existing HP>0 post-check can omit a lethal commit. Unless a new raw qualifier
actually observes the final valid FOV/commit/identity chain, do not infer a kill
from disappearing contacts, missing objects, HP net change or a result screen.

Suggested additional result fields, while keeping the existing nine mission
progress fields and seven execution fields compatible:

- `engagement_policy`, `engagement_start_frame`, `engagement_end_frame`
- `engagement_initial_target_hp`, `attributed_damage_goal`
- `source_damage_amount`, `qualified_hit_count`, `observed_rounds_consumed`
- `observed_reload_count`, `damage_goal_reached`, `engagement_partial`
- `effect_verified`, `sustained_engagement_verified`
- `approach_verified`, `retreat_verified`, `restoration_verified`

The physical retreat and control-release booleans remain independent from the
damage result. A safe return with 0 or small damage is a failed/partial tactical
task with real cleanup, not an unknown lease and not a successful attack.

## Field acceptance

Use new raw reports and exact source hashes. First demonstrate multiple
attributed hits with at least one observed natural reload and an actual retreat,
then inspect a safe early exit separately. Preserve no-hit, FOV-loss, death and
cleanup failures. Record real initial/remaining visible target HP and damage
percentage. Do not relabel old single-hit cases as sustained combat.

For the final match, distinguish model-selected missions, actual contact,
attributed damage, retreat, deaths and native continuation. Victory is not proof
of model contribution. Economic suppression additionally requires observable
economic/production consequences; ordinary sourced damage alone remains damage.

## Actual range/preparation finding (harass-mct5-03)

The exact SDK Weapon.xml file SHA is
`7a82e52aa6142f96271173195366227b21a552657bd683f7a33a22e770e1bad1`.
AK47 has AttackRange 150, ATTACK_NEEDS_LINE_OF_SIGHT and cannot fire while
moving. The current approach distance 125 is local validation policy, not the
engine's weapon range. Fog visibility does not itself establish a clear weapon
line of fire, or an effective range after native modifiers.

The real actor was still using Molotov asset41872ecc/ammo1 at frame2432
(distance146.97, HP70), frame2433 (distance144.47, HP70), and frame2435
(distance139.59, HP40). It had neither prepared AK nor received an Attack.
Low HP caused retreat at2435/HP40; HP10 was observed later at2440. The case
does not demonstrate an AK failure to fire inside150, or a failed native LOS
check. In the next independent combat mode, consider normal preparation before
the dangerous final approach and let the sole normal Attack perform native
range/LOS behavior once the intended current-visible engagement condition is
met. Changing a threshold alone must not be presented as a proved range fix.

## Actual lethal-commit observation gap

Both frozen damage hooks recheck `visible_target()` after the real native call.
That predicate requires target HP>0. Therefore a lethal call can be observed
before entry yet have its damage/commit record omitted after HP reaches0.
Keep all old reports and their conservative assessments intact.

A new revision can capture current full-FOV eligibility, exact target
Thing/body/ID/template/owner and frame before the synchronous native call.
Immediately after it, require the same thread/frame and revalidate those
identities before reading the same body's HP. Permit finite HP0 as an observed
lethal commit; do not require that the post-death fog record still exists.
Do not refresh XYZ or follow another target. A released/replaced body, ownership
change, read failure or frame change is unknown, never a kill inferred from
absence. Expose the pre-visibility proof and post-identity outcome as raw fields
for independent qualification rather than setting a success boolean.

Keep engine-reported damage and effective positive-health depletion separate if
overkill makes HP negative. An observed lethal HP transition is distinct from a
later object-disposal observation. Natural own casualties still require their
independent inert/absence certificate; none of these enemy-hit changes creates a
normal return, physical retreat or completed task for a dead actor.
