"""Negative focus-return proof fixtures. No Game, process opener or native IO."""
import copy
import unittest

from host_runtime.native7_release import verified_focus_restoration


def proof():
    owned=dict(phase=4,baseline_captured=1,selector=0x10000,baseline_scheme=2,target_player=4,request=1,
               manual=0,isolated=0,priority=[1,1],alive_mask=3,frame=100,callback=10,
               deadline_frame=0,call_reservations=2,ms=1000,deadline_ms=0)
    actual=dict(source='bound_native_enemy_selector_v1',selector=0x10000,automatic_scheme=2,
                manual=0,isolated=0,enumeration_lock=0,priority_p4=1,priority_p5=1,alive_mask=3,
                own_player_id=3,public_opponent_ids=[4,5],native_calls=0,process_writes=0,
                enemy_details_read=False,mission_success_verified=False)
    return dict(native=dict(focus=owned,callback_serial=11),enemy_focus=actual,frame=101)


class Native7FocusReturn(unittest.TestCase):
    def test_duel_return_requires_absent_second_opponent_priority(self):
        value=proof();value['enemy_focus'].update(public_opponent_ids=[4],priority_p5=0,alive_mask=1)
        value['native']['focus'].update(priority=[1,0],alive_mask=1)
        self.assertTrue(verified_focus_restoration(value))
        value['enemy_focus']['priority_p5']=1
        self.assertFalse(verified_focus_restoration(value))
        value['enemy_focus'].update(priority_p5=0,alive_mask=3)
        self.assertFalse(verified_focus_restoration(value))

    def test_fresh_actual_automatic_selector_and_later_callback_are_required(self):
        self.assertTrue(verified_focus_restoration(proof()))
        for field, value in (('manual',1),('isolated',1),('enumeration_lock',1),('automatic_scheme',1),
                             ('priority_p4',10),('selector',0x10004),('own_player_id',2),
                             ('enemy_details_read',True),('native_calls',1)):
            changed=copy.deepcopy(proof());changed['enemy_focus'][field]=value
            with self.subTest(field=field):
                self.assertFalse(verified_focus_restoration(changed))
        changed=proof();changed['native']['callback_serial']=10
        self.assertFalse(verified_focus_restoration(changed))

    def test_owned_status_cannot_claim_baseline_from_held_or_unknown(self):
        for field,value in (('phase',1),('phase',2),('phase',3),('phase',6),('deadline_frame',200),
                            ('deadline_ms',2000),('baseline_scheme',1),('target_player',3),
                            ('manual',1),('priority',[10,1]),('baseline_captured',True)):
            changed=proof();changed['native']['focus'][field]=value
            with self.subTest(field=field,value=value):
                self.assertFalse(verified_focus_restoration(changed))

    def test_never_owned_focus_requires_zero_status_and_fresh_actual_baseline(self):
        value=proof();owned=value['native']['focus']
        for key in owned:
            owned[key]=[0,0] if key=='priority' else 0
        self.assertTrue(verified_focus_restoration(value))
        owned['target_player']=4
        self.assertFalse(verified_focus_restoration(value))

    def test_public_elimination_can_change_after_return_without_reviving_focus(self):
        value=proof();value['enemy_focus']['alive_mask']=2;value['enemy_focus']['priority_p4']=0
        self.assertTrue(verified_focus_restoration(value))
        value['enemy_focus']['manual']=1
        self.assertFalse(verified_focus_restoration(value))

    def test_missing_focus_and_scalar_type_substitutions_fail(self):
        value=proof();del value['enemy_focus']
        self.assertFalse(verified_focus_restoration(value))
        for section,field in (('enemy_focus','native_calls'),('enemy_focus','priority_p4'),
                              ('native','callback_serial')):
            value=proof();value[section][field]=float(value[section][field])
            self.assertFalse(verified_focus_restoration(value))


if __name__=='__main__':
    unittest.main()
