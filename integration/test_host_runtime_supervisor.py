"""Live supervisor identity is a narrow barrier exception, never game proof."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from host_runtime import host_supervisor as module
from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.journal import CommandJournal
from host_runtime.host_tactical import HostTactical
import test_host_runtime_tactical_adapter as fixtures


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.j=CommandJournal(Path(self.temp.name)/'ledger.sqlite3')
        self.binding=SessionBinding(1,fixtures.uid(),3,fixtures.uid(),1234,'2026-10-27T00:00:00+00:00',fixtures.uid(),'a'*64,'b'*64)
        self.run=fixtures.uid();self.j.register_run(self.run,self.binding.public())
        self.row=self.j.reserve_command(self.run,fixtures.uid(),'host_start',{})
        self.j.mark_dispatching(self.run,self.row['request_id'])
        self.j.record_outcome(self.run,self.row['request_id'],'started',{'host_pid':7777,'host_start_time':'actual-start'})
        self.host=SimpleNamespace(runtime_production=SimpleNamespace(journal=self.j,run_id=self.run,binding=self.binding))
        self.identity=patch.object(module,'_identity',return_value=(7777,'actual-start'));self.identity.start();self.addCleanup(self.identity.stop)

    def tearDown(self):self.j.close();self.temp.cleanup()

    def test_only_actual_current_supervisor_is_excluded_without_rewriting_started(self):
        supervisor=module.supervisor_for_host(self.host)
        child=replace(self.binding,host_id=fixtures.uid())
        self.assertEqual(len(self.j.unresolved_for_session(child.public())),1)
        self.assertEqual(module.pending_native_commands(self.j,child,supervisor),[])
        self.assertEqual(self.j.get_command(self.run,self.row['request_id'])['status'],'started')
        pending=self.j.reserve_command(self.run,fixtures.uid(),'produce',{'unit':'conscript'})
        rows=module.pending_native_commands(self.j,child,supervisor)
        self.assertEqual([r['command_id'] for r in rows],[pending['command_id']])

    def test_stale_pid_start_or_uncertain_launch_cannot_be_ignored(self):
        supervisor=module.supervisor_for_host(self.host)
        for observed in ((7778,'actual-start'),(7777,'reused-pid-start')):
            with patch.object(module,'_identity',return_value=observed):
                with self.assertRaisesRegex(ContractError,'process_unverified'):module.pending_native_commands(self.j,self.binding,supervisor)
        self.j.record_outcome(self.run,self.row['request_id'],'uncertain',{'reason_code':'owner_interrupted'})
        with self.assertRaisesRegex(ContractError,'process_unverified'):module.pending_native_commands(self.j,self.binding,supervisor)

    def test_other_game_or_unsealed_description_cannot_exclude_any_launch(self):
        supervisor=module.supervisor_for_host(self.host)
        with self.assertRaisesRegex(ContractError,'binding_changed'):
            module.pending_native_commands(self.j,replace(self.binding,session_id=fixtures.uid()),supervisor)
        with self.assertRaisesRegex(ContractError,'live_supervisor_required'):
            module.pending_native_commands(self.j,self.binding,SimpleNamespace(command_id=self.row['command_id']))

    def test_child_owner_composes_with_live_supervisor_but_not_outstanding_game_command(self):
        supervisor=module.supervisor_for_host(self.host);child=replace(self.binding,host_id=fixtures.uid())
        fixture=fixtures.TacticalAdapterTests();fixture.binding=child;catalog=fixture.catalog_for()
        transport=fixtures.Transport(child);transport.poll=lambda:{}
        owner=HostTactical(self.j,fixtures.uid(),child,catalog,test_transport=transport,supervisor=supervisor)
        self.assertFalse(owner.snapshot()['field_evidence_eligible'])
        self.j.reserve_command(self.run,fixtures.uid(),'produce',{'unit':'conscript'})
        with self.assertRaisesRegex(ContractError,'prior_host_commands_require_recovery'):
            HostTactical(self.j,fixtures.uid(),child,catalog,test_transport=transport,supervisor=supervisor)


if __name__=='__main__':unittest.main()
