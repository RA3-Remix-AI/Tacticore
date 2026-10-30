from pathlib import Path
import unittest
import macro_guarded_cost_supplier as guarded
from macro_cost_identity_guard import TrustedCostGuard
import test_macro_coherent_registered_cost_supplier as fixture_module
from test_macro_payment_observation_v2 import queue_node

class GuardedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture_module.CoherentSupplierTests.setUpClass()
    def setUp(self):
        f=fixture_module.CoherentSupplierTests();f.setUp()
        self.mem,self.p,self.binding,self.universe=f.mem,f.p,f.binding,f.universe
        for at,raw in guarded.PAYER_PINS.items():self.mem.put(at,bytes.fromhex(raw))
        self.files={'source':'digest','package':'digest'};self.file_calls=0;self.live_calls=0
        def files():self.file_calls+=1;return dict(self.files)
        def live():
            self.live_calls+=1
            if guarded.baseline.readiness._word(self.mem.read,guarded.baseline.readiness.GAME_GLOBAL)!=self.p['game']:
                raise ValueError('native_identity_changed')
            return self.binding
        self.guard=TrustedCostGuard(session=self.binding,file_check=files,live_check=live)
    def supplier(self):
        return guarded.GuardedCostSupplier(self.mem.read,session=self.binding,guard=self.guard,
            universe=self.universe,product_scope=guarded.RESEARCH_SCOPE)
    def test_two_complete_file_guards_live_checks_and_original_window(self):
        s=self.supplier();row=s.observe('producesickle',game_seconds=100/15)
        self.assertEqual(self.file_calls,2);self.assertGreater(self.live_calls,5)
        self.assertEqual(row['financial_window_frame'],100);self.assertEqual(row['financial_window_frame_after'],100)
        self.assertTrue(row['pure_file_guards_outside_financial_window']);self.assertFalse(row['product_fact_eligible'])
    def test_review_epoch_change_on_failed_finish_latches(self):
        s=self.supplier();original=s.core.costs.sample
        def mutate(*a,**kw):
            value=original(*a,**kw);self.mem.word(guarded.baseline.readiness.GAME_GLOBAL,self.p['game']+0x1000);return value
        s.core.costs.sample=mutate
        with self.assertRaises(ValueError):s.observe('producesickle',game_seconds=100/15)
        self.assertTrue(self.guard.invalidated);self.assertEqual(self.file_calls,2)
        self.mem.word(guarded.baseline.readiness.GAME_GLOBAL,self.p['game']);s.core.costs.sample=original
        with self.assertRaisesRegex(ValueError,'epoch_invalidated'):s.observe('producesickle',game_seconds=100/15)
    def test_same_frame_new_queue_and_file_change_reject(self):
        for domain in ('queue','files'):
            self.setUp();s=self.supplier();original=s.core.costs.sample
            def mutate(*a,**kw):
                value=original(*a,**kw)
                if domain=='queue':queue_node(self.mem,self.p,cost=1000,paid=0)
                else:self.files['source']='changed'
                return value
            s.core.costs.sample=mutate
            with self.subTest(domain=domain),self.assertRaises(ValueError):s.observe('producesickle',game_seconds=100/15)
            self.assertEqual(self.file_calls,2);self.assertIsNone(s.last_observation)
    def test_guard_not_callable_payload_and_file_after_expiry_not_retimed(self):
        with self.assertRaisesRegex(ValueError,'trusted_object'):
            guarded.GuardedCostSupplier(self.mem.read,session=self.binding,guard=lambda:None,
                universe=self.universe,product_scope=guarded.RESEARCH_SCOPE)
        original=self.guard.file_check
        def files():
            value=original()
            if self.file_calls==2:self.mem.word(self.p['game']+0x50,116)
            return value
        self.guard.file_check=files;s=self.supplier()
        with self.assertRaisesRegex(ValueError,'candidate_expired'):s.observe('producesickle',game_seconds=100/15)
        self.assertIsNone(s.last_observation)
    def test_file_after_failure_still_calls_fresh_live_and_latches(self):
        s=self.supplier();initial=self.guard.file_check
        def files():
            value=initial()
            if self.file_calls==2:raise ValueError('disk_source_changed')
            return value
        self.guard.file_check=files
        with self.assertRaisesRegex(ValueError,'disk_source_changed'):s.observe('producesickle',game_seconds=100/15)
        self.assertTrue(self.guard.invalidated)
        self.assertEqual(self.guard.metrics[-1]['kind'],'fresh_live_identity')
    def test_live_binding_is_read_again_not_cached(self):
        from dataclasses import replace
        self.guard.live_check();self.guard.native_check=lambda:replace(self.binding,process_creation_filetime=self.binding.process_creation_filetime+1)
        with self.assertRaisesRegex(ValueError,'identity_changed'):self.guard.live_check()
        self.assertTrue(self.guard.invalidated)

    def test_payer_caller_pin_required(self):
        s=self.supplier();self.mem.put(0x7ba807,b'\0')
        with self.assertRaisesRegex(ValueError,'payer_context_signature_changed'):s.observe('producesickle',game_seconds=100/15)

if __name__=='__main__':unittest.main()
