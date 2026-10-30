"""Bind declared strategy to actual dispatch receipts and bounded native facts.

This adapter never selects an action or relaxes the existing native controller.
Acknowledgement establishes delivery only; separately sampled facts establish
bounded effects, and current native state or verified replacement establishes release.
"""
from dataclasses import dataclass

from .contracts import ContractError

@dataclass
class _Tracked:
    plan_id:str
    command_id:str
    actions:tuple
    started:float
    expires:float
    seq:int
    had_effect:bool=False
    released:bool=False
    unknown:bool=False
    native_window_verified:bool=False
    budget_observed:bool=False
    model_expires:float=0

class MacroStrategyRuntime:
    def __init__(self,memory,event):
        self.memory=memory;self.event=event;self.commands={};self.last_ack_sequence=0

    def _outcome(self,row,outcome,at,*,seen=None,reason='observed',released=False):
        from macro_strategy import StrategyError
        try:self.memory.record_outcome(command_id=row.command_id,plan_id=row.plan_id,
            outcome=outcome,game_seconds=at,observed_game_seconds=seen,
            effect_verified=seen is not None,release_verified=released,reason_code=reason)
        except StrategyError as error:raise ContractError(str(error)) from None
        if seen is not None:row.had_effect=True
        if released:row.released=True
        self.event('macro_strategy_outcome',plan_id=row.plan_id,command_id=row.command_id,
            outcome=outcome,reason_code=reason,observed_game_seconds=seen,
            native_release_verified=released,effect_observed=row.had_effect)

    def review(self,plan,audit,latest_context):
        from macro_strategy import StrategyError
        try:result=self.memory.review(plan,plan.macro_strategy,audit.request_context_for(plan),latest_context)
        except StrategyError as error:raise ContractError(str(error)) from None
        self.event('macro_strategy_review',plan_id=plan.plan_id,strategy_id=result.strategy_id,
            allowed=result.allowed,reason_code=result.reason_code)
        return result

    def dispatched(self,review,plan,receipt,game_seconds,*,unknown_command_id=None):
        from macro_strategy import StrategyError
        actions=tuple(plan.macro_actions)
        unknown=unknown_command_id is not None
        if unknown:
            ident=unknown_command_id;seq=0
        else:
            if type(receipt) is not dict or receipt.get('native_gate_acknowledged') is not True:
                raise ContractError('strategy_native_receipt_required')
            ident=receipt.get('command_id');seq=receipt.get('seq')
            if (type(seq) is not int or seq<=self.last_ack_sequence
                    or receipt.get('plan_id')!=plan.plan_id or receipt.get('actions')!=list(actions)):
                raise ContractError('strategy_native_receipt_required')
        try:self.memory.record_dispatch(review,command_id=ident if actions or unknown else None,
            game_seconds=game_seconds,outcome='unknown' if unknown else 'pending')
        except StrategyError as error:raise ContractError(str(error)) from None
        # The preceding plan is replaced only after a new independent gate ACK.
        # An uncertain new command narrows the old effect window inside memory,
        # but cannot prove release or turn uncertainty into a completed task.
        if not unknown:
            self.last_ack_sequence=seq
            for row in self.commands.values():
                if not row.released and not row.unknown:
                    self._outcome(row,'replaced',game_seconds,reason='acknowledged_replacement',released=True)
        if actions or unknown:
            begin=(receipt or {}).get('native_start_frame');end=(receipt or {}).get('native_deadline_frame')
            window=(type(begin) is int and type(end) is int and 0<begin<end<=0xffffffff)
            start=max(game_seconds,begin/15) if window else game_seconds
            deadline=min(plan.expires_at_game_seconds,end/15) if window else plan.expires_at_game_seconds
            self.commands[ident]=_Tracked(plan.plan_id,ident,actions,start,deadline,seq,unknown=unknown,native_window_verified=window,model_expires=plan.expires_at_game_seconds)
        self.event('macro_strategy_declared',plan_id=plan.plan_id,strategy_id=review.strategy_id,
            command_id=ident if actions or unknown else None,delivery_unknown=unknown)

    @staticmethod
    def _positive(action,value):
        if type(value) is not dict:return False
        if action.startswith('budget'):
            return value.get('selected_policy')==action and value.get('native_effect_verified') is True
        if action.startswith('produce') or action.startswith('build'):
            return (value.get('action')==action and type(value.get('observed_new_queue_count')) is int
                and value['observed_new_queue_count']>0 and (not action.startswith('build')
                    or value.get('positive_native_build_state_observed') is True))
        if action=='scout':return value.get('native_execution_observed') is True and value.get('moved_native_groups',0)>0
        if value.get('action')!=action or value.get('native_execution_observed') is not True:return False
        if action=='withdraw':return value.get('withdrawing_native_groups',0)>0
        if action=='regroup':return value.get('groups_near_home_region',0)>0
        if action=='reinforce':return value.get('defender_groups_near_infrastructure',0)>0 and value.get('moved_native_groups',0)>0
        if action=='deploydefense' and value.get('native_tactic_family')=='static_defense':
            return value.get('defender_groups_near_infrastructure',0)>0
        return value.get('groups_progressing_toward_region',0)>0

    def observe(self,controller,native,game_seconds,*,budget_feedback=None):
        if type(native) is not dict:return
        domains=[]
        for plan_attr,tracker_attr in (('active_plan','tracker'),('construction_plan','construction_tracker'),
                                      ('scout_plan','scout_tracker'),('regional_plan','regional_tracker'),
                                      ('expansion_plan','expansion_tracker')):
            plan=getattr(controller,plan_attr,None);tracker=getattr(controller,tracker_attr,None)
            if plan is not None and tracker is not None:domains.append((plan[0],tracker.public()))
        for row in self.commands.values():
            if row.released or row.unknown:continue
            facts=[value for plan,value in domains if plan==row.plan_id]
            if any(a.startswith('budget') for a in row.actions) and budget_feedback is not None:facts.append(budget_feedback)
            workers=[a for a in row.actions if not a.startswith('budget')]
            effect_actions=workers or list(row.actions)
            for value in facts:
                frames=[value[k] for k in ('observed_frame','view_frame','builder_frame','own_census_frame') if k in value]
                if (not row.native_window_verified or not frames or any(type(f) is not int or f<=0 for f in frames)
                        or max(frames)-min(frames)>30 or value.get('policy_released',False) is not False):continue
                first,seen=min(frames)/15,max(frames)/15
                if not (row.started<=first<=seen<row.expires and seen<=game_seconds):continue
                if not row.had_effect and any(self._positive(a,value) for a in effect_actions):
                    self._outcome(row,'effect_observed',game_seconds,seen=seen,reason='bounded_native_fact')
                if workers and not row.budget_observed and any(self._positive(a,value) for a in row.actions if a.startswith('budget')):
                    row.budget_observed=True
                    self.event('macro_strategy_budget_observed',plan_id=row.plan_id,command_id=row.command_id,
                        observed_game_seconds=seen,work_effect_verified=False)
            if (all(type(native.get(k)) is int for k in ('active','request','ack','error','phase','applied_mask'))
                    and native['active']==0 and native['request']==native['ack'] and native['error']==0
                    and native['phase'] in (1,2) and native['applied_mask']==0 and native['ack']>=row.seq):
                if game_seconds>=row.model_expires:outcome='expired'
                else:outcome='replaced' if row.had_effect else 'no_effect'
                self._outcome(row,outcome,game_seconds,reason='independent_empty_native_gates',released=True)

    def finish(self,game_seconds,*,release_verified):
        if type(release_verified) is not bool:raise ContractError('strategy_release_assertion')
        if release_verified:
            for row in self.commands.values():
                if not row.released:self._outcome(row,'cancelled',game_seconds,reason='verified_host_stop',released=True)
        self.memory.stop()
