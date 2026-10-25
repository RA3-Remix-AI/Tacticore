"""Actual saved late poses replayed purely; no process, SDK or native launch."""
import copy,ctypes as c,hashlib,importlib.util,json,types,unittest,uuid,tempfile
from pathlib import Path
from unittest.mock import patch
H=Path(__file__).resolve().parent;P=H.parent;B=P.parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
w=load('v4_wrapper_test',H/'lease_admission_v4.py');q=load('v4_q_test',H/'formation_mission_qualification_v4.py');h=load('v4_rebase_test',H/'route_rebase_v4.py');ad=load('v4_actual_admission',P/'mission_actor_admission_v2.py')
RAW=B/'acceptance/runs/20261025-142348-commander/coord-admission-v3-01.json'
def fixture():
 r=json.loads(RAW.read_text(encoding='utf-8'));points=copy.deepcopy(r['request']['route']);records=r['last_admission_attempt']['records'];f,s=[x['grounded_status'] for x in records];frame=f['frame'];rb=h.rebase(points,f['xyz'],s['xyz'],frame);session=dict(session_id=r['session_id'],pid=r['preflight']['pid']);rb.update(source_validation=h.source_records(points,session,frame,r['preflight']['owner']),source_validation_frame=frame,occupancy=dict(frame_start=frame,frame_end=frame,owned_positions=[dict(object_id=x['object_id'],xyz=x['grounded_status']['xyz']) for x in records]));target=copy.deepcopy(r['private_target']);target['observed_frame']=frame
 r.update(route_rebase=rb,last_admission=dict(protocol='mfm3_last_admission_v4',frame=frame,validated_frame=frame,front=records[0],support=records[1],target=target,route_rebase=copy.deepcopy(rb),route_geometry_verified=True,mutations=False));r['request'].update(original_input_route=points,route=rb['route']);r['private_target']=target;r['preflight'].update(frame=frame)
 for key,record in [('selected',records[0]),('support',records[1])]:r['preflight'][key].update(xyz=record['grounded_status']['xyz'],hp=record['grounded_status']['hp'])
 r['native']=dict(issued_frame=frame+1,route_count=len(rb['route']),route=[x['xyz'] for x in rb['route']]);return r
class V4PrefixTests(unittest.TestCase):
 def test_exact_original_late_pose_only_prefix_one_passes(self):
  r=fixture();rb=r['route_rebase'];self.assertEqual(rb['pruned_count'],1);self.assertEqual(len(rb['route']),13);self.assertAlmostEqual(rb['pruned'][0]['front_distance'],21.24409216387518);self.assertAlmostEqual(h.roles.xy(rb['front_xyz'],rb['route'][0]['xyz']),137.84697723610591);self.assertTrue(q.route_rebase_verified(r));self.assertTrue(q.last_admission_verified(r))
 def test_cannot_overprune_nonprefix_or_invent_a_point(self):
  for mode in ['overprune','middle_delete','newpoint','native_old_route','scalar_only']:
   r=fixture()
   if mode=='overprune':r['route_rebase']['pruned_count']=2;r['route_rebase']['route']=r['request']['original_input_route'][2:]
   elif mode=='middle_delete':r['route_rebase']['route'].pop(1)
   elif mode=='newpoint':r['route_rebase']['route'][0]['xyz'][0]+=1
   elif mode=='native_old_route':r['native']['route']=[x['xyz'] for x in r['request']['original_input_route']]
   else:r['route_rebase']['pruned'][0]['front_distance']=59
   r['last_admission']['route_rebase']=copy.deepcopy(r['route_rebase']);self.assertFalse(q.route_rebase_verified(r),mode)
 def test_every_original_source_even_pruned_point_must_reverify(self):
  for mode in ['wronghash','unknownposition','foreignowner']:
   r=fixture()
   if mode=='wronghash':r['route_rebase']['original_route'][0]['own_source_sha256']='0'*64
   elif mode=='unknownposition':r['route_rebase']['original_route'][0]['xyz'][0]+=10
   else:r['preflight']['owner']='0x1234'
   r['request']['original_input_route']=copy.deepcopy(r['route_rebase']['original_route']);r['last_admission']['route_rebase']=copy.deepcopy(r['route_rebase']);self.assertFalse(q.route_rebase_verified(r),mode)
 def test_final_pair_and_full_reverse_geometry_are_mandatory(self):
  r=fixture();front=r['route_rebase']['front_xyz'];support=r['route_rebase']['support_xyz'];original=r['request']['original_input_route']
  with self.assertRaises(ValueError):h.rebase(original[2:],front,support,r['last_admission']['frame'])
  with self.assertRaises(ValueError):h.rebase(original,front,front,r['last_admission']['frame'])
  with self.assertRaises(ValueError):h.rebase(original[:2],front,support,r['last_admission']['frame'])
 def test_occupancy_including_pruned_prefix_and_frame_are_checked(self):
  for mode in ['occupied','stale','omitactors']:
   r=fixture();rb=r['route_rebase']
   if mode=='occupied':rb['occupancy']['owned_positions'].append(dict(object_id=999999,xyz=rb['original_route'][0]['xyz']))
   elif mode=='stale':rb['occupancy']['frame_end']-=5;rb['occupancy']['frame_start']-=5
   else:rb['occupancy']['owned_positions']=[]
   r['last_admission']['route_rebase']=copy.deepcopy(rb);self.assertFalse(q.route_rebase_verified(r),mode)
 def test_wrapper_rechecks_twice_and_returns_exact_native_ready_suffix(self):
  r=fixture();records=[r['last_admission'][x] for x in ['front','support']];by={int(x['address'],0):x for x in records};frame=r['last_admission']['frame'];memory=types.SimpleNamespace(u32=lambda addr:frame if addr==int(r['preflight']['logic'],0)+0x50 else 0);reader=types.SimpleNamespace(private_targets={'contact':r['private_target']},collect=lambda _:None);calls=[]
  admission=types.SimpleNamespace(actor_admission=lambda m,t:(calls.append(t) or copy.deepcopy(by[t])),verify_evidence=ad.verify_evidence)
  def module(name,path):return admission if name=='formation_last_actor_admission' else h
  owned=[dict(object_id=x['object_id'],xyz=x['grounded_status']['xyz']) for x in records]
  with patch.object(w,'module',module),patch.object(w.b,'own_candidates',return_value=dict(candidates=owned)):
   late=w.last_admission(memory,r['preflight'],r['preflight']['selected'],r['preflight']['support'],r['request']['original_input_route'],reader,'contact',r['private_target'],dict(session_id=r['session_id'],pid=r['preflight']['pid']))
  self.assertEqual(len(calls),4);self.assertEqual(late['route_rebase']['route'],r['request']['route']);self.assertEqual(late['route_rebase']['pruned_count'],1)
 def test_real_ctypes_route_readback_uses_native_array_and_count(self):
  r=fixture();shared=w.Tactical();shared.route_count=13
  for i,node in enumerate(r['request']['route']):shared.route[i][:]=node['xyz']
  captured={'request':{'task_id':str(uuid.uuid4())}};w.capture(captured,shared);self.assertEqual(captured['native']['route_count'],13);self.assertEqual(captured['native']['route'],[list(x) for x in shared.route[:13]])
 def test_old_native_and_all_v3_hashes_are_untouched(self):
  manifest=json.loads((H/'admission-v3-revision.json').read_text(encoding='utf-8'))
  for rel,digest in manifest['hashes'].items():self.assertEqual(hashlib.sha256((B.parent/rel).read_bytes()).hexdigest(),digest,rel)
 def test_initial_source_validation_does_not_reject_expired_dynamic_first_leg(self):
  r=fixture();pre=r['preflight'];front=pre['selected'];support=pre['support'];session=dict(session_id=r['session_id'],pid=pre['pid']);plan=dict(schema_version=1,session_id=session['session_id'],player_id=3,front_id=front['object_id'],support_id=support['object_id'],route=r['request']['original_input_route'])
  self.assertLess(h.roles.xy(front['xyz'],plan['route'][0]['xyz']),30)
  with patch.object(w.b,'own_candidates',return_value=dict(candidates=[])):points=w.route_points(plan,pre,session,None,front,support)
  self.assertEqual(len(points),14);self.assertEqual(h.rebase(points,front['xyz'],support['xyz'],pre['frame'])['pruned_count'],1)
 def test_pre_native_v4_proof_rejects_v3_filename(self):
  helper=load('v4_pre',P/'pre_dispatch_formation_v3_admission_v4_contract.py');session_file=B/'acceptance/runs/20261025-131138-commander/session.json';session=json.loads(session_file.read_text(encoding='utf-8-sig'))
  with tempfile.TemporaryDirectory() as folder:
   args=types.SimpleNamespace(output=Path(folder)/'reject.json',session=session_file,command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=7,front_id=11,support_id=12,contact_id='contact');r=helper.rejection(args,H,ValueError('rebase_suffix_role_geometry'));kw=dict(child_exit_code=64,session=session,commander_id=session['scenario']['commander_id'],command_id=args.command_id,task_id=args.task_id,seq=7,object_ids=[11,12],directory=H.name,target_contact_id='contact');self.assertTrue(helper.verify_no_dispatch(r,**kw)['no_dispatch_verified']);r['wrapper_filename']='lease_admission_v3.py';self.assertFalse(helper.verify_no_dispatch(r,**kw)['no_dispatch_verified'])
if __name__=='__main__':unittest.main()
