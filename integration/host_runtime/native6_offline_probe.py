"""Run only in an isolated companion; validate Native6 without game access."""
import argparse
import ctypes as c
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

from . import native6_journal as journal
from .native6_paths import Native6Paths
from .native6_runtime_contract import GAME_SHA, PACKAGE_SHA, read, sha, verify_build, verify_inventory


def denied(*args, **kwargs):
    raise AssertionError('native6_offline_probe_forbidden_operation')


def probe(runtime):
    runtime = Path(runtime).resolve()
    before = sha(runtime / 'manifest.json')
    manifest = verify_build(runtime / 'native/strategic6')
    helper = runtime / 'native/strategic6/manager_host.exe'
    socket.socket.connect = denied
    socket.create_connection = denied

    def call(*arguments, expected=0):
        process = subprocess.run([str(helper), *map(str, arguments)], capture_output=True, timeout=30,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode != expected:
            raise ValueError('native6_helper_offline_check_failed')
        return process.stdout

    compiled = json.loads(call('--profile'))
    if compiled != dict(protocol_version=6, field_candidate=False, source_closure_sha256=manifest['source_closure_sha256'],
                        package_sha256=PACKAGE_SHA, game_sha256=GAME_SHA):
        raise ValueError('native6_compiled_identity_changed')
    call('--check-export')
    call('--validate-runtime-root', str(runtime))
    call('--validate-runtime-root', str(runtime / 'wrong'), expected=25)
    call('--validate-relative', 'app/native-ai/strategic-portable-runtime-v6/client.py')
    for value in ('-1', '4294967296', '1024', '0x70', '0x38f', 'garbage'):
        call('--validate-mask', value, expected=23)
    call('--validate-mask', '0')
    for path in ('../manifest.json', '/manifest.json', 'C:/manifest.json', 'app\\x', 'app//x', 'app/./x', 'app/../x'):
        call('--validate-relative', path, expected=25)
    # Even a real positive PID is refused before EnumWindows/OpenProcess or
    # mapping attachment by the compiled false gate.
    call(str(os.getpid()), expected=24)
    source = runtime / 'app/native-ai/strategic-portable-runtime-v6/client.py'
    spec = importlib.util.spec_from_file_location('native6_offline_client', source)
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)
    sdk.verify_layout(manifest)
    actual = dict(binding_size=c.sizeof(sdk.Binding), shared_size=c.sizeof(sdk.Shared), journal_size=c.sizeof(sdk.JournalRecord),
                  journal_binding=sdk.JournalRecord.binding.offset, journal_audit=sdk.JournalRecord.audit.offset,
                  journal_flags=sdk.JournalRecord.flags.offset, journal_end=sdk.JournalRecord.end.offset)
    expected = dict(binding_size=journal.BINDING_SIZE, shared_size=journal.SHARED_SIZE, journal_size=journal.JOURNAL_SIZE,
                    journal_binding=journal.JOURNAL_BINDING, journal_audit=journal.JOURNAL_AUDIT,
                    journal_flags=journal.JOURNAL_FLAGS, journal_end=journal.JOURNAL_END)
    if actual != expected:
        raise ValueError('native6_independent_layout_mismatch')
    binding = sdk.Binding()
    for index, name in enumerate(journal.WORDS):
        setattr(binding, name, index + 1)
    for index, (name, size) in enumerate(journal.ARRAYS):
        getattr(binding, name)[:] = bytes([index + 1] * size)
    for name, value in dict(deployment=r'C:\Test\Documents\Red Alert 3\Mods\fixture.big',
                            game_image=r'D:\Test Game\Data\RA3_1.12.game', runtime_root=str(runtime),
                            journal_root=r'C:\Test\AppData\Local\Tacticore\desktop-runtime\native6\journals').items():
        setattr(binding, name, value)
    projected = sdk.projection(binding)
    if bytes(binding) != journal.wire_binding(projected):
        raise ValueError('native6_independent_binding_encoding_mismatch')
    raw = b''
    for index in range(2):
        row = sdk.JournalRecord()
        row.magic=journal.MAGIC; row.version=6; row.sequence=index+1; row.size=journal.JOURNAL_SIZE
        row.kind=index+1; row.binding=binding; row.end=0x454e4436
        raw += bytes(row)
    with tempfile.TemporaryDirectory(prefix='native6-offline-') as temporary:
        temporary = Path(temporary)
        sample = temporary / 'fixture.bin'
        sample.write_bytes(raw)
        if len(sdk.read_journal(sample, bytes(binding))) != 2 or len(journal.decode(raw, projected)) != 2:
            raise ValueError('native6_independent_journal_decode_mismatch')
        session = temporary / 'session.json'
        session.write_text('{}', encoding='utf-8')
        old_memory, old_win_dll, old_popen, old_current = sdk.Memory, c.WinDLL, subprocess.Popen, Native6Paths.__dict__['current']
        try:
            sdk.Memory = denied
            c.WinDLL = denied
            subprocess.Popen = denied
            Native6Paths.current = classmethod(denied)
            try:
                sdk.Probe(session, runtime / 'native/strategic6', temporary / 'must-not-create')
            except ValueError as error:
                if str(error) != 'native6_offline_candidate_cannot_attach':
                    raise
            else:
                raise ValueError('native6_sdk_offline_gate_missing')
        finally:
            sdk.Memory, c.WinDLL, subprocess.Popen, Native6Paths.current = old_memory, old_win_dll, old_popen, old_current
        if (temporary / 'must-not-create').exists():
            raise ValueError('native6_sdk_wrote_before_offline_refusal')
    for module in tuple(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file and not str(file).startswith('<') and not Path(file).resolve().is_relative_to(runtime):
            raise ValueError('native6_probe_import_outside_companion')
    verify_inventory(runtime, expected=before)
    return dict(schema_version=1, kind='native6_offline_candidate_smoke', runtime_manifest_sha256=before,
                source_closure_sha256=manifest['source_closure_sha256'], runtime_code_pins=len(manifest['input_pins']),
                layout_verified=actual, compiled_identity_verified=True, relative_paths_verified=True,
                imports_confined=True, sdk_and_helper_attach_blocked=True, independent_journal_verified=True,
                inventory_unchanged=True, game_access=False, model_requests=0, formal_games=0,
                product_capability_granted=False, public_release_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(args.runtime)))
