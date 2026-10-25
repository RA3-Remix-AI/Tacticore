"""Lease scope excludes legal pre/post AI, preserves real in-lease rejection."""
import copy,ctypes as c,importlib.util,json,subprocess,unittest
from pathlib import Path
from test_mission_combat_v3 import fixture as v3_fixture
import mission_combat_v4_qualification as q
HERE=Path(__file__).resolve().parent;D=HERE/'mission-combat-v4'
def fixture():
 r=v3_fixture();r.update(json.loads((D/'revision.json').read_text()));r['native'].update(native_move=0,native_attack=0,native_add=0,native_remove=0);return r
class MissionCombat4Tests(unittest.TestCase):
 def test_compiled_layout_unchanged(self):
  sp=importlib.util.spec_from_file_location('mct4_layout',D/'lease.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(event=c.sizeof(m.Event),tactical=c.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0))
 def test_direct_source_with_legal_postreturn_ai(self):
  a=q.qualify(fixture());self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks']);self.assertFalse(a['sustained_engagement_verified']);self.assertFalse(a['economic_disruption_verified'])
 def test_same_frame_pre_detach_move_not_an_override(self):
  r=fixture();e=copy.deepcopy(r['events'][0]);e.update(kind=10,tag=0,frame=100,tick=6000);r['events'].insert(0,e)
  for i,x in enumerate(r['events']):x['seq']=i+1
  a=q.qualify(r);self.assertTrue(a['checks']['no_native_override']);self.assertTrue(a['checks']['native_counter_lease_scope']);self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks'])
 def test_all_five_real_inlease_hook_entries_still_rejected(self):
  for kind,key in [(10,'native_move'),(52,'native_move'),(12,'native_attack'),(16,'native_add'),(18,'native_remove')]:
   r=fixture();e=copy.deepcopy(next(x for x in r['events'] if x['kind']==3));e.update(kind=kind,tag=0,frame=110,tick=6600);at=next(i for i,x in enumerate(r['events']) if x['frame']>=110);r['events'].insert(at,e);r['native'][key]=1
   for i,x in enumerate(r['events']):x['seq']=i+1
   a=q.qualify(r);self.assertFalse(a['checks']['no_native_override'],kind);self.assertTrue(a['checks']['native_counter_lease_scope'],kind)
 def test_forged_zero_counter_does_not_hide_foreign_move(self):
  r=fixture();e=copy.deepcopy(r['events'][0]);e.update(kind=52,tag=0,frame=110,tick=6600);r['events'].insert(20,e)
  for i,x in enumerate(r['events']):x['seq']=i+1
  self.assertFalse(q.qualify(r)['checks']['native_counter_lease_scope'])
 def test_native_diff_is_only_scope_guard_and_new_revision_identity(self):
  new=(D/'lease.cpp').read_text();old=(HERE/'mission-combat-v3/lease.cpp').read_text();self.assertEqual((D/'mission_tick.inc').read_bytes(),(HERE/'mission-combat-v3/mission_tick.inc').read_bytes());self.assertEqual(new.count('if(!tag&&actor_lease_active())'),5);self.assertIn('p->issued_frame>0&&p->detach_calls>0&&p->returned_frame==0',new)
if __name__=='__main__':unittest.main()
