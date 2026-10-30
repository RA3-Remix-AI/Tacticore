"""Memoized first collect and complete priority-ordered final collect.

Safety remains conditional on the same undetected-ABA limitation as ordinary
read/recheck snapshots. This does not promise future native spending bounds.
"""
import time
import macro_coherent_registered_cost_supplier as baseline
from macro_coherent_registered_cost_supplier import lifecycle,readiness,dependency

class OrderedStableRead:
    def __init__(self,read):
        self.read=read;self.copies={};self.bytes_seen={};self.priority=[]
        self.phase='collecting';self.cache_hits=0;self.final_order=[];self.first_collect_error=None
        self.collect_closed_ns=None;self.final_started_ns=None;self.final_ended_ns=None
    def __call__(self,at,size):
        if self.phase!='collecting':raise ValueError('financial_collection_phase_sealed')
        key=(at,size)
        if key in self.copies:self.cache_hits+=1;return self.copies[key]
        if len(self.copies)>=16000:
            self.phase='failed';self.first_collect_error='range_bound';raise ValueError('dependency_sample_read_bound')
        try:
            raw=readiness._read(self.read,at,size)
            for index,value in enumerate(raw):
                previous=self.bytes_seen.get(at+index)
                if previous is not None and previous!=value:raise ValueError('financial_first_collect_overlap_changed')
        except Exception as error:
            self.phase='failed'
            self.first_collect_error='overlap_conflict' if str(error)=='financial_first_collect_overlap_changed' else 'first_read_failed'
            raise
        for index,value in enumerate(raw):self.bytes_seen[at+index]=value
        self.copies[key]=raw;return raw
    def mark_priority(self,at,size,*,label):
        if self.phase!='collecting':raise ValueError('financial_collection_phase_sealed')
        if type(at) is not int or type(size) is not int or size<=0:
            raise ValueError('financial_priority_range')
        if not any(start<=at and at+size<=start+length for start,length in self.copies):
            raise ValueError('financial_priority_range_not_collected')
        self.priority.append((at,size,label))
    def finish(self):
        if self.phase!='collecting':raise ValueError('financial_collection_phase_sealed')
        self.phase='finalizing';self.collect_closed_ns=time.monotonic_ns()
        def priority(key):
            at,size=key
            return 0 if any(at<p+n and p<at+size for p,n,label in self.priority) else 1
        ordered=sorted(self.copies,key=priority)
        self.final_started_ns=time.monotonic_ns()
        try:
            for at,size in ordered:
                raw=readiness._read(self.read,at,size);self.final_order.append((at,size))
                if raw!=self.copies[at,size]:raise ValueError('dependency_sample_changed')
        except Exception:self.phase='failed';raise
        finally:self.final_ended_ns=time.monotonic_ns()
        self.phase='finished'
    def metadata(self):
        return dict(source='memoized_exact_ranges_complete_priority_final_collect_v1',phase=self.phase,
            first_collect_actual_range_count=len(self.copies),cache_hit_count=self.cache_hits,
            final_collect_actual_range_count=len(self.final_order),final_collect_all_ranges_verified=self.phase=='finished',
            exact_first_range_set_equals_final_range_set=set(self.copies)==set(self.final_order),
            collect_closed_monotonic_ns=self.collect_closed_ns,final_started_monotonic_ns=self.final_started_ns,
            final_ended_monotonic_ns=self.final_ended_ns,
            marked_priority_ranges=[dict(address=hex(a),size=s,label=l) for a,s,l in self.priority],
            all_first_reads_complete_before_any_final_read=self.collect_closed_ns is not None,
            overlapping_first_bytes_consistent=self.first_collect_error is None,first_collect_error=self.first_collect_error,
            undetected_ABA_excluded_by_assumption=True)

class PrioritizedCostCore(baseline.CoherentRegisteredCostSupplier):
    def observe(self,action,*,game_seconds,component_frames=()):
        if self.reader.current is not None:raise ValueError('cost_supplier_financial_nested_window')
        began=self._epoch();outer=OrderedStableRead(self.raw);self.reader.current=outer
        self.last_observation=None;self.last_partial_observation=None
        try:
            contract=lifecycle.verify_owner_lifecycle_contract(self.reader,executable_sha256=self.session.executable_sha256)
            partial=self.delegate.observe(action,game_seconds=game_seconds,component_frames=component_frames)
            # Private failed observations must never masquerade as verified
            # financial facts if final cross-stage revalidation fails.
            self.last_partial_observation=dict(partial,cross_stage_necessary_bytes_revalidated=False,
                product_fact_eligible=False)
            for queue in partial['queue_commitments']['queues']:
                for node in queue['nodes']:
                    outer.mark_priority(int(node['node'],0)+0x68,4,label='native_paid')
                    outer.mark_priority(int(node['node'],0)+0x30,4,label='native_queue_total_cost')
            account=partial['quote']['current_payment_balance'].get('account')
            if account is not None:
                outer.mark_priority(int(account,0)+4,4,label='native_primary_credits')
                outer.mark_priority(int(account,0)+0x14,4,label='native_additional_credits')
            try:outer.finish()
            except ValueError as error:
                if str(error)=='dependency_sample_changed':
                    raise ValueError('cost_supplier_shared_financial_bytes_changed') from None
                raise
            ended=self._epoch()
            if not 0<=ended-began<=2:raise ValueError('cost_supplier_shared_financial_frame_span')
            result=dict(partial,schema_version=4,source='native_prioritized_registry_live_union_financial_window_observation_v4',
                owner_lifecycle_contract=contract,cross_stage_necessary_bytes_revalidated=True,
                financial_collection=outer.metadata(),
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

