"""Protocol-2 expansion controller, preserving the old thirteen consumers."""
from dataclasses import fields
import math
import uuid

from .contracts import ContractError
from .macro_group_role_scope import GroupRoleScope
from .macro_policy_runtime import COMMANDER, PRESETS
from .macro_regions import MacroRegionalController
from .macro_expansion_scope import ExpansionScope, EXTRA_ACTIONS, TARGETS
from .macro_expansion_feedback import ExpansionFeedback, live_gate
from .resource_reservations import ResourceReservationStore,validate_cost


class MacroExpansionController(MacroRegionalController):
    def __init__(self,transport,scope,session_id,effective_hash,event,*,cost_supplier=None,reservation_store=None):
        if not isinstance(scope,ExpansionScope):raise ContractError('macro_expansion_scope_required')
        # The old controller's production tracker deliberately knows only its
        # original three unit types. A legacy view prevents accidental widening
        # through virtual production_counts while reusing the unchanged code.
        legacy=GroupRoleScope(**{field.name:getattr(scope,field.name) for field in fields(GroupRoleScope)})
        super().__init__(transport,legacy,session_id,effective_hash,event)
        self.expansion_scope=scope;self.expansion_latest=None;self.expansion_tracker=None
        self.expansion_sent={};self.expansion_fingerprints={};self.expansion_plan=None;self.expansion_blocked={}
        self.expansion_prerequisite_revoked=False
        self.cost_supplier=cost_supplier;self.reservation_store=reservation_store;self.expansion_resource_command=None

    def _cost_fact(self,action,game_seconds):
        if (not callable(self.cost_supplier) or type(self.reservation_store) is not ResourceReservationStore
                or self.reservation_store.session_id!=self.session_id):
            raise ContractError('blocked_native_cost_reservation_unverified')
        try:fact=self.cost_supplier(action,self.expansion_latest,game_seconds)
        except Exception:raise ContractError('blocked_native_cost_reservation_unverified') from None
        sample=self.expansion_latest;identity=sample.get('dependency',{}).get('session_identity',{})
        validate_cost(fact,session_id=self.session_id,player_id=3,action=action,template_hash=TARGETS[action][0],
            game_identity=tuple(identity.get(key) for key in ('game','owner','template_factory')),
            producer_ids=tuple(live_gate(action,sample,game_seconds)['producer_ids']),
            game_seconds=game_seconds,component_frames=(sample['observation']['frame'],
                sample['observation']['construction_feedback']['frame'],sample['build_observation']['frame'],
                sample['readiness']['frame'],sample['dependency']['frame']))
        self.reservation_store.can_reserve(fact)
        return fact

    @property
    def sent(self):return {**super().sent,**self.expansion_sent}

    @property
    def expansion_busy(self):return self.expansion_tracker is not None and not self.expansion_tracker.policy_released

    @property
    def busy(self):return super().busy or self.expansion_busy

    def refresh(self,sample):
        super().refresh(sample);self.expansion_latest=sample
        from .macro_live import expansion_component_frames
        try:
            expansion_component_frames(sample)
            if sample.get('expansion_sample_coherent') is False:raise ContractError('macro_expansion_components_unavailable')
        except ContractError:
            self.expansion_latest=None
            if self.expansion_busy:self.expansion_prerequisite_revoked=True
            return
        if self.expansion_tracker:
            flag=self.expansion_scope.expansion_flags[self.expansion_tracker.action]
            self.expansion_tracker.observe(sample,flag)
            self.expansion_prerequisite_revoked=False
            if self.expansion_busy and not self.expansion_tracker.new_queues:
                try:live_gate(self.expansion_tracker.action,sample,max(self.expansion_tracker.frames)/15)
                except ContractError:self.expansion_prerequisite_revoked=True

    def available_actions(self,game_seconds):
        result=super().available_actions(game_seconds);self.expansion_blocked={}
        if self.stopped or self.busy:return result
        for action in self.expansion_scope.expansion_choices:
            try:
                if not callable(self.cost_supplier) or self.reservation_store is None:
                    raise ContractError('blocked_native_cost_reservation_unverified')
                if self.expansion_latest is None:raise ContractError('macro_expansion_components_unavailable')
                live_gate(action,self.expansion_latest,game_seconds)
                self._cost_fact(action,game_seconds)
            except ContractError as error:self.expansion_blocked[action]=error.code
            else:result+=(action,)
        return tuple(dict.fromkeys(result))

    def dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        actions=tuple(getattr(plan,'macro_actions',()))
        work=[action for action in actions if action in EXTRA_ACTIONS]
        if not work:
            if plan is not None and plan.plan_id in self.expansion_sent:raise ContractError('macro_plan_id_conflict')
            return super().dispatch(plan,game_seconds,effective_hash=effective_hash,paused=paused)
        quantity=getattr(plan,'macro_production',None);action=work[0]
        if (self.stopped or paused or effective_hash!=self.effective_hash or plan is None or plan.origin!='model'
                or plan.session_id!=self.session_id or plan.commander_id!=COMMANDER or plan.player_id!=3
                or not plan.based_on_game_time_seconds<=game_seconds<plan.expires_at_game_seconds
                or plan.tactical_tasks or plan.runtime_task is not None or len(work)!=1
                or len(actions)!=len(set(actions)) or len(actions)>2
                or any(item!=action and item not in self.scope.budget.available_actions for item in actions)
                or action not in self.expansion_scope.expansion_choices):
            raise ContractError('macro_expansion_plan_binding_or_qualification')
        if TARGETS[action][2]=='production':
            if (quantity is None or getattr(quantity,'action',None)!=action or type(quantity.additional_count) is not int
                    or quantity.additional_count!=1):raise ContractError('macro_expansion_quantity_not_qualified')
        elif quantity is not None:raise ContractError('macro_expansion_construction_quantity_refused')
        fingerprint=(actions,1 if quantity is not None else None,plan.based_on_game_time_seconds,
                     plan.expires_at_game_seconds,effective_hash)
        if plan.plan_id in self.expansion_sent:
            if fingerprint!=self.expansion_fingerprints[plan.plan_id]:raise ContractError('macro_plan_id_conflict')
            return self.expansion_sent[plan.plan_id]
        if plan.plan_id in super().sent:raise ContractError('macro_plan_id_conflict')
        if action not in self.available_actions(game_seconds):
            raise ContractError(self.expansion_blocked.get(action,'macro_expansion_not_currently_available'))
        tracker=ExpansionFeedback(action,self.expansion_latest,game_seconds)
        duration=max(1,min(600,math.floor((plan.expires_at_game_seconds-game_seconds)*15)))
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':expansion:'+effective_hash))
        fact=self._cost_fact(action,game_seconds)
        self.reservation_store.reserve(plan.plan_id,command_id,fact)
        self.expansion_resource_command=command_id
        try:
            self.event('model_macro_expansion_prepared',plan_id=plan.plan_id,command_id=command_id,
                       actions=list(actions),additional_count=1,duration_frames=duration)
        except Exception:
            self.reservation_store.abort_before_delivery(command_id);raise
        self.reservation_store.delivery_started(command_id)
        try:
            receipt=self.transport.apply(list(actions),duration,command_id)
            tracker.bind_native_window(receipt.get('native_start_frame'),receipt.get('native_deadline_frame'))
            self.reservation_store.acknowledged(command_id,receipt.get('seq'))
        except Exception:
            try:self.reservation_store.delivery_unknown(command_id)
            except Exception:pass
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        self.expansion_tracker=tracker;self.expansion_prerequisite_revoked=False
        self.expansion_plan=(plan.plan_id,min(plan.expires_at_game_seconds,tracker.deadline_frame/15))
        self.budget.current_actions=tuple(item for item in actions if item in PRESETS)
        public=dict(plan_id=plan.plan_id,command_id=command_id,actions=list(actions),additional_count=1,
                    seq=receipt['seq'],native_gate_acknowledged=True,native_effect_verified=False,
                    resource_reservation=self.resource_feedback())
        self.expansion_sent[plan.plan_id]=public;self.expansion_fingerprints[plan.plan_id]=fingerprint
        self.event('model_macro_expansion_acknowledged',**public)
        return public

    def tick(self,game_seconds):
        if not self.expansion_busy:return super().tick(game_seconds)
        if self.stopped:return
        tracker=self.expansion_tracker
        # Ongoing work may outlive its enqueue readiness (e.g. queue now full).
        # Queue acceptance itself releases the preference immediately below.
        if not tracker.release_required and not self.expansion_prerequisite_revoked and game_seconds<self.expansion_plan[1]:return
        reason='queue_target_observed' if tracker.new_queues else 'producer_unavailable' \
            if tracker.eligible!=tracker.baseline_producers else 'prerequisite_changed' \
            if self.expansion_prerequisite_revoked else 'expired'
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),self.expansion_plan[0]+':expansion-release:'+self.effective_hash))
        try:self.transport.apply([],1,command_id)
        except Exception:
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        tracker.mark_policy_released(reason);self.budget.current_actions=()
        self.event('macro_expansion_preference_released',reason_code=reason,feedback=tracker.public())

    def expansion_feedback(self):
        if self.expansion_tracker is None:return None
        value=self.expansion_tracker.public()
        if self.expansion_resource_command is not None:
            value['resource_reservation']=self.reservation_store.public(self.expansion_resource_command)
            value['resource_reservation_verified']=True
        return value

    def resource_feedback(self):
        return self.reservation_store.public(self.expansion_resource_command) if self.expansion_resource_command is not None else None

    def record_resource_fact(self,fact):
        """Trusted backend adapter only; not exposed as a model or UI method."""
        if type(self.reservation_store) is not ResourceReservationStore:
            raise ContractError('blocked_native_cost_reservation_unverified')
        return self.reservation_store.settle(fact)

    def stop(self):
        super().stop()
        if self.expansion_busy:
            self.expansion_tracker.mark_policy_released('stopped')
            self.event('macro_expansion_preference_released',reason_code='stopped',feedback=self.expansion_tracker.public())
