"""Explicit research supplier for the new GameLogic-live queue scanner.

Uses frozen quote/envelope code; no CurrentQueueBudgetFact is returned until
the new roster/payment coverage obtains independent field qualification.
"""
import macro_cost_supplier as baseline
from macro_payment_observation_v2 import PaymentCommitmentObserverV2

RESEARCH_SCOPE='gamelogic_live_owned_production_upgrade_queues_v2_research'


class StrictNativeCostSupplierV2(baseline.StrictNativeCostSupplier):
    def __init__(self,read,*,session,identity_reader,universe,product_scope):
        if product_scope!=RESEARCH_SCOPE:raise ValueError('cost_supplier_v2_explicit_research_scope_required')
        super().__init__(read,session=session,identity_reader=identity_reader,universe=universe,
            product_scope='current_owned_production_upgrade_queues_v3')
        self.payments=PaymentCommitmentObserverV2(read,int(session.game_identity[1],0),
            executable_sha256=session.executable_sha256,expected_owner_index=session.player_index)
        self.product_scope=RESEARCH_SCOPE

    def observe(self,action,*,game_seconds,component_frames=()):
        result=super().observe(action,game_seconds=game_seconds,component_frames=component_frames)
        result.update(schema_version=2,source='native_gamelogic_live_queue_budget_research_observation_v2',
            field_qualified_complete_queue_coverage=False,product_fact_eligible=False,
            product_fact_block_reason='blocked_payment_v2_field_coverage_unqualified')
        return result

    def _current_queue_fact(self,observation):
        from host_runtime.contracts import ContractError
        raise ContractError('blocked_payment_v2_field_coverage_unqualified')

    def __call__(self,action,sample,game_seconds):
        from host_runtime.contracts import ContractError
        frames=[]
        if type(sample) is not dict:raise ContractError('blocked_payment_v2_field_coverage_unqualified')
        for key in ('observation','build_observation','dependency','readiness'):
            value=sample.get(key)
            if type(value) is dict and 'frame' in value:frames.append(value['frame'])
        census=sample.get('observation',{}).get('construction_feedback')
        if type(census) is dict and 'frame' in census:frames.append(census['frame'])
        self.last_observation=self.observe(action,game_seconds=game_seconds,component_frames=tuple(frames))
        raise ContractError('blocked_payment_v2_field_coverage_unqualified')
