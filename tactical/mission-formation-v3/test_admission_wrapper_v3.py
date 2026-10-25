"""Pure boundary tests. Synthetic records are never runtime source evidence."""
import copy,hashlib,importlib.util,json,types,unittest,tempfile,uuid
from pathlib import Path
from unittest.mock import patch
H=Path(__file__).resolve().parent;P=H.parent;B=P.parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
w=load('new_admission_wrapper',H/'lease_admission_v3.py');q=load('new_admission_qualifier',H/'formation_mission_qualification_v3.py');a=load('actual_admission',P/'mission_actor_admission_v2.py');planner=load('actual_roles',H/'role_route_planner.py')
class Admission(unittest.TestCase):
 def fixture(self):
  d=json.loads((B/'acceptance/runs/20261025-131138-commander/admission-early01.json').read_text(encoding='utf-8'));by={x['object_id']:x['admission'] for x in d['rows']};f=copy.deepcopy(by[771]);s=copy.deepcopy(by[773]);f.update(protocol=a.PROTOCOL,**a.fingerprints());s.update(protocol=a.PROTOCOL,**a.fingerprints());fg=f['grounded_status'];sg=s['grounded_status'];x,y,z=fg['xyz'];vx,vy=x-sg['xyz'][0],y-sg['xyz'][1];scale=100/(vx*vx+vy*vy)**.5;dx,dy=vx*scale,vy*scale;route=[dict(xyz=[x+dx,y+dy,z]),dict(xyz=[x+2*dx,y+2*dy,z])];target=dict(object_id=987,address=0x1234,owner=0x2345,type_hash='0xc45aaeab',xyz=route[-1]['xyz'],observed_frame=fg['frame'])
  pre=dict(owner=fg['owner'],logic='0x1000',selected=dict(object_id=fg['object_id'],address=fg['address'],type_hash=fg['type_hash'],xyz=fg['xyz'],hp=fg['hp'],ai_address=f['state_snapshot']['update']),support=dict(object_id=sg['object_id'],address=sg['address'],type_hash=sg['type_hash'],xyz=sg['xyz'],hp=sg['hp'],ai_address=s['state_snapshot']['update']))
  last=dict(protocol='mfm3_last_admission_v3',frame=fg['frame'],validated_frame=fg['frame'],front=f,support=s,target=target,route_geometry_verified=True,mutations=False)
  return dict(last_admission=last,preflight=pre,request=dict(route=route,target_object_id=987,target=target['xyz']),private_target=target,native=dict(issued_frame=fg['frame']+2))
 def test_actual_normal_admissions_geometry_positive(self):self.assertTrue(q.last_admission_verified(self.fixture()))
 def test_garrison_state_cannot_copy_true_claim(self):
  r=self.fixture();r['last_admission']['front']['state_snapshot']['state_id']=54;self.assertFalse(q.last_admission_verified(r))
 def test_crossed_support_goal_rejected(self):
  r=self.fixture();r['request']['route'][0]['xyz']=r['last_admission']['support']['grounded_status']['xyz'];self.assertFalse(q.last_admission_verified(r))
 def test_old_frame_and_target_identity_rejected(self):
  for mode in ('old_frame','target','clock'):
   r=self.fixture()
   if mode=='old_frame':r['native']['issued_frame']+=61
   elif mode=='target':r['private_target']=dict(r['private_target'],object_id=988)
   else:r['last_admission']['validated_frame']+=5
   self.assertFalse(q.last_admission_verified(r),mode)
 def test_wrapper_same_checks_are_before_native_launch(self):
  r=self.fixture();records={int(x['grounded_status']['address'],0):x for x in (r['last_admission']['front'],r['last_admission']['support'])};frame=r['last_admission']['frame']
  memory=types.SimpleNamespace(u32=lambda x:frame if x==0x1050 else 0)
  admission=types.SimpleNamespace(actor_admission=lambda m,t:records[t],verify_evidence=a.verify_evidence)
  reader=types.SimpleNamespace(private_targets={'contact_fixture':r['private_target']},collect=lambda t:None)
  def module(name,path):return admission if name=='formation_last_actor_admission' else planner
  with patch.object(w,'module',module):
   late=w.last_admission(memory,r['preflight'],r['preflight']['selected'],r['preflight']['support'],r['request']['route'],reader,'contact_fixture',r['private_target']);self.assertTrue(late['route_geometry_verified'])
   reader.private_targets={}
   with self.assertRaisesRegex(ValueError,'last_target_not_currently_visible'):w.last_admission(memory,r['preflight'],r['preflight']['selected'],r['preflight']['support'],r['request']['route'],reader,'contact_fixture',r['private_target'])
  text=(H/'lease_admission_v3.py').read_text(encoding='utf-8');self.assertLess(text.index('late=last_admission('),text.index('   NATIVE_LAUNCH_INTENT=True;'));self.assertLess(text.index('   NATIVE_LAUNCH_INTENT=True;'),text.index('host=subprocess.Popen'))
 def test_frozen_old_files_still_preserved(self):
  self.assertEqual(hashlib.sha256((H/'lease.py').read_bytes()).hexdigest(),'fd52c92762214821594be8a2ee32a072facfa2a1f5d68d8c750e9e00b8288a2f')
  old=json.loads((B/'acceptance/runs/20261025-123933-commander/coord3-mission06.json').read_text(encoding='utf-8'));self.assertFalse(q.source_pins(old));self.assertFalse(q.last_admission_verified(old))
 def test_new_pre_native_helper_binds_revision_and_command(self):
  helper=load('new_pre_native',P/'pre_dispatch_formation_v3_admission_v3_contract.py');session_file=B/'acceptance/runs/20261025-131138-commander/session.json';session=json.loads(session_file.read_text(encoding='utf-8-sig'))
  with tempfile.TemporaryDirectory() as folder:
   args=types.SimpleNamespace(output=Path(folder)/'rejected.json',session=session_file,command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=7,front_id=11,support_id=12,contact_id='contact_fixture')
   r=helper.rejection(args,H,ValueError('last_actor_admission_rejected'))
   kw=dict(child_exit_code=64,session=session,commander_id=session['scenario']['commander_id'],command_id=args.command_id,task_id=args.task_id,seq=7,object_ids=[11,12],directory=H.name,target_contact_id=args.contact_id)
   self.assertTrue(helper.verify_no_dispatch(r,**kw)['no_dispatch_verified']);r['wrapper_filename']='lease.py';self.assertFalse(helper.verify_no_dispatch(r,**kw)['no_dispatch_verified'])
 def test_exact_attack_state_10_requires_its_vtable(self):
  r=self.fixture()
  for actor in (r['last_admission']['front'],r['last_admission']['support']):actor['state_snapshot'].update(state_id=10,state_vtable='0xc548c0')
  self.assertTrue(q.last_admission_verified(r))
  r['last_admission']['support']['state_snapshot']['state_vtable']='0xc548c4';self.assertFalse(q.last_admission_verified(r))
 def test_unsupported_7_54_77_and_locked_attack_rejected(self):
  for state in (7,54,77):
   r=self.fixture();r['last_admission']['front']['state_snapshot']['state_id']=state;self.assertFalse(q.last_admission_verified(r))
  r=self.fixture();r['last_admission']['front']['state_snapshot'].update(state_id=10,state_vtable='0xc548c0',sm_flags=1);self.assertFalse(q.last_admission_verified(r))
 def test_actual_entry_stop_cannot_keep_attack_state_or_copy_counter(self):
  events=[]
  for role in (0,1):
   base=role*10
   events += [dict(role=role,seq=base+1,kind=1,tag=1,frame=10,state_id=10),dict(role=role,seq=base+2,kind=33,frame=10,arg=1,caller=0x787791)]
   events += [dict(role=role,seq=base+i-8,kind=3,frame=i,x=0,y=0,z=210,path=0,sm_flags=0,source=1,state_id=16) for i in (11,12,13)]
   events += [dict(role=role,seq=base+6,kind=58,frame=13,x=0,y=0,z=210,mission_stage=1,route_index=0),dict(role=role,seq=base+7,kind=50,tag=6,frame=13)]
  r=dict(events=sorted(events,key=lambda e:e['seq']));self.assertTrue(q.entry_state_audit(r)['verified']);self.assertTrue(q.entry_state_audit(r)['attack_state_admission_observed'])
  for role in (0,1):
   broken=copy.deepcopy(r);next(e for e in reversed(broken['events']) if e.get('role')==role and e['kind']==3)['state_id']=10;self.assertFalse(q.entry_state_audit(broken)['verified'])
if __name__=='__main__':unittest.main()
