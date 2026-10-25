"""Independent raw MFM7 departure counterexamples; never SDK or field evidence."""
import copy,importlib.util,unittest
from pathlib import Path
from test_complete_qualification import full_fixture,q
spec=importlib.util.spec_from_file_location('mfm7_departure_tests',Path(__file__).with_name('retreat_departure.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def event(r,k):return next(e for e in r['events'] if e['kind']==k and (k!=81 or e['mission_stage']==3))
def abort_fixture(reason):
 r=full_fixture();start=event(r,98);r['events']=[e for e in r['events'] if e['seq']<=start['seq']];frame=start['frame']+(31 if reason==2 else 1);source=start['breadcrumb'];front=next(e for e in r['events'] if e['kind']==80 and e['role']==0 and e['mission_stage']==3)
 def add(e,**fields):
  row=copy.deepcopy(e);row.update(seq=len(r['events'])+1,frame=frame,tick=frame*60,**fields);r['events'].append(row);return row
 a=add(front,kind=3,x=501. if reason==3 else front['x']);b=add(start,kind=3)
 gap=m.dist(m.xyz(a),m.xyz(b));end=add(start,kind=99,arg=reason,actual_gap=gap);add(start,kind=53);add(start,kind=5)
 return r

class Departure(unittest.TestCase):
 def test_complete_raw_window_preserves_nonzero_origin_index(self):
  r=full_fixture();a=m.audit(r);self.assertTrue(a['verified'],a);self.assertTrue(a['success_verified']);self.assertGreater(a['source_index'],0);self.assertGreater(a['source_published_seq'],0);self.assertFalse(a['field_verified'])
 def test_timeout_and_hard_gap_abort_are_recomputed(self):
  for reason in (2,3):
   r=abort_fixture(reason);a=m.audit(r);self.assertTrue(a['verified'],a);self.assertFalse(a['success_verified']);self.assertEqual(q.qualify(r)['status'],'not_passed')
 def test_unclosed_repeated_or_missing_window(self):
  for kind in (98,99):
   r=full_fixture();r['events'].remove(event(r,kind));self.assertFalse(m.audit(r)['verified'])
   r=full_fixture();r['events'].append(copy.deepcopy(event(r,kind)));self.assertFalse(m.audit(r)['verified'])
 def test_frozen_source_echo_full_fields_and_original_index(self):
  for kind in (98,99):
   for key,value in [('published_seq',0),('index',0),('frame',196),('xyz',[0.,0.,210.]),('thing',4),('holder',1),('status_words',[1]*7),('path_distance',25.)]:
    r=full_fixture();event(r,kind)['breadcrumb'][key]=value;self.assertFalse(m.audit(r)['verified'],(kind,key))
 def test_startframe_initial_gap_deadline_role_and_reason_are_fixed(self):
  for kind in (98,99):
   for key,value in [('argument_path',196),('argument_limit',201.),('actual_gap',0.),('mission_deadline_frame',4601),('leader_role',0),('follower_role',1),('role',0),('follow_active',1),('motion_state',3),('mission_stage',1)]:
    r=full_fixture();event(r,kind)[key]=value;self.assertFalse(m.audit(r)['verified'],(kind,key))
  for reason in (0,2,3,4):
   r=full_fixture();event(r,99)['arg']=reason;self.assertFalse(m.audit(r)['verified'],reason)
 def test_no_source1_stop_three_or_positive_ground_no_open(self):
  for role in (0,1):
   for field,value in [('path',1),('source',0),('sm_flags',1),('state_id',1),('x',999.)]:
    r=full_fixture();next(e for e in r['events'] if e['kind']==3 and e['role']==role and e['frame']==193)[field]=value;self.assertFalse(m.audit(r)['verified'],(role,field))
   r=full_fixture();next(e for e in r['events'] if e['kind']==80 and e['role']==role and e['mission_stage']==3)['breadcrumb']['height_flags']=0;self.assertFalse(m.audit(r)['verified'])
 def test_actual_path_and_euclidean_clear_both_required(self):
  r=full_fixture()
  for e in r['events']:
   if e['kind']==3 and e['role']==1 and e['frame']==200:e['x']=130.
  self.assertFalse(m.audit(r)['verified'])
  # A path counter and 25m total travel around the origin do not clear it.
  r=full_fixture();end=event(r,99);base=next(e for e in r['events'] if e['kind']==3 and e['role']==1 and e['frame']==200)
  for frame,pos in [(196,155.),(197,140.)]:
   for role in (0,1):
    row=copy.deepcopy(base);row.update(seq=end['seq']-.9+(frame-196)*.2+role*.05,role=role,frame=frame,tick=frame*60,x=340. if role==0 else pos);r['events'].insert(r['events'].index(end),row)
  base['x']=140.;end['x']=140.;end['actual_gap']=200.;self.assertFalse(m.audit(r)['verified'])
 def test_no_81_or_240_regroup_before_close_and_no_delayed_follow(self):
  for kind in (81,82,89,96,98):
   r=full_fixture();end=event(r,99);row=copy.deepcopy(end);row.update(kind=kind,seq=end['seq']-.1);r['events'].insert(r['events'].index(end),row);self.assertFalse(m.audit(r)['verified'],kind)
  for field,value in [('frame',201),('breadcrumb',{}),('follow_crumb_index',0)]:
   r=full_fixture();event(r,81)[field]=value;self.assertFalse(m.audit(r)['verified'],field)
 def test_cannot_delay_close_past_first_ready_or_reset_30f_window(self):
  r=full_fixture();end=event(r,99);end['frame']=226;self.assertFalse(m.audit(r)['verified'])
  r=abort_fixture(2);event(r,99)['argument_path']=200;self.assertFalse(m.audit(r)['verified'])
 def test_missing_pair_header_mutation_and_failure_reopen_rejected(self):
  r=full_fixture();r['events']=[e for e in r['events'] if not(e['kind']==3 and e['frame']==200 and e['role']==0)];self.assertFalse(m.audit(r)['verified'])
  r=full_fixture();r['native']['crumbs'][1][-2]['xyz'][0]=999.;self.assertFalse(m.audit(r)['verified'])
  r=abort_fixture(2);r['events'][-1]['kind']=85;self.assertFalse(m.audit(r)['verified'])
 def test_unknown_never_grants_source_success(self):
  a=m.audit({});self.assertFalse(a['verified']);self.assertFalse(a['success_verified']);self.assertFalse(a['field_verified'])

if __name__=='__main__':unittest.main()
