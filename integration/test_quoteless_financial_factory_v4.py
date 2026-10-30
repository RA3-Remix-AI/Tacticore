import json
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
for folder in ('integration','native-ai'):
    if str(ROOT/folder) not in sys.path:sys.path.insert(0,str(ROOT/folder))
from host_runtime import macro_cost_factory_v2 as f
from host_runtime.resource_admission_reservations_v4 import FinancialStateV4,validate_financial
from host_runtime.contracts import ContractError
from macro_cost_identity_guard import TrustedCostGuard
from macro_quoteless_financial_observation import QuotelessFinancialObserver
import test_macro_quoteless_financial_observation as fixtures

class FinancialFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.QuotelessTests.setUpClass()
    def setUp(self):
        self.f=fixtures.QuotelessTests();self.f.setUp()
        self.binding=replace(self.f.f.binding,session_id='00000000-0000-4000-8000-000000000001')
        self.guard=TrustedCostGuard(session=self.binding,file_check=lambda:{'placeholder':'digest'},live_check=lambda:self.binding)
        self.reader=QuotelessFinancialObserver(self.f.f.mem.read,session=self.binding,guard=self.guard)
        self.temp=tempfile.TemporaryDirectory(prefix='artificial-financial-v4-',dir=ROOT/'reports');self.addCleanup(self.temp.cleanup)
        review=ROOT/'reports/macro-sickle-prioritized-cost-independent-89844-20261029-v1/review.json'
        self.qualification=f.load_current_financial_coverage_qualification(coverage_review=review,coverage_sha256=f.sha(review))
        from host_runtime.resource_settlement_adapter import SettlementSession
        session=SettlementSession(self.binding.session_id,self.binding.pid,self.binding.process_creation_filetime,
            self.binding.executable_sha256,self.binding.package_sha256,self.binding.game_identity,'0x800000','0x802000','0x807000')
        self.provider=f.QualifiedQuotelessFinancialSupplierV4(self.reader,qualification=self.qualification,session=session,output=Path(self.temp.name)/'fresh')
        self.guard.file_check=lambda:dict(self.provider.required_guard_files)
    def test_canonical_financial_state_without_producer_price_or_attribute(self):
        mem,p=self.f.f.mem,self.f.f.p
        mem.word(p['templates'][0xd50c222e]+8,0x11223344);mem.word(p['thing']+0x36c,0xdeadbeef)
        value=self.provider()
        self.assertIs(type(value),FinancialStateV4)
        validate_financial(value,value.session,current_game_frame=100,now_monotonic_ns=time.monotonic_ns())
        self.assertEqual(value.credits,1235);self.assertFalse(value.prior_preference_latent_work_covered)
        self.assertFalse(value.actual_payment_attribution_verified);self.assertEqual(value.frame_after,100)
        artifact=Path(self.temp.name)/'fresh/financial-000001.json'
        self.assertEqual(f.sha(artifact),value.source_evidence_sha256)
        self.assertTrue(json.loads(artifact.read_text())['necessary_ranges'])
    def test_known_debt_above_cash_still_is_valid_financial_state(self):
        from test_macro_payment_observation_v2 import queue_node
        mem,p=self.f.f.mem,self.f.f.p;queue_node(mem,p,cost=2800,paid=910)
        mem.word(p['account']+4,596);mem.word(p['account']+0x14,0)
        value=self.provider()
        self.assertEqual((value.credits,value.production_upgrade_commitment_upper_bound),(596,1890))
        validate_financial(value,value.session,current_game_frame=100,now_monotonic_ns=time.monotonic_ns())
    def test_no_receipt_guard_cannot_sign_financial_fact(self):
        self.guard.file_check=lambda:{'missing':'source'}
        with self.assertRaisesRegex(ContractError,'complete_files'):self.provider()
        self.assertIsNone(self.provider.last_fact)

if __name__=='__main__':unittest.main()
