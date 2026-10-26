"""Isolated scene-reset history parser, never a new field Source certificate."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf17_history_parser_test',HERE/'reserve_controller_audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SceneHistory(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=HERE.parents[1]/'acceptance/runs/20261026-082848-commander/paid-pair16-v2-01-controller.json'
  cls.raw=cls.path.read_bytes()
  assert hashlib.sha256(cls.raw).hexdigest()=='8ba17e7350f41ce96be6cc16cd5b3a7ef2cff7eee096fcbeadc4b3a8275a1737'
  cls.original=json.loads(cls.raw.decode('utf-8-sig'))
 def fixture(self):
  r=copy.deepcopy(self.original)
  r['native'].update(phase=4,error=31,active=0,restore_mask=131071)
  r['events'][-1].update(frame=0,native_error=31)
  return r
 def inspect(self,r):
  # Only isolate the publication-history gate from the old fixture's explicit
  # MF16 namespace/producer-reader pins. All real payment/cohort/borrow/origin
  # records remain original. These mocks cannot grant q17 Source or release.
  with patch.object(m,'input_audit',return_value={'verified':True}),patch.object(m,'producer_arm_audit',return_value={'verified':True}):
   return m.live_facts(r),m.historical_borrow_facts(r)
 def test_scene_tail_can_recover_only_real_historical_borrows(self):
  r=self.fixture();before=copy.deepcopy(r);ordinary,historical=self.inspect(r)
  self.assertFalse(ordinary['verified']);self.assertTrue(historical['verified'])
  self.assertEqual([c['object_id'] for c in historical['claims']],[801,804])
  self.assertTrue(historical['clock']['verified']);self.assertFalse(historical['ready']['verified'])
  for key in ('scene_closed_verified','control_release_verified','restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','tactical_source_granted'):
   self.assertFalse(historical[key],key)
  self.assertEqual(r,before);self.assertEqual(self.path.read_bytes(),self.raw)
 def test_only_one_exact_terminal_reset_is_allowed(self):
  for change in ('host_zero','host_unknown','wrong_error','duplicate_finish','earlier_reset','truncated_count','last_error'):
   r=self.fixture()
   if change=='host_zero':r['host_exit']=0
   elif change=='host_unknown':r['host_exit']=None
   elif change=='wrong_error':r['native']['error']=52
   elif change=='duplicate_finish':r['events'][-2]['kind']=4
   elif change=='earlier_reset':r['events'][500]['frame']=0
   elif change=='truncated_count':r['native']['count']-=1
   else:r['events'][-1]['native_error']=52
   self.assertFalse(self.inspect(r)[1]['verified'],change)
  self.assertEqual(self.path.read_bytes(),self.raw)

if __name__=='__main__':unittest.main()
