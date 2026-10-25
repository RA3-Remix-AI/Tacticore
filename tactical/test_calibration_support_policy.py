"""Reject fabricated, stale, borrowed, immobile and casualty army support."""
import copy
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'acceptance/calibration/support_policy.py'
spec=importlib.util.spec_from_file_location('calibration_support_policy_tests',path)
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

class SupportPolicy(unittest.TestCase):
 def unit(self, ident, **changes):
  return dict(dict(object_id=ident,owner_index=3,frame=100,role='infantry',hp=100.,
   independently_movable=True,native_pool=True,xyz=[100.,0.,0.]),**changes)
 def evidence(self, units, excluded=()):
  return policy.support_evidence(units,dict(xyz=[0.,0.,0.]),set(excluded),100)
 def test_owned_army_support_beats_isolated_objective(self):
  supported=self.evidence([self.unit(1,role='armor'),self.unit(2)])
  isolated=self.evidence([])
  self.assertTrue(supported['ready']);self.assertLess(policy.priority(supported),policy.priority(isolated))
 def test_pair_cannot_supply_its_own_two_native_supporters(self):
  self.assertFalse(self.evidence([self.unit(1),self.unit(2)],excluded=[1,2])['ready'])
 def test_each_unknown_dead_foreign_or_stale_unit_is_excluded(self):
  for change in [dict(owner_index=4),dict(frame=99),dict(role='economy'),dict(hp=0),
   dict(hp=float('nan')),dict(independently_movable=False),dict(native_pool=False),
   dict(xyz=[float('inf'),0.,0.]),dict(xyz=[451.,0.,0.])]:
   with self.subTest(change=change):
    self.assertFalse(self.evidence([self.unit(1),self.unit(2,**change)])['ready'])
 def test_duplicate_id_cannot_manufacture_army(self):
  self.assertFalse(self.evidence([self.unit(1),self.unit(1)])['ready'])

if __name__=='__main__':unittest.main()
