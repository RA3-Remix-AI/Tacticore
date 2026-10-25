import copy,hashlib,json,re,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_common_qualification import fixture,q

def disposition_fixture(root):
 r=fixture();pre=r['preflight'];pre.update(pid=123,logic='0x9000',default_team='0x7000',script_team='0x7100');r['request']['token']=9;r['native_binary_sha256']='fixed-offline-dll';n=r['native'];n.update(phase=4,error=32,active=0,overflow=0,restore_mask=8191,return_verified=0);n['support'].update(returned=1)
 lease=(q.HERE/'lease.cpp').read_text();(root/'lease.cpp').write_text(lease);layout=dict(dll_sha256=r['native_binary_sha256'],timer_rva=1,shared_pointer_rva=2);(root/'inert-layout.json').write_text(json.dumps(layout))
 block=lease.split('static Hook hooks[]={',1)[1].split(';',1)[0];entries=[dict(address=a,expected=s.replace('\\x',''),actual=s.replace('\\x',''),restored=True) for a,s in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',block)]
 bind=dict(pid=123,session_id=r['session_id'],commander_id=pre['commander_id'],command_id=r['request']['command_id'],task_id=r['request']['task_id'],seq=1,token=9,owner=pre['owner'],logic=pre['logic'],native_binary_sha256=r['native_binary_sha256'])
 terminal=dict(bind,layout=layout,module_base='0x10000000',shared_pointer='0x20000000',phase=4,error=32,timer=0,active=0,restore_mask=8191,binding_verified=True,mutations=False,front_return_verified=0,support_return_verified=1,entries=entries)
 canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 d=dict(bind,object_id=42,role=0,source_session_id=r['session_id'],source_request_sha256=canonical(r['request']),source_preflight_sha256=canonical(pre),mutations=False,terminal_before=copy.deepcopy(terminal),terminal_after=copy.deepcopy(terminal),scans=[dict(logic=pre['logic'],complete=True,frame=f,end_frame=f,ids=[55,56],count=2) for f in (200,201)])
 r['terminal_readonly']=terminal;r['disposal_readonly']={'0':d};return r,d

class ReadonlyDisposal(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.r,self.d=disposition_fixture(self.root);self.patch=patch.object(q,'HERE',self.root);self.patch.start()
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def test_two_forward_complete_absence_and_actual_fixed_thirteen_entries(self):
  self.assertTrue(q.disposal_binding_verified(self.d,self.r,0));release=q.control_release(self.r);self.assertTrue(release['actors'][0]['disposed']);self.assertFalse(release['return_verified']);self.assertFalse(release['completion_claim']);self.assertFalse(release['restoration_verified']) # No compiled source grant in this offline fixture.
 def test_id_still_present_or_single_frame_is_not_disposal(self):
  for mutate in (lambda d:d['scans'][0].update(ids=[42,56]),lambda d:d['scans'][1].update(frame=200,end_frame=200),lambda d:d['scans'][0].update(end_frame=201),lambda d:d['scans'][1].update(complete=False)):
   d=copy.deepcopy(self.d);mutate(d);self.assertFalse(q.disposal_binding_verified(d,self.r,0))
 def test_no_empty_partial_duplicate_id_lists(self):
  for ids,count in [([],0),([55,55],2),([55],2),([True,56],2)]:
   d=copy.deepcopy(self.d);d['scans'][0].update(ids=ids,count=count);self.assertFalse(q.disposal_binding_verified(d,self.r,0))
 def test_wrong_actor_role_or_lease_binding(self):
  for key,value in [('object_id',43),('role',1),('pid',456),('token',10),('session_id','other'),('task_id','other'),('logic','0x9001'),('source_request_sha256','bad'),('source_preflight_sha256','bad')]:
   d=copy.deepcopy(self.d);d[key]=value;self.assertFalse(q.disposal_binding_verified(d,self.r,0),key)
 def test_no_duplicate_hooks_self_signed_bytes_or_hot_timer(self):
  for mutation in ('duplicate','fakebytes','timer','active','pointer','return'):
   d=copy.deepcopy(self.d);t=d['terminal_after']
   if mutation=='duplicate':t['entries']=[copy.deepcopy(t['entries'][0]) for _ in range(13)]
   if mutation=='fakebytes':t['entries'][0].update(expected='90',actual='90')
   if mutation=='timer':t['timer']=1
   if mutation=='active':t['active']=1
   if mutation=='pointer':t['shared_pointer']='0x20000001'
   if mutation=='return':t['front_return_verified']=1
   self.assertFalse(q.disposal_binding_verified(d,self.r,0),mutation)
 def test_source_native_layout_mismatch_is_rejected(self):
  self.d['terminal_before']['layout']['dll_sha256']='other';self.assertFalse(q.disposal_binding_verified(self.d,self.r,0))
if __name__=='__main__':unittest.main()
