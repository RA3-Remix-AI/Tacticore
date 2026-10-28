"""Read-only script flag readback independent of the native setter.

This mirrors the pinned native tree key comparison, not Lua acknowledgement.
Missing and false are distinct. A stable double read is still non-atomic and
does not prove that a flag was consumed by an AI state or produced an effect.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from probe import k, EXPECTED

ENGINE_GLOBAL = 0xcdd190
FLAG_MAP_OFFSET = 0x16ce4
CONTEXT_OFFSET = 0x17d60


def fnv1(value):
    result = 0x811c9dc5
    for byte in value:
        result = ((result * 0x1000193) & 0xffffffff) ^ byte
    return result


def scoped_name(name, context):
    if not isinstance(name, str) or not name or '\0' in name or len(name.encode('utf-8')) > 255:
        raise ValueError('invalid_flag_name')
    if not isinstance(context, str) or '\0' in context:
        raise ValueError('invalid_script_context')
    scope, separator, unqualified = name.partition('/')
    if not separator:
        scope, unqualified = context, name
    if not unqualified:
        raise ValueError('empty_unqualified_flag_name')
    return scope, unqualified


def _address(value, size=4):
    if value % 4 or not 0x10000 <= value <= 0x100000000-size:
        raise ValueError('invalid_native_pointer')
    return value


def _word(read, address):
    return struct.unpack('<I', read(address, 4))[0]


def _native_text(read, wrapper):
    address = _word(read, wrapper)
    if not address:
        return ''
    _address(address)
    length = struct.unpack('<H', read(address-4, 2))[0]
    if length > 1024:
        raise ValueError('script_context_too_long')
    raw = read(address, length+1)
    if raw[-1:] != b'\0' or b'\0' in raw[:-1]:
        raise ValueError('invalid_native_string')
    return raw[:-1].decode('utf-8', errors='strict')


def _lookup(read, table, key):
    header = read(table, 0x18)
    root, count = struct.unpack_from('<I', header, 0xc)[0], struct.unpack_from('<I', header, 0x14)[0]
    if count > 16384 or bool(root) != bool(count):
        raise ValueError('invalid_flag_tree_header')
    at, parent = root, table+4
    visited, samples = set(), []
    lower, upper = None, None
    found = None
    while at:
        _address(at, 0x1c)
        if at == table+4 or at in visited or len(visited) >= min(count, 64):
            raise ValueError('invalid_flag_tree_path')
        visited.add(at)
        raw = read(at, 0x1c)
        right, left, back, color, scope_hash, name_hash = struct.unpack_from('<6I', raw)
        node_key = scope_hash, name_hash
        if back != parent or (lower is not None and node_key <= lower) or (upper is not None and node_key >= upper):
            raise ValueError('invalid_flag_tree_order_or_parent')
        samples.append((at, raw))
        if node_key == key:
            if raw[0x18] not in (0, 1):
                raise ValueError('invalid_flag_boolean')
            found = dict(node=hex(at), value=bool(raw[0x18]))
            break
        parent = at
        if key < node_key:
            upper, at = node_key, left
        else:
            lower, at = node_key, right
    # Native code may run concurrently. Refuse a changed path or header instead
    # of stitching a successful receipt from different samples.
    if read(table, 0x18) != header or any(read(address, len(raw)) != raw for address, raw in samples):
        raise ValueError('flag_tree_changed_during_read')
    return dict(present=found is not None, value=found['value'] if found else None,
        node=found['node'] if found else None, visited_nodes=len(samples), total_flags=count)


def inspect_flags(read, names):
    if not isinstance(names, (list, tuple)) or not 1 <= len(names) <= 32 or len(set(names)) != len(names):
        raise ValueError('invalid_flag_query_list')
    engine = _address(_word(read, ENGINE_GLOBAL), CONTEXT_OFFSET+4)
    context = _native_text(read, engine+CONTEXT_OFFSET)
    rows = []
    for name in names:
        scope, unqualified = scoped_name(name, context)
        key = fnv1(scope.encode()), fnv1(unqualified.encode())
        rows.append(dict(name=name, resolved_scope=scope, resolved_name=unqualified,
            key=[hex(x) for x in key], **_lookup(read, engine+FLAG_MAP_OFFSET, key)))
    if _word(read, ENGINE_GLOBAL) != engine or _native_text(read, engine+CONTEXT_OFFSET) != context:
        raise ValueError('script_engine_or_context_changed')
    return dict(engine=hex(engine), script_context=context, flags=rows,
        sample_atomic=False, native_calls=0, process_writes=0, ai_consumption_verified=False,
        macro_effect_verified=False, capability_granted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--creation-filetime', type=int, required=True)
    parser.add_argument('--flag', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT.parent / 'reports'):
        raise ValueError('fresh_local_report_required')
    handle = k.OpenProcess(0x410, False, args.pid)
    if not handle:
        raise c.WinError(c.get_last_error())
    try:
        k.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4
        times = [w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle, *[c.byref(x) for x in times]):
            raise c.WinError(c.get_last_error())
        creation = times[0].dwLowDateTime | times[0].dwHighDateTime << 32
        if creation != args.creation_filetime:
            raise ValueError('process_creation_mismatch')
        path = c.create_unicode_buffer(32768); size = w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(handle, 0, path, c.byref(size)):
            raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest() != EXPECTED:
            raise ValueError('unsupported_executable')

        def read(address, length):
            buffer = c.create_string_buffer(length); got = c.c_size_t()
            if not k.ReadProcessMemory(handle, address, buffer, length, c.byref(got)) or got.value != length:
                raise ValueError('native_read_failed')
            return buffer.raw

        for address, expected in [(0x571370, '8b410c85c0538d5904'), (0x573b9c, '8d8fe46c0100'),
                                  (0x573bcf, '5f8d46185e83c410c20400')]:
            if read(address, len(bytes.fromhex(expected))) != bytes.fromhex(expected):
                raise ValueError('native_flag_layout_signature_mismatch')
        report = dict(pid=args.pid, process_creation_filetime=creation, executable_sha256=EXPECTED,
            sampled_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            **inspect_flags(read, args.flag))
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        k.CloseHandle(handle)


if __name__ == '__main__':
    main()
