import ctypes
import importlib.util
import json
from pathlib import Path
import unittest
import uuid

HERE=Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
client=module('macro_policy_candidate_client',HERE/'client.py')
build=module('macro_policy_candidate_build',HERE/'build.py')
REPORT=HERE.parent/'staging/macro-policy-20261028-v1/build-report.json'


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads(REPORT.read_text(encoding='utf-8'))
        _,self.manifest=build.profile(self.report,3)

    def test_exact_compiled_field_layout(self):
        self.assertEqual(ctypes.sizeof(client.Shared),128)
        self.assertEqual(client.Shared.request.offset,48);self.assertEqual(client.Shared.mask.offset,112)
        self.assertEqual(client.Shared.client_heartbeat.offset,104)

    def test_each_exclusive_domain_rejects_conflict(self):
        for domain in ['construction','production','budget']:
            actions=[r['action'] for r in self.manifest['consumers'] if r['domain']==domain]
            with self.assertRaisesRegex(ValueError,'conflicting_macro'):client.action_mask(actions[:2],self.manifest)
        with self.assertRaisesRegex(ValueError,'conflicting_macro'):
            client.action_mask(['deployattack','deploydefense'],self.manifest)

    def test_parallel_nonconflicting_macro_domains(self):
        mask=client.action_mask(['scout','buildreactor','produceconscript','budgeteconomy','deploydefense'],self.manifest)
        self.assertEqual(mask.bit_count(),5)

    def test_no_raw_units_scripts_or_invalid_actions(self):
        for actions in [['Move'],['Attack'],['scout','scout'],[{'unit_id':1}],[None],['scout']*14]:
            with self.subTest(actions=actions),self.assertRaises(ValueError):client.action_mask(actions,self.manifest)

    def test_idempotent_receipt_no_game_read_or_redispatch(self):
        transport=client.MacroPolicyProbe.__new__(client.MacroPolicyProbe);ident=str(uuid.uuid4());receipt={'seq':1}
        transport.ledger={ident:dict(fingerprint=(1,2,450),status='acknowledged',receipt=receipt)}
        self.assertIs(transport.command(1,2,450,ident),receipt)
        with self.assertRaisesRegex(ValueError,'id_conflict'):transport.command(1,4,450,ident)

    def test_unknown_result_blocks_reuse_and_new_command(self):
        transport=client.MacroPolicyProbe.__new__(client.MacroPolicyProbe);ident=str(uuid.uuid4())
        transport.ledger={ident:dict(fingerprint=(1,2,450),status='unknown')};transport.pending=True
        with self.assertRaisesRegex(ValueError,'previous_command_unknown'):transport.command(1,2,450,ident)
        with self.assertRaisesRegex(ValueError,'outstanding_command_unknown'):transport.command(1,2,450,str(uuid.uuid4()))

    def test_duration_and_scope_are_bounded(self):
        transport=client.MacroPolicyProbe.__new__(client.MacroPolicyProbe);transport.manifest=self.manifest
        for duration in [True,0,4501,1.5]:
            with self.assertRaisesRegex(ValueError,'duration_bounds'):transport.apply(['scout'],duration)
        for epoch in [0,1000,True]:
            with self.assertRaisesRegex(ValueError,'bounded_macro_runtime_epoch'):build.profile(self.report,epoch)
        self.report['flags']['scout']='/arbitrary_flag'
        with self.assertRaisesRegex(ValueError,'flag_scope'):build.profile(self.report,4)


if __name__=='__main__':unittest.main()
