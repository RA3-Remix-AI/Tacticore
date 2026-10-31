"""Portable Native6 negative contracts. These tests never attach a game."""
import copy
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import uuid
from unittest.mock import patch

from host_runtime.native6_journal import (BINDING_SIZE, JOURNAL_BINDING, JOURNAL_END, JOURNAL_SIZE, MAGIC,
                                        SHARED_SIZE, decode, verified, wire_binding)
from host_runtime.native6_paths import Native6Paths, plain_local, session_hex
from host_runtime.native6_runtime_contract import closure, locked_inputs, pin_map, profile, sha, verify_inventory


class PortableNative6Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='native6-contract-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def binding(self):
        from host_runtime.native6_journal import WORDS, ARRAYS
        value = {name: index + 1 for index, name in enumerate(WORDS)}
        value.update({name: [index + 1] * size for index, (name, size) in enumerate(ARRAYS)})
        value.update(deployment=r'C:\Users\tester\Documents\Red Alert 3\Mods\qualified.big',
                     game_image=r'D:\Installed Game\Data\RA3_1.12.game', runtime_root=r'D:\Tacticore\runtime',
                     journal_root=r'C:\Users\tester\AppData\Local\Tacticore\desktop-runtime\native6\journals')
        return value

    def journal(self, binding, count=2):
        result = bytearray()
        for sequence in range(1, count + 1):
            record = bytearray(JOURNAL_SIZE)
            struct.pack_into('<7I', record, 0, MAGIC, 6, sequence, JOURNAL_SIZE, sequence, 7, 100)
            record[JOURNAL_BINDING:JOURNAL_BINDING + BINDING_SIZE] = wire_binding(binding)
            struct.pack_into('<I', record, JOURNAL_END, 0x454e4436)
            result.extend(record)
        return bytes(result)

    def test_paths_use_supplied_known_roots_and_do_not_use_localappdata_environment(self):
        local, documents = self.root / 'local', self.root / 'documents'
        local.mkdir(); documents.mkdir()
        with patch.dict(os.environ, LOCALAPPDATA=str(self.root / 'hostile')):
            paths = Native6Paths.from_roots(local, documents)
            paths.ensure()
        session = str(uuid.uuid4())
        self.assertEqual(paths.journal(session).parent, paths.journals)
        self.assertTrue(paths.report(session).is_relative_to(local))
        self.assertFalse((self.root / 'hostile').exists())

    def test_actual_windows_known_folder_lookup_ignores_inherited_override(self):
        with patch.dict(os.environ, LOCALAPPDATA=str(self.root / 'hostile')):
            paths = Native6Paths.current()
        self.assertFalse(paths.root.is_relative_to(self.root))
        self.assertEqual(paths.root.parts[-3:], ('Tacticore', 'desktop-runtime', 'native6'))
        self.assertEqual(paths.root.name, 'native6')

    def test_port_preserves_native_command_and_unknown_delivery_logic(self):
        repo = Path(__file__).resolve().parents[1]
        old = repo / 'native-ai/strategic-unified-runtime-v5'
        new = repo / 'native-ai/strategic-portable-runtime-v6'
        self.assertEqual((old / 'flag_api.h').read_bytes(), (new / 'flag_api.h').read_bytes())
        def section(directory, name, begin, end):
            return (directory / name).read_text(encoding='utf-8').split(begin, 1)[1].split(end, 1)[0]
        self.assertEqual(section(old, 'native.cpp', 'static void tick(){', 'static DWORD WINAPI watchdog('),
                         section(new, 'native.cpp', 'static void tick(){', 'static DWORD WINAPI watchdog('))
        self.assertEqual(section(old, 'client.py', '    def _command(', '    def close('),
                         section(new, 'client.py', '    def _command(', '    def close('))
        flags = (new / 'flags.h').read_text().replace('row.version=6', 'row.version=5').replace('0x454e4436', '0x454e4435')
        self.assertEqual((old / 'flags.h').read_text(), flags)

    def test_session_and_path_escapes_fail(self):
        for value in (r'\\server\share\x', r'\\?\C:\x', 'relative', str(self.root / 'x/../escape')):
            with self.assertRaises((ValueError, FileNotFoundError)):
                plain_local(value, existing=False)
        for session in ('../x', '00000000-0000-0000-0000-000000000000', '{' + str(uuid.uuid4()) + '}'):
            with self.assertRaises(ValueError):
                session_hex(session)

    def test_mod_must_be_plain_file_inside_known_documents_mods(self):
        paths = Native6Paths.from_roots(self.root, self.root)
        mod = paths.mods / 'candidate/test.big'
        mod.parent.mkdir(parents=True)
        mod.write_bytes(b'fixture, not a qualified game package')
        self.assertEqual(paths.require_mod(mod), mod)
        other = self.root / 'outside.big'
        other.write_bytes(b'outside')
        with self.assertRaises(ValueError):
            paths.require_mod(other)

    def test_only_code_is_in_compiled_input_closure_and_paths_are_relative(self):
        value = dict(files={'app/integration/core.py': '1' * 64, 'app/integration/__pycache__/core.pyc': '2' * 64,
                            'python/python.exe': '3' * 64, 'python/DLLs/ssl.pyd': '4' * 64,
                            'python/Lib/license.txt': '5' * 64, 'native/strategic6/manager_host.exe': '6' * 64})
        pins = locked_inputs(value)
        self.assertEqual(len(pins), 4)
        emitted = profile(pins, {'native.cpp': '9' * 64})
        self.assertIn('FIELD_CANDIDATE=false', emitted)
        self.assertNotIn(str(self.root), emitted)
        self.assertNotIn('JOURNAL_ROOT', emitted)
        self.assertNotIn('DEPLOYMENT_ROOT', emitted)

    def test_all_stdlib_dependency_source_cache_and_container_are_continuously_pinned(self):
        names=('app/integration/core.py','python/Lib/json/decoder.py','python/Lib/json/__pycache__/decoder.pyc',
               'python/Lib/site-packages/retained/core.py','python/Lib/site-packages.zip','dependency-container.json')
        inventory=dict(files={name:'1'*64 for name in names})
        self.assertEqual(set(locked_inputs(inventory)),set(names))
        with self.assertRaisesRegex(ValueError,'bounded'):
            locked_inputs(dict(files={f'python/Lib/package{i}.py':'2'*64 for i in range(4094)}))

    def test_field_and_offline_closures_are_distinct_and_no_mode_is_inferred_from_json(self):
        pins={'app/core.py':'1'*64};provenance={'native.cpp':'2'*64}
        self.assertNotEqual(closure(pins,provenance),closure(pins,provenance,field_candidate=True))
        self.assertIn('FIELD_CANDIDATE=true',profile(pins,provenance,field_candidate=True))
        self.assertIn('FIELD_CANDIDATE=false',profile(pins,provenance))

    def test_absolute_duplicate_and_escaping_pins_refused(self):
        for pins in ({'C:/dev/source.py': '0' * 64}, {'../source.py': '0' * 64},
                     {'app/x': '0' * 64, 'APP/X': '1' * 64}, {'app/x.': '0' * 64}):
            with self.assertRaises(ValueError):
                pin_map(pins)

    def test_closure_does_not_depend_on_object_key_order_but_detects_changes(self):
        left = {'app/b.py': '1' * 64, 'app/a.py': '2' * 64}
        right = dict(reversed(list(left.items())))
        self.assertEqual(closure(left, {'native.cpp': '3' * 64}), closure(right, {'native.cpp': '3' * 64}))
        right['app/a.py'] = '4' * 64
        self.assertNotEqual(closure(left, {'native.cpp': '3' * 64}), closure(right, {'native.cpp': '3' * 64}))

    def test_complete_inventory_rejects_extra_code_and_missing_file(self):
        for name in ('python/python.exe', 'app/integration/host_runtime/bridge_service.py'):
            path = self.root / name
            path.parent.mkdir(parents=True)
            path.write_bytes(b'fixture')
        files = {name: sha(self.root / name) for name in ('python/python.exe', 'app/integration/host_runtime/bridge_service.py')}
        (self.root / 'manifest.json').write_text(json.dumps(dict(schema_version=1, python='python/python.exe', working_directory='app/integration', files=files)))
        verify_inventory(self.root)
        extra = self.root / 'app/injected.py'
        extra.write_bytes(b'extra')
        with self.assertRaises(ValueError):
            verify_inventory(self.root)
        extra.unlink()
        (self.root / 'python/python.exe').unlink()
        with self.assertRaises(ValueError):
            verify_inventory(self.root)

    def test_journal_is_bound_to_every_epoch_path_and_runtime_manifest(self):
        binding = self.binding()
        raw = self.journal(binding)
        self.assertEqual(len(decode(raw, binding)), 2)
        for key in ('session', 'lease', 'runtime_manifest', 'sources', 'game_image', 'runtime_root', 'journal_root'):
            changed = copy.deepcopy(binding)
            if isinstance(changed[key], list):
                changed[key][0] ^= 1
            else:
                changed[key] += 'x'
            with self.assertRaises(ValueError):
                decode(raw, changed)

    def test_old_protocol_truncation_reordering_and_partial_tail_are_rejected(self):
        binding = self.binding()
        raw = self.journal(binding)
        old = bytearray(raw)
        struct.pack_into('<I', old, 4, 5)
        for changed in (bytes(old), raw[:-1], raw + b'partial', raw[JOURNAL_SIZE:] + raw[:JOURNAL_SIZE]):
            with self.assertRaises(ValueError):
                decode(changed, binding)

    def test_valid_journal_checks_count_and_is_not_a_restoration_certificate(self):
        binding = self.binding()
        raw = self.journal(binding)
        native = dict(magic=MAGIC, version=6, size=SHARED_SIZE, binding=binding, journal_records=2)
        self.assertTrue(verified(raw, native))
        self.assertNotIn('native_release_verified', native)
        self.assertFalse(verified(raw, dict(native, journal_records=1)))
        self.assertFalse(verified(raw, dict(native, version=5)))


if __name__ == '__main__':
    unittest.main()
