"""Bounded retired-channel waiting is read-only and needs actual frame progress."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'integration'))
import rotation_trial as trial
from host_runtime.contracts import SessionBinding
from host_runtime.journal import RequestConflict


class RetiredGapTests(unittest.TestCase):
    def setUp(self):
        self.clock=SimpleNamespace(now=0)
        self.actor=SimpleNamespace(object_id=20,thing=200,update=400,owner=100,type_hash=0x19ab11af)
        self.record={};self.temp=tempfile.TemporaryDirectory();self.output=Path(self.temp.name)/'trial.json'
    def tearDown(self):self.temp.cleanup()
    def census(self,memory,player,catalog):
        frame=100+15*self.clock.now
        return dict(frame_start=frame,frame_end=frame,candidates=[dict(object_id=20,address='0xc8',
            ai_address='0x190',owner_address='0x64',type_hash='0x19ab11af')])
    def run_gap(self,census,**kwargs):
        def sleep(seconds):self.clock.now+=seconds
        with patch.object(trial.time,'monotonic',side_effect=lambda:self.clock.now),\
                patch.object(trial.time,'sleep',side_effect=sleep),patch.object(trial,'own_candidates',side_effect=census):
            trial.wait_retired_gap(object(),3,self.actor,3,self.record,self.output,**kwargs)
    def test_closed_interval_has_no_commands_and_requires_progressing_game(self):
        self.run_gap(self.census);gap=self.record['retired_channel_intervals'][0]
        self.assertEqual(gap['status'],'completed_read_only_no_control_held')
        self.assertEqual(gap['game_commands'],0);self.assertFalse(gap['native_channel_held'])
        self.assertEqual([r['frame_start'] for r in gap['samples']],[100,115,130])
    def test_missing_or_changed_actor_refuses_before_successor_attach(self):
        def missing(*args):
            value=self.census(*args)
            if self.clock.now:value['candidates']=[]
            return value
        with self.assertRaisesRegex(ValueError,'unavailable_no_successor_attach'):self.run_gap(missing)
        self.assertEqual(self.record['retired_channel_intervals'][0]['status'],'actor_unavailable_no_successor_attach')
    def test_wall_wait_without_game_progress_does_not_qualify(self):
        def paused(*args):
            value=self.census(*args);value['frame_start']=value['frame_end']=100
            return value
        with self.assertRaisesRegex(ValueError,'no_verified_game_progress'):self.run_gap(paused)

    def test_explicit_fresh_paid_policy_records_old_actor_loss_without_reusing_it(self):
        def missing(*args):
            value=self.census(*args);value['candidates']=[];return value
        self.run_gap(missing,require_previous_actor=False)
        gap=self.record['retired_channel_intervals'][0]
        self.assertFalse(gap['previous_actor_required'])
        self.assertTrue(all(not s['actor_present'] for s in gap['samples']))
        self.assertEqual(gap['status'],'completed_read_only_no_control_held')
        self.assertEqual(gap['game_commands'],0)

    def test_successor_purchase_is_journaled_once_and_does_not_reset_tactical_sequence(self):
        journal=trial.CommandJournal(Path(self.temp.name)/'journal.sqlite3');run_id=str(uuid.uuid4())
        binding=SessionBinding(1,str(uuid.uuid4()),3,str(uuid.uuid4()),1234,'2026-10-26T00:00:00+00:00',str(uuid.uuid4()),'a'*64,'b'*64)
        journal.register_run(run_id,binding.public())
        handoff=SimpleNamespace(binding=binding,journal=journal,run_id=run_id)
        command_id=str(uuid.uuid4());calls=[]
        def submit(command):calls.append(command);return dict(accepted=True)
        producer=SimpleNamespace(shared=SimpleNamespace(last_seq=1),reserve_floor=1000,submit=submit,
            status=lambda:dict(ledger=[dict(command_id=command_id,completed=True,paid_verified=True,paid=85,cost=85,created=True,object_id=21)]))
        memory=SimpleNamespace(u32=lambda address:100)
        record=dict(production_commands=[])
        try:
            trial.produce_successor_actor(producer,handoff,command_id,record,self.output,memory)
            self.assertEqual(len(calls),1);self.assertEqual(calls[0]['seq'],2)
            rows=journal.commands_for_run(run_id,operation='runtime_successor_produce')
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'completed')
            self.assertEqual(journal.native_sequence_high_water(binding.public()),0)
            with self.assertRaises(RequestConflict):trial.produce_successor_actor(producer,handoff,command_id,record,self.output,memory)
            self.assertEqual(len(calls),1)
        finally:journal.close()

    def test_unknown_successor_purchase_remains_uncertain_without_an_attach_or_retry(self):
        journal=trial.CommandJournal(Path(self.temp.name)/'unknown.sqlite3');run_id=str(uuid.uuid4())
        binding=SessionBinding(1,str(uuid.uuid4()),3,str(uuid.uuid4()),1234,'2026-10-26T00:00:00+00:00',str(uuid.uuid4()),'a'*64,'b'*64)
        journal.register_run(run_id,binding.public());handoff=SimpleNamespace(binding=binding,journal=journal,run_id=run_id)
        calls=[];producer=SimpleNamespace(shared=SimpleNamespace(last_seq=1),reserve_floor=1000,
            submit=lambda command:(calls.append(command) or dict(accepted=False,status='unknown')))
        try:
            with self.assertRaisesRegex(ValueError,'not_accepted_no_retry'):
                trial.produce_successor_actor(producer,handoff,str(uuid.uuid4()),dict(production_commands=[]),self.output,SimpleNamespace(u32=lambda _:100))
            self.assertEqual(len(calls),1)
            self.assertEqual(journal.unresolved(run_id)[0]['operation'],'runtime_successor_produce')
            self.assertEqual(journal.unresolved(run_id)[0]['status'],'uncertain')
        finally:journal.close()


if __name__=='__main__':unittest.main()
