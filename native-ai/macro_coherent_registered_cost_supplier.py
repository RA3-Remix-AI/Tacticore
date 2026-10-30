"""Shared necessary-byte financial window; research facts remain closed."""
import struct
from macro_cost_observation_v2 import NativeCostObserverV2
import macro_cost_supplier as legacy
import macro_registered_cost_supplier as registered
import macro_queue_owner_coverage_contract as lifecycle
import macro_readiness_observation as readiness
import readiness_dependency_contract as dependency

RESEARCH_SCOPE='registry_live_union_shared_financial_window_research_v2'


class _WindowRead:
    def __init__(self,raw,game):self.raw=raw;self.frame_address=game+0x50;self.current=None
    def __call__(self,at,size):
        # Frame is a bounded timestamp, not a price/roster/payment byte. Only
        # this exact scalar bypasses byte equality; the outer <=2-frame check
        # still applies. All other reads share one final revalidation set.
        if self.current is None or (at,size)==(self.frame_address,4):return self.raw(at,size)
        return self.current(at,size)


class CoherentRegisteredCostSupplier:
    def __init__(self,read,*,session,identity_reader,universe,product_scope):
        if product_scope!=RESEARCH_SCOPE:raise ValueError('cost_supplier_coherent_explicit_scope_required')
        legacy._validate_session(session)
        self.session=session;self.raw=read;self.game,self.owner,self.factory=(int(v,0) for v in session.game_identity)
        self.reader=_WindowRead(read,self.game)
        self.delegate=registered.RegisteredCostSupplier(self.reader,session=session,identity_reader=identity_reader,
            universe=universe,product_scope=registered.RESEARCH_SCOPE)
        self.delegate.costs=NativeCostObserverV2(self.reader,self.owner,
            executable_sha256=session.executable_sha256,expected_owner_index=session.player_index)
        self.costs=self.delegate.costs;self.payments=self.delegate.payments
        self.identity_reader=identity_reader;self.product_scope=product_scope
        self.epoch_failed=False;self.last_observation=None;self.last_partial_observation=None
        self.frame_floor=self._frame()
        if not self.frame_floor:raise ValueError('cost_supplier_financial_epoch_not_running')

    def _frame(self):return struct.unpack('<I',readiness._read(self.raw,self.game+0x50,4))[0]

    def _epoch(self):
        if self.epoch_failed:raise ValueError('cost_supplier_financial_epoch_invalidated')
        try:
            observed=self.identity_reader();legacy._validate_session(observed)
            if observed!=self.session:raise ValueError('cost_supplier_financial_session_changed')
            if (readiness._word(self.raw,readiness.GAME_GLOBAL)!=self.game
                    or readiness._word(self.raw,dependency.TEMPLATE_FACTORY_GLOBAL)!=self.factory
                    or readiness._word(self.raw,self.owner)!=readiness.PLAYER_VTABLE
                    or readiness._word(self.raw,self.owner+0x20)!=self.session.player_index):
                raise ValueError('cost_supplier_financial_native_identity_changed')
            frame=self._frame()
            if frame<self.frame_floor or not frame:raise ValueError('cost_supplier_financial_epoch_frame_regressed')
        except Exception:
            self.epoch_failed=True;raise
        self.frame_floor=frame;return frame

    def observe(self,action,*,game_seconds,component_frames=()):
        if self.reader.current is not None:raise ValueError('cost_supplier_financial_nested_window')
        began=self._epoch();outer=dependency.StableRead(self.raw);self.reader.current=outer
        self.last_observation=None;self.last_partial_observation=None
        try:
            contract=lifecycle.verify_owner_lifecycle_contract(self.reader,executable_sha256=self.session.executable_sha256)
            partial=self.delegate.observe(action,game_seconds=game_seconds,component_frames=component_frames)
            # Private failed observations must never masquerade as verified
            # financial facts if final cross-stage revalidation fails.
            self.last_partial_observation=dict(partial,cross_stage_necessary_bytes_revalidated=False,
                product_fact_eligible=False)
            try:outer.finish()
            except ValueError as error:
                if str(error)=='dependency_sample_changed':
                    raise ValueError('cost_supplier_shared_financial_bytes_changed') from None
                raise
            ended=self._epoch()
            if not 0<=ended-began<=2:raise ValueError('cost_supplier_shared_financial_frame_span')
            result=dict(partial,schema_version=2,source='native_registry_live_union_shared_financial_window_observation_v2',
                owner_lifecycle_contract=contract,cross_stage_necessary_bytes_revalidated=True,
                financial_window_frame=began,financial_window_frame_after=ended,
                maximum_financial_window_frame_span=2,shared_financial_cached_ranges=len(outer.copies),
                shared_financial_cached_bytes=sum(size for at,size in outer.copies),
                exact_clock_equality_excluded=dict(address=hex(self.game+0x50),size=4),
                no_future_native_spending_cap=True,product_fact_eligible=False,
                product_fact_block_reason='blocked_coherent_queue_coverage_field_review_pending')
            self.last_observation=result;self.last_partial_observation=None;return result
        except ValueError as error:
            if str(error)=='dependency_sample_changed':
                raise ValueError('cost_supplier_shared_financial_bytes_changed') from None
            raise
        finally:self.reader.current=None

    def __call__(self,action,sample,game_seconds):
        from host_runtime.contracts import ContractError
        if type(sample) is not dict:raise ContractError('blocked_coherent_queue_coverage_field_review_pending')
        frames=[]
        for key in ('observation','build_observation','dependency','readiness'):
            value=sample.get(key)
            if type(value) is dict and 'frame' in value:frames.append(value['frame'])
        self.last_observation=self.observe(action,game_seconds=game_seconds,component_frames=tuple(frames))
        raise ContractError('blocked_coherent_queue_coverage_field_review_pending')
