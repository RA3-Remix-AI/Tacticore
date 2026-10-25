"""Source branch coverage stays factual and separate from effect qualification."""
import copy
import unittest
import evidence
import mission_combat_v7_qualification as strict
from test_mission_combat_v7 import fixture

class SourceCoverage(unittest.TestCase):
    def test_visible_success_does_not_certify_unobserved_memory_reacquisition(self):
        report=fixture();result=strict.qualify(report)
        self.assertEqual(result['status'],'continuous_ak_combat_mission_verified')
        scoped=evidence.navigation_field_coverage('mission-combat-v7',result,report)
        coverage=scoped['navigation_field_validation']
        self.assertTrue(coverage['invariants_verified'])
        for key in ('memory_reacquisition_field_verified','hidden_navigation_observed','reacquisition_observed','hidden_movement_observed'):self.assertFalse(coverage[key])
        self.assertEqual(coverage['maximum_hidden_displacement'],0)
        self.assertEqual(coverage['unobserved_branch_status'],'experimental_not_field_certified')
        self.assertEqual(scoped['qualified_hits'],result['qualified_hits'])
        self.assertEqual(scoped['checks'],result['checks'])

    def test_old_families_keep_same_trace_coverage_requirement(self):
        report=fixture();result=strict.qualify(report)
        for family in ('mission-combat-v5','mission-combat-v6'):
            with self.assertRaises(ValueError):evidence.navigation_field_coverage(family,result,report)

    def test_memory_invariant_failure_never_becomes_an_experimental_pass(self):
        report=fixture();result=strict.qualify(report);result['navigation_memory']['verified']=False
        with self.assertRaises(ValueError):evidence.navigation_field_coverage('mission-combat-v7',result,report)

    def test_headers_cannot_invent_hidden_movement(self):
        report=fixture();report['native'].update(hidden_displacement=999.,reacquired=1)
        result=strict.qualify(report);result['navigation_memory'].update(hidden_navigation_observed=True,reacquisition_observed=True)
        scoped=evidence.navigation_field_coverage('mission-combat-v7',result,report)
        self.assertFalse(scoped['navigation_field_validation']['memory_reacquisition_field_verified'])

if __name__=='__main__':unittest.main()
