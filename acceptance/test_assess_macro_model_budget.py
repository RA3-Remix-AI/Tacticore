import unittest
from acceptance.assess_macro_model_budget import feedback_memory,context_call_order

class MacroAssessmentTests(unittest.TestCase):
    def test_same_clock_tick_uses_actual_journal_order(self):
        context={'kind':'context','monotonic_ns':100};start={'kind':'start','monotonic_ns':100}
        response={'kind':'response','monotonic_ns':101}
        self.assertTrue(context_call_order([context,start,response],context,start,response))
        self.assertFalse(context_call_order([start,context,response],context,start,response))
        response['monotonic_ns']=99
        self.assertFalse(context_call_order([context,start,response],context,start,response))

    def test_compacted_conversation_can_retain_actual_strategy_and_feedback(self):
        context={'conversation_tail':[],'working_memory':{
            'current_strategy':{'origin':'model','macro_actions':['budgeteconomy']},
            'recent_execution_feedback':[{'status':'native_budget_adopted','actions':['budgeteconomy'],
                'native_effect_verified':True}]}}
        self.assertTrue(feedback_memory(context))
        context['working_memory']['current_strategy']['macro_actions']=['budgetarmy']
        self.assertFalse(feedback_memory(context))
        context['working_memory']['current_strategy']=None
        self.assertFalse(feedback_memory(context))

if __name__=='__main__':unittest.main()
