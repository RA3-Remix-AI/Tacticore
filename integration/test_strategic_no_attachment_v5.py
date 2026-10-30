"""Synthetic certificate boundary tests; not evidence of an actual capture."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from host_runtime.contracts import SessionBinding
from host_runtime.strategic_no_attachment_v5 import KIND,verified_capture,capture
from host_runtime.diagnostics import project_plan
from host_runtime.strategic_contract_v5 import STRATEGIC_ACTIONS
from host_runtime.macro_delegation_boundary_v1 import validate_policy

ROOT=Path(__file__).resolve().parents[1]

class NoAttachment(unittest.TestCase):
    def test_partial_readonly_reader_construction_closes_acquired_handle(self):
        calls=[]
        class Reader:
            def __init__(self,pid,session):
                self.handle=123;calls.append('opened')
                raise RuntimeError('synthetic image identity read failed')
            def close(self):calls.append(('closed',self.handle))
        with patch('host_runtime.strategic_unified_transport_v5.native_module',return_value=(None,SimpleNamespace(Memory=Reader))):
            with self.assertRaisesRegex(RuntimeError,'image identity'):
                capture(None,{'pid':1},None,'synthetic')
        self.assertEqual(calls,['opened',('closed',123)])

    def fixture(self):
        folder=ROOT/'acceptance/runs/desktop-d3aea588-682e-4d58-a8d5-1b2cd9ec473e'
        if not all((folder/name).is_file() for name in ('session.json','battle-host/macro-release.json')):
            raise unittest.SkipTest('requires local pre-attach evidence; not distributed with source')
        session=json.loads((folder/'session.json').read_bytes())
        release=json.loads((folder/'battle-host/macro-release.json').read_bytes())
        binding=SessionBinding.from_dict(release['binding']);pid=binding.game_process_id
        objects=dict(source='win32_read_only_macro_channel_and_semaphore_v1',
            mapping_name='Local'+chr(92)+'RA3StrategicCommanderV5_'+str(pid),
            semaphore_name='Local'+chr(92)+'RA3MacroPolicyLease_'+str(pid),mapping_status='absent',
            semaphore_status='absent',mapping_open_error=2,semaphore_open_error=2,native_writes=0,acquire_or_wait_calls=0)
        identity=dict(pid=pid,process_creation_filetime=session['process_creation_filetime'])
        value=dict(kind=KIND,schema_version=1,run_id=release['run_id'],binding=binding.public(),
            actual_OS_before=identity,actual_OS_after=copy.deepcopy(identity),policy_modules_before=[],policy_modules_after=[],
            objects_before=objects,objects_after=copy.deepcopy(objects),started_monotonic_ns=100,ended_monotonic_ns=200,
            image_before=str(Path(session['game']).resolve()),image_after=str(Path(session['game']).resolve()),
            image_sha256=binding.game_sha256,no_control_acquired=True,manager_restoration_claimed=False,mission_effect_verified=False)
        return value,session,binding,release['run_id']
    def test_format_acceptance_is_not_manager_restore_or_mission_success(self):
        proof,*args=self.fixture();self.assertTrue(verified_capture(proof,*args))
        for key in ('manager_restoration_claimed','mission_effect_verified'):
            bad=copy.deepcopy(proof);bad[key]=True;self.assertFalse(verified_capture(bad,*args))
    def test_existing_policy_module_mapping_or_lease_cannot_be_called_never_acquired(self):
        proof,*args=self.fixture()
        for modify in (lambda p:p.update(policy_modules_after=['StrategicCommanderV5.dll']),
            lambda p:p['objects_before'].update(mapping_status='present'),
            lambda p:p['objects_after'].update(semaphore_status='free'),
            lambda p:p['actual_OS_after'].update(process_creation_filetime=1),
            lambda p:p.update(image_sha256='0'*64),lambda p:p.update(schema_version=True),
            lambda p:p.update(ended_monotonic_ns=250_000_101)):
            bad=copy.deepcopy(proof);modify(bad);self.assertFalse(verified_capture(bad,*args))
    def test_all_high_intents_survive_real_diagnostic_projection_without_granting_precision(self):
        source=ROOT/'acceptance/runs/desktop-bcd88e90-e31e-4f87-94c1-9f2ec32da025/battle-host/host-events.jsonl'
        if not source.is_file():
            raise unittest.SkipTest('requires the local historical high-intent context archive')
        events=[json.loads(s) for s in source.read_text().splitlines()]
        base=next(e['plan'] for e in events if e['kind']=='plan_applied')
        for action in STRATEGIC_ACTIONS:
            plan=dict(base,macro_actions=[action],macro_strategy=None);validate_policy(plan)
            self.assertEqual(project_plan(plan)['macro_actions'],[action])
        for action in ('unit_123:move:1,2','produceconscript:99','building@1,2'):
            self.assertNotIn('macro_actions',project_plan(dict(base,macro_actions=[action],macro_strategy=None)))

if __name__=='__main__':unittest.main()
