Normal Conscript weapon-toggle review (offline), 2026-10-25
=========================================================

This review reads SDK XML and the EXE file only. No active SDK, GUI, memory
writes, native calls, model calls, or debug registers were used.

SDK scope
---------

`Mods/TriadFront/data/objects/SovietAntiInfantryInfantry.xml` defines
`SpecialPower_MolotovCocktail` and `ToggleStatusSpecialAbilityUpdate` with:

- Default state weapon `SovietAntiInfantryInfantryAK47`.
- Alternate state `GENERIC_TOGGLE_STATE ANTI_GARRISON`, weapon
  `SovietAntiInfantryInfantryMolotovCocktail`.
- `PackTime="1s"`, `ReloadAllWeaponsOnToggle="false"`,
  `Options="RECONSTITUTE_STORED_COMMAND"`.

`SovietAntiInfantryInfantryCommandSet` includes the exact logic command
`Command_ToggleMolotovCocktailSpecialPower`; its type is `SPECIAL_POWER` and
its template is `SpecialPower_MolotovCocktail`. The special-power template has
`TargetType="NONE"`. `AssetTypeLogicCommand.xsd` places SPECIAL_POWER at enum 1.
This is a toggle, so issuing it twice can undo the desired change.

Normal ABI and branch
---------------------

The script helper `590020` resolves its named actor, obtains its command set
through `6fcce0` / manager `4df970`, and enumerates actual button entries. The
entry's `+4` schema leads to an asset header whose `+4` command asset ID is
compared with the script's requested command ID. On a match it pushes `0`, `1`,
and that entry pointer, then calls `790990` with ECX equal to **Thing**, not
AIUpdate and not AIUpdate+24.

`790990` is thiscall, stack arguments `(button_entry, source, third_flag)`,
`ret 12`. It forwards six arguments to `7904e0`:
`(button_entry, source, third_flag, 0, 0, 0)`; that function returns `ret 24`.
The observed script call thus uses `(entry, 1, 0)` exactly.

`7904e0` retains normal actor-status guards (including its Thing+26c test),
then dispatches `button.schema.type - 1` through table `790950`. File-backed
table entry zero is `7905dd`, matching SPECIAL_POWER enum 1. The targetless
branch reaches `790699`: it obtains the special-power template using
`4d7190(button)`, combines the button options with `8`, compares source with
`1`, and passes that comparison as the script boolean to
`7178a0(Thing, special_power_template, flags, is_script)`.

`7178a0` expands the ordinary targetless call to `7176c0` with null target
arguments and the normal `FLT_MAX` sentinel. That method resolves the actual
actor's matching module through `6ddc40`, applies its normal availability and
status checks, and invokes its virtual special-power implementation. No part
of this route requires a direct status, slot, ammo, pack-state, or timer write.
Instruction excerpts are saved in `toggle-command-disassembly.txt`.

The EXE also contains the literal `NAMED_USE_COMMANDBUTTON_ABILITY` at VA
`bf9a6c` (constructor reference `561a40`), and the script dispatcher directly
calls `590020` at `5a7aa1` / `5a7ab8`. The ABI claim above is grounded in the
actual push/call sequence, not inferred from the literal's name alone.

Bounded calibration acceptance
-------------------------------

Use only the exact own Conscript and its exact registered command entry.
Observe Molotov as the precondition; issue one normal Stop, wait for its clean
boundary, then one normal button input. A function return is merely an input
attempt. Wait using advancing simulation frames (at least the documented pack
interval, with a bounded timeout), and require three distinct-frame read-only
getter observations of the exact AK asset before returning native ownership.
Pauses do not advance that timer. The real active getter and template identity
must be checked; no fixed ammo count establishes the weapon's identity.

The SDK's stored-command restoration is a reason to clear prior local commands
with normal Stop first. Native AI may toggle again after ownership is returned;
this auxiliary alone does not prove a later attack still uses AK. Attack
qualification must continue to verify the actual selected entry/asset for its
own new order. This static review is no model capability grant or live result.
