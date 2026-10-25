import unittest
from unittest.mock import patch
import match_participants as module

class ParticipantTests(unittest.TestCase):
    def setUp(self):
        self.words={0xce8c9c:0x1000,0x1038:0x2000,0x103c:0x3000,0x1040:0x4000,0x2000:0xc5bce0,0x2020:2,0x2090:0}
        self.memory=type('Memory',(),{'u32':lambda obj,address:self.words.get(address,0),'read':lambda *args:None})()
        self.state={'victory_conditions':{'participants':[{'player_index':3,'player':'0x3000'},{'player_index':4,'player':'0x4000'}]}}
        self.registry={'commanders':[{'assets':[{'instance_id':'0x1234'}]}]}
        self.identities={0x3000:{'player_index':3,'instance_id':'0x1234'},0x4000:{'player_index':4,'instance_id':'0x5678'}}
    def verify(self):
        with patch.object(module,'inspect_player',side_effect=lambda read,address:self.identities[address]),patch.object(module,'read_player_relation',return_value=getattr(self,'relation','enemy')):
            return module.verify_two_ai(self.memory,self.state,self.registry,3,4)
    def test_two_ai_and_separate_observer_accepted(self):
        self.assertTrue(self.verify()['opponent_native_ai_verified'])
    def test_idle_human_combatant_rejected(self):
        self.state['victory_conditions']['participants'][1]={'player_index':2,'player':'0x2000'}
        with self.assertRaises(ValueError):self.verify()
    def test_native_opponent_cannot_be_another_registered_model(self):
        self.identities[0x4000]['instance_id']='0x1234'
        with self.assertRaises(ValueError):self.verify()
    def test_stale_pointer_rejected(self):
        self.words[0x1040]=0x5000
        with self.assertRaises(ValueError):self.verify()
    def test_observer_with_ai_controller_rejected(self):
        self.words[0x2090]=0x9000
        with self.assertRaises(ValueError):self.verify()
    def test_extra_participant_rejected(self):
        self.state['victory_conditions']['participants'].append({'player_index':5,'player':'0x5000'})
        with self.assertRaises(ValueError):self.verify()
    def test_allied_ai_players_are_not_accepted_as_opponents(self):
        self.relation='ally'
        with self.assertRaises(ValueError):self.verify()

if __name__=='__main__':unittest.main()
