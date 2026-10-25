# Exact static structures: evidence and smallest read-only follow-up

This review changes no classifier, radius, wrapper or native executor. Its JSON
companion binds the exact2d7873 package, compiled-manifest hash, four template
hashes, inheritance, behavior fragments and SDK schema sources. It is a source
audit, not a decompiler proof that a live binary has no firing capabilities.

| Exact current template | Type hash | Source finding | Conditional hazards |
| --- | --- | --- | --- |
| SovietRefinery | c45aaeab | No ordinary WeaponSet or firing passenger/garrison module found | Miner spawn, production/docking, capture/infiltration, Catalyst death weapon, destruction/sale Conscript spawn |
| SovietPowerPlant | cf8d9f20 | Same source finding | Capture/infiltration, Catalyst death weapon, destruction/sale Conscript spawn |
| SovietBarracks | 80d4ea1e | Same source finding; StructureAIUpdate name alone is not a weapon | Normal paid production, capture/infiltration, Catalyst death weapon, destruction/sale Conscript spawn |
| SovietConstructionYard | c16ff13f | Same source finding | Pack/replace into mobile SovietMCV, production, capture/infiltration, Catalyst death weapon, destruction/sale **Engineer** spawn |

`EngineerContain` and `InfiltratorContain` inherit `ContainModuleData` with
capture/infiltration effects. `GarrisonContain` separately inherits
`OpenContainModuleData` with passenger infrastructure. Their names must not be
treated as interchangeable. Conversely, neither `TransportSlotCount=1` nor
`Thing+238==0` proves an empty passenger inventory: the former is a template
slot-cost field; the latter's audited use is an ownership/list-holder link.

The inherited `FireWeaponWhenDead` triggers on CATALYST death and references
`CatalystBuildingDeathWeapon` (EXPLOSIVE200, radius100, delay1.5s). It is not an
autonomous unit-targeting gun. Keep it as a conditional hazard; do not call these
objects universally harmless or absolutely safe. ConYard's special destruction
OCL creates an Engineer, while the other three use generic Conscript-producing
OCLs. All mobile objects, including miners, transporters and crushers, continue
to count as threats even if they have no ordinary weapon.

## Minimum live evidence before any exact-template exclusion

1. Use an owned structure for initial layout controls, then only an enemy
   `VisibilityCollector.private_targets` record that has passed the current full
   footprint FOV proof. Never enumerate hidden enemies or refresh hidden XYZ/HP.
   Capture session/PID/start/executable/package, current frame, Thing ID/owner,
   exact template pointer/hash and static class. Recheck the same identity and
   frame after all reads. Packing/replacement, ownership change or ambiguous
   template means unknown and continues to count as a threat.
2. Read the verified Thing+37c weapon-container path and its backpointer; record
   the container vtable, vector bounds, every slot's vtable/backpointer and all
   six entry pointers per slot. Inspect every mode, not just the selected one.
   `active_weapon(...).selected is None`, index5 or a disabled slot cannot prove
   no configured weapon. A null container or zero vector is also unknown until
   the exact structure constructor/empty-state semantics have been verified;
   do not silently turn a failed read or uninitialized container into absence.
3. Confirm the exact compiled structure module identities have no
   Open/Garrison/Transport/Horde firing-containment modules, and bind them to the
   audited source chain. If a containment inventory must be read, first verify
   its real ABI/backpointers and take a stable complete snapshot. No generic
   container offset is established by this review. Missing layout evidence is
   unknown, not zero passengers. Actual occupied or firing-capable containers
   remain threats.
4. Repeat controls on a known armed structure and a known garrison-capable
   structure. Both must remain threats. Recheck the chosen exact static
   structure before dispatch, since a mode, upgrade or replacement can change
   capabilities. Source classification and a single old sample are not a live
   permit.

A later independently reviewed result can be named
`no_autonomous_direct_fire_or_firing_garrison_verified`, with separate
`conditional_hazards` metadata. It should not be named `no_weapons` or
`safe_origin`. Keep the350 radius exactly unchanged; only explicitly verified
exact static types may be excluded from the **immediate direct-fire** threat
set. Everything unknown, all mobile objects, armed structures and firing
garrisons remain in it. This plan grants no exclusion now and does not block the
independent two-stage MFM4 work.
