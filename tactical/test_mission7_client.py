"""Trusted worker integration with synthetic evidence; no game operations."""
import json
from pathlib import Path
import tempfile
import types
import unittest
import uuid
from unittest.mock import patch
import test_client as boundary
from test_mission_combat_v7 import fixture, goal_and_safety

m=boundary.m

class Mission7Client(unittest.TestCase):
    def run_worker(self, report):
        with tempfile.TemporaryDirectory() as folder:
            e=m.TacticalExecutor('unused','unused',report['preflight']['commander_id'])
            e.session={'session_id':report['session_id'],'pid':report['preflight']['pid']}
            e.run=Path(folder);e.native_seq=100;e._binding=lambda:None;e._validate_task_dispatch=lambda row:None
            command,task=str(uuid.uuid4()),str(uuid.uuid4())
            r=dict(kind='attack',module='attack',purpose='main_attack',executor_directory='mission-combat-v7',command_id=command,task_id=task,object_ids=[report['preflight']['selected']['object_id']],status='queued',unit_results=[],started=False,issued_frame=0,dispatch_attempted=False,wrapper_attempted=False,visibility_proof_path='unused',target_contact_id=report['request']['target_contact_id'],mission_input=report['request']['mission'],expires_frame=4599)
            e.ledger[command]=r;e.pending.put(command)
            def audit(event):
                if event['event']=='task_feedback':e.stopping.set()
            e._audit=audit
            def spawn(args,**kwargs):
                value=lambda flag:args[args.index(flag)+1]
                self.assertEqual(Path(args[1]).parent.name,'mission-combat-v7')
                identity=dict(command_id=value('--command-id'),task_id=value('--task-id'),seq=int(value('--seq')))
                report['request'].update(identity);report['native'].update(identity)
                Path(value('--output')).write_text(json.dumps(report),encoding='utf-8')
                return types.SimpleNamespace(poll=lambda:0,returncode=0)
            with patch.object(m.subprocess,'Popen',side_effect=spawn):e._work()
            return r

    def test_worker_requires_actual_brief_effect_and_return(self):
        r=self.run_worker(fixture())
        self.assertTrue(r['completed'],r)
        self.assertTrue(r['unit_results'][0]['assessment']['runtime_goal_verified'])
        self.assertEqual(r['unit_results'][0]['assessment']['source_damage_amount'],30.)

    def test_safety_goal_uses_runtime_without_claiming_source_qualification(self):
        r=self.run_worker(goal_and_safety())
        self.assertTrue(r['completed'],r)
        a=r['unit_results'][0]['assessment']
        self.assertTrue(a['runtime_goal_verified']);self.assertFalse(a['strict_burst_trace_verified'])
        self.assertEqual(a['reason_code'],'low_hp')

    def test_missing_actual_goal_remains_failed_after_safe_return(self):
        report=fixture();report['native']['engagement_goal_reached']=0
        r=self.run_worker(report)
        self.assertFalse(r['completed']);self.assertTrue(r['restoration_verified'])

    def test_manifest_fixed_short_profile_and_trusted_reader(self):
        e=boundary.ModelBoundary().executor()
        e.capability_grants={('attack','main_attack'):dict(executor_directory='mission-combat-v7',stop_schema=dict(actor_roles=['infantry'],mission_protocol='continuous_tactical_v1'))}
        a=e.manifest()['attack']
        self.assertEqual((a['engage_frames'],a['damage_goal_cap'],a['retreat_hp_fraction']),(60,30.,.8))
        self.assertEqual(m.combat_qualifier_path('mission-combat-v7',m.trusted_executor('mission-combat-v7')).name,'mission_combat_v7_runtime_qualification.py')
        with self.assertRaises(ValueError):m.combat_qualifier_path('mission-combat-v7',{'runtime_qualifier_filename':'../arbitrary.py'})

if __name__=='__main__':unittest.main()
