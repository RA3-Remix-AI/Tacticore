import copy
import unittest

from assess_macro_budget_lifecycles import ROOT,join,records,trial


class BudgetLifecycleEvidenceTests(unittest.TestCase):
    def field(self):
        ident='3608bf2c-b214-44ce-91dd-81b02c4b2cdc'
        _,final,manifest,rows,_=trial(ROOT/'reports'/('macro-desktop-'+ident))
        events=records(ROOT/'acceptance/runs/20261028-065549-macro-probe/battle-host/host-events.jsonl')
        return events,rows,manifest,final

    def test_actual_unadopted_opening_intent_remains_unadopted_despite_later_effects(self):
        results,bound=join(*self.field())
        self.assertTrue(bound);self.assertTrue(all(r['bounded_activation'] for r in results))
        self.assertFalse(results[0]['native_adoption_verified'])
        self.assertEqual(results[0]['matching_native_adoption_samples'],0)
        self.assertTrue(any(r['native_adoption_verified'] for r in results))
        self.assertTrue(any(r['native_adoption_verified'] and r['feedback_to_later_genuine_response_verified'] for r in results))

    def test_observations_outside_the_command_window_cannot_be_an_effect(self):
        events,rows,manifest,final=self.field();rows=copy.deepcopy(rows)
        for r in rows:
            if r['kind']=='macro_observation' and 'observation' in r:r['observation']['frame']=0
        results,bound=join(events,rows,manifest,final)
        self.assertTrue(bound);self.assertTrue(all(r['bounded_activation'] for r in results))
        self.assertFalse(any(r['native_adoption_verified'] for r in results))

    def test_a_mismatched_acknowledgement_is_not_model_adoption(self):
        events,rows,manifest,final=self.field();rows=copy.deepcopy(rows)
        for r in rows:
            if r['kind']=='command_acknowledged':r['native']['applied_mask']=8191
        results,bound=join(events,rows,manifest,final)
        self.assertFalse(bound);self.assertFalse(any(r['native_adoption_verified'] for r in results))


if __name__=='__main__':unittest.main()
