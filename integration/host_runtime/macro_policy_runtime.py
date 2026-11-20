"""Model request audit and shared constants for strategic dispatch. No unit control."""
import hashlib
import json
import math
from pathlib import Path

from .contracts import ContractError

ROOT=Path(__file__).resolve().parents[2]
COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'
# Early construction field evidence starts before the native opening finishes.
# Model planning can begin after identity/visibility settle; native opening and
# prerequisite heuristics still decide when any preference can be consumed.
MIN_MACRO_MODEL_GAME_SECONDS=30.
ACCOUNTS=('investment','special_operations','production','defense','technology','slush_fund')
PRESETS={
    'budgeteconomy':dict(zip(ACCOUNTS,[.4,0,.25,.1,.15,.1])),
    'budgetarmy':dict(zip(ACCOUNTS,[.1,0,.7,.1,.05,.05])),
    'budgettech':dict(zip(ACCOUNTS,[.15,0,.25,.1,.4,.1]))}

def ratios_match(actual,expected):
    return (isinstance(actual,dict) and set(actual)==set(expected) and all(type(actual[k]) in (int,float)
        and math.isfinite(actual[k]) and abs(actual[k]-v)<1e-5 for k,v in expected.items()))


def compact_account_shares(value):
    if (type(value) is not dict or set(value)!=set(ACCOUNTS)
            or any(type(number) not in (int,float) or not math.isfinite(number) or not 0<=number<=1 for number in value.values())
            or abs(sum(value.values())-1)>1e-4):
        raise ContractError('macro_native_account_shares_invalid')
    return {name:round(float(value[name]),4) for name in ACCOUNTS}


class MacroRequestAudit:
    """Record the exact public agent context passed to the normal backend."""
    def __init__(self,backend,event,*,feedback_supplier=None,forces_supplier=None,catalog_supplier=None,
                 strategy_supplier=None,strategic_only=False):
        self.backend=backend;self.event=event;self.sequence=0;self.feedback_supplier=feedback_supplier
        self.forces_supplier=forces_supplier
        self.catalog_supplier=catalog_supplier
        self.strategy_supplier=strategy_supplier
        self._last_request_context=None
        self.strategic_only=strategic_only

    def fresh_for_game_seconds(self,game_seconds):
        """Defer asynchronous decisions when sequential native reads diverge.

        This only tests age. Full field/source validation still runs at the
        provider boundary; malformed values cannot pass that validation.
        """
        for supplier in (self.feedback_supplier,self.forces_supplier):
            value=supplier() if supplier else None
            if not isinstance(value,dict):continue
            frame=value.get('observed_frame')
            if type(frame) is int and 0<frame<=0xffffffff and not -15<=game_seconds*15-frame<=30:
                return False
        return True

    def prepare(self,context):
        if self.feedback_supplier is None:return self._prepare_strategy(context)
        feedback=self.feedback_supplier()
        if not isinstance(feedback,dict):raise ContractError('macro_latest_feedback_unavailable')
        status=feedback.get('status');selected=feedback.get('selected_policy');actions=feedback.get('actions')
        frame=feedback.get('observed_frame')
        known={'native_budget_adopted','native_budget_pending','native_delegation_observed','native_budget_clearing'}
        if (status not in known or selected is not None and selected not in PRESETS
                or type(actions) is not list or len(actions)>1 or any(action not in PRESETS for action in actions)
                or type(frame) is not int or not 0<frame<=0xffffffff
                or not 0<=context.get('game_time_seconds',-2)*15-frame+15<=45
                or type(feedback.get('native_effect_verified')) is not bool
                or status=='native_budget_adopted' and (actions!=[selected] or feedback['native_effect_verified'] is not True)):
            raise ContractError('macro_latest_feedback_invalid_or_stale')
        # This bounded current observation lives outside compactable historical
        # memory. Never copy native addresses, IDs or arbitrary nested fields.
        compact=dict(source='native_macro_budget_observation',status=status,actions=list(actions),selected_policy=selected,
            observed_frame=frame,native_effect_verified=feedback['native_effect_verified'],payment_verified=False,
            production_queue_observed=False,idle_producers_observed=False,own_roles_coverage='audited_templates_only')
        if feedback.get('native_account_shares') is not None:
            compact['native_account_shares']=compact_account_shares(feedback['native_account_shares'])
        result=dict(context,macro_execution_feedback=compact)
        if self.forces_supplier is not None:
            forces=self.forces_supplier()
            if forces is not None:
                from .macro_forces import compact_forces
                result['own_forces']=compact_forces(forces,context['game_time_seconds'])
        if self.catalog_supplier is not None:
            overrides=self.catalog_supplier()
            if type(overrides) is not dict:raise ContractError('macro_base_defense_catalog_invalid')
            # The catalog must equal one rebuilt from the scenario's home region.
            if overrides not in strategic_catalogs(overrides,context):
                raise ContractError('macro_base_defense_catalog_invalid')
            for action,description in overrides.items():
                if action not in result.get('allowed_macro_actions',[]):continue
                old=result.get('macro_policy_catalog',{}).get(action,{})
                if 'target_region' in description and old.get('target_region')!=description['target_region']:
                    raise ContractError('macro_base_defense_catalog_region_binding')
                result['macro_policy_catalog']={**result['macro_policy_catalog'],action:description}
        if 'macro_policy_catalog' in result:
            from macro_policy import model_catalog
            result['macro_policy_catalog']=model_catalog(result['macro_policy_catalog'])
        return self._prepare_strategy(result)

    def _prepare_strategy(self,context):
        if self.strategic_only:
            from .macro_delegation_boundary_v1 import restrict_context
            context=restrict_context(context)
        if self.strategy_supplier is None:return context
        from macro_strategy import StrategyError
        # Build this after all fresh domain feedback and the trusted capability
        # catalog have been projected. The model cannot supply its own facts.
        try:value=self.strategy_supplier(context)
        except StrategyError as error:raise ContractError(str(error)) from None
        if (type(value) is not dict or value.get('schema_version')!=1
                or type(value.get('fact_catalog')) is not dict
                or len(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8'))>1536):
            raise ContractError('macro_strategy_context_invalid_or_oversized')
        if self.strategic_only:
            # The canonical memory below carries the declared strategy and
            # outcomes. Keep the accepted executable intent without embedding
            # a second full model declaration in the same bounded request.
            current=context.get('working_memory',{}).get('current_strategy')
            if type(current) is dict:current.pop('macro_strategy',None)
        from macro_policy import project_strategy_defaults
        try:return project_strategy_defaults(dict(context,macro_strategy=json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False))))
        except ValueError:raise ContractError('macro_default_contract_invalid') from None

    def request_context_for(self,plan):
        """Exact last sent request, bound to this accepted plan, never globals."""
        value=plan.public() if hasattr(plan,'public') else plan
        context=self._last_request_context
        if type(value) is not dict or context is None or any(
                value.get(key)!=context.get(key) for key in ('session_id','commander_id','player_id','snapshot_id')):
            raise ContractError('macro_strategy_request_binding')
        if value.get('based_on_game_time_seconds')!=context.get('game_time_seconds'):
            raise ContractError('macro_strategy_request_binding')
        return json.loads(json.dumps(context,ensure_ascii=False,allow_nan=False))

    def input_size(self,context):
        try:return self.backend.input_size(self.prepare(context))
        except ContractError as error:
            # BattleAgent treats a strategy contract failure as a rejected
            # context. Telemetry freshness never implies a native-channel fault.
            from engine import ContractError as StrategyContractError
            self.event('macro_context_rejected',reason_code=error.code,stage='wire_size')
            raise StrategyContractError(error.code) from None

    async def __call__(self,context):
        if not isinstance(context,dict) or context.get('control_mode')!='macro_native':
            raise ContractError('macro_request_audit_mode')
        context=self.prepare(context)
        encoded=json.dumps(context,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
        limit=getattr(self.backend,'max_input_bytes',16384)
        if type(limit) is not int or not 4096<=limit<=32768:raise ContractError('macro_request_audit_limit')
        if len(encoded)>limit:raise ContractError('macro_request_audit_bounds')
        measure=getattr(self.backend,'input_size',None)
        if self.strategy_supplier is not None:
            if not callable(measure):raise ContractError('macro_request_wire_measurement_required')
            if measure(context)>limit:raise ContractError('macro_request_audit_wire_bounds')
        self._last_request_context=json.loads(encoded)
        self.sequence+=1
        self.event('model_macro_request_context',sequence=self.sequence,context=json.loads(encoded),
            context_sha256=hashlib.sha256(encoded).hexdigest(),context_bytes=len(encoded))
        result=await self.backend(context)
        if self.strategic_only:
            from engine import parse_model_json,ContractError as StrategyContractError
            from .macro_delegation_boundary_v1 import validate_policy
            try:validate_policy(parse_model_json(result) if isinstance(result,(str,bytes)) else result)
            except ContractError as error:raise StrategyContractError(error.code) from None
        if self.strategy_supplier is not None:
            from engine import parse_model_json
            value=parse_model_json(result) if isinstance(result,(str,bytes)) else result
            if type(value) is not dict or 'macro_strategy' not in value:
                self.event('macro_strategy_response_rejected',reason_code='macro_strategy_declaration_missing')
                raise ContractError('macro_strategy_declaration_missing')
        return result

    def __getattr__(self,name):return getattr(self.backend,name)


def strategic_catalogs(overrides,context):
    """Canonical native catalogs for the home region the overrides name.

    The home region and focus targets come from the runtime scenario, so the
    supplied catalog is only accepted when it equals one rebuilt from them.
    """
    from .macro_group_role_contract import home_group_role_catalog_overrides,home_strategic_catalog_overrides
    from .scenario import is_region
    defense=overrides.get('deploydefense')
    home=defense.get('target_region') if type(defense) is dict else None
    if not is_region(home):return ()
    catalogs=(home_group_role_catalog_overrides(home),home_strategic_catalog_overrides(home))
    from .native_runtime import NativeScope
    from .strategic_contract_v5 import INDEPENDENT_DEVELOPMENT_CONTRACT
    if context.get('macro_intent_contract')==INDEPENDENT_DEVELOPMENT_CONTRACT:
        focus_targets=tuple(sorted(row['target_player_id'] for row in overrides.values()
            if type(row) is dict and row.get('domain')=='enemy_focus' and type(row.get('target_player_id')) is int))
        native=NativeScope('',(),(),(),required_origin_region=home,opponent_player_ids=focus_targets)
        catalogs+=(native.model_catalog_overrides(),)
    return catalogs
