# Read-only base-height research

This module reproduces the no-normal scalar branch of the pinned RA3 image's
`0x8ed070`. It calls no game function and implements neither IO, NativeCalls nor
SurfacePoints. It grants no walkability, endpoint, actor or execution capability.

The fixed version uses global0xce9c40, vtable0xc0a6f0, slot+0x54. Its map data
is root+0x14; width/height/border are+0x24/+0x28/+0x2c and the uint16 grid is+0x44.
World xy scales by0.1; two triangular pieces interpolate four heights, then
scale by0.0390625. `heightmap.py` retains those four original words, indices,
fractional coordinates, dimensions and process-frame context. It requires an
active map, fixed native prefix/constants, valid interior indices, paired
identical cells/metadata and the same simulation frame. Missing maps and native
out-of-bounds fallbacks never become zero-height placement evidence.

The `0x85a780` bool is not a general validity query: it compares self+0x3c with
the base terrain height and conditionally writes a different surface value.
Water surfaces, bridges, placement, object footprints, collision and paths are
separate unresolved contracts. Base-height agreement alone must not authorize
a movement target.

Run the synthetic reader checks with the workspace Python:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tactical/terrain -p test_*.py
```

A direct read-only probe requires a pinned owned model-disabled session and a
new output inside its run. It returns a separate sampled/refused artifact:

```powershell
.\.venv\Scripts\python.exe tactical/terrain/heightmap.py --session ... --output ... --x 1790 --y 1850
```

The first actual probe in003832 correctly refused the inactive frame0 scene.
The read-only011212 fixture supplied17 flat samples from3 native own foot actors
and17 distinct frames. A later bounded slope window supplied27 samples from11
actors and6 distinct frames, including3 nonflat samples across3 frames and both
triangle branches. The offline reviewer independently recomputed the raw vertex
geometry, barycentric height, native pose/cache surface and deltas:9 checks
passed,0 mismatches. Slope variation was small (210..210.023727), so this is
bounded active-map height evidence, not general water/bridge/placement proof.

`compare_native.py --require-nonflat` requires3 distinct nonflat frames, keeps
at most24 flat rows, and archives the exact reader/collector before reading.
The earlier slope attempt filled64 flat slots before reaching a slope; its
`insufficient_references` output is retained. No failed output is overwritten.

`pathgrid.py` reproduces the layer1 coordinate/cell-address lookup from
`0x68d010` and `0x544720`: native global0xce3e30, root vtable0xc18e20,
child+0x28, bounds+0x0c..+0x18, column pointer table+4, world scale0.05,
48-byte cells indexed column then row. Registration of the named
ThePathfindSystem and its constructor were traced statically; active roots and
21 same-frame native own foot/cell pairs from6 actors/9 frames are retained.
All21 raw terrain nibbles were0; other cell bits remain uninterpreted. Four
offline consistency checks and3 synthetic reader checks passed. No native query
was called. Layer masks, terrain enum semantics, actor footprints, collision,
dynamic obstacles, passability and routes still require separate validation.

The fixture used no injected executor, producer, model or lease. All19 original
hook entries were independently read before ending the pinned owned process.
That is unchanged-entry evidence, not a control-release or natural-match result.
Evidence: `acceptance/runs/20261027-011212-runtime-calibration/` and
`reports/runtime-terrain-height-checkpoint-20261027.json`.

The013405 study added the restricted empty-land research reader in
`land_surface.py`: native actor LocomotorSet+0x14 surface mask, native footprint
width/center, paired footprint cells, mask table and base height. The initial
dimension/field interpretation refused every row; its frozen source and output
remain intact. Real native path parameters then proved settings=UnitAI+0x1fc,
surface mask=UnitAI+0x210. UnitAI+0x180/+0x184 are ignored-object fields. The
geometry override-1 leaves the native radius5/width1 footprint in effect.

The final101 cell rows from9 actors/3 frames include32 positive restricted
preconditions and69 negative rows, with raw terrain codes0/2/4/7/9. Eight offline
checks independently recompute the raw fields and accept only the correctly
bound native parameter witness. All101 foot cache/status references were
refused; this study therefore qualifies no actor for Borrow. Fifteen synthetic
checks pass. No movement was dispatched or scope granted. See
`ENDPOINT_CONTRACT.md` for the pending game-thread integration and full field
calibration requirements. Original entries19/19 were read before ending the
owned fixture; there is no executor-release or natural-result claim.
# Read-only native path context

`native_path.py` reads a paired, same-frame own-foot PathfinderPath and its
complete bounded node chain. It requires the supported actor layout, typed
params with the actual unit ID and embedded LocomotorSet mask1. This contract
is separate from endpoint admission and grants no action. Mask/params/path
refusals remain unqualified research; the Bear comparison has no positive row.

The024440 field sample for paid Flak790 has two original nodes and4 independent
raw-byte checks. The outer yield-scan prerequisite is false at frame960 only.
The stationary actor occupies a different center cell. The original diagnostic
did not enter yield and was cancelled/restored; its failure remains retained.
