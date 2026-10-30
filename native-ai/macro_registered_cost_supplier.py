"""Explicit registry/live-union research cost supplier, field facts closed."""
import macro_cost_supplier_v2 as baseline
from macro_registered_queue_observation import RegisteredQueueCommitmentObserver

RESEARCH_SCOPE='registry_live_union_owned_production_upgrade_queues_research_v1'


class RegisteredCostSupplier(baseline.StrictNativeCostSupplierV2):
    def __init__(self,read,*,session,identity_reader,universe,product_scope):
        if product_scope!=RESEARCH_SCOPE:raise ValueError('registered_cost_explicit_research_scope_required')
        super().__init__(read,session=session,identity_reader=identity_reader,universe=universe,
            product_scope=baseline.RESEARCH_SCOPE)
        self.payments=RegisteredQueueCommitmentObserver(read,int(session.game_identity[1],0),
            executable_sha256=session.executable_sha256,expected_owner_index=session.player_index)
        self.product_scope=RESEARCH_SCOPE

    def observe(self,action,*,game_seconds,component_frames=()):
        result=super().observe(action,game_seconds=game_seconds,component_frames=component_frames)
        result.update(source='native_registry_live_union_queue_budget_research_observation_v1',
            product_fact_block_reason='blocked_registered_queue_coverage_field_review_pending')
        return result
