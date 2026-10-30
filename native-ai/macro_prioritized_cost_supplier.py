"""Guarded research supplier with a complete prioritized final collect."""
import time
from macro_guarded_cost_supplier import GuardedCostSupplier
from macro_cost_identity_guard import TrustedCostGuard
from macro_prioritized_financial_window import PrioritizedCostCore

RESEARCH_SCOPE='prioritized_guarded_registry_live_union_financial_window_research_v4'

class PrioritizedCostSupplier(GuardedCostSupplier):
    def __init__(self,read,*,session,guard,universe,product_scope):
        if type(guard) is not TrustedCostGuard or guard.session!=session or product_scope!=RESEARCH_SCOPE:
            raise ValueError('cost_guard_explicit_trusted_object_required')
        self.guard=guard;self.raw=read;self.session=session
        from macro_coherent_registered_cost_supplier import RESEARCH_SCOPE as CORE_SCOPE
        self.core=PrioritizedCostCore(read,session=session,identity_reader=guard.live_check,
            universe=universe,product_scope=CORE_SCOPE)
        self.last_observation=None;self.last_partial_observation=None;self.frame_floor=self.core.frame_floor
        self.last_financial_timing=None;operation=self.core.observe
        def timed(*a,**kw):
            start=time.monotonic_ns()
            try:return operation(*a,**kw)
            finally:
                end=time.monotonic_ns();self.last_financial_timing=dict(started_monotonic_ns=start,
                    ended_monotonic_ns=end,elapsed_ms=(end-start)/1000000,includes_pure_file_guards=False)
        self.core.observe=timed
    def observe(self,*args,**kwargs):
        self.last_financial_timing=None
        value=super().observe(*args,**kwargs)
        value=dict(value,source='native_guarded_prioritized_registry_live_union_financial_window_observation_v4',
            schema_version=4,financial_core_timing=self.last_financial_timing)
        self.last_observation=value;return value
