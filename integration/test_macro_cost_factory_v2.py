"""Only artificial native memory and artificial review fixtures; no live grant."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
for folder in ('integration','native-ai'):
    if str(ROOT/folder) not in sys.path:sys.path.insert(0,str(ROOT/folder))
from host_runtime import macro_cost_factory_v2 as f
from host_runtime.resource_reservations import CurrentQueueBudgetFact,validate_cost
from host_runtime.contracts import ContractError
import macro_active_attribute_cost_supplier as active
import macro_attribute_cost_bound as attribute
import test_macro_guarded_cost_supplier as fixtures
from test_macro_payment_observation_v2 import queue_node

class FactoryV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.GuardedTests.setUpClass()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='artificial-cost-v2-',dir=ROOT/'reports');self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.raw=self.folder/'artificial-input.json';self.raw.write_text('{"artificial_only":true}')
        self.input=dict(path=str(self.raw),sha256=f.sha(self.raw));self.cov=self.folder/'coverage.json';self.attr=self.folder/'attributes.json'
        self.coverage=dict(kind='independent_current_queue_coverage_and_cash_field_review',schema_version=1,
            inputs=[self.input],all_reads_consumed_in_original_order=True,
            executable_sha256=fixtures.guarded.baseline.readiness.EXE_SHA256,
            package_sha256='d516540d3d51a48a2d385dd1534e329bd5139bc67a6a0bde3e59a3ea5b9690a5',
            qualification=dict(source_algorithm=f.COVERAGE_ALGORITHM,
                current_owned_production_upgrade_queue_coverage_supported=True,
                current_player_resource_zero_cash_balance_supported=True,old_cash_or_queue_snapshot_reuse_allowed=False))
        self.attributes=dict(kind='independent_native_attribute_cost_upper_review',schema_version=1,inputs=[self.input],
            static_supported=True,field_supported=True,exact_enqueue_quote_asserted=False,source_scope='active_nonincreasing',
            executable_sha256=self.coverage['executable_sha256'],package_sha256=self.coverage['package_sha256'],
            upper_bound_scope='current_native_attribute14_nonincreasing_divisor_context',
            source_pins={name:f.COVERAGE_PINS[name] for name in ('native-ai/macro_attribute_cost_bound.py','native-ai/macro_active_attribute_cost_supplier.py')})
        self.write_reviews();self.fix=fixtures.GuardedTests();self.fix.setUp()
        for at,raw in attribute.PINS.items():self.fix.mem.put(at,bytes.fromhex(raw))
        self.fix.universe._archives_verified=True
        self.reader=active.ActiveAttributeCostSupplier(self.fix.mem.read,session=self.fix.binding,guard=self.fix.guard,
            universe=self.fix.universe,product_scope=active.RESEARCH_SCOPE)
    def write_reviews(self):self.cov.write_text(json.dumps(self.coverage));self.attr.write_text(json.dumps(self.attributes))
    def qualify(self):return f.load_current_queue_cost_qualification(coverage_review=self.cov,coverage_sha256=f.sha(self.cov),
        attribute_review=self.attr,attribute_sha256=f.sha(self.attr))
    def supplier(self):
        provider=f.make_current_queue_cost_supplier_v2(self.reader,qualification=self.qualify())
        self.fix.guard.file_check=lambda:dict(provider.required_guard_files)
        return provider
    def test_known_low_cash_fact_has_truthful_amounts_and_resource_gate_rejects(self):
        queue_node(self.fix.mem,self.fix.p,cost=2800,paid=910)
        self.fix.mem.word(self.fix.p['account']+4,596);self.fix.mem.word(self.fix.p['account']+0x14,0)
        value=self.supplier()('producesickle',{},100/15)
        self.assertIs(type(value),CurrentQueueBudgetFact);self.assertEqual(value.credits,596)
        self.assertEqual(value.production_upgrade_queue_payment_commitment_upper_bound,1890)
        self.assertEqual(value.upper_cost,850);self.assertEqual(value.frame,100)
        self.assertFalse(value.single_new_request_hard_limit_verified)
        with self.assertRaises(ContractError):validate_cost(value,session_id=self.fix.binding.session_id,player_id=3,
            action='producesickle',template_hash='0x60f0b4e9',game_identity=self.fix.binding.game_identity,
            game_seconds=100/15,producer_ids=(17,))
    def test_active_nonincreasing_attribute_yields_upper_without_exact_quote(self):
        import struct
        mem,p=self.fix.mem,self.fix.p
        pool,entry,wrapper,definition,array=0x790000,0x792000,0x793000,0x794000,0x795000
        mem.zeros(pool,0xb5);mem.word(pool,0xbe9748);mem.word(pool+4,0x791000);mem.word(pool+8,p['thing'])
        mem.word(p['thing']+0x36c,pool);mem.word(pool+0x28,entry);mem.word(pool+0x2c,entry+16)
        mem.zeros(entry,16);mem.word(entry,wrapper);mem.word(wrapper,definition);mem.zeros(definition,0x38)
        mem.word(definition+0x24,1);mem.word(definition+0x30,1);mem.word(definition+0x34,array)
        mem.put(array,struct.pack('<If',14,999.989990234375))
        vector=int.from_bytes(mem.read(p['thing']+0x310,4),'little')
        for index in range(256):
            if mem.read(vector+4*index,4)==b'\0'*4:break
        mem.word(vector+4*index,pool);mem.word(vector+4*index+4,0)
        provider=self.supplier();fact=provider('producesickle',{},100/15)
        self.assertEqual(fact.upper_cost,850);self.assertTrue(fact.native_quote_context_verified)
        self.assertIsNone(provider.last_observation['quote']['ordinary_unit_enqueue_cost'])
        self.assertFalse(provider.last_observation['exact_enqueue_quote_verified'])

    def test_empty_only_qualification_cannot_expand_to_active_entry(self):
        self.attributes['source_scope']='empty_attribute_vector_only';self.write_reviews()
        provider=self.supplier();provider('producesickle',{},100/15)
        value=self.reader.last_observation
        value['quote']['producer_attribute_evidence']['cost_adjustment_absent']=False
        value['quote']['producer_attribute_evidence']['entry_count']=1
        with self.assertRaisesRegex(ContractError,'outside_reviewed_empty_scope'):provider._fact(value)

    def test_known_affordable_current_fact_passes_canonical_resource_validation(self):
        value=self.supplier()('producesickle',{},100/15)
        validate_cost(value,session_id=self.fix.binding.session_id,player_id=3,
            action='producesickle',template_hash='0x60f0b4e9',game_identity=self.fix.binding.game_identity,
            game_seconds=100/15,producer_ids=(17,))
        self.assertEqual(value.production_upgrade_queue_payment_commitment_upper_bound,0)
        self.assertEqual(value.credits,1235)

    def test_missing_or_static_only_attribute_receipt_never_qualifies(self):
        with self.assertRaisesRegex(ContractError,'field_review_missing'):
            f.load_current_queue_cost_qualification(coverage_review=self.cov,coverage_sha256=f.sha(self.cov),
                attribute_review=None,attribute_sha256=None)
        self.attributes['field_supported']=False;self.write_reviews()
        with self.assertRaisesRegex(ContractError,'review_scope'):self.qualify()
    def test_real_nonempty_field_receipt_loads_source_qualification_only(self):
        coverage=ROOT/'reports/macro-sickle-prioritized-cost-independent-89844-20261029-v1/review.json'
        field=ROOT/'reports/macro-native-attribute-upper-field-68180-independent-20261029-v1.json'
        q=f.load_current_queue_cost_qualification(coverage_review=coverage,coverage_sha256=f.sha(coverage),
            attribute_review=field,attribute_sha256=f.sha(field))
        self.assertEqual(q.attribute_source_scope,'active_nonincreasing')
        self.assertEqual(q.package_sha256,self.fix.binding.package_sha256)

    def test_safe_boot_with_real_static_receipt_stays_disabled(self):
        coverage=ROOT/'reports/macro-sickle-prioritized-cost-independent-89844-20261029-v1/review.json'
        static=ROOT/'reports/macro-native-attribute-upper-independent-20261029-v1/review.json'
        boot=f.boot_current_queue_cost_supplier_v2(self.reader,coverage_review=coverage,coverage_sha256=f.sha(coverage),
            attribute_review=static,attribute_sha256=f.sha(static))
        self.assertFalse(boot.enabled);self.assertIsNone(boot.supplier)
        self.assertEqual(boot.reason,'blocked_cost_v2_active_attribute_review_scope')

    def test_review_raw_tamper_rejects(self):
        self.raw.write_text('changed')
        with self.assertRaisesRegex(ContractError,'raw_changed'):self.qualify()
    def test_reviews_and_factory_must_be_in_actual_file_guards(self):
        provider=f.make_current_queue_cost_supplier_v2(self.reader,qualification=self.qualify())
        with self.assertRaisesRegex(ContractError,'not_in_complete_file_guards'):provider('producesickle',{},100/15)
    def test_copied_or_expired_dictionary_is_never_accepted(self):
        provider=self.supplier();provider('producesickle',{},100/15)
        with self.assertRaisesRegex(ContractError,'fresh_typed_observation'):provider._fact(dict(self.reader.last_observation))
        self.fix.mem.word(self.fix.p['game']+0x50,116)
        with self.assertRaisesRegex(ContractError,'expired'):provider._fact(self.reader.last_observation)

if __name__=='__main__':unittest.main()
