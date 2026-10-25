"""Read-only RA3 1.12 bridge feasibility probe. Never writes target memory.

Offsets are hypotheses from ProbiusOfficial/Ra3-Copilot; matches are candidates,
not proof of live objects or AI ownership. Run with the bundled 64-bit Python.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time

ROOT = Path(__file__).resolve().parent
EXPECTED = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
k = c.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k.OpenProcess.restype = w.HANDLE
k.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
k.ReadProcessMemory.restype = w.BOOL
k.CloseHandle.argtypes = [w.HANDLE]
k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]

class MBI(c.Structure):
    _fields_ = [('base', c.c_void_p), ('allocation', c.c_void_p),
                ('allocation_protect', w.DWORD), ('region_size', c.c_size_t),
                ('state', w.DWORD), ('protect', w.DWORD), ('type', w.DWORD)]

k.VirtualQueryEx.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(MBI), c.c_size_t]
k.VirtualQueryEx.restype = c.c_size_t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--owner-index', type=int, help='Export only this player; hidden enemy data is omitted')
    args = ap.parse_args()
    handle = k.OpenProcess(0x0400 | 0x0010, False, args.pid)
    if not handle:
        raise c.WinError(c.get_last_error())
    try:
        path = c.create_unicode_buffer(32768)
        size = w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(handle, 0, path, c.byref(size)):
            raise c.WinError(c.get_last_error())
        digest = hashlib.sha256(Path(path.value).read_bytes()).hexdigest()
        if Path(path.value).name.lower() != 'ra3_1.12.game' or digest != EXPECTED:
            raise RuntimeError('Unsupported executable; refusing offset-based scan')

        def read(addr, size):
            buf = c.create_string_buffer(size)
            got = c.c_size_t()
            if k.ReadProcessMemory(handle, addr, buf, size, c.byref(got)) and got.value == size:
                return buf.raw
            return None

        def u32(addr):
            raw = read(addr, 4)
            return struct.unpack('<I', raw)[0] if raw else 0

        catalog = {}
        source = ROOT / 'reference/Ra3-Copilot/ra3-copilot/src/battle_catalog.h'
        for match in re.finditer(r'\{\s*0x([0-9A-Fa-f]+)u, u8"([^"]*)", "([^"]*)", (\d+), (\d+), (\d+)\s*\}', source.read_text(encoding='utf-8')):
            h, name, template, side, cls, cat = match.groups()
            catalog[int(h, 16)] = dict(name=name, template=template, side=int(side), cls=int(cls), category=int(cat))

        # This target is expected to use its preferred image base. Verify the
        # vtable's first function pointer before scanning with this hypothesis.
        vtable = 0xC4DB60
        if not 0x400000 <= u32(vtable) < 0xD3B000:
            raise RuntimeError('Vtable/image-base hypothesis failed')
        needle = struct.pack('<I', vtable)
        started = time.monotonic()
        candidates = []
        scanned = 0
        address = 0x10000
        while address < 0x100000000:
            mbi = MBI()
            if not k.VirtualQueryEx(handle, address, c.byref(mbi), c.sizeof(mbi)):
                break
            base, length = mbi.base or 0, mbi.region_size
            if not length or base + length <= address:
                break
            if mbi.state == 0x1000 and mbi.type == 0x20000 and not mbi.protect & 0x101:
                for offset in range(0, length, 1024 * 1024):
                    chunk = read(base + offset, min(1024 * 1024, length - offset))
                    if not chunk:
                        continue
                    scanned += len(chunk)
                    pos = chunk.find(needle)
                    while pos >= 0:
                        obj = base + offset + pos
                        if obj % 4 == 0:
                            raw = read(obj, 0x41C)
                            if raw:
                                template = struct.unpack_from('<I', raw, 4)[0]
                                owner = struct.unpack_from('<I', raw, 0x418)[0]
                                owner_vt = u32(owner)
                                h = u32(template + 8) if template else 0
                                xyz = struct.unpack_from('<fff', raw, 0x38)
                                if 0x400000 <= owner_vt < 0xD3B000 and (args.owner_index is None or u32(owner + 0x20) == args.owner_index) and all(math.isfinite(x) and abs(x) < 1000000 for x in xyz):
                                    info = catalog.get(h, {})
                                    candidates.append(dict(address=hex(obj), owner_address=hex(owner), owner_index_candidate=u32(owner + 0x20), type_hash=hex(h), ai_address=hex(struct.unpack_from('<I', raw, 0x374)[0]), xyz=xyz, catalog=info))
                        pos = chunk.find(needle, pos + 4)
            address = base + length
        report = dict(pid=args.pid, executable=path.value, sha256=digest,
                      owner_index_filter=args.owner_index,
                      elapsed_seconds=round(time.monotonic()-started, 2), scanned_bytes=scanned,
                      candidate_count=len(candidates), candidates=candidates,
                      status='read_only_candidates', ai_ownership_verified=False,
                      movement_tested=False, note='Non-atomic read; stale objects and uncertain fields are possible. Catalog is a Corona reference, not a verified catalog of the active mod.')
        out = ROOT / 'reports'
        out.mkdir(exist_ok=True)
        target = out / ('snapshot-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(report=str(target), candidates=len(candidates), known=sum(bool(x['catalog']) for x in candidates), elapsed=report['elapsed_seconds']), ensure_ascii=False))
    finally:
        k.CloseHandle(handle)

if __name__ == '__main__':
    main()
