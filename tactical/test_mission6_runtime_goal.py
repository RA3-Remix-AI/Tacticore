"""Synthetic goal boundaries plus a recorded casualty; never game operations."""
import json
from pathlib import Path
import tempfile
import types
import unittest
import uuid
from unittest.mock import patch
import mission_combat_v6_qualification as strict
import mission_combat_v6_runtime_qualification as runtime
from test_mission_combat_v6 import fixture


def short_goal(hp=20.,after=15.):
    r=fixture()
    r['events']=[e for e in r['events'] if e['kind'] not in [20,24,22,67] or e['kind'] in [20,24] and e['frame']==156 or e['kind']==22 and e['frame']==157]
    r['native'].update(damage_count=1,damage_total=5.,shot_samples=1,rounds_consumed=1,reload_samples=0,last_ammo=2,engagement_initial_hp=hp,damage_goal=hp*.2,lethal_source_hits=int(after==0))
    for e in r['events']:
        if e['kind']==68:e.update(damage_before=hp,damage_after=hp*.2)
        if e['kind'] in [20,24]:e.update(damage_before=hp,damage_after=after,damage_reported=5.)
    for i,e in enumerate(r['events']):e['seq']=i+1
    return r


class RuntimeGoal(unittest.TestCase):
    def test_single_hit_goal_returns_without_claiming_sustained_source(self):
        report=short_goal();source=strict.qualify(report);result=runtime.qualify(report)
        self.assertEqual({k:v for k,v in source['checks'].items() if not v},{'sustained_source_effect':False})
        self.assertTrue(result['runtime_goal_verified']);self.assertFalse(result['sustained_engagement_verified'])
        self.assertFalse(result['strict_burst_trace_verified']);self.assertEqual(result['observed_reload_count'],0)
        self.assertEqual(result['source_damage_amount'],5);self.assertTrue(result['retreat_verified'])

    def test_exact_source_kill_and_return_is_completed(self):
        result=runtime.qualify(short_goal(5.,0.))
        self.assertTrue(result['runtime_goal_verified']);self.assertEqual(result['observed_lethal_hit_count'],1)
        self.assertFalse(result['sustained_engagement_verified'])

    def test_goal_and_attribution_stay_mandatory(self):
        report=short_goal();report['native']['engagement_goal_reached']=0
        self.assertFalse(runtime.qualify(report)['runtime_goal_verified'])
        report=short_goal()
        next(e for e in report['events'] if e['kind']==20)['damage_source']=9999
        self.assertFalse(runtime.qualify(report)['runtime_goal_verified'])

    def test_no_return_never_becomes_completed(self):
        report=short_goal();report['native'].update(returned_frame=0,return_verified=0,phase=4,error=32)
        self.assertFalse(runtime.qualify(report)['runtime_goal_verified'])

    def test_real_ninety_damage_casualty_stays_failed(self):
        path=Path(__file__).resolve().parent.parent/'acceptance/runs/20261025-142348-commander/continuous-paid-v6-01-combat-v6.json'
        if not path.exists():self.skipTest('Recorded V6 casualty unavailable')
        result=runtime.qualify(json.loads(path.read_text(encoding='utf-8-sig')))
        self.assertFalse(result['runtime_goal_verified']);self.assertEqual(result['status'],'not_passed')

    def test_sustained_fixture_keeps_all_existing_facts(self):
        report=fixture();source=strict.qualify(report);result=runtime.qualify(report)
        self.assertTrue(result['runtime_goal_verified']);self.assertTrue(result['strict_burst_trace_verified'])
        for key in ('source_damage_amount','qualified_hits','observed_reload_count','navigation_memory','retreat_verified','restoration_verified'):
            self.assertEqual(result[key],source[key])

    def test_actual_worker_accepts_short_goal_via_runtime_route_only(self):
        import test_client as boundary
        client=boundary.m;report=short_goal()
        with tempfile.TemporaryDirectory() as folder:
            executor=client.TacticalExecutor('unused','unused',report['preflight']['commander_id'])
            executor.session={'session_id':report['session_id'],'pid':report['preflight']['pid']}
            executor.run=Path(folder);executor.native_seq=100;executor._binding=lambda:None;executor._validate_task_dispatch=lambda row:None
            command,task=str(uuid.uuid4()),str(uuid.uuid4())
            receipt=dict(kind='attack',module='attack',purpose='main_attack',executor_directory='mission-combat-v6',command_id=command,task_id=task,object_ids=[report['preflight']['selected']['object_id']],status='queued',unit_results=[],started=False,issued_frame=0,dispatch_attempted=False,wrapper_attempted=False,visibility_proof_path='unused',target_contact_id=report['request']['target_contact_id'],mission_input=report['request']['mission'],expires_frame=4599)
            executor.ledger[command]=receipt;executor.pending.put(command)
            def audit(event):
                if event['event']=='task_feedback':executor.stopping.set()
            executor._audit=audit
            def spawn(args,**kwargs):
                value=lambda flag:args[args.index(flag)+1]
                identity=dict(command_id=value('--command-id'),task_id=value('--task-id'),seq=int(value('--seq')))
                report['request'].update(identity);report['native'].update(identity)
                report['assessment']=strict.qualify(report)
                self.assertEqual(report['assessment']['status'],'not_passed')
                Path(value('--output')).write_text(json.dumps(report),encoding='utf-8')
                return types.SimpleNamespace(poll=lambda:0,returncode=0)
            with patch.object(client.subprocess,'Popen',side_effect=spawn):executor._work()
            self.assertTrue(receipt['completed'],receipt)
            assessment=receipt['unit_results'][0]['assessment']
            self.assertTrue(assessment['runtime_goal_verified'])
            self.assertFalse(assessment['sustained_engagement_verified'])


if __name__=='__main__':unittest.main()
