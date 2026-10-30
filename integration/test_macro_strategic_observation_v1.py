"""Real Host/controller flow with synthetic, read-only native observations."""
import asyncio
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'strategy'),str(ROOT/'native-ai'),str(ROOT)]
import test_macro_delegation_independent_v1 as independent
from test_macro_optional_builder_gap_v1 import artificial
from host_runtime import test_macro_regions as regional
from host_runtime.contracts import ContractError
from host_runtime.macro_durable import DurableMacroTransport
from host_runtime.macro_policy_runtime import MacroRequestAudit
from host_runtime.macro_strategic_observation_v1 import (
    bind_strategic_transport_v1,validate_strategic_observation_v1,KIND)
from fixtures import SESSION


def transport_facts(transport,protocol=2):
    sample,args=artificial();sample.pop('build_observation_error')
    state=args['native_state'];identity=args['native_identity']
    state.update(version=protocol,magic=0x4d503032 if protocol==2 else 0x4d504f4c)
    names=args['flag_names'][:20 if protocol==2 else 13]
    flags=dict(flags=args['flags']['flags'][:len(names)])
    transport.native_status=lambda:copy.deepcopy(state)
    transport.owner=identity['owner'];transport.native=sample['observation']['native']
    transport.creation=identity['process_creation_filetime']
    transport.memory=SimpleNamespace(u32=lambda address:identity['engine'],read=lambda *a:None)
    transport.manifest=dict(protocol_version=protocol,flags=list(names),consumers=[
        dict(action=action,flag=names[index]) for index,action in enumerate(('budgetarmy','scout','deployattack'))])
    transport.pending=False;transport.ledger={}
    session=dict(pid=identity['pid'],process_creation_filetime=identity['process_creation_filetime'])
    binding=bind_strategic_transport_v1(transport,session)
    return sample,args['lawful_view'],state,flags,binding


class StrategicObservationTests(unittest.TestCase):
    def test_both_existing_protocols_bind_without_builder_or_new_capabilities(self):
        for protocol in (1,2):
            sample,view,state,flags,binding=transport_facts(SimpleNamespace(),protocol)
            self.assertEqual(validate_strategic_observation_v1(sample,view,state,flags,binding),(1500,1500))
            self.assertNotIn('build_observation',sample)

    def test_real_host_model_journal_and_final_dispatch_use_no_builder(self):
        for protocol in (1,2):
            for action in ('budgetarmy','scout','deployattack'):
                with self.subTest(protocol=protocol,action=action):
                    outer=independent.StrategicDelegationIndependentTests();case=outer.case();self.addCleanup(outer.doCleanups)
                    host=case.host();controller=regional.RegionalControllerTests();controller.setUp()
                    host.controller=controller.controller;host.controller.session_id=SESSION;host.controller.budget.session_id=SESSION
                    durable=DurableMacroTransport(host.transport,host.journal,host.run_id)
                    host.controller.transport=durable;host.controller.budget.transport=durable
                    host.sampler=SimpleNamespace(scope=controller.scope)
                    sample,host.latest,state,flags,host.strategic_transport_binding=transport_facts(host.transport,protocol)
                    with patch('read_script_flags.inspect_flags',return_value=flags):
                        self.assertTrue(host.consume_observation(sample))
                    self.assertEqual(host.capability_sample_kind,KIND)
                    self.assertIsNone(host.last_infrastructure)
                    self.assertEqual(host.latest['macro_control']['production_counts'],{})
                    calls=[]
                    async def model(context):
                        calls.append(context);value=independent.base.model_policy(context)
                        value.update(macro_actions=[action],objective_region='region_1_3' if action=='deployattack' else None)
                        return value
                    audit=MacroRequestAudit(model,lambda *a,**k:None,strategic_only=True)
                    decision=asyncio.run(host.agent.decide(host.latest,audit))
                    self.assertEqual(decision.status,'accepted',decision.reason_code)
                    self.assertTrue(host.dispatch_plan(decision.plan))
                    self.assertEqual(host.transport.calls[0][0],[action])
                    self.assertEqual(host.journal.commands_for_run(host.run_id)[0]['status'],'completed')
                    self.assertNotIn('macro_production_feedback',calls[0])

    def test_identity_unknown_precision_and_flags_fail_closed(self):
        mutations=(lambda s,v,n,f:n.update(pid=999),lambda s,v,n,f:n.update(ack=1),
                   lambda s,v,n,f:n.update(applied_mask=1<<12),lambda s,v,n,f:n.update(lease_held=0),
                   lambda s,v,n,f:f['flags'][0].update(present=True,value=True),
                   lambda s,v,n,f:s.update(read_error='signature_changed'),
                   lambda s,v,n,f:s['observation']['native'].update(player='0x99'),
                   lambda s,v,n,f:v['battlefield'].update(visibility_verified=False))
        for mutate in mutations:
            sample,view,native,flags,binding=transport_facts(SimpleNamespace())
            mutate(sample,view,native,flags)
            with self.assertRaises(ContractError):validate_strategic_observation_v1(sample,view,native,flags,binding)

    def test_explicit_builder_and_queue_race_are_not_a_strategic_sample(self):
        for key,value in (('build_observation',{}),('build_observation_error','macro_builder_queue_changed')):
            sample,view,native,flags,binding=transport_facts(SimpleNamespace());sample[key]=value
            with self.assertRaises(ContractError):validate_strategic_observation_v1(sample,view,native,flags,binding)

    def test_sequential_clock_or_callback_defers_without_retiming(self):
        for key,value in (('active',1),('last_frame',1450)):
            sample,view,native,flags,binding=transport_facts(SimpleNamespace());native[key]=value
            self.assertIsNone(validate_strategic_observation_v1(sample,view,native,flags,binding))
            self.assertEqual(sample['observation']['frame'],1500)

    def test_binding_is_not_recreated_from_current_native_identity(self):
        transport=SimpleNamespace();sample,view,native,flags,binding=transport_facts(transport)
        native['engine']=999
        with self.assertRaises(ContractError):validate_strategic_observation_v1(sample,view,native,flags,binding)
        transport.native_status=lambda:native
        with self.assertRaises(ContractError):bind_strategic_transport_v1(transport,dict(pid=101,process_creation_filetime=transport.creation))

    def test_strategic_audit_never_calls_precise_suppliers_before_filtering(self):
        def forbidden():
            self.fail('strategic mode requested historical precise telemetry')
        outer=independent.StrategicDelegationIndependentTests();case=outer.case();self.addCleanup(outer.doCleanups)
        audit=MacroRequestAudit(lambda context:None,lambda *a,**k:None,strategic_only=True,
            production_supplier=forbidden,construction_supplier=forbidden,infrastructure_supplier=forbidden,
            expansion_supplier=forbidden,resource_supplier=forbidden)
        self.assertTrue(audit.fresh_for_game_seconds(case.view['game_time_seconds']))
        case.agent.observe(case.view)
        context=case.agent.context(case.agent.latest.model_context(case.agent.engine.binding),commit=False)
        result=audit.prepare(context)
        self.assertNotIn('own_infrastructure',result)
        self.assertNotIn('macro_resource_feedback',result)


if __name__=='__main__':unittest.main()
