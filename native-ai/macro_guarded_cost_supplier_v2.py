"""Unchanged guarded semantics with exact core-only monotonic timings."""
import time
from macro_guarded_cost_supplier import GuardedCostSupplier,RESEARCH_SCOPE

class GuardedCostSupplierV2(GuardedCostSupplier):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.last_financial_timing=None
        operation=self.core.observe
        def timed(*a,**kw):
            start=time.monotonic_ns()
            try:return operation(*a,**kw)
            finally:
                end=time.monotonic_ns()
                self.last_financial_timing=dict(started_monotonic_ns=start,ended_monotonic_ns=end,
                    elapsed_ms=(end-start)/1000000,includes_pure_file_guards=False)
        self.core.observe=timed
    def observe(self,*args,**kwargs):
        self.last_financial_timing=None
        value=super().observe(*args,**kwargs)
        value=dict(value,financial_core_timing=self.last_financial_timing)
        self.last_observation=value;return value
