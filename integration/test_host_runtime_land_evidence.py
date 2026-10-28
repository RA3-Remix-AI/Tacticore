"""Cross-language native reader fixture and raw proof tampering, no game."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from host_runtime import runtime_evidence as main
from host_runtime.runtime_land_evidence import groups,has_move_proof

class LandProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(subprocess.check_output([str(main.RUNTIME/'bin/test_controller.exe'),'--land-evidence-fixture'],text=True))
        assert cls.fixture['game_access'] is False
    def setUp(self):
        l=main._layout();self.actor=l.Actor();self.actor.object_id=55;self.actor.thing=0x5000;self.actor.template_ptr=0x7000
        self.actor.update=0x6000;self.actor.owner=0x2000;self.actor.type_hash=0x19ab11af
        self.rows=[]
        for source in self.fixture['proofs']:
            row=l.HookTrace();row.kind=source['kind'];row.frame=self.fixture['frame'];row.word_count=24
            row.self=self.actor.update;row.target=self.actor.thing;row.words[:]=source['words'];self.rows.append(row)
    def review(self):return groups(self.rows,self.actor,self.fixture['logic'])
    def test_actual_cpp_reader_proof_recomputes_independently(self):
        result=self.review();self.assertEqual(1,len(result));self.assertEqual((150.,110.,210.),result[0]['target'])
        point=main._layout().Point();point.x,point.y,point.z=result[0]['target']
        self.assertTrue(has_move_proof(result,point,100));self.assertFalse(has_move_proof(result,point,101))
    def test_mask_cannot_be_replaced_with_an_ignored_object_id(self):
        self.rows[0].words[9]=353;self.assertIsNone(self.review())
    def test_radius_override_and_actor_backref_are_not_declarations(self):
        for index in (6,7,22):
            original=self.rows[0].words[index];self.rows[0].words[index]=0
            self.assertIsNone(self.review());self.rows[0].words[index]=original
    def test_original_cell_bytes_reject_objects_other_terrain_and_flags(self):
        for index,value in ((9,0x10000),(12,0x11),(12,0x12),(12,0x40010),(12,0x20)):
            original=self.rows[2].words[index];self.rows[2].words[index]=value
            self.assertIsNone(self.review());self.rows[2].words[index]=original
    def test_outside_map_bounds_or_wrong_cell_address_are_refused(self):
        self.rows[2].words[23]=0;self.assertIsNone(self.review())
        self.setUp();self.rows[2].words[8]+=48;self.assertIsNone(self.review())
    def test_raw_vertex_or_native_interpolation_changed(self):
        self.rows[1].words[10]+=8;self.assertIsNone(self.review())
        self.setUp();self.rows[1].words[14]=0x3f000000;self.assertIsNone(self.review())
    def test_partial_swapped_or_reused_groups_cannot_qualify(self):
        last=self.rows.pop();self.assertIsNone(self.review());self.rows.append(last)
        self.rows[1],self.rows[2]=self.rows[2],self.rows[1];self.assertIsNone(self.review())
        self.setUp();self.rows+=self.rows[:];self.assertIsNone(self.review())
    def test_frame_actor_or_control_scope_mismatch(self):
        for field,value in (('frame',101),('self',1),('scope',1),('source',1)):
            original=getattr(self.rows[1],field);setattr(self.rows[1],field,value)
            self.assertIsNone(self.review());setattr(self.rows[1],field,original)

if __name__=='__main__':unittest.main()
