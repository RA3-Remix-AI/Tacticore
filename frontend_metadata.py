"""Extract experimental frontend records; this does not fix runtime imports.

Copying a record preserves its serialized imports, but does not prove those
imports bind in the AdditionalMaps loader's context. Use only in lab mods.
"""
from patch_global import parts, parse
from pathlib import Path
import argparse
import hashlib
import json
import struct

DEFAULT_STAGE = Path(r'E:\RA3Modding\SDK\BuiltMods\mods\CommanderLab\data')


def build_subset(source, destination, prefix='4TFLLM', include_random=False):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Subset destination must differ from its source')
    h, allrows, mrefs, files = parts(source)
    rows = [r for r in allrows
            if r['name'].startswith('AIPersonalityDefinition:' + prefix)
            and (include_random or not r['name'].endswith('Random'))]
    if not rows:
        raise ValueError('No matching personality records')
    refs, names, sources, records = bytearray(), bytearray(), bytearray(), []
    blobs = {ext: bytearray(struct.pack('<I', h[1])) for ext in files}
    for r in rows:
        ro, no, so = len(refs), len(names), len(sources)
        for key in r['refs']:
            refs.extend(struct.pack('<2I', *key))
        names.extend(r['name'].encode() + b'\0')
        sources.extend(r['source'].encode() + b'\0')
        records.append(struct.pack('<12I', r['type_id'], r['instance_id'],
                       r['type_hash'], r['instance_hash'], ro, len(r['refs']),
                       no, so, r['binary_size'], r['relo_size'], r['imp_size'], r['flags']))
        for ext, off, size in [('bin', 'binary_offset', 'binary_size'),
                               ('relo', 'relo_offset', 'relo_size'),
                               ('imp', 'imp_offset', 'imp_size')]:
            payload = files[ext][r[off]:r[off] + r[size]]
            if len(payload) != r[size]:
                raise ValueError('Truncated ' + ext + ' for ' + r['name'])
            blobs[ext].extend(payload)
    h[3], h[4] = len(rows), len(blobs['bin']) - 4
    h[5:8] = [max(r[key] for r in rows)
              for key in ['binary_size', 'relo_size', 'imp_size']]
    h[8:12] = [len(refs), len(mrefs), len(names), len(sources)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(struct.pack('<12I', *h) + b''.join(records)
                            + refs + mrefs + names + sources)
    for ext, data in blobs.items():
        destination.with_suffix('.' + ext).write_bytes(data)
    if len(parse(destination)) != len(rows):
        raise ValueError('Subset round-trip failed')
    return dict(source=str(source), destination=str(destination),
                records=[r['name'] for r in rows],
                sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                runtime_verified=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stream', type=Path, default=DEFAULT_STAGE / 'mod.manifest')
    ap.add_argument('--output', type=Path,
                    default=DEFAULT_STAGE / 'AdditionalMaps/mapmetadata_commander.manifest')
    ap.add_argument('--prefix', default='4TFLLM')
    ap.add_argument('--include-random', action='store_true')
    a = ap.parse_args()
    print(json.dumps(build_subset(a.stream, a.output, a.prefix, a.include_random), indent=2))


if __name__ == '__main__':
    main()
