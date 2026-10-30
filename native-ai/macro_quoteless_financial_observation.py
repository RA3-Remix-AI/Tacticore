"""Complete current owned queue/cash window, independent of all producers.

No action, target template, quote, attribute or uniqueness gate is involved.
This module never opens a process, calls native functions, reserves or dispatches.
"""
import hashlib
import json
import struct
import time
import macro_cost_observation as cash
import macro_cost_supplier as binding
import macro_readiness_observation as readiness
import readiness_dependency_contract as dependency
import macro_queue_owner_coverage_contract as lifecycle
from macro_registered_queue_observation import RegisteredQueueCommitmentObserver
from macro_prioritized_financial_window import OrderedStableRead
from macro_coherent_registered_cost_supplier import _WindowRead
from macro_cost_identity_guard import TrustedCostGuard
from macro_guarded_cost_supplier import verify_payer_pins
from read_selected_personality import inspect_player

SOURCE='native_quoteless_complete_current_queue_cash_observation_v4'

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class QuotelessFinancialObserver:
    def __init__(self,read,*,session,guard):
        binding._validate_session(session)
        if type(guard) is not TrustedCostGuard or guard.session!=session:
            raise ValueError('quoteless_finance_trusted_guard_required')
        cash.verify_pins(read,session.executable_sha256)
        for at,raw in ((0x8d5727,'89beb0080000'),(0x844a3f,'898690000000')):
            if readiness._read(read,at,len(bytes.fromhex(raw)))!=bytes.fromhex(raw):
                raise ValueError('quoteless_finance_personality_layout_signature_changed')
        self.session=session;self.raw=read;self.guard=guard
        self.game,self.owner,self.factory=(int(v,0) for v in session.game_identity)
        self.window=_WindowRead(read,self.game)
        self.base=readiness.ReadinessObserver(self.window,self.owner,
            executable_sha256=session.executable_sha256,expected_owner_index=3)
        self.payments=RegisteredQueueCommitmentObserver(self.window,self.owner,
            executable_sha256=session.executable_sha256,expected_owner_index=3)
        if self.base.game!=self.game or self.payments.factory!=self.factory:
            raise ValueError('quoteless_finance_initial_native_identity')
        self.frame_floor=0;self.last_observation=None;self.last_partial_observation=None;self.last_raw_manifest=None
        self._epoch()
    def _frame(self):return struct.unpack('<I',readiness._read(self.raw,self.game+0x50,4))[0]
    def _epoch(self):
        try:
            self.guard.live_check()
            if (readiness._word(self.raw,readiness.GAME_GLOBAL)!=self.game
                    or readiness._word(self.raw,self.owner)!=readiness.PLAYER_VTABLE
                    or readiness._word(self.raw,self.owner+0x20)!=3
                    or readiness._word(self.raw,dependency.TEMPLATE_FACTORY_GLOBAL)!=self.factory):
                raise ValueError('quoteless_finance_native_identity_changed')
            frame=self._frame()
            if not frame or frame<self.frame_floor:raise ValueError('quoteless_finance_epoch_frame_regressed')
            self.frame_floor=frame;return frame
        except Exception:self.guard.invalidated=True;raise
    def observe(self):
        if self.window.current is not None:raise ValueError('quoteless_finance_nested_window')
        self.last_observation=None;self.last_partial_observation=None;self.last_raw_manifest=None
        token=self.guard.begin();result=None;error=None;started=None;ended=None
        try:
            before=self._epoch();started=time.monotonic_ns();outer=OrderedStableRead(self.raw);self.window.current=outer
            contract=lifecycle.verify_owner_lifecycle_contract(self.window,executable_sha256=self.session.executable_sha256)
            verify_payer_pins(self.window)
            native=inspect_player(self.window,self.owner)
            if native['player_index']!=3 or native['instance_id']!='0x799613e0':raise ValueError('quoteless_finance_wrong_personality')
            queues=self.payments.sample()
            cash_before=readiness._word(self.window,self.game+0x50)
            balance=cash.NativeCostObserver._credits(self,self.window)
            cash_after=readiness._word(self.window,self.game+0x50)
            if balance.get('credits_verified') is not True:raise ValueError('quoteless_finance_cash_unknown')
            for queue in queues['queues']:
                for node in queue['nodes']:
                    outer.mark_priority(int(node['node'],0)+0x68,4,label='native_paid')
                    outer.mark_priority(int(node['node'],0)+0x30,4,label='native_queue_cost')
            account=int(balance['account'],0)
            for offset in (4,0x14):outer.mark_priority(account+offset,4,label='native_payment_balance')
            self.last_partial_observation=dict(queues=queues,balance=balance,verified=False)
            outer.finish();after=self._epoch();ended=time.monotonic_ns()
            components=(queues['frame'],queues['frame_after'],cash_before,cash_after)
            if not 0<=after-before<=2 or any(not before<=frame<=after for frame in components):
                raise ValueError('quoteless_finance_frame_span')
            manifest=[dict(address=hex(at),size=size,first_raw_hex=raw.hex(),final_equal=True)
                for (at,size),raw in outer.copies.items()]
            self.last_raw_manifest=manifest
            result=dict(kind='current_own_production_upgrade_cash_financial_window',schema_version=4,source=SOURCE,
                session_id=self.session.session_id,pid=self.session.pid,process_creation_filetime=self.session.process_creation_filetime,
                executable_sha256=self.session.executable_sha256,package_sha256=self.session.package_sha256,
                game_identity=self.session.game_identity,native_profile=native,
                frame=before,frame_after=after,component_frames=components,
                started_monotonic_ns=started,ended_monotonic_ns=ended,
                credits=balance['credits'],production_upgrade_commitment_upper_bound=queues['production_queue_payment_commitment_upper_bound'],
                payment_balance=balance,queue_commitments=queues,owner_lifecycle_contract=contract,
                financial_collection=outer.metadata(),necessary_raw_manifest_sha256=digest(manifest),
                action_required=False,unique_producer_required=False,price_or_attribute_context_required=False,
                no_future_or_latent_work_coverage=True,product_admission_authority_granted=False)
        except Exception as caught:error=caught
        finally:
            self.window.current=None
            try:
                proof=self.guard.finish(token);guard_frame=self._epoch()
                if result is not None and not 0<=guard_frame-result['frame_after']<=15:
                    raise ValueError('quoteless_finance_after_guard_expired')
            except Exception as caught:error=caught
        if error is not None:raise error
        result.update(file_guard=proof,guard_verified_current_frame=guard_frame)
        self.last_observation=result;self.last_partial_observation=None;return result
