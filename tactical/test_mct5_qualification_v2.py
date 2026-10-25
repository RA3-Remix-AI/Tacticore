"""Independent qualification correction; no physical backend/source edits."""
import copy,json,tempfile,types,unittest,uuid
from pathlib import Path
from unittest.mock import MagicMock,patch
from test_mission_combat_v4 import fixture as previous
import mission_combat_v5_qualification as old
import mission_combat_v5_qualification_v2 as q
HERE=Path(__file__).resolve().parent

def fixture():
 r=previous();r.update(json.loads((HERE/'mission-combat-v5/revision.json').read_text()));first=copy.deepcopy(r['events'][0]);first.update(kind=64,mission_stage=0);rows=[first]
 for e in r['events']:
  if e.get('kind')==50 and e.get('arg')==3:
   sample=copy.deepcopy(e);sample.update(kind=3,mission_stage=2);rows.append(sample)
  rows.append(e)
 seen=0
 for i,e in enumerate(rows):
  if e['kind'] in [64,3] and e.get('current_visible') and e.get('mission_stage')<=6:seen=e['frame']
  e.update(seq=i+1,target_id=r['request']['target_object_id'],target_last_seen_frame=seen,memory_wait_started=0,remembered_target_xyz=[600.,0.,210.])
 r['events']=rows;return r

def renumber(r):
 for i,e in enumerate(r['events']):e['seq']=i+1

class Qualification2Tests(unittest.TestCase):
 def test_actual_client_worker_uses_v2_not_old_wrapper_assessment(self):
  import test_client as boundary
  m=boundary.m;raw=fixture();oid=raw['preflight']['selected']['object_id'];command=str(uuid.uuid4());task=str(uuid.uuid4());schema=dict(kind='attack',restore_mask=16383,mission_protocol='continuous_tactical_v1',success='continuous_ak_combat_mission_verified');old_assessment=MagicMock(return_value=dict(status='not_passed'))
  runtime=types.SimpleNamespace(assessment=old_assessment)
  with tempfile.TemporaryDirectory() as folder:
   e=m.TacticalExecutor('unused','unused',raw['preflight']['commander_id']);e.session=dict(session_id=raw['session_id'],pid=raw['preflight']['pid']);e.run=Path(folder);e.native_seq=0;e._validate_task_dispatch=MagicMock();e._binding=MagicMock();e._record_pre_native_rejection=MagicMock(return_value=False)
   r=dict(kind='attack',command_id=command,task_id=task,seq=1,session_id=e.session['session_id'],commander_id=e.commander_id,player_id=3,status='queued',executor_directory='mission-combat-v5',object_ids=[oid],mission_input=raw['request']['mission'],target_contact_id=raw['request']['target_contact_id'],visibility_proof_path='unused-proof',expires_frame=raw['request']['expires_frame'],unit_results=[],formation_versions={},started=False,issued_frame=0,dispatch_attempted=False,wrapper_attempted=False,completed=False)
   e.ledger[command]=r;e.pending.put(command);e._audit=lambda event:e.stopping.set() if event.get('event')=='task_feedback' else None
   def child(args,**kwargs):
    out=Path(args[args.index('--output')+1]);report=copy.deepcopy(raw)
    for k,arg in [('command_id','--command-id'),('task_id','--task-id'),('seq','--seq')]:
     value=args[args.index(arg)+1];value=int(value) if k=='seq' else value;report['request'][k]=report['native'][k]=value
    report['assessment']={'status':'not_passed','diagnostic':'original_wrapper_kept'};out.write_text(json.dumps(report),encoding='utf-8');return types.SimpleNamespace(poll=lambda:0,returncode=0)
   with patch.object(m,'runtime_backend',return_value=(schema,runtime)),patch.object(m.subprocess,'Popen',side_effect=child):e._work()
   self.assertTrue(r['completed'],r.get('reason_code'));self.assertTrue(r['started']);self.assertTrue(r['restoration_verified']);self.assertEqual(r['unit_results'][0]['assessment']['qualification_revision'],'lease_scoped_bridge_move_v2');old_assessment.assert_not_called()
 def test_baseline_source_damage_and_retreat_still_pass(self):
  r=fixture();self.assertEqual(q.qualify(r)['status'],'continuous_ak_combat_mission_verified')
 def test_same_frame_predetach_native_move_and_postreturn_pair_ignored(self):
  r=fixture();e=copy.deepcopy(r['events'][0]);e.update(kind=52,tag=0,current_visible=0,target_last_seen_frame=0,mission_stage=0);r['events'].insert(0,e)
  for kind in [52,53]:
   e=copy.deepcopy(r['events'][-1]);e.update(kind=kind,tag=0,mission_stage=10);r['events'].append(e)
  renumber(r);self.assertFalse(old.qualify(r)['checks']['normal_move_chains']);a=q.qualify(r);self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks'])
 def test_real_inlease_foreign_move_rejected_even_if_counter_forged_zero(self):
  for kind in [52,54]:
   r=fixture();at=next(i for i,e in enumerate(r['events']) if e['kind']==54 and e['tag']==6);e=copy.deepcopy(r['events'][at]);e.update(kind=kind,tag=0);r['events'].insert(at,e);renumber(r);a=q.qualify(r);self.assertFalse(a['checks']['no_native_override']);self.assertEqual(a['checks']['native_counter_lease_scope'],kind==54);self.assertEqual(a['status'],'not_passed')
 def test_actual_inlease_counter_is_not_ignored(self):
  r=fixture();at=next(i for i,e in enumerate(r['events']) if e['kind']==52 and e['tag']==6);e=copy.deepcopy(r['events'][at]);e['tag']=0;r['events'].insert(at,e);renumber(r);r['native']['native_move']=1;a=q.qualify(r);self.assertFalse(a['checks']['no_native_override']);self.assertTrue(a['checks']['native_counter_lease_scope']);self.assertEqual(a['status'],'not_passed')
 def test_incomplete_or_wrong_bridge_chain_still_rejected(self):
  for mutation in ['missing','wrong_tag']:
   r=fixture();at=next(i for i,e in enumerate(r['events']) if e['kind']==53 and e['tag']==6)
   if mutation=='missing':r['events'].pop(at)
   else:r['events'][at]['tag']=0
   renumber(r);a=q.qualify(r);self.assertFalse(a['checks']['normal_move_chains']);self.assertEqual(a['status'],'not_passed')
 def test_real_no_hit_failure_is_not_reclassified(self):
  path=HERE.parent/'acceptance/runs/20261025-114145-commander/main-mct5-01.json';r=json.loads(path.read_text(encoding='utf-8'));a=q.qualify(r);self.assertTrue(a['checks']['normal_move_chains']);self.assertFalse(a['effect_verified']);self.assertEqual(a['status'],'not_passed');self.assertTrue(a['restoration_verified'])

if __name__=='__main__':unittest.main()
