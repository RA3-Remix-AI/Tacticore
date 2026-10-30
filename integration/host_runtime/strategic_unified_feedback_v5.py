"""Project bounded own strategic facts before constructing model memory."""
from .contracts import ContractError
from .macro_policy_runtime import MacroRequestAudit
from .macro_strategy_runtime import MacroStrategyRuntime
from .strategic_contract_v5 import FLAG_ACTIONS,GATE_ACTIONS,STRATEGIC_ACTIONS

class UnifiedRequestAuditV5(MacroRequestAudit):
    def __init__(self,*args,unified_supplier,**kwargs):
        super().__init__(*args,**kwargs);self.unified_supplier=unified_supplier
    def _prepare_strategy(self,context):
        value=project_unified_feedback(self.unified_supplier(),game_seconds=context['game_time_seconds'])
        # Full readback remains in the UI/private audit. The model receives
        # each original component frame and its distinct state, without
        # repeating global non-completion claims in every row.
        rows=[{key:r[key] for key in ('action','status','observed_frame','preference_active','movement_observed','state_already_satisfied')}
            for r in value['observations']]
        compact=dict(source=value['source'],observed_frame=value['observed_frame'],observations=rows,
            completion_and_exclusive_causality_verified=False)
        return super()._prepare_strategy(dict(context,macro_unified_feedback=compact,
            macro_policy_catalog=compact_model_catalog(context.get('macro_policy_catalog',{}))))

def compact_model_catalog(catalog):
    result={}
    for action,description in catalog.items():
        if action not in STRATEGIC_ACTIONS or type(description) is not dict:raise ContractError('unified_model_catalog_invalid')
        # The trusted scope and the full catalogue were already validated by
        # base prepare(). This projection never creates a capability or region.
        result[action]={k:v for k,v in description.items() if k in ('domain','goal','target_region','target_policy')}
        if action in ('regroup','withdraw','deployattack'):result[action].pop('target_policy',None)
        if action in GATE_ACTIONS:result[action]['goal']='advance_scheduling' if GATE_ACTIONS[action][1] else 'defer_scheduling'
        if action.startswith('budget'):result[action]['goal']='prefer_'+action[6:]+'_investment'
    return result

def project_unified_feedback(value,*,game_seconds=None):
        if (type(value) is not dict or value.get('source')!='bound_native_strategy_v5'
                or type(value.get('observed_frame')) is not int
                or not 0<value['observed_frame']<=0xffffffff
                or game_seconds is not None and not -15<=game_seconds*15-value['observed_frame']<=30
                or value.get('details_owner')!='native_ai' or type(value.get('observations')) is not list
                or len(value['observations'])>4):raise ContractError('unified_current_feedback_invalid_or_stale')
        rows=[]
        for row in value['observations']:
            if (type(row) is not dict or row.get('action') not in STRATEGIC_ACTIONS
                    or row.get('status') not in ('native_task_active','native_manager_state_observed','native_waiting_or_no_effect','preference_released')
                    or any(type(row.get(key)) is not bool for key in ('preference_active','active_native_task_observed',
                        'movement_observed','component_state_adopted','state_already_satisfied','mission_success_verified','exclusive_attribution_verified'))
                    or row['mission_success_verified'] or row['exclusive_attribution_verified']):
                raise ContractError('unified_feedback_exceeds_observation')
            if type(row.get('observed_frame')) is not int or not 0<=value['observed_frame']-row['observed_frame']<=15:
                raise ContractError('unified_feedback_component_clock_invalid')
            rows.append({key:row[key] for key in ('action','status','observed_frame','preference_active','active_native_task_observed',
                'movement_observed','component_state_adopted','state_already_satisfied','mission_success_verified','exclusive_attribution_verified')})
        if len({r['action'] for r in rows})!=len(rows):raise ContractError('unified_feedback_duplicate_action')
        return dict(source=value['source'],observed_frame=value['observed_frame'],details_owner='native_ai',observations=rows)

class UnifiedStrategyRuntimeV5(MacroStrategyRuntime):
    def observe(self,controller,native,game_seconds,*,budget_feedback=None):
        if type(native) is not dict:return
        feedback=controller.unified_feedback()
        if feedback is None:return
        frame=feedback['observed_frame'];at=frame/15
        if not at<=game_seconds<=at+2:return
        for row in self.commands.values():
            if row.released or row.unknown:continue
            if row.native_window_verified and row.started<=at<row.expires and controller.current_plan==row.plan_id:
                work=[a for a in row.actions if not a.startswith('budget')]
                effects=controller.effects
                positive_frames=[effects[a]['observed_frame'] for a in work if a in effects and
                    (effects[a].get('component_state_adopted') is True if a in GATE_ACTIONS else effects[a].get('movement_observed') is True)]
                seen=max(positive_frames)/15 if positive_frames else None
                if not work and budget_feedback is not None:
                    if any(self._positive(a,budget_feedback) for a in row.actions):seen=budget_feedback['observed_frame']/15
                if seen is not None and row.started<=seen<row.expires and seen<=game_seconds and not row.had_effect:
                    self._outcome(row,'effect_observed',game_seconds,seen=seen,reason='bounded_native_state_or_movement_not_mission_success')
            idle=(native['active']==0 and native['request']==native['ack'] and native['phase'] in (1,2)
                and native['error']==0 and native['ack']>=row.seq)
            flags_clear=all(not native['applied_mask']&(1<<FLAG_ACTIONS.index(a)) for a in row.actions if a in FLAG_ACTIONS)
            gates_clear=all(native['gates'][GATE_ACTIONS[a][0]]['phase'] in (0,4) for a in row.actions if a in GATE_ACTIONS)
            if idle and flags_clear and gates_clear:
                outcome='expired' if game_seconds>=row.model_expires else 'replaced' if row.had_effect else 'no_effect'
                self._outcome(row,outcome,game_seconds,reason='independent_current_unified_domains_released',released=True)
