"""Separate schema4 admission controller; old thirteen actions retain their code."""
import math
import uuid
from dataclasses import replace

from .contracts import ContractError
from .macro_expansion_runtime import MacroExpansionController
from .macro_regions import MacroRegionalController
from .macro_expansion_scope import EXTRA_ACTIONS,TARGETS
from .macro_expansion_feedback import ExpansionFeedback,live_gate
from .macro_policy_runtime import COMMANDER,PRESETS
from .macro_expansion_factory_v4 import NativeEvidencePortV4
from .resource_admission_reservations_v4 import AdmissionCostV4,AdmissionReservationStoreV4,validate_cost
from .resource_admission_reconciliation_v4 import work_ack_v4,independent_clear_v4,native_ledger_window_v4,reconciliation_v4
from .macro_admission_delivery_v4 import BeforeNativeRefusalV4,abort_proven_before_native_v4
from .resource_settlement_adapter import digest


class MacroExpansionControllerV4(MacroExpansionController):
    def __init__(self,port,scope,session_id,effective_hash,event,*,cost_supplier=None,financial_supplier=None,reservation_store=None):
        if (type(port) is not NativeEvidencePortV4 or type(reservation_store) is not AdmissionReservationStoreV4
                or reservation_store.session!=port.session or port.session.session_id!=session_id
                or not callable(reservation_store.persist)):
            raise ContractError('macro_admission_v4_trusted_persisted_binding_required')
        consumers=port.manifest.get('consumers');flags=port.manifest['flags']
        if (type(consumers) is not list or len(consumers)!=20 or any(type(row) is not dict for row in consumers)
                or [row.get('flag') for row in consumers]!=flags
                or len({row.get('action') for row in consumers})!=20
                or getattr(scope,'native_transport_protocol',None)!=2 or getattr(scope,'native_transport_client',None)!='client.py'
                or any(sum(row.get('action')==action and row.get('flag')==scope.expansion_flags.get(action) for row in consumers)!=1
                    for action in getattr(scope,'expansion_choices',()))):
            raise ContractError('macro_admission_v4_scope_transport_mismatch')
        super().__init__(port.transport,scope,session_id,effective_hash,event,cost_supplier=None,reservation_store=None)
        self.port=port;self.dispatch_lock=port.lock;self.cost_supplier=cost_supplier;self.financial_supplier=financial_supplier
        self.reservation_store=reservation_store;self.reconciliation_blocked=None

    @property
    def busy(self):
        store=getattr(self,'reservation_store',None)
        return super().busy or type(store) is AdmissionReservationStoreV4 and store.unresolved

    def refresh(self,sample):
        with self.dispatch_lock:return super().refresh(sample)

    def _cost_fact(self,action,game_seconds):
        self.dispatch_lock.require_owned()
        if not callable(self.cost_supplier) or not callable(self.financial_supplier):
            raise ContractError('blocked_native_cost_reservation_unverified')
        if self.reservation_store.unresolved:raise ContractError('macro_admission_v4_active_buffer_unresolved')
        self.port.require_new_work_capacity()
        if self.expansion_latest is None:raise ContractError('macro_expansion_components_unavailable')
        gate=live_gate(action,self.expansion_latest,game_seconds)
        try:fact=self.cost_supplier(action,self.expansion_latest,game_seconds)
        except Exception:raise ContractError('blocked_native_cost_reservation_unverified') from None
        if type(fact) is not AdmissionCostV4 or fact.action!=action:raise ContractError('macro_admission_v4_cost_required')
        identity=self.expansion_latest['dependency']['session_identity']
        if (fact.financial.session!=self.port.session or fact.producer_thing_id not in gate['producer_ids']
                or fact.financial.session.game_identity!=tuple(identity.get(key) for key in ('game','owner','template_factory'))):
            raise ContractError('macro_admission_v4_cost_live_binding_mismatch')
        current=self.port.current_frame()
        validate_cost(fact,self.port.session,current_game_frame=current,now_monotonic_ns=self.port.clock())
        # A complete financial collection can outlive the earlier readiness
        # snapshot. Recheck its actual original frames against the fresh clock.
        live_gate(action,self.expansion_latest,current/15)
        return fact

    def available_actions(self,game_seconds):
        with self.dispatch_lock:
            result=MacroRegionalController.available_actions(self,game_seconds);self.expansion_blocked={}
            if self.stopped or self.busy:return result
            for action in self.expansion_scope.expansion_choices:
                try:self._cost_fact(action,game_seconds)
                except ContractError as error:self.expansion_blocked[action]=error.code
                else:result+=(action,)
            return tuple(dict.fromkeys(result))

    def _plan_duration_at_native_frame(self,plan,current):
        if not plan.based_on_game_time_seconds<=current/15<plan.expires_at_game_seconds:
            raise ContractError('macro_admission_v4_plan_expired_before_native')
        # The relative native command is normally applied on the next game
        # tick. Reserve that tick; the actual ACK deadline is checked as well.
        remaining=math.floor(plan.expires_at_game_seconds*15)-current-1
        if remaining<1:raise ContractError('macro_admission_v4_plan_expired_before_native')
        return min(600,remaining)

    def dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        with self.dispatch_lock:
            actions=tuple(getattr(plan,'macro_actions',()))
            work=[action for action in actions if action in EXTRA_ACTIONS]
            if not work:
                if plan is not None and plan.plan_id in self.expansion_sent:raise ContractError('macro_plan_id_conflict')
                return MacroRegionalController.dispatch(self,plan,game_seconds,effective_hash=effective_hash,paused=paused)
            action=work[0];quantity=getattr(plan,'macro_production',None)
            if (self.stopped or paused or effective_hash!=self.effective_hash or plan is None or plan.origin!='model'
                    or plan.session_id!=self.session_id or plan.commander_id!=COMMANDER or plan.player_id!=3
                    or not plan.based_on_game_time_seconds<=game_seconds<plan.expires_at_game_seconds
                    or plan.tactical_tasks or plan.runtime_task is not None or len(work)!=1
                    or len(actions)!=len(set(actions)) or len(actions)>2
                    or any(item!=action and item not in self.scope.budget.available_actions for item in actions)
                    or action not in self.expansion_scope.expansion_choices):
                raise ContractError('macro_expansion_plan_binding_or_qualification')
            if TARGETS[action][2]=='production':
                if (quantity is None or getattr(quantity,'action',None)!=action or type(quantity.additional_count) is not int or quantity.additional_count!=1):
                    raise ContractError('macro_expansion_quantity_not_qualified')
            elif quantity is not None:raise ContractError('macro_expansion_construction_quantity_refused')
            fingerprint=(actions,1 if quantity is not None else None,plan.based_on_game_time_seconds,plan.expires_at_game_seconds,effective_hash)
            if plan.plan_id in self.expansion_sent:
                if fingerprint!=self.expansion_fingerprints[plan.plan_id]:raise ContractError('macro_plan_id_conflict')
                return self.expansion_sent[plan.plan_id]
            if plan.plan_id in MacroRegionalController.sent.fget(self):raise ContractError('macro_plan_id_conflict')
            if self.busy:raise ContractError('macro_admission_v4_active_buffer_unresolved')
            fact=self._cost_fact(action,game_seconds)
            tracker=ExpansionFeedback(action,self.expansion_latest,game_seconds)
            duration=self._plan_duration_at_native_frame(plan,self.port.current_frame())
            command=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':expansion-v4:'+effective_hash))
            self.reservation_store.reserve(plan.plan_id,command,fact,current_game_frame=self.port.current_frame(),now_monotonic_ns=self.port.clock())
            self.expansion_resource_command=command
            try:
                self.event('model_macro_expansion_prepared',plan_id=plan.plan_id,command_id=command,actions=list(actions),additional_count=1,duration_frames=duration,admission_schema_version=4)
                current=self.port.current_frame()
                duration=self._plan_duration_at_native_frame(plan,current)
                validate_cost(fact,self.port.session,current_game_frame=current,now_monotonic_ns=self.port.clock())
                live_gate(action,self.expansion_latest,current/15)
                self.port.require_new_work_capacity()
            except BaseException:self.reservation_store.abort_before_delivery(command);raise
            self.reservation_store.delivery_started(command)
            try:
                final_event_recorded=False
                def prepare_duration():
                    nonlocal duration
                    duration=self._plan_duration_at_native_frame(plan,self.port.current_frame())
                    return duration
                def last_check(uninvoked):
                    nonlocal final_event_recorded
                    def fresh_gate():
                        frame=self.port.current_frame()
                        if self._plan_duration_at_native_frame(plan,frame)<duration:
                            raise ContractError('macro_admission_v4_plan_window_shortened_before_native')
                        validate_cost(fact,self.port.session,current_game_frame=frame,now_monotonic_ns=self.port.clock())
                        live_gate(action,self.expansion_latest,frame/15)
                        return frame
                    fresh_gate()
                    self.port.require_new_work_capacity(uninvoked_command_id=uninvoked)
                    frame=fresh_gate()
                    if not final_event_recorded:
                        self.event('model_macro_expansion_delivery_prepared',plan_id=plan.plan_id,command_id=command,
                            actions=list(actions),duration_frames=duration,native_frame=frame,admission_schema_version=4)
                        final_event_recorded=True
                        # Event persistence also precedes physical delivery.
                        fresh_gate()
                expected_mask=sum(1<<index for index,row in enumerate(self.port.manifest['consumers']) if row['action'] in actions)
                def exact_raw_ack(prepared,ack,completed):
                    if (prepared.get('command_id')!=command or type(prepared.get('kind_code')) is not int or prepared['kind_code']!=1
                            or type(prepared.get('mask')) is not int or prepared['mask']!=expected_mask
                            or type(prepared.get('duration_frames')) is not int or prepared['duration_frames']!=duration):
                        raise ContractError('macro_admission_v4_requested_native_payload_mismatch')
                    candidate=work_ack_v4(self.port.session,action,self.port.manifest,prepared,ack,completed_monotonic_ns=completed)
                    if candidate.deadline_frame>math.floor(plan.expires_at_game_seconds*15):
                        raise ContractError('macro_admission_v4_native_deadline_exceeds_plan')
                receipt=self.port.guarded_admission_apply(list(actions),duration,command,prepare_duration=prepare_duration,
                    last_check=last_check,raw_ack_check=exact_raw_ack)
                prepared,ack,completed=self.port.known_pair(command,receipt)
                exact_raw_ack(prepared,ack,completed)
                known=work_ack_v4(self.port.session,action,self.port.manifest,prepared,ack,completed_monotonic_ns=completed)
                tracker.bind_native_window(known.start_frame,known.deadline_frame)
                self.reservation_store.acknowledge(known)
            except BeforeNativeRefusalV4 as error:
                abort_proven_before_native_v4(self.reservation_store,error.proof)
                self.event('macro_admission_request_not_delivered',plan_id=plan.plan_id,command_id=command,
                    reason_code=error.proof.reason_code,stage=error.proof.stage,proof_sha256=error.proof.evidence_sha256)
                raise ContractError('macro_admission_v4_refused_before_native') from None
            except BaseException:
                try:self.reservation_store.delivery_unknown(command)
                except BaseException:pass
                self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
            self.expansion_tracker=tracker;self.expansion_prerequisite_revoked=False
            self.expansion_plan=(plan.plan_id,min(plan.expires_at_game_seconds,known.deadline_frame/15))
            self.budget.current_actions=tuple(item for item in actions if item in PRESETS)
            public=dict(plan_id=plan.plan_id,command_id=command,actions=list(actions),additional_count=1,seq=receipt['seq'],
                native_gate_acknowledged=True,native_effect_verified=False,admission_schema_version=4,admission_buffer=self.resource_feedback())
            self.expansion_sent[plan.plan_id]=public;self.expansion_fingerprints[plan.plan_id]=fingerprint
            self.event('model_macro_expansion_acknowledged',**public);return public

    def _clear_preference(self,reason):
        self.dispatch_lock.require_owned();command=self.expansion_resource_command
        if command is None:return
        row=self.reservation_store.rows[command]
        if row['status']!='acknowledged':return
        clear_id=str(uuid.uuid5(uuid.UUID(self.session_id),row['plan_id']+':expansion-v4-clear:'+self.effective_hash))
        try:
            receipt=self.transport.apply([],1,clear_id)
            prepared,ack,completed=self.port.known_pair(clear_id,receipt)
            fact=independent_clear_v4(row['work_ack'],prepared,ack,completed_monotonic_ns=completed)
            self.reservation_store.clear(fact)
        except BaseException:
            try:self.reservation_store.delivery_unknown(command)
            except BaseException:pass
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        if self.expansion_tracker is not None:self.expansion_tracker.mark_policy_released(reason)
        self.budget.current_actions=()
        self.event('macro_expansion_preference_released',reason_code=reason,feedback=self.expansion_feedback())

    def reconcile_active_buffer(self):
        """No native command is sent here; retry only fresh financial observation."""
        with self.dispatch_lock:
            command=self.expansion_resource_command
            if command is None or self.reservation_store.rows[command]['status']!='preference_cleared':return False
            if not callable(self.financial_supplier):
                self.reconciliation_blocked='macro_admission_v4_financial_supplier_unavailable';return False
            row=self.reservation_store.rows[command]
            try:before=self.port.snapshot()
            except Exception:
                self.reservation_store.delivery_unknown(command);self.stopped=True;raise ContractError('macro_admission_v4_ledger_unknown') from None
            try:financial=self.financial_supplier()
            except Exception:
                self.reconciliation_blocked='macro_admission_v4_fresh_financial_state_unavailable';return False
            try:
                after=self.port.snapshot()
                if (before.full_durable!=after.full_durable or before.known_not_invoked_exclusions!=after.known_not_invoked_exclusions
                        or before.full_records!=after.full_records or before.unpublished_record_exclusions!=after.unpublished_record_exclusions):
                    raise ContractError('macro_admission_v4_full_durable_ledger_changed')
                ledger=native_ledger_window_v4(row['work_ack'],row['clear_fact'],self.port.manifest,before.records,after.records,
                    native_before=before.native,flags_before=before.flags,native_after=after.native,flags_after=after.flags,
                    durable_before=before.durable,durable_after=after.durable,
                    started_monotonic_ns=before.started_monotonic_ns,ended_monotonic_ns=after.ended_monotonic_ns)
                ledger=replace(ledger,source_evidence_sha256=digest(dict(verified_native_window=ledger.source_evidence_sha256,
                    full_durable_before=before.full_durable,full_durable_after=after.full_durable,
                    verified_not_invoked_before=before.known_not_invoked_exclusions,verified_not_invoked_after=after.known_not_invoked_exclusions,
                    full_raw_records_before=before.full_records,full_raw_records_after=after.full_records,
                    verified_unpublished_before=before.unpublished_record_exclusions,verified_unpublished_after=after.unpublished_record_exclusions)))
            except Exception:
                self.reservation_store.delivery_unknown(command);self.stopped=True;raise ContractError('macro_admission_v4_ledger_unknown') from None
            try:
                fact=reconciliation_v4(self.reservation_store,command,financial,ledger,
                    current_game_frame=self.port.current_frame(),now_monotonic_ns=self.port.clock())
            except ContractError as error:
                self.reconciliation_blocked=error.code;return False
            self.reconciliation_blocked=None
            self.event('macro_admission_current_state_reconciled',fact_id=fact.fact_id,admission_buffer=self.resource_feedback())
            return True

    def tick(self,game_seconds):
        with self.dispatch_lock:
            command=self.expansion_resource_command
            if command is not None:
                row=self.reservation_store.rows[command]
                if row['status']=='unknown':return
                if row['status']=='preference_cleared':self.reconcile_active_buffer();return
                if row['status']=='acknowledged':
                    tracker=self.expansion_tracker
                    if (not self.stopped and tracker is not None and (tracker.release_required or tracker.policy_released
                            or self.expansion_prerequisite_revoked or game_seconds>=self.expansion_plan[1])):
                        reason='queue_target_observed' if tracker.new_queues else 'producer_unavailable' if tracker.eligible!=tracker.baseline_producers \
                            else 'prerequisite_changed' if self.expansion_prerequisite_revoked else 'expired'
                        self._clear_preference(reason);self.reconcile_active_buffer()
                    return
            return MacroRegionalController.tick(self,game_seconds)

    def expansion_feedback(self):
        if self.expansion_tracker is None:return None
        value=self.expansion_tracker.public()
        value['admission_schema_version']=4
        return value

    def resource_feedback(self):
        if self.expansion_resource_command is None:return None
        value=self.reservation_store.public(self.expansion_resource_command)
        fact=self.reservation_store.rows[self.expansion_resource_command]['reconciliation_fact']
        return dict(value,reconciliation_blocked_reason=self.reconciliation_blocked,
            financial_observation_frames=[fact.financial.frame,fact.financial.frame_after] if fact else None)

    def record_resource_fact(self,fact):raise ContractError('macro_admission_v4_legacy_cash_settlement_api_refused')

    def stop(self,*,reconcile_before_close=True):
        with self.dispatch_lock:
            error=None
            try:
                self._clear_preference('stopped')
                if reconcile_before_close:self.reconcile_active_buffer()
                elif self.expansion_resource_command is not None and self.reservation_store.rows[self.expansion_resource_command]['status']=='preference_cleared':
                    self.reconciliation_blocked='macro_admission_v4_final_stop_reconciliation_not_attempted'
            except BaseException as caught:error=caught
            try:MacroRegionalController.stop(self)
            finally:
                if self.expansion_tracker and not self.expansion_tracker.policy_released:self.expansion_tracker.mark_policy_released('stopped')
            if error is not None:raise error
