"""Native6 helper seal and independent observation of an ended Host's epoch.

This is not wired into the product ledger. A fresh baseline observation does
not settle unknown delivery rows or automatically release a run. The current
Native6 build cannot attach, so only offline/fixture verification is available.
"""
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

from .native5_helper_identity_v1 import ended_incarnation, process_identity
from .native6_journal import BINDING_SIZE, SHARED_SIZE, verified, wire_binding
from .native6_paths import Native6Paths, plain_local
from .native6_runtime_contract import read, sha, verify_build

KIND = 'portable_native6_helper_identity_v1'


def record_helper_identity(probe):
    helper, parent = process_identity(probe.host.pid), process_identity(os.getpid())
    binding = probe.status()['binding']
    root = plain_local(binding['runtime_root'])
    if (not helper['alive'] or not parent['alive'] or probe.host.poll() is not None
            or Path(helper['image']) != probe.build / 'manager_host.exe'
            or bytes(binding['runtime_manifest']).hex() != sha(root / 'manifest.json')
            or bytes(binding['session']) != uuid.UUID(probe.session['session_id']).bytes):
        raise ValueError('native6_helper_seal_not_current')
    value = dict(kind=KIND, session_id=probe.session['session_id'], native_binding=binding,
                 helper=helper, parent=parent, helper_sha256=sha(probe.build / 'manager_host.exe'),
                 build_manifest_sha256=sha(probe.build / 'build-manifest.json'),
                 source_sha256=sha(__file__), native_commands_issued=0)
    with (probe.output / 'helper-identity.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    return value


def collect_existing_readonly(sdk, session, identity):
    """Only query/FILE_MAP_READ; never construct a Probe, heartbeat or command.

    The caller must separately bind a durable STOP and reconcile its ledger
    before making any product-level release claim.
    """
    if identity.get('kind') != KIND or identity.get('session_id') != session['session_id']:
        raise ValueError('native6_helper_seal_required')
    binding = identity['native_binding']
    raw_binding = wire_binding(binding)
    if (binding['pid'] != session['pid'] or (binding['start_low'] | binding['start_high'] << 32) != session['process_creation_filetime']
            or bytes(binding['session']) != uuid.UUID(session['session_id']).bytes
            or bytes(binding['package']).hex() != session['mod_sha256']):
        raise ValueError('native6_recovery_session_changed')
    root = plain_local(binding['runtime_root'])
    paths = Native6Paths.current()
    if Path(binding['journal_root']) != paths.journals or bytes(binding['runtime_manifest']).hex() != sha(root / 'manifest.json'):
        raise ValueError('native6_recovery_runtime_or_journal_changed')
    build = root / 'native/strategic6'
    manifest = verify_build(build)
    inventory = read(root / 'manifest.json')['files']
    source = 'app/integration/host_runtime/native6_readonly_return.py'
    if (identity['source_sha256'] != inventory.get(source) or sha(__file__) != inventory.get(source)
            or identity['helper_sha256'] != manifest['artifacts']['manager_host.exe']
            or identity['build_manifest_sha256'] != sha(build / 'build-manifest.json')
            or Path(identity['helper']['image']) != build / 'manager_host.exe'
            or bytes(binding['sources']).hex() != manifest['source_closure_sha256']
            or c.sizeof(sdk.Shared) != SHARED_SIZE or c.sizeof(sdk.Binding) != BINDING_SIZE
            or Path(sdk.__file__).resolve() != root / 'app/native-ai/strategic-portable-runtime-v6/client.py'):
        raise ValueError('native6_recovery_frozen_inputs_changed')
    parent, helper_before = ended_incarnation(identity['parent']), ended_incarnation(identity['helper'])
    if parent['ended'] is not True or helper_before['ended'] is not True:
        raise ValueError('native6_recovery_owner_still_alive')
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenFileMappingW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]; kernel.OpenFileMappingW.restype = w.HANDLE
    kernel.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, c.c_size_t]; kernel.MapViewOfFile.restype = c.c_void_p
    kernel.UnmapViewOfFile.argtypes = [c.c_void_p]; kernel.CloseHandle.argtypes = [w.HANDLE]
    mapping = kernel.OpenFileMappingW(4, False, 'Local\\RA3StrategicCommanderV6_' + str(session['pid']))
    if not mapping:
        raise c.WinError(c.get_last_error())
    view = None
    try:
        view = kernel.MapViewOfFile(mapping, 4, 0, 0, SHARED_SIZE)
        if not view:
            raise c.WinError(c.get_last_error())
        state = sdk.Shared.from_address(view)
        status = lambda: sdk.projection(sdk.Shared.from_buffer_copy(c.string_at(view, SHARED_SIZE)))
        if bytes(state.binding) != raw_binding:
            raise ValueError('native6_recovery_epoch_changed')
        reader = SimpleNamespace(kernel=kernel, session=session, manifest=manifest, state=state,
                                 binding=raw_binding, status=status, unknown=None)
        proof = sdk.Probe.independent_release(reader)
        raw = paths.journal(session['session_id']).read_bytes()  # missing zero-record file is unknown
        after = status()
        helper_after = ended_incarnation(identity['helper'])
        if (helper_after['ended'] is not True or bytes(state.binding) != raw_binding
                or after != proof['native'] or not verified(raw, after)):
            raise ValueError('native6_recovery_journal_or_epoch_changed')
        return dict(kind='native6_readonly_current_baseline_v1', helper_identity=identity,
                    parent_ended=parent, helper_ended_before=helper_before, helper_ended_after=helper_after,
                    current_restoration=proof, mapping_access='FILE_MAP_READ', native_commands_issued=0,
                    helper_exit_code=None, ownership_return_claimed=False, product_capability_granted=False), raw
    finally:
        if view:
            kernel.UnmapViewOfFile(view)
        kernel.CloseHandle(mapping)
