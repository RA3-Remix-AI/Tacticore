Offline normal Move review, 2026-10-25
====================================

No GUI, process access, hooks, model calls, or active game commands were used.
The reviewed EXE file SHA256 is
`ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`.
Relevant instruction excerpts are retained in `movement-normal-disassembly.txt`.

The normal facade at `571d90` is thiscall on `AIUpdate+24`, with stack arguments
`Vec3* target, source`, and `ret 8`. It constructs command opcode **0**, copies
the target's three floats into its command payload, and calls the facade's
virtual dispatch function. The script path at `58e28e..58e298` explicitly pushes
source **1**, the coordinate pointer, and calls this facade. It follows a
particular guarded branch of that script handler, not every movement variant.

Reading the file-backed dispatch table proves `table[0] == 787642`.
For an empty extra-argument list, that handler calls `6d3b60` with the target
payload and source. `6d3b60` calls AIUpdate virtual slot `+58` with target,
null auxiliary point, `FLT_MAX` (`c0d47c`), and source. In both the known Flak
vtable `c48670` and Twinblade vtable `c4e268`, slot `+58` is **76d9d0**.
That method retains normal guards, clears the current SM via virtual `+38`,
passes target/float/source through `70cba0`, clears AIUpdate `+190` and `+43a`,
writes command source at `+50`, and changes SM to **state 1**. It returns `ret 16`.

The old direct entry **6eff70** is a different virtual slot: `+5c` in both
vtables. Its normal dispatch-table opcode is **83 decimal (`0x53`)**, whose
handler `78767b` selects slot `+5c`. It clears the SM, calls `603a70` directly,
writes source, clears the same local flags, and selects **state `0x4e`**.
Do not confuse decimal opcode 83 with hexadecimal `0x83`, or command opcodes
with SM state identifiers.

`70cba0` copies the desired point and ultimately calls `603a70`, but can first
clamp X/Y to a world rectangle plus margin when source is zero. A nonzero source
skips that clamp. This is a normal-path behavioral difference, not a reason to
write private precision, path, or state fields. The earlier repeated ground
arrival failures do not establish that clamp or terrain was their cause.

The normal facade is therefore a materially different candidate from the old
direct entry. Static correctness does not prove real arrival or fog updates.
A new experiment must separately show the normal facade/private chain, source
and bound actor, same-lease distinct-frame arrival, newly visible player-view
terrain for recon, absence of interference, and restoration. Old failed reports
remain failed; this review grants no new purpose.
