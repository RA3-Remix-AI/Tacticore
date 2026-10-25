"""Only complete positive records whose clocks differ may be resampled."""
import copy
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf8_late_admission_test',H/'lease.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)


class Admission(unittest.TestCase):
    def setup(self,frames):
        self.records=[];self.calls=0
        self.actors=[dict(object_id=7,address='0x7',type_hash='0x19ab11af',ai_address='0x70'),dict(object_id=8,address='0x8',type_hash='0x2c358c61',ai_address='0x80')]
        for i,frame in enumerate(frames):
            actor=self.actors[i%2];g=dict(actor,owner='0x9',hp=100.,xyz=[100. if i%2==0 else 0.,0.,210.])
            self.records.append(dict(frame=frame,grounded_status=g,state_snapshot=dict(update=actor['ai_address']),valid=True))
        def actor(*_):
            record=self.records[self.calls];self.calls+=1;return record
        self.admission=types.SimpleNamespace(actor_admission=actor,verify_evidence=lambda r:dict(verified=r['valid']))
        self.pre=dict(owner='0x9',logic='0x1000')
        self.memory=types.SimpleNamespace(u32=lambda p:0 if p==0x115c else 100)
        self.target=dict(object_id=90,address=900,owner=91,type_hash='0xc45aaeab',xyz=[500.,0.,210.],observed_frame=100)
        self.reader=types.SimpleNamespace(private_targets={'contact_ore':self.target},collect=lambda *_:None)

    def run_sample(self):
        with patch.object(w,'module',return_value=self.admission):return w.initial_admission(self.memory,self.pre,*self.actors,self.reader,'contact_ore',dict(self.target))

    def test_only_clock_skew_retries_then_current_same_frame_pair_passes(self):
        self.setup([99,100,100,100]);result=self.run_sample()
        self.assertEqual(self.calls,4);self.assertEqual([r['matched'] for r in result['attempts']],[False,True])
        self.assertEqual(result['frame'],100)

    def test_three_pairs_is_a_hard_limit(self):
        self.setup([99,100]*3)
        with self.assertRaisesRegex(ValueError,'initial_actor_pair_not_same_frame'):self.run_sample()
        self.assertEqual(self.calls,6)

    def test_backward_scene_clock_is_hard_failure_not_a_retry(self):
        self.setup([101,100]*3)
        with self.assertRaisesRegex(ValueError,'initial_clock_rollback'):self.run_sample()
        self.assertEqual(self.calls,2)

    def test_bad_identity_health_ground_or_update_never_retries(self):
        for key,value in [('object_id',999),('address','0x999'),('type_hash','0xdead'),('owner','0x99'),('hp',49.)]:
            self.setup([100,100]*3);self.records[0]['grounded_status'][key]=value
            with self.assertRaisesRegex(ValueError,'initial_actor_admission_rejected'):self.run_sample()
            self.assertEqual(self.calls,1,key)
        for change in ('ground','update'):
            self.setup([100,100]*3)
            if change=='ground':self.records[0]['valid']=False
            else:self.records[0]['state_snapshot']['update']='0x999'
            with self.assertRaisesRegex(ValueError,'initial_actor_admission_rejected'):self.run_sample()
            self.assertEqual(self.calls,1)

    def test_fresh_visibility_and_initial_direction_still_required(self):
        self.setup([100,100]);self.reader.private_targets={}
        with self.assertRaisesRegex(ValueError,'initial_current_visibility_or_capacity'):self.run_sample()
        self.setup([100,100]);self.target['xyz']=[-500.,0.,210.]
        with self.assertRaisesRegex(ValueError,'initial_pair_not_ahead_target'):self.run_sample()


if __name__=='__main__':unittest.main()
