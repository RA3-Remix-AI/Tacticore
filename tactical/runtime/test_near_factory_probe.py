"""Command-free qualification boundaries; no process or native DLL is opened."""
import ctypes as c
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tactical.runtime import near_factory_probe as probe
from tactical.runtime import near_layout as n


class NearFactoryProbeBoundaries(unittest.TestCase):
    def test_first_observation_does_not_finish_startup_before_both_receipts(self):
        buffer=c.create_string_buffer(c.sizeof(n.Shared));p=object.__new__(probe.NearFactoryProbe)
        p.full=n.Shared.from_address(c.addressof(buffer));p.shared=p.full.movement
        p.shared.state=2;p.shared.admitted_actor.generation=1;p.shared.observation_generation=2
        self.assertFalse(p._initial_snapshot_ready())
        p.shared.receipt_generation=2
        self.assertFalse(p._initial_snapshot_ready())
        p.full.near_receipt_generation=1
        self.assertFalse(p._initial_snapshot_ready())
        p.full.near_receipt_generation=2
        self.assertTrue(p._initial_snapshot_ready())
        p.shared.observation_generation=3
        self.assertFalse(p._initial_snapshot_ready())
        p.shared.observation_generation=4;p.shared.state=5
        self.assertFalse(p._initial_snapshot_ready())

    def test_probe_cannot_submit_or_promote_a_field_capability(self):
        p=object.__new__(probe.NearFactoryProbe)
        with self.assertRaisesRegex(ValueError,'never_publishes_commands'):p.submit({'operation':'reserve'})
        with self.assertRaisesRegex(ValueError,'no_field_capability'):p._field_admission(object())

    def test_model_session_is_refused_before_parent_or_build_code(self):
        with tempfile.TemporaryDirectory(prefix='near-probe-session-')as temporary:
            folder=Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            session=folder/'session.json'
            session.write_text(json.dumps({'scenario':dict(trial_kind='near_factory_channel2_readonly',diagnostic_only=True,
                model_requests_enabled=True,full_match_acceptance=False,lobby_verified=True)}))
            with patch.object(probe.legacy.NativeRuntimeClient,'__init__',side_effect=AssertionError('parent reached')):
                with self.assertRaisesRegex(ValueError,'explicit_owned_readonly'):
                    probe.NearFactoryProbe(session,None,None,'',folder/'result.json',build=folder,build_sha256='0'*64)

    def test_integrity_check_refuses_either_command_publication_and_bootstrap_edit(self):
        with tempfile.TemporaryDirectory(prefix='near-probe-integrity-')as temporary:
            folder=Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            session=folder/'session.json';session.write_bytes(b'{}')
            buffer=c.create_string_buffer(c.sizeof(n.Shared));p=object.__new__(probe.NearFactoryProbe)
            p.session_path=session;p.session_bytes=b'{}';p.view=c.addressof(buffer)
            p.full=n.Shared.from_address(p.view);p.shared=probe.layout.SharedChannel.from_address(p.view)
            p.shared.magic_word=n.MAGIC;p.shared.protocol=n.VERSION;p.shared.structure_size=c.sizeof(n.Shared);p.shared.token=p.token=7
            p.full.bootstrap.schema=2;p.bootstrap_bytes=bytes(p.shared.bootstrap);p.near_bootstrap_bytes=bytes(p.full.bootstrap)
            p._check();p.full.near_command_generation=2
            with self.assertRaisesRegex(ValueError,'unexpected_command'):p._check()
            p.full.near_command_generation=0;p.shared.command_generation=2
            with self.assertRaisesRegex(ValueError,'unexpected_command'):p._check()
            p.shared.command_generation=0;p.full.bootstrap.mod_path='changed'
            with self.assertRaisesRegex(ValueError,'bootstrap_changed'):p._check()
            p.full.bootstrap=n.NativeBootstrap.from_buffer_copy(p.near_bootstrap_bytes);p.source_snapshot={probe.__file__:'0'*64}
            with self.assertRaisesRegex(ValueError,'source_changed'):p._check()


if __name__=='__main__':unittest.main()
