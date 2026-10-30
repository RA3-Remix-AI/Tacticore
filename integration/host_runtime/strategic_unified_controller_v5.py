"""Dispatch high-level domains with durable parent/child records, never NLP."""
import math
import uuid
from contextlib import nullcontext

from .contracts import ContractError
from .macro_policy_runtime import COMMANDER,PRESETS,ratios_match
from .macro_delegation_boundary_v1 import validate_policy
from .strategic_contract_v5 import split_intents,FLAG_ACTIONS,GATE_ACTIONS

class UnifiedStrategicControllerV5:
    def __init__(self,transport,journal,run_id,scope,session_id,effective_hash,event):
        self.transport=transport;self.journal=journal;self.run_id=run_id;self.scope=scope
        self.session_id=session_id;self.effective_hash=effective_hash;self.event=event
        self.sent={};self.fingerprints={};self.current_actions=();self.stopped=False
        self.effects={};self.tracks={};self.current_plan=None;self.last_native=None
        self.last_frame=None;self.native_start=0;self.absolute_deadline=0
        self.delivery_unknown=False;self.action_domain_windows={};self.current_seq=None
    def available_actions(self,game_seconds):return () if self.stopped else tuple(self.scope.available_actions)
    def dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        guard=getattr(self.transport,'stop_batch',None)
        with guard(plan_id=plan.plan_id,effective_hash=effective_hash) if callable(guard) else nullcontext() as admission:
            self._admission=admission
            return self._dispatch(plan,game_seconds,effective_hash=effective_hash,paused=paused)
    def _dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        validate_policy(plan)
        if self.delivery_unknown:raise ContractError('macro_durable_dispatch_already_claimed')
        if self.stopped or paused:raise ContractError('strategic_controller_stopped_or_paused')
        if effective_hash!=self.effective_hash:raise ContractError('macro_profile_revision_changed')
        if (plan.origin!='model' or plan.session_id!=self.session_id or plan.commander_id!=COMMANDER or plan.player_id!=3
                or not plan.based_on_game_time_seconds<=game_seconds<plan.expires_at_game_seconds):raise ContractError('macro_plan_binding_or_expiry')
        actions=tuple(plan.macro_actions)
        if any(a not in self.scope.available_actions for a in actions):raise ContractError('macro_action_not_qualified')
        try:flags,gates=split_intents(actions)
        except ValueError as error:raise ContractError(str(error)) from None
        fingerprint=(actions,plan.based_on_game_time_seconds,plan.expires_at_game_seconds,effective_hash)
        if plan.plan_id in self.sent:
            if self.fingerprints[plan.plan_id]!=fingerprint:raise ContractError('macro_plan_id_conflict')
            return self.sent[plan.plan_id]
        absolute=math.floor(plan.expires_at_game_seconds*15);model_start=math.ceil(plan.based_on_game_time_seconds*15)
        # Stable request bytes come from the original model window. Native
        # clips to its original absolute bound after publication delay.
        duration=max(1,min(900,math.floor((plan.expires_at_game_seconds-plan.based_on_game_time_seconds)*15)))
        parent=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':'+effective_hash))
        admitted={'admission_id':self._admission['admission_id']} if getattr(self,'_admission',None) is not None else {}
        self.event('model_macro_dispatch_prepared',plan_id=plan.plan_id,command_id=parent,actions=list(actions),duration_frames=duration,**admitted)
        reservation=self.journal.reserve_command(self.run_id,parent,'macro_policy',dict(actions=list(actions),plan_id=plan.plan_id,
            native_command_id=parent,duration_frames=duration,not_after_frame=absolute,unit_operation_policy='native_ai',**admitted))
        if not reservation['created']:
            if reservation['status']=='completed':return reservation['receipt']
            raise ContractError('macro_durable_dispatch_already_claimed')
        self.journal.mark_dispatching(self.run_id,parent);children=[];windows={}
        try:
            state=self.transport.native_status()
            for gate in (0,1):
                if gate not in gates and state['gates'][gate]['phase'] in (0,4):continue
                child=str(uuid.uuid5(uuid.UUID(parent),'manager:'+str(gate)))
                payload=dict(parent_command_id=parent,gate=gate,enabled=gates.get(gate),release=gate not in gates,
                    duration_frames=duration,not_after_frame=absolute)
                self._reserve_child(child,payload)
                result=self.transport.manager(gate,gates.get(gate,False),duration,child,not_after_frame=absolute,release=gate not in gates)
                for action,(owned_gate,_) in GATE_ACTIONS.items():
                    if action in actions and owned_gate==gate:
                        windows[action]=self._receipt_window(result,action,absolute,model_start)
                self.journal.record_outcome(self.run_id,child,'completed',dict(seq=result['seq'],native_gate_acknowledged=True,native_effect_verified=False))
                children.append(result)
            child=str(uuid.uuid5(uuid.UUID(parent),'flags'))
            self._reserve_child(child,dict(parent_command_id=parent,actions=list(flags),duration_frames=duration,not_after_frame=absolute))
            result=self.transport.apply(list(flags),duration,child,not_after_frame=absolute)
            for action in flags:windows[action]=self._receipt_window(result,action,absolute,model_start)
            self.journal.record_outcome(self.run_id,child,'completed',dict(seq=result['seq'],native_gate_acknowledged=True,native_effect_verified=False));children.append(result)
        except BaseException as error:
            self.delivery_unknown=True
            try:self.journal.record_outcome(self.run_id,child,'uncertain',dict(reason_code='strategic_child_outcome_unverified'))
            except BaseException:pass
            self.journal.record_outcome(self.run_id,parent,'uncertain',dict(reason_code='strategic_batch_not_fully_verified',known_children=len(children)))
            raise ContractError('macro_dispatch_outcome_unknown') from error
        end=self.transport.native_status();start=max(r['native']['last_frame'] for r in children)
        receipt=dict(command_id=parent,plan_id=plan.plan_id,actions=list(actions),seq=children[-1]['seq'],
            native_gate_acknowledged=True,native_effect_verified=False,
            native_start_frame=min((w['start_frame'] for w in windows.values()),default=start),
            native_deadline_frame=max((w['end_frame'] for w in windows.values()),default=start),
            native_window_semantics='owned_domain_envelope_not_continuous_per_action',
            action_domain_windows=windows,child_sequences=[r['seq'] for r in children])
        self.journal.record_outcome(self.run_id,parent,'completed',receipt)
        self.sent[plan.plan_id]=receipt;self.fingerprints[plan.plan_id]=fingerprint
        self.current_actions=actions;self.current_plan=plan.plan_id;self.last_native=end
        self.native_start=receipt['native_start_frame'];self.absolute_deadline=receipt['native_deadline_frame']
        self.action_domain_windows=windows;self.current_seq=receipt['seq']
        self.event('macro_policy_acknowledged',**receipt);return receipt
    @staticmethod
    def _receipt_window(receipt,action,model_end,model_start):
        # These are actual independently verified child ACK projections. Never
        # infer an effective deadline from duration/request/model expiry alone.
        try:
            native=receipt['native'];seq=receipt['seq'];start=native['last_frame']
            if (receipt['native_gate_acknowledged'] is not True
                    or type(seq) is not int or seq<=0 or type(start) is not int or start<=0
                    or any(type(native[k]) is not int for k in ('phase','active','error','request','ack'))
                    or (native['phase'],native['active'],native['error'],native['request'],native['ack'])!=(1,0,0,seq,seq)):
                raise ValueError('unverified child')
            if action in GATE_ACTIONS:
                gate,desired=GATE_ACTIONS[action];state=native['gates'][gate]
                indices=(0,) if gate==0 else (1,2)
                if (type(state['phase']) is not int or state['phase']!=1
                        or type(state['frame']) is not int or not 0<state['frame']<=start
                        or any(type(state[k]) is not int or state[k]!=int(desired)
                               for k in ('requested_enabled','operation_enabled'))
                        or any(type(state['observed'][i]) is not int or state['observed'][i]!=int(desired) for i in indices)):
                    raise ValueError('unverified manager domain')
                deadline=state['deadline_frame'];domain='base_builder' if gate==0 else 'production_family'
            else:
                bit=1<<FLAG_ACTIONS.index(action)
                if (type(native['flag_phase']) is not int or native['flag_phase']!=1
                        or type(native['applied_mask']) is not int or not native['applied_mask']&bit):
                    raise ValueError('unverified flags domain')
                deadline=native['flag_deadline'];domain='flags'
            begin=max(start,model_start)
            if type(deadline) is not int or not begin<min(deadline,model_end)<=0xffffffff:
                raise ValueError('missing/expired child deadline')
            return dict(domain=domain,child_seq=seq,start_frame=begin,end_frame=min(deadline,model_end),
                native_start_frame=start,native_deadline_frame=deadline,model_start_frame=model_start,model_deadline_frame=model_end,
                start_basis='child_ack_last_frame_conservative_intersect_model',end_basis='verified_child_deadline_intersect_model')
        except (KeyError,IndexError,TypeError,ValueError):
            raise ContractError('strategic_child_domain_window_unverified') from None

    def _domain_active(self,action,frame,native):
        window=self.action_domain_windows.get(action)
        if (window is None or self.delivery_unknown or type(frame) is not int
                or not window['start_frame']<=frame<window['end_frame']
                or any(type(native.get(k)) is not int for k in ('phase','active','error','request','ack'))
                or (native['phase'],native['active'],native['error'])!=(1,0,0)
                or native['request']!=native['ack'] or native['ack']!=self.current_seq):return False
        if action in GATE_ACTIONS:
            gate,desired=GATE_ACTIONS[action];state=native['gates'][gate]
            return (type(state.get('phase')) is int and state['phase']==1
                and type(state.get('deadline_frame')) is int
                and state['deadline_frame']==window['native_deadline_frame'])
        return (type(native.get('flag_phase')) is int and native['flag_phase']==1
            and type(native.get('flag_deadline')) is int and native['flag_deadline']==window['native_deadline_frame']
            and type(native.get('applied_mask')) is int and bool(native['applied_mask']&(1<<FLAG_ACTIONS.index(action))))

    def _domain_released(self,action,native):
        # Expiry/unknown is not evidence of physical preference restoration.
        if (action not in self.action_domain_windows or self.delivery_unknown
                or any(type(native.get(k)) is not int for k in ('phase','active','error','request','ack'))
                or (native['phase'],native['active'],native['error'])!=(1,0,0)
                or native['request']!=native['ack'] or native['ack']!=self.current_seq):return False
        if action in GATE_ACTIONS:
            state=native['gates'][GATE_ACTIONS[action][0]]
            return type(state.get('phase')) is int and state['phase'] in (0,4)
        return (type(native.get('flag_phase')) is int and native['flag_phase']==4
            and type(native.get('applied_mask')) is int and not native['applied_mask']&(1<<FLAG_ACTIONS.index(action)))

    def _reserve_child(self,ident,payload):
        value=self.journal.reserve_command(self.run_id,ident,'native_strategic_v5',payload)
        if not value['created']:raise ContractError('strategic_child_already_claimed')
        self.journal.mark_dispatching(self.run_id,ident)
    def tick(self,game_seconds):return None
    def observe(self,observation,native,controls):
        if observation.get('observation_complete') is not True:return False
        self.last_native=native;frame=observation['frame'];self.last_frame=max(frame,controls['frame']);effects={}
        for runtime in observation.get('runtimes',[]):
            if not runtime.get('authoritative_runtime_membership_verified') or not runtime.get('native_execution_active') or runtime.get('cleanup_requested'):continue
            flag=runtime['flag'];action=next((a for a,f in self.scope.action_flags.items() if f==flag),None)
            if (action is None or action not in self.current_actions or not self._domain_active(action,frame,native)
                    or not self._domain_active(action,controls['frame'],native)):continue
            moved=False;members=0
            for group in runtime.get('owned_groups',[]):
                if not group.get('found') or not group.get('all_members_resolved'):continue
                for member in group.get('members',[]):
                    key=(self.current_plan,action,runtime['address'],group['native_id'],member['thing_id']);position=member['xyz'];members+=1
                    first=self.tracks.setdefault(key,tuple(position))
                    moved|=math.dist(first,position)>=10
            effects[action]=dict(action=action,status='native_task_active',observed_frame=frame,
                active_native_task_observed=True,owned_members_resolved=members>0,movement_observed=moved,
                mission_success_verified=False,policy_released=False)
        for action,(gate,desired) in GATE_ACTIONS.items():
            state=native['gates'][gate]
            indices=(0,) if gate==0 else (1,2)
            if (action in self.current_actions and self._domain_active(action,controls['frame'],native)
                    and self._domain_active(action,self.last_frame,native)
                    and state['phase']==1 and all(controls['components'][i]['enabled']==int(desired) for i in indices)):
                effects[action]=dict(action=action,status='native_manager_state_observed',observed_frame=controls['frame'],
                    component_state_adopted=True,physical_api_attempts=state['attempted'],state_already_satisfied=bool(state['already_satisfied']),
                    construction_or_production_completion_verified=False,policy_released=False)
        self.effects=effects;return True
    def feedback(self,observation):
        budget=observation.get('budget_feedback') or {};selected=next((a for a in PRESETS if self.scope.action_flags.get(a)==budget.get('selected_macro_flag')),None)
        desired=next((a for a in self.current_actions if a in PRESETS),None)
        active=(desired is not None and self.last_native is not None
            and self._domain_active(desired,observation['frame'],self.last_native)
            and self._domain_active(desired,self.last_frame,self.last_native))
        adopted=active and selected==desired and ratios_match(budget.get('account_shares'),PRESETS[desired])
        status='native_budget_adopted' if adopted else 'native_budget_pending' if active else 'native_budget_clearing' if selected else 'native_delegation_observed'
        return dict(status=status,actions=[desired] if active else [],selected_policy=selected,
            observed_frame=observation['frame'],native_effect_verified=adopted,payment_verified=False)
    def unified_feedback(self):
        if self.last_frame is None:return None
        native=self.last_native;rows=[]
        for action in self.current_actions:
            active=self._domain_active(action,self.last_frame,native)
            facts=self.effects.get(action,{}) if active else {}
            rows.append(dict(action=action,preference_active=active,
                observed_frame=facts.get('observed_frame',self.last_frame),
                status=facts.get('status','preference_released' if not active and self._domain_released(action,native) else 'native_waiting_or_no_effect'),
                active_native_task_observed=bool(facts.get('active_native_task_observed')),
                movement_observed=bool(facts.get('movement_observed')),
                component_state_adopted=bool(facts.get('component_state_adopted')),
                state_already_satisfied=bool(facts.get('state_already_satisfied')),
                mission_success_verified=False,exclusive_attribution_verified=False))
        return dict(source='bound_native_strategy_v5',observed_frame=self.last_frame,details_owner='native_ai',
            observations=rows,no_active_task_is_waiting_not_success=True)
    def stop(self):
        self.stopped=True;self.transport.close()
