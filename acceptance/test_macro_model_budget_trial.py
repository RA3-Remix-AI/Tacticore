"""Projection tests use synthetic own objects; no game or provider is opened."""
import json
import unittest
from acceptance.macro_model_budget_trial import public_snapshot,OBSERVATION_LIMITS
from integration.host_runtime.contracts import ContractError

class MacroProjectionTests(unittest.TestCase):
    def setUp(self):
        self.session={'session_id':'7b34e141-8398-4e54-909d-a0227a9c10f6'}
        self.census={'own_objects':[{'type_hash':'private_type','thing_id':999,'hp':1234,
            'address':'private_address','xyz':[1,2,3]},{'type_hash':'unknown'}],
            'resources':{'resource_available':True,'display_sum':3420,'address':'private_owner'}}
        self.field={'schema_version':1,'viewer_player_id':3,'visibility_verified':True,
            'regions':[],'contacts':[],'formations':[]}
        self.safety={'templates':{'private_type':{'role':'infantry'}}}

    def test_projection_excludes_private_data_and_marks_missing_counters(self):
        value=public_snapshot(self.session,1,150.,False,self.census,self.field,self.safety,['budgeteconomy'])
        self.assertEqual(value['resources']['credits'],3420)
        self.assertEqual(value['production']['own_roles'],{'infantry':1})
        encoded=json.dumps(value)
        for private in ('private_type','private_address','private_owner','thing_id','xyz','1234'):
            self.assertNotIn(private,encoded)
        self.assertFalse(OBSERVATION_LIMITS['production_queue_observed'])
        self.assertFalse(OBSERVATION_LIMITS['idle_producers_observed'])

    def test_missing_credit_observation_cannot_become_fake_zero(self):
        self.census['resources']={'resource_available':False}
        with self.assertRaisesRegex(ContractError,'credit_observation_unavailable'):
            public_snapshot(self.session,1,150.,False,self.census,self.field,self.safety,[])

if __name__=='__main__':unittest.main()
