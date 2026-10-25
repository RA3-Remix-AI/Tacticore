"""Pure field-selection, frozen input and pre-launch no-dispatch boundaries."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid

H=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
field=load('mf5_selector_pure_test',H/'field_plan.py')
driver=load('mf5_coordinate_pure_test',H/'field_coordinate.py')
pre=load('mf5_predispatch_pure_test',H.parent/'pre_dispatch_formation_v5_contract.py')


class FieldAndPreDispatch(unittest.TestCase):
    def test_ahead_filter_precedes_paid_preference_for_each_target(self):
        actor=lambda i,x:dict(object_id=i,xyz=[x,0.,210.])
        east=(actor(7,100.),actor(8,0.));west=(actor(9,0.),actor(10,100.))
        self.assertEqual(field.ahead_pairs([east,west],[500.,0.,210.],9,10),[east])
        self.assertEqual(field.ahead_pairs([east,west],[-500.,0.,210.],7,8),[west])

    def test_coordinate_preserves_original_expiry_not_now_plus4500(self):
        args=driver.child_arguments('session','natural','output',dict(front_id=7,support_id=8,contact_id='contact_ore',frame=100,expires_frame=1234),'mission','proof','command','task',1)
        self.assertEqual(args[args.index('--expires-frame')+1],'1234')
        self.assertEqual(Path(args[1]),H/'lease.py')
        self.assertNotIn('--routes',args)
        self.assertEqual(args.count('--execute'),1)

    def fixture(self,folder):
        session=dict(session_id=str(uuid.uuid4()),pid=1,mod_sha256='package',scenario=dict(commander_id=str(uuid.uuid4())))
        root=Path(folder);path=root/'session.json';path.write_text(json.dumps(session))
        args=argparse.Namespace(session=path,output=root/'report.json',command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=1,front_id=7,support_id=8,contact_id='contact_ore')
        return session,args

    def test_real_file_hashes_bind_pre_native_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            s,a=self.fixture(folder);report=pre.rejection(a,H,ValueError('current_visibility_unavailable'))
            result=pre.verify_no_dispatch(report,child_exit_code=64,session=s,commander_id=s['scenario']['commander_id'],command_id=a.command_id,task_id=a.task_id,seq=a.seq,object_ids=[7,8],directory='mission-formation-v5',target_contact_id='contact_ore')
            self.assertTrue(result['no_dispatch_verified'],result)
            self.assertFalse(result['restoration_verified']);self.assertFalse(result['completion_claim'])

    def test_persisted_launch_intent_can_never_be_overwritten_as_no_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            s,a=self.fixture(folder)
            a.output.write_text(json.dumps(dict(request=dict(command_id=a.command_id,task_id=a.task_id,seq=a.seq),native_launch_intent_persisted=True,native={},events=[])))
            old=a.output.read_bytes()
            with self.assertRaisesRegex(ValueError,'cannot_relabel_native_launch_as_no_dispatch'):pre.rejection(a,H,ValueError('anything'),owned=True)
            self.assertEqual(a.output.read_bytes(),old)

    def test_existing_other_order_and_duplicate_actor_cannot_be_attested(self):
        with tempfile.TemporaryDirectory() as folder:
            s,a=self.fixture(folder);a.output.write_text(json.dumps(dict(request=dict(command_id='other',task_id=a.task_id,seq=1))))
            with self.assertRaisesRegex(ValueError,'existing_report_binding_mismatch'):pre.rejection(a,H,ValueError('failure'),owned=True)
            a.support_id=a.front_id
            with self.assertRaisesRegex(ValueError,'cannot_attest_unbound_actors'):pre.rejection(a,H,ValueError('failure'))

    def test_field_never_loads_history_graph_or_planner(self):
        for filename in ('field_plan.py','field_coordinate.py'):
            text=(H/filename).read_text(encoding='utf-8')
            for forbidden in ('--routes','plan_from_history','covered_goal','formation_history_dir'):
                self.assertNotIn(forbidden,text)


if __name__=='__main__':unittest.main()
