"""Pure identity/deadline tests; no native ABI, game, SDK or model calls."""
import copy
import unittest
import uuid

import mission_contract as c


class Contract(unittest.TestCase):
    def fixture(self):
        session=dict(session_id=str(uuid.uuid4()),pid=1234)
        value=dict(schema_version=1,session_id=session['session_id'],pid=1234,player_id=3,front_id=7,support_id=8,navigation_mode=c.MODE,target_contact_id='contact_ore',expires_frame=4600)
        return value,session

    def validate(self,value,session,**updates):
        args=dict(target_contact_id='contact_ore',now_frame=100,expires_frame=4600)
        args.update(updates)
        return c.validate_mission(value,session,7,8,**args)

    def test_exact_identities_and_deadline_only(self):
        v,s=self.fixture();before=copy.deepcopy(v)
        self.assertEqual(self.validate(v,s)['lease_frames'],4500)
        self.assertEqual(v,before)

    def test_route_coordinates_history_and_code_never_enter_input(self):
        for key in ('route','xyz','target','retreat_point','formation_history_dir','source_plan','code','address'):
            v,s=self.fixture();v[key]=[]
            with self.assertRaisesRegex(ValueError,'mission_identity_fields'):self.validate(v,s)

    def test_required_explicit_identity_fields(self):
        for key in c.FIELDS:
            v,s=self.fixture();del v[key]
            with self.assertRaisesRegex(ValueError,'mission_identity_fields'):self.validate(v,s)

    def test_session_player_and_actor_swaps_are_rejected(self):
        for key,value in [('session_id',str(uuid.uuid4())),('pid',4321),('player_id',2),('front_id',8),('support_id',7),('target_contact_id','contact_other'),('navigation_mode','precomputed_route')]:
            v,s=self.fixture();v[key]=value
            with self.assertRaises(ValueError,msg=key):self.validate(v,s)

    def test_bool_never_substitutes_an_integer_binding(self):
        for key in ('schema_version','pid','player_id','front_id','support_id','expires_frame'):
            v,s=self.fixture();v[key]=True
            with self.assertRaises(ValueError,msg=key):self.validate(v,s)

    def test_frozen_expiry_cannot_extend_or_shorten(self):
        for value in (4599,4601,False):
            v,s=self.fixture();v['expires_frame']=value
            with self.assertRaisesRegex(ValueError,'mission_deadline'):self.validate(v,s)
        v,s=self.fixture()
        for now in (0,True,4301,99):
            with self.assertRaisesRegex(ValueError,'mission_deadline'):self.validate(v,s,now_frame=now)

    def test_shorter_lease_never_extends_absolute_expiry(self):
        v,s=self.fixture();v['expires_frame']=1000
        result=self.validate(v,s,expires_frame=1000,lease_frames=4500)
        self.assertEqual(result['lease_frames'],900)
        self.assertEqual(result['expires_frame'],1000)

    def test_missing_or_arbitrary_contact_is_not_a_target(self):
        v,s=self.fixture()
        for ident in ('','http://arbitrary','../contact','x'*97,None):
            with self.assertRaisesRegex(ValueError,'mission_explicit_contact_binding'):self.validate(v,s,target_contact_id=ident)

    def test_native_uint32_deadline_must_not_wrap(self):
        v,s=self.fixture();v['expires_frame']=0x100000001
        with self.assertRaisesRegex(ValueError,'mission_deadline'):self.validate(v,s,now_frame=0xffffffff-100,expires_frame=v['expires_frame'])


if __name__=='__main__':unittest.main()
