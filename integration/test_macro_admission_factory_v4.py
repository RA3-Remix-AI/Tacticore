from dataclasses import replace
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
for folder in ('integration','native-ai'):
    if str(ROOT/folder) not in sys.path:sys.path.insert(0,str(ROOT/folder))
from host_runtime.macro_admission_factory_v4 import QualifiedAdmissionCostSupplierV4
from host_runtime.resource_admission_reservations_v4 import AdmissionCostV4,FinancialStateV4,validate_financial,validate_cost
from host_runtime.resource_settlement_adapter import SettlementSession
from host_runtime.contracts import ContractError
from macro_profiled_admission_cost_supplier import ProfiledAdmissionCostSupplier,RESEARCH_SCOPE
from macro_cost_identity_guard import TrustedCostGuard
from test_macro_quoteless_financial_observation import native_profile
from test_macro_payment_observation_v2 import queue_node
import test_macro_cost_factory_v2 as fixture

class AdmissionFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.FactoryV2Tests.setUpClass()
    def setUp(self):
        self.f=fixture.FactoryV2Tests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        native_profile(self.f.fix.mem,self.f.fix.p)
        self.binding=replace(self.f.fix.binding,session_id='00000000-0000-4000-8000-000000000001')
        self.guard=TrustedCostGuard(session=self.binding,file_check=lambda:{'initial':'digest'},live_check=lambda:self.binding)
        self.reader=ProfiledAdmissionCostSupplier(self.f.fix.mem.read,session=self.binding,guard=self.guard,
            universe=self.f.fix.universe,product_scope=RESEARCH_SCOPE)
        self.session=SettlementSession(self.binding.session_id,self.binding.pid,self.binding.process_creation_filetime,
            self.binding.executable_sha256,self.binding.package_sha256,self.binding.game_identity,'0x800000','0x802000','0x807000')
    def provider(self,session=None):
        provider=QualifiedAdmissionCostSupplierV4(self.reader,qualification=self.f.qualify(),session=session or self.session,
            output=self.f.folder/'v4-fresh')
        self.guard.file_check=lambda:dict(provider.required_guard_files)
        return provider
    def test_real_same_window_v4_types_not_v3_conversion(self):
        value=self.provider()('producesickle',{},100/15)
        self.assertIs(type(value),AdmissionCostV4);self.assertIs(type(value.financial),FinancialStateV4)
        self.assertEqual(value.upper_cost,850);self.assertEqual(value.financial.session,self.session)
        self.assertEqual(value.source_evidence_sha256,value.financial.source_evidence_sha256)
        import time
        validate_cost(value,self.session,current_game_frame=100,now_monotonic_ns=time.monotonic_ns())
    def test_known_low_cash_finance_is_valid_but_admission_rejects(self):
        mem,p=self.f.fix.mem,self.f.fix.p;queue_node(mem,p,cost=2800,paid=910)
        mem.word(p['account']+4,596);mem.word(p['account']+0x14,0)
        value=self.provider()('producesickle',{},100/15)
        import time
        validate_financial(value.financial,self.session,current_game_frame=100,now_monotonic_ns=time.monotonic_ns())
        with self.assertRaisesRegex(ContractError,'insufficient_current_funds'):
            validate_cost(value,self.session,current_game_frame=100,now_monotonic_ns=time.monotonic_ns())
    def test_personality_inspector_is_explicitly_pinned_not_ambient(self):
        from host_runtime import macro_admission_factory_v4 as module
        provider=self.provider();key=str(ROOT/'native-ai/read_selected_personality.py')
        self.assertEqual(provider.required_guard_files[key],module.PERSONALITY_INSPECTOR_SHA256)
        complete=dict(provider.required_guard_files);del complete[key]
        self.guard.file_check=lambda:dict(complete)
        with self.assertRaisesRegex(ContractError,'source_or_complete_files_unverified'):
            provider('producesickle',{},100/15)
        self.assertIsNone(provider.last_fact)

    def test_controller_profile_mismatch_and_unguarded_files_reject(self):
        provider=self.provider(replace(self.session,personality_wrapper='0x802004'))
        with self.assertRaisesRegex(ContractError,'profile_differs'):provider('producesickle',{},100/15)
        self.assertIsNone(provider.last_fact)

if __name__=='__main__':unittest.main()
