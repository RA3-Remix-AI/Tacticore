"""Prioritized coherent research with native active-attribute upper context."""
from macro_prioritized_cost_supplier import PrioritizedCostSupplier,RESEARCH_SCOPE as BASE_SCOPE
from macro_attribute_cost_bound import AttributeBoundCostObserver
RESEARCH_SCOPE='active_attribute_prioritized_financial_upper_research_v5'

class ActiveAttributeCostSupplier(PrioritizedCostSupplier):
    def __init__(self,read,*,session,guard,universe,product_scope):
        if product_scope!=RESEARCH_SCOPE:raise ValueError('attribute_cost_explicit_scope_required')
        super().__init__(read,session=session,guard=guard,universe=universe,product_scope=BASE_SCOPE)
        observer=AttributeBoundCostObserver(self.core.reader,int(session.game_identity[1],0),
            executable_sha256=session.executable_sha256,expected_owner_index=session.player_index)
        self.core.costs=observer;self.core.delegate.costs=observer
    def observe(self,*args,**kwargs):
        value=super().observe(*args,**kwargs)
        value=dict(value,schema_version=5,source='native_coherent_active_attribute_current_upper_research_observation_v5',
            conditional_upper_basis='native_pre_attribute_quote_and_nonincreasing_current_active_attributes',
            native_attribute_upper_context=value['quote']['producer_attribute_evidence']['attribute_upper_context'],
            exact_enqueue_quote_verified=value['quote']['ordinary_unit_enqueue_cost_verified'],
            product_fact_eligible=False,product_fact_block_reason='blocked_active_attribute_upper_field_review_pending')
        self.last_observation=value;return value
