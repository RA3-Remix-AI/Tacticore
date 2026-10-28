"""Evidence-bound macro budget dispatch. No unit-control or UI authority inputs."""
from dataclasses import dataclass,field
import hashlib
import json
import math
from pathlib import Path
import uuid

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

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def ratios_match(actual,expected):
    return (isinstance(actual,dict) and set(actual)==set(expected) and all(type(actual[k]) in (int,float)
        and math.isfinite(actual[k]) and abs(actual[k]-v)<1e-5 for k,v in expected.items()))


def trial(directory,*,fault=False):
    directory=Path(directory).resolve();pre=load(directory/'preflight.json');final=load(directory/'final-state.json')
    evidence={str(directory/name):sha(directory/name) for name in ['preflight.json','final-state.json','policy-probe.jsonl']}
    copies={}
    for source in pre['sources']:
        path=(directory/'source'/source['copy']).resolve()
        if path.parent!=(directory/'source').resolve() or sha(path)!=source['sha256']:
            raise ContractError('macro_field_source_changed')
        name=Path(source['path']).name
        if name in copies:raise ContractError('macro_field_source_alias')
        copies[name]=(path,Path(source['path']))
    manifest=load(copies['build-manifest.json'][0])
    session_copies=[row for name,row in copies.items() if name.endswith('.json') and sha(row[0])==pre['session_sha256']]
    if len(session_copies)!=1:raise ContractError('macro_field_session_source')
    session_path=session_copies[0][0];session=load(session_path)
    if (final.get('cleanup_verified') is not True or final.get('unknown_command_ids')!=[]
        or final.get('session_id')!=session['session_id'] or final.get('pid')!=session['pid']
        or final.get('mod_sha256')!=session['mod_sha256'] or final.get('process_creation_filetime')!=session['process_creation_filetime']
        or pre['process_creation_filetime']!=session['process_creation_filetime'] or pre['session_sha256']!=sha(session_path)
        or manifest['package_sha256']!=session['mod_sha256']):raise ContractError('macro_field_binding_or_cleanup')
    native=final['native']
    required=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0)
    if any(native.get(key)!=value for key,value in required.items()) or native['personality_id']!=0x799613e0:
        raise ContractError('macro_field_native_stop')
    if final.get('intentional_external_host_loss',False) is not fault:
        raise ContractError('macro_field_fault_scope')
    if fault:
        if final.get('host_returncode') in (None,0) or native.get('watchdog_reason')!=1:raise ContractError('macro_field_watchdog_missing')
    elif final.get('host_returncode')!=0:raise ContractError('macro_field_normal_exit_missing')
    flags=final.get('independent_flags',{}).get('flags',[])
    if len(flags)!=13 or any(row['present'] and row['value'] is not False for row in flags):raise ContractError('macro_field_gate_cleanup')
    for name,digest in manifest['sources'].items():
        if name not in {'shared.h','native.cpp','host.cpp','build.py'} or sha(copies[name][0])!=digest:
            raise ContractError('macro_field_native_source_mismatch')
    for name,digest in manifest['artifacts'].items():
        path=copies['build-manifest.json'][1].parent/name
        if Path(name).name!=name or sha(path)!=digest:raise ContractError('macro_field_binary_changed')
    records=[json.loads(line) for line in (directory/'policy-probe.jsonl').read_text(encoding='utf-8').splitlines()]
    return pre,final,manifest,records,evidence


@dataclass(frozen=True)
class BudgetScope:
    package_sha256:str
    native_sources:dict
    flags:tuple[str,...]=field(repr=False)
    action_flags:dict=field(repr=False)
    evidence:dict=field(repr=False)
    available_actions:tuple[str,...]=('budgeteconomy','budgetarmy')

    def public(self):
        return dict(kind='verified_native_macro_budget_scope',package_sha256=self.package_sha256,
            available_actions=list(self.available_actions),unit_operation_policy='native_ai',
            production_and_construction_granted=False,arbitrary_region_granted=False,
            evidence_hash=hashlib.sha256(json.dumps(self.evidence,sort_keys=True).encode()).hexdigest())


def verify_budget_scope(budget_directory,host_loss_directory,expiry_directory,build):
    normal=trial(budget_directory);fault=trial(host_loss_directory,fault=True);expiry=trial(expiry_directory)
    manifest=load(Path(build)/'build-manifest.json')
    common=normal[2]
    if any(row[2]['package_sha256']!=common['package_sha256'] or row[2]['sources']!=common['sources'] or row[2]['flags']!=common['flags'] for row in [fault,expiry]):
        raise ContractError('macro_field_evidence_build_mismatch')
    if manifest['package_sha256']!=common['package_sha256'] or manifest['sources']!=common['sources'] or manifest['flags']!=common['flags']:
        raise ContractError('macro_current_build_not_qualified')
    action_flags={row['action']:row['flag'] for row in manifest['consumers'] if row['action'] in PRESETS}
    if set(action_flags)!=set(PRESETS):raise ContractError('macro_budget_scope_missing')
    observations=lambda records:[row['observation'] for row in records if row.get('kind')=='macro_observation' and 'observation' in row]
    for action,rows in [('budgeteconomy',normal[3]),('budgetarmy',fault[3])]:
        adopted=[o for o in observations(rows) if o.get('budget_feedback',{}).get('selected_macro_flag')==action_flags[action]
            and ratios_match(o['budget_feedback'].get('account_shares'),PRESETS[action])]
        if len(adopted)<2:raise ContractError('macro_budget_native_adoption_missing')
    baseline=dict(zip(ACCOUNTS,[0,0,.85,.05,0,.1]))
    if not any(row.get('label')=='after_native_policy_reassessment' and row.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag') is None
            and ratios_match(row['observation']['budget_feedback'].get('account_shares'),baseline) for row in normal[3]):
        raise ContractError('macro_budget_delegation_not_verified')
    if not any(row.get('kind')=='native_host_loss_cleanup_verified' for row in fault[3]):raise ContractError('macro_host_loss_not_verified')
    if not any(row.get('kind')=='native_policy_expiry_verified' and row.get('native',{}).get('applied_mask')==0
            and row['native']['last_frame']>=row['expected_deadline_frame'] for row in expiry[3]):
        raise ContractError('macro_expiry_not_verified')
    evidence={key:value for row in [normal,fault,expiry] for key,value in row[4].items()}
    return BudgetScope(common['package_sha256'],common['sources'],tuple(common['flags']),action_flags,evidence)


class BudgetController:
    """Dispatch validated model plans; never infer executable actions from prose."""
    def __init__(self,transport,scope,session_id,effective_hash,event):
        if transport.session['session_id']!=session_id or transport.session['mod_sha256']!=scope.package_sha256:
            raise ContractError('macro_controller_binding')
        self.transport=transport;self.scope=scope;self.session_id=session_id;self.effective_hash=effective_hash
        self.event=event;self.sent={};self.current_actions=();self.stopped=False
        self.fingerprints={}

    def dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        if self.stopped:raise ContractError('macro_controller_stopped')
        if effective_hash!=self.effective_hash:raise ContractError('macro_profile_revision_changed')
        if paused:raise ContractError('macro_game_paused')
        if (plan is None or plan.origin!='model' or plan.session_id!=self.session_id or plan.commander_id!=COMMANDER
            or plan.player_id!=3 or not plan.based_on_game_time_seconds<=game_seconds<plan.expires_at_game_seconds):
            raise ContractError('macro_plan_binding_or_expiry')
        if plan.tactical_tasks or plan.runtime_task is not None:raise ContractError('macro_unit_tasks_refused')
        actions=tuple(plan.macro_actions)
        if (len(actions)>1 or any(action not in self.scope.available_actions for action in actions)
                or getattr(plan,'macro_production',None) is not None):raise ContractError('macro_action_not_qualified')
        fingerprint=(actions,plan.based_on_game_time_seconds,plan.expires_at_game_seconds,effective_hash)
        if plan.plan_id in self.sent:
            if self.fingerprints[plan.plan_id]!=fingerprint:raise ContractError('macro_plan_id_conflict')
            return self.sent[plan.plan_id]
        duration=max(1,min(900,math.floor((plan.expires_at_game_seconds-game_seconds)*15)))
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':'+effective_hash))
        self.event('model_macro_dispatch_prepared',plan_id=plan.plan_id,command_id=command_id,actions=list(actions),duration_frames=duration)
        try:receipt=self.transport.apply(list(actions),duration,command_id)
        except Exception:
            self.stopped=True;self.event('model_macro_dispatch_unknown',plan_id=plan.plan_id,command_id=command_id)
            raise ContractError('macro_dispatch_outcome_unknown') from None
        public=dict(plan_id=plan.plan_id,command_id=command_id,actions=list(actions),seq=receipt['seq'],
            native_gate_acknowledged=True,native_effect_verified=False,expires_at_game_seconds=plan.expires_at_game_seconds)
        self.sent[plan.plan_id]=public;self.fingerprints[plan.plan_id]=fingerprint;self.current_actions=actions
        self.event('model_macro_native_acknowledged',**public);return public

    def feedback(self,observation):
        budget=observation['budget_feedback'];selected=budget['selected_macro_flag']
        action=next((action for action,flag in self.scope.action_flags.items() if flag==selected),None)
        adopted=bool(len(self.current_actions)==1 and action==self.current_actions[0]
            and ratios_match(budget['account_shares'],PRESETS[action]))
        status='native_budget_adopted' if adopted else 'native_budget_pending' if self.current_actions else 'native_delegation_observed' if selected is None else 'native_budget_clearing'
        return dict(module='macro',status=status,
            actions=list(self.current_actions),selected_policy=action,observed_frame=observation['frame'],
            native_account_shares=dict(budget['account_shares']),payment_verified=False,
            unit_operation_policy='native_ai',native_effect_verified=adopted)

    def stop(self):
        self.stopped=True
        self.transport.close()


class MacroRequestAudit:
    """Record the exact public agent context passed to the normal backend."""
    def __init__(self,backend,event,*,feedback_supplier=None,production_supplier=None,construction_supplier=None,infrastructure_supplier=None,scouting_supplier=None,regional_supplier=None,forces_supplier=None,catalog_supplier=None):
        self.backend=backend;self.event=event;self.sequence=0;self.feedback_supplier=feedback_supplier
        self.production_supplier=production_supplier
        self.construction_supplier=construction_supplier
        self.infrastructure_supplier=infrastructure_supplier
        self.scouting_supplier=scouting_supplier
        self.regional_supplier=regional_supplier
        self.forces_supplier=forces_supplier
        self.catalog_supplier=catalog_supplier

    def fresh_for_game_seconds(self,game_seconds):
        """Defer asynchronous decisions when sequential native reads diverge.

        This only tests age. Full field/source validation still runs at the
        provider boundary; malformed values cannot pass that validation.
        """
        for supplier,keys in (
                (self.feedback_supplier,('observed_frame',)),
                (self.production_supplier,('builder_frame','own_census_frame')),
                (self.construction_supplier,('builder_frame','own_census_frame')),
                (self.infrastructure_supplier,('builder_frame','own_census_frame')),
                (self.scouting_supplier,('observed_frame','view_frame')),
                (self.regional_supplier,('observed_frame','view_frame')),
                (self.forces_supplier,('observed_frame',))):
            value=supplier() if supplier else None
            if not isinstance(value,dict):continue
            for key in keys:
                frame=value.get(key)
                if type(frame) is int and 0<frame<=0xffffffff and not -15<=game_seconds*15-frame<=30:
                    return False
        return True

    def prepare(self,context):
        if self.feedback_supplier is None:return context
        feedback=self.feedback_supplier()
        if not isinstance(feedback,dict):raise ContractError('macro_latest_feedback_unavailable')
        status=feedback.get('status');selected=feedback.get('selected_policy');actions=feedback.get('actions');frame=feedback.get('observed_frame')
        if (status not in {'native_budget_adopted','native_budget_pending','native_delegation_observed','native_budget_clearing'}
                or selected is not None and selected not in PRESETS
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
        result=dict(context,macro_execution_feedback=compact)
        if self.production_supplier is not None:
            production=self.production_supplier()
            if production is not None:
                from .macro_production_public import compact_production_feedback
                result['macro_production_feedback']=compact_production_feedback(production,context['game_time_seconds'])
        if self.construction_supplier is not None:
            construction=self.construction_supplier()
            if construction is not None:
                from .macro_construction_feedback import compact_construction_feedback
                result['macro_construction_feedback']=compact_construction_feedback(construction,context['game_time_seconds'])
        if self.infrastructure_supplier is not None:
            infrastructure=self.infrastructure_supplier()
            if infrastructure is not None:
                from .macro_infrastructure import compact_infrastructure
                result['own_infrastructure']=compact_infrastructure(infrastructure,context['game_time_seconds'])
        if self.forces_supplier is not None:
            forces=self.forces_supplier()
            if forces is not None:
                from .macro_forces import compact_forces
                result['own_forces']=compact_forces(forces,context['game_time_seconds'])
        if self.scouting_supplier is not None:
            scouting=self.scouting_supplier()
            if scouting is not None:
                from .macro_scouting import compact_scout_feedback
                result['macro_scouting_feedback']=compact_scout_feedback(scouting,context['game_time_seconds'])
        if self.regional_supplier is not None:
            regional=self.regional_supplier()
            if regional is not None:
                from .macro_regions import compact_regional_feedback
                result['macro_regional_feedback']=compact_regional_feedback(regional,context['game_time_seconds'])
        if self.catalog_supplier is not None:
            from .macro_base_defense_scope import defense_catalog_override
            from .macro_group_role_contract import group_role_catalog_overrides
            overrides=self.catalog_supplier()
            if overrides not in (defense_catalog_override(),group_role_catalog_overrides()):raise ContractError('macro_base_defense_catalog_invalid')
            for action,description in overrides.items():
                if action not in result.get('allowed_macro_actions',[]):continue
                old=result.get('macro_policy_catalog',{}).get(action,{})
                if old.get('target_region')!='region_8_3':raise ContractError('macro_base_defense_catalog_region_binding')
                result['macro_policy_catalog']={**result['macro_policy_catalog'],action:description}
        if 'macro_policy_catalog' in result:
            from macro_policy import model_catalog
            result['macro_policy_catalog']=model_catalog(result['macro_policy_catalog'])
        return result

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
        if len(encoded)>16384:raise ContractError('macro_request_audit_bounds')
        self.sequence+=1
        self.event('model_macro_request_context',sequence=self.sequence,context=json.loads(encoded),
            context_sha256=hashlib.sha256(encoded).hexdigest(),context_bytes=len(encoded))
        return await self.backend(context)

    def __getattr__(self,name):return getattr(self.backend,name)
