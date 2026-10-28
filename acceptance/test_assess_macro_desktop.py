import copy
import unittest
from assess_macro_desktop import feedback_verified,PRESETS


class LatestFeedbackProof(unittest.TestCase):
    def setUp(self):
        self.context=dict(game_time_seconds=100.,macro_execution_feedback=dict(
            source='native_macro_budget_observation',observed_frame=1501,status='native_budget_adopted',
            selected_policy='budgetarmy',actions=['budgetarmy'],native_effect_verified=True))
        self.observations=[dict(frame=1501,budget_feedback=dict(selected_macro_flag='private-army',
            account_shares=dict(PRESETS['budgetarmy'])))]
        self.actions=dict(budgetarmy='private-army',budgeteconomy='private-economy')

    def test_marker_needs_matching_native_frame_selection_and_account_shares(self):
        self.assertTrue(feedback_verified(self.context,self.observations,self.actions))
        for change in [dict(observed_frame=1502),dict(selected_policy='budgeteconomy'),dict(actions=['budgeteconomy'])]:
            value=copy.deepcopy(self.context);value['macro_execution_feedback'].update(change)
            with self.subTest(change=change):self.assertFalse(feedback_verified(value,self.observations,self.actions))
        self.observations[0]['budget_feedback']['account_shares']=dict(PRESETS['budgeteconomy'])
        self.assertFalse(feedback_verified(self.context,self.observations,self.actions))

    def test_stale_or_absent_feedback_is_not_a_verified_current_observation(self):
        self.context['game_time_seconds']=110.
        self.assertFalse(feedback_verified(self.context,self.observations,self.actions))
        self.assertFalse(feedback_verified(dict(game_time_seconds=100.),self.observations,self.actions))


if __name__=='__main__':unittest.main()
