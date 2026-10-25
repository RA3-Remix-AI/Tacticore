# Conscript normal weapon toggle: static + read-only evidence

Scope: this is a candidate ordinary scripting entry, **not a completed toggle experiment**. No getter or command was invoked by the inspector.

Pinned executable SHA256: `ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`.

`NAMED_USE_COMMANDBUTTON_ABILITY` enters `0x590020`. Its matching-button branch at `0x590080..0x590087` pushes `0`, `1`, and a `CommandButtonInfo*`, uses `ECX=Thing`, and calls `0x790990`. That callee removes 12 argument bytes and forwards to `0x7904e0` with three extra zero arguments. The `1` is the ordinary script-source value, independently consistent with the other pinned Script commands. This uses the existing unit command, not player-power granting.

The current unit's command-set getter `0x6fcce0` reads `Thing+0x464`, or, when zero, calls the `Thing+0x78` interface's `vtable+0x2c`. For this exact Conscript that method is `0x6de330`, a direct read of `Thing+4`. The subsequent script reads `[[Thing+4]+0x14]+0x94`, yielding `0xb74cf71a` (`SovietAntiInfantryInfantryCommandSet`, lowercase SAGE hash).

`0x4df970` searches the map at `[0xcd8d00]+0x40`: root is `+0x4c` from the store, node key `+0x10`, child `+4` for the lower-bound branch and `+0` for its other branch, value `+0x14`. Its returned list is `value+8`. The observed list vtable is `0xbe9178`: `0x524c70` returns `[[list+4]+4]`, and `0x4d8fc0` returns `[[[list+4]+8]+4*index]`. No virtual method invocation is necessary to reproduce these reads.

The exact ability entry has asset type `0x7d464170` and instance `0x5977a798` (`Command_ToggleMolotovCocktailSpecialPower`, lowercase SAGE hash). `entry+4 -> schema -> asset header` matches how the native script checks the button ID.

SDK `SAGEXML/GlobalData/LogicCommand.xml` binds this command to `SpecialPower_MolotovCocktail`; the SpecialPowerTemplate has target type `NONE`. The current mod Conscript XML uses `ToggleStatusSpecialAbilityUpdate`, `PackTime=1s`, `ReloadAllWeaponsOnToggle=false`, with state 0 AK47 and state 1 Molotov. Merely changing a status bit, weapon index, ammo, or global AI setting would not validate this command.

Reproduce without commands:

```powershell
python bridge-probe/tactical/recon/read_own_command_buttons.py --session bridge-probe/acceptance/active-session.json --object-id 784 --output <new-private-report.json>
```

Current read-only result: `acceptance/runs/20261025-022351-commander/command-button-784.json`, session `03109549-eaf4-472a-9fdc-7303fee87ad9`, PID 57152, frame 1532. All pointers in that result are valid only for that process/session and must be resolved again before a native callback. The Inspector source SHA is recorded in the report.

Live acceptance still requires a bounded native-thread command, actual dispatch evidence, the game's packing transition, the real active-slot getter changing from Molotov `0x41872ecc` to AK `0x447ea26e`, per-weapon ammo observations without direct ammo writes, and clean release/restoration. It grants no model capability by itself.
