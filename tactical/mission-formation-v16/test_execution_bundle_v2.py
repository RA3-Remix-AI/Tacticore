"""Versioned reader/source boundaries; old field bytes remain unchanged."""
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import unittest
import sys
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
def load(name,filename):
 spec=importlib.util.spec_from_file_location(name,HERE/filename);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
q=load('mf16v2_bundle_qualification','formation_mission_qualification_v2.py')
homes=load('mf16v2_bundle_homes','wait_anchor_replan_v2.py')

class VersionedExecutionBundle(unittest.TestCase):
 def fixture(self):
  path=HERE.parents[1]/'acceptance/runs/20261026-081800-commander/paid-pair16-01-controller.json';data=path.read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),'64bd113485a953d0d0e5addd27d150b6adb2a8ce591a0848c3e79e6c09974ba5');return path,data,json.loads(data.decode('utf-8-sig'))
 def test_new_source_bundle_rejects_original_wrapper_and_original_raw(self):
  rt=load('mf16v2_bundle_runtime','lease_v2.py');source=rt.source_record();self.assertTrue(q.source_pins(source));self.assertTrue(rt.frozen_sources_match(source))
  self.assertIn(HERE/'wait_anchor_replan_v2.py',q.source_paths());self.assertIn(HERE/'formation_mission_qualification_v2.py',q.source_paths());self.assertNotIn(HERE/'wait_anchor_replan.py',q.source_paths());self.assertNotIn(HERE/'formation_mission_qualification.py',q.source_paths())
  path,data,r=self.fixture();self.assertFalse(q.source_pins(r));out=q.qualify(r);self.assertEqual(out['status'],'not_passed');self.assertFalse(out['checks']['compiled_source_revision']);self.assertFalse(out['effect_verified']);self.assertEqual(path.read_bytes(),data)
 def test_committed_homes_join_actual_anchor_and_153_76_not_old71(self):
  path,data,r=self.fixture();out=homes.audit(r);self.assertTrue(out['verified'],out['checks']);self.assertFalse(out['observed']);self.assertFalse(out['field_verified'])
  for role in (0,1):
   borrow=next(e for e in r['events'] if e['kind']==71 and e['role']==role);self.assertNotEqual([borrow[k] for k in ('x','y','z')],r['native']['slots'][role]['anchor']);self.assertTrue(homes.mission_home_binding(r,role))
  self.assertEqual(path.read_bytes(),data)
 def test_missing_original_accept_dispatch_or_anchor_cannot_bind_home(self):
  for kind in (153,76,150):
   _,_,r=self.fixture();r['events'].remove(next(e for e in r['events'] if e['kind']==kind));self.assertFalse(homes.audit(r)['checks']['old_origins_preserved'])
 def test_home_header_rewrite_or_changed_slot_anchor_rejected(self):
  for where in ('safe_front','slot'):
   _,_,r=self.fixture()
   if where=='slot':r['native']['slots'][0]['anchor'][0]+=20
   else:r['native']['safe_front'][0]+=20
   self.assertFalse(homes.mission_home_binding(r,0))
 def test_invented_replan_does_not_get_vacuous_branch_credit(self):
  _,_,r=self.fixture();r['events'].append(dict(kind=96,role=0,seq=len(r['events'])+1,frame=2600,arg=1,mission_stage=1));out=homes.audit(r);self.assertFalse(out['verified']);self.assertTrue(out['observed'])
 def test_existing_actual_replan_conditions_are_preserved(self):
  old=(HERE/'wait_anchor_replan.py').read_text().split(' for i,start in enumerate(starts):',1)[1];new=(HERE/'wait_anchor_replan_v2.py').read_text().split(' for i,start in enumerate(starts):',1)[1];self.assertEqual(old,new)
 def test_post_return_native_attack_has_no_this_mission_credit(self):
  _,_,r=self.fixture();scope=q.controlled_role_observations(r,1);out=q.effect_audit(r)
  self.assertTrue(scope['verified']);self.assertEqual(scope['return_completed_seq'],4572);self.assertEqual([e['seq'] for e in out['post_return_native']],[4573,4574]);self.assertTrue(out['checks']['no_support_attack']);self.assertFalse(out['verified']);self.assertEqual(out['qualified_hits'],[]);self.assertEqual(out['source_damage_amount'],0)
 def test_attack_inside_borrowed_interval_or_missing_return_still_rejected(self):
  _,_,r=self.fixture();attack=copy.deepcopy(next(e for e in r['events'] if e['seq']==4573));attack['seq']=4560;r['events'].append(attack);self.assertFalse(q.effect_audit(r)['checks']['no_support_attack'])
  _,_,r=self.fixture();r['events']=[e for e in r['events'] if not(e['kind']==5 and e['tag']==3 and e['role']==1)];self.assertFalse(q.effect_audit(r)['checks']['no_support_attack'])
 def test_duplicate_return_cannot_shorten_controlled_interval(self):
  _,_,r=self.fixture();done=copy.deepcopy(next(e for e in r['events'] if e['seq']==4572));done['seq']=2000;r['events'].append(done);self.assertFalse(q.controlled_role_observations(r,1)['verified'])
 def test_actual_source_consumers_call_real_single_report_interfaces(self):
  inspect.signature(homes.audit).bind({});inspect.signature(q.wait_anchor_audit).bind({});inspect.signature(q.controller.audit).bind({});inspect.signature(q.stance.audit).bind({})
  rt=load('mf16v2_consumer_runtime','lease_v2.py');self.assertEqual(Path(rt.qualifier().__file__).resolve(),(HERE/'formation_mission_qualification_v2.py').resolve())
  tree=ast.parse(inspect.getsource(q.controller.audit));loop=next(x for x in ast.walk(tree) if isinstance(x,ast.For) and isinstance(x.iter,ast.List))
  for row in loop.iter.elts:inspect.signature(getattr(q.controller,row.elts[1].id)).bind(*[{} if x.id=='r' else [] for x in row.elts[2].elts])
 def test_helper_stance_dependency_is_exact_pinned_file_not_global_cache(self):
  with patch.dict(sys.modules,{'stance_ownership':object()}):actual=load('mf16v2_cache_adversary','wait_anchor_replan_v2.py')
  self.assertEqual(Path(actual.stance.__file__).resolve(),(HERE/'stance_ownership.py').resolve());self.assertEqual(actual.stance.__name__,'mf16v2_wait_anchor_actual_stance')

if __name__=='__main__':unittest.main()
