"""Evidence-bound native production preferences; no unit-operation interface."""
from dataclasses import dataclass
import math
from pathlib import Path
import uuid

from .contracts import ContractError
from .macro_policy_runtime import BudgetController,BudgetScope,COMMANDER,PRESETS,load,sha,trial
from .macro_production_feedback import ProductionFeedback
from .macro_construction_feedback import ConstructionFeedback,ACTION as BUILD_ACTION

ROOT=Path(__file__).resolve().parents[2]
# The stock Hammer Tank GameDependency requires SovietPowerPlantAdvanced.
# Own-template presence is necessary; the native producer still validates the
# completed dependency and resources before committing its normal build work.
PREREQUISITES={'producetank':('0x524bbd01',)}


def prerequisites_present(action,census):
    own={row['type_hash'] for row in census['own_objects']}
    return all(template in own for template in PREREQUISITES.get(action,()))


@dataclass(frozen=True)
class ProductionPreferenceScope:
    budget: BudgetScope
    production_flag: str
    evidence: dict
    available_counts: tuple=(2,)
    extra_choices: tuple=()
    construction_flag: str|None=None

    @property
    def package_sha256(self):return self.budget.package_sha256

    @property
    def available_actions(self):return self.budget.available_actions+tuple(self.production_counts)+((BUILD_ACTION,) if self.construction_flag else ())

    @property
    def production_counts(self):
        return {'produceflak':self.available_counts,**{action:counts for action,counts,flag in self.extra_choices}}

    @property
    def production_flags(self):
        return {'produceflak':self.production_flag,**{action:flag for action,counts,flag in self.extra_choices}}

    def public(self):
        return dict(kind='verified_native_production_choice_scope' if self.extra_choices else 'verified_native_flak_preference_scope',package_sha256=self.package_sha256,
            available_actions=list(self.available_actions),available_additional_counts=list(self.available_counts),
            production_counts={action:list(counts) for action,counts in self.production_counts.items()},
            count_control_basis='new_native_queue_acceptances',completed_units_guaranteed=False,
            arbitrary_production_granted=False,construction_granted=bool(self.construction_flag),
            construction_choices=[BUILD_ACTION] if self.construction_flag else [],construction_completed_guaranteed=False,unit_operation_policy='native_ai',
            prerequisites_checked_as='live_own_template_presence',native_dependency_validation_required=True,
            evidence_files=len(self.evidence))


def verify_production_preference_scope(budget,directory,static_directory):
    """Qualify the observed two-queue preference, preserving incomplete results."""
    if not isinstance(budget,BudgetScope):raise ContractError('macro_production_budget_scope_required')
    directory=Path(directory).resolve();static=Path(static_directory).resolve()
    pre,final,manifest,rows,evidence=trial(directory/'transport')
    if (manifest['package_sha256']!=budget.package_sha256 or manifest['sources']!=budget.native_sources
            or tuple(manifest['flags'])!=budget.flags):raise ContractError('macro_production_transport_scope_mismatch')
    driver=load(directory/'driver-preflight.json')
    if (driver['driver_sha256']!=sha(directory/'count-driver.py') or driver['target']!='0x2c358c61'
            or driver['additional_count']!=2 or driver['policy']!=['produceflak','budgetarmy']):
        raise ContractError('macro_production_field_driver')
    audit=load(static/'audit.json')
    if sha(static/'audit.json')!='e53731a72b9e1f8cdc6286cbae31d0d16340379e5219e94a1e2948ef3abb048b':
        raise ContractError('macro_production_static_review_changed')
    if audit['executable_sha256']!='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165':
        raise ContractError('macro_production_static_executable')
    pins={row['address']:row['bytes'] for row in audit['byte_checks']}
    required={'0x8d2d08':'6805020000','0x6da6b0':'8b41e08b4030c3',
              '0x723f50':'81eca8000000538bd98b43dc8b5058558d6bdc'}
    if any(pins.get(key)!=value for key,value in required.items()):raise ContractError('macro_production_static_consumer')
    for row in audit['sources']:
        path=static/'source'/row['copy']
        if path.resolve().parent!=(static/'source').resolve() or sha(path)!=row['sha256']:
            raise ContractError('macro_production_static_source')
    observer_hash=sha(ROOT/'native-ai/macro_build_observation.py')
    if (not any(Path(row['path']).name=='macro_build_observation.py' and row['sha256']==observer_hash for row in pre['sources'])
            or not any(Path(row['path']).name=='macro_build_observation.py' and row['sha256']==observer_hash for row in audit['sources'])):
        raise ContractError('macro_production_observer_not_qualified')
    flag=next(row['flag'] for row in manifest['consumers'] if row['action']=='produceflak')
    mask=(1<<manifest['flags'].index(flag))|(1<<manifest['flags'].index(budget.action_flags['budgetarmy']))
    acks=[row for row in rows if row['kind']=='command_acknowledged']
    if len(acks)!=3 or [row['native']['applied_mask'] for row in acks]!=[mask,0,0]:
        raise ContractError('macro_production_field_gate_sequence')
    census=None;tracker=None;first_positive=None;count_frame=None
    for row in rows:
        if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
        if row['kind']=='native_builder_observation' and 'observation' in row and census:
            sample=row['observation']
            if any(entry['flag']==flag and entry['state_score']>0 and any(
                item['build_type_hash_raw']=='0x2c358c61' for item in entry['entries']) for entry in sample['macro_entries']):
                if first_positive is None:first_positive=sample['frame']
            if tracker is None:tracker=ProductionFeedback('produceflak',2,sample,census)
            else:tracker.observe(sample,census)
            if len(tracker.new_queues)>=2 and count_frame is None:count_frame=sample['frame']
    if (tracker is None or first_positive is None or count_frame is None or len(tracker.baseline_queues)!=0
            or len(tracker.new_queues)!=2 or not acks[0]['native']['last_frame']<=first_positive<count_frame
            or not count_frame<=acks[1]['native']['last_frame']<=count_frame+15):
        raise ContractError('macro_production_native_sequence_not_verified')
    # This field record includes producer loss. It qualifies observing/releasing
    # preferences, never a promise that two units complete or remain alive.
    if tracker.public()['new_own_unit_observations']!=1 or tracker.public()['incomplete_queues_with_unavailable_producer']!=1:
        raise ContractError('macro_production_partial_result_missing')
    for path in [directory/'driver-preflight.json',directory/'count-driver.py',static/'audit.json']:
        evidence[str(path)]=sha(path)
    return ProductionPreferenceScope(budget,flag,evidence)


class MacroProductionController:
    """One bounded production goal at a time, with continuous native feedback."""
    def __init__(self,transport,scope,session_id,effective_hash,event):
        self.transport=transport;self.scope=scope;self.session_id=session_id;self.effective_hash=effective_hash;self.event=event
        self.budget=BudgetController(transport,scope.budget,session_id,effective_hash,event)
        self.production_sent={};self.fingerprints={};self.latest=None;self.tracker=None;self.active_plan=None;self.stopped=False;self.scope_revoked=False
        self.construction_tracker=None;self.construction_candidate=None;self.construction_plan=None;self.construction_sent={}

    @property
    def sent(self):return {**self.budget.sent,**self.production_sent,**self.construction_sent}

    @property
    def busy(self):return self.production_busy or self.construction_busy

    @property
    def production_busy(self):return self.tracker is not None and not self.tracker.policy_released

    @property
    def construction_busy(self):return self.construction_tracker is not None and not self.construction_tracker.policy_released

    def refresh(self,sample):
        self.latest=None
        if 'observation' not in sample or 'build_observation' not in sample:return
        census=sample['observation']['construction_feedback'];builder=sample['build_observation']
        self.construction_candidate=None
        if self.scope.construction_flag:
            if self.construction_tracker:self.construction_tracker.observe(builder,census,self.scope.construction_flag)
            try:
                candidate=ConstructionFeedback(builder,census)
                # Any CY queue occupies the native builder. Do not override an
                # ongoing original-AI build, even when its type differs.
                occupied=any(row.get('observation_available') is True and
                    row['factory']['thing_id'] in candidate.eligible and row['queue_candidate']['nodes']
                    for row in builder['builders'])
                if not occupied and not candidate.baseline_objects:self.construction_candidate=candidate
            except ContractError as error:
                if error.code!='macro_construction_unique_builder_required':raise
        try:
            if self.tracker:self.tracker.observe(builder,census)
            self.scope_revoked=bool(self.production_busy and len(self.tracker.eligible)!=1)
            probes={}
            for action,counts in self.scope.production_counts.items():
                if not prerequisites_present(action,census):continue
                try:probe=ProductionFeedback(action,counts[0],builder,census)
                except ContractError as error:
                    if error.code=='macro_production_no_available_producer':continue
                    raise
                if len(probe.eligible)==1:probes[action]=probe
            self.latest=(builder,census,probes)
        except ContractError as error:
            if error.code=='macro_production_no_available_producer':self.scope_revoked=True
            elif self.busy:raise

    def available_actions(self,game_seconds):
        if self.stopped or self.busy:return ()
        available=self.scope.budget.available_actions
        if self.latest:
            builder,census,probes=self.latest
            # Sequential native reads may be a frame ahead of the earlier
            # public snapshot. Bound each sample on both sides of that clock.
            if all(-15<=game_seconds*15-frame<=15 for frame in (builder['frame'],census['frame'])):
                available+=tuple(action for action,probe in probes.items() if not probe.baseline_queues)
                if self.construction_candidate is not None:available+=(BUILD_ACTION,)
        return available

    def dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        if self.stopped:raise ContractError('macro_controller_stopped')
        if (effective_hash!=self.effective_hash or paused or plan is None or plan.origin!='model'
                or plan.session_id!=self.session_id or plan.commander_id!=COMMANDER or plan.player_id!=3
                or not plan.based_on_game_time_seconds<=game_seconds<plan.expires_at_game_seconds
                or plan.tactical_tasks or plan.runtime_task is not None):raise ContractError('macro_production_plan_binding')
        actions=tuple(plan.macro_actions);quantity=getattr(plan,'macro_production',None)
        if BUILD_ACTION in actions:
            return self.dispatch_construction(plan,game_seconds,effective_hash,actions,quantity)
        if plan.plan_id in self.construction_sent:raise ContractError('macro_plan_id_conflict')
        production=[action for action in actions if action.startswith('produce')]
        if not production:
            if self.busy:raise ContractError('macro_production_goal_active')
            if plan.plan_id in self.production_sent:raise ContractError('macro_plan_id_conflict')
            return self.budget.dispatch(plan,game_seconds,effective_hash=effective_hash,paused=paused)
        if (len(production)!=1 or quantity is None or getattr(quantity,'action',None)!=production[0]
                or type(quantity.additional_count) is not int
                or quantity.additional_count not in self.scope.production_counts.get(production[0],())
                or len(actions)!=len(set(actions)) or len(actions)>2
                or any(action not in self.scope.available_actions for action in actions)):
            raise ContractError('macro_production_action_or_count_not_qualified')
        fingerprint=(actions,quantity.additional_count,plan.based_on_game_time_seconds,plan.expires_at_game_seconds,effective_hash)
        if plan.plan_id in self.production_sent:
            if self.fingerprints[plan.plan_id]!=fingerprint:raise ContractError('macro_plan_id_conflict')
            return self.production_sent[plan.plan_id]
        if plan.plan_id in self.budget.sent:raise ContractError('macro_plan_id_conflict')
        if production[0] not in self.available_actions(game_seconds):raise ContractError('macro_production_not_currently_available')
        builder,census,_=self.latest
        tracker=ProductionFeedback(production[0],quantity.additional_count,builder,census)
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':production:'+effective_hash))
        duration=max(1,min(600,math.floor((plan.expires_at_game_seconds-game_seconds)*15)))
        self.event('model_macro_production_prepared',plan_id=plan.plan_id,command_id=command_id,
            actions=list(actions),additional_count=quantity.additional_count,duration_frames=duration)
        try:receipt=self.transport.apply(list(actions),duration,command_id)
        except Exception:
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        self.tracker=tracker;self.active_plan=(plan.plan_id,min(plan.expires_at_game_seconds,game_seconds+40))
        self.budget.current_actions=tuple(action for action in actions if action in PRESETS)
        public=dict(plan_id=plan.plan_id,command_id=command_id,actions=list(actions),additional_count=quantity.additional_count,
            seq=receipt['seq'],native_gate_acknowledged=True,native_effect_verified=False)
        self.production_sent[plan.plan_id]=public;self.fingerprints[plan.plan_id]=fingerprint
        self.event('model_macro_production_acknowledged',**public);return public

    def tick(self,game_seconds):
        if self.construction_busy and not self.stopped:
            tracker=self.construction_tracker
            if tracker.release_required or game_seconds>=self.construction_plan[1]:
                reason=('queue_observed' if tracker.new_queues else 'target_present' if tracker.new_objects else
                        'builder_unavailable' if tracker.eligible!=tracker.baseline_builders else 'expired')
                command_id=str(uuid.uuid5(uuid.UUID(self.session_id),self.construction_plan[0]+':construction-release:'+self.effective_hash))
                try:self.transport.apply([],1,command_id)
                except Exception:
                    self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
                tracker.mark_policy_released(reason);self.budget.current_actions=()
                self.event('macro_construction_preference_released',reason_code=reason,feedback=tracker.public())
            return
        if self.stopped or not self.production_busy:return
        if not self.tracker.release_required and not self.scope_revoked and game_seconds<self.active_plan[1]:return
        reason=('queue_target_observed' if len(self.tracker.new_queues)>=self.tracker.additional_count else
            'producer_unavailable' if not self.tracker.eligible or self.tracker.unavailable else 'scope_changed' if self.scope_revoked else 'expired')
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),self.active_plan[0]+':production-release:'+self.effective_hash))
        try:self.transport.apply([],1,command_id)
        except Exception:
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        self.tracker.mark_policy_released(reason);self.budget.current_actions=()
        self.event('macro_production_preference_released',reason_code=reason,feedback=self.tracker.public())

    def feedback(self,observation):return self.budget.feedback(observation)

    def production_feedback(self):return self.tracker.public() if self.tracker else None

    def construction_feedback(self):return self.construction_tracker.public() if self.construction_tracker else None

    def dispatch_construction(self,plan,game_seconds,effective_hash,actions,quantity):
        if (not self.scope.construction_flag or quantity is not None or len(actions)!=len(set(actions)) or len(actions)>2
                or any(action!=BUILD_ACTION and action not in self.scope.budget.available_actions for action in actions)):
            raise ContractError('macro_construction_action_not_qualified')
        fingerprint=(actions,plan.based_on_game_time_seconds,plan.expires_at_game_seconds,effective_hash)
        if plan.plan_id in self.construction_sent:
            if self.fingerprints[plan.plan_id]!=fingerprint:raise ContractError('macro_plan_id_conflict')
            return self.construction_sent[plan.plan_id]
        if plan.plan_id in self.budget.sent or plan.plan_id in self.production_sent:raise ContractError('macro_plan_id_conflict')
        if BUILD_ACTION not in self.available_actions(game_seconds):raise ContractError('macro_construction_not_currently_available')
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':construction:'+effective_hash))
        duration=max(1,min(900,math.floor((plan.expires_at_game_seconds-game_seconds)*15)))
        self.event('model_macro_construction_prepared',plan_id=plan.plan_id,command_id=command_id,
            actions=list(actions),duration_frames=duration)
        try:receipt=self.transport.apply(list(actions),duration,command_id)
        except Exception:
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        self.construction_tracker=self.construction_candidate
        self.construction_plan=(plan.plan_id,min(plan.expires_at_game_seconds,game_seconds+60))
        self.budget.current_actions=tuple(action for action in actions if action in PRESETS)
        public=dict(plan_id=plan.plan_id,command_id=command_id,actions=list(actions),seq=receipt['seq'],
            native_gate_acknowledged=True,native_effect_verified=False,construction_completed_verified=False)
        self.construction_sent[plan.plan_id]=public;self.fingerprints[plan.plan_id]=fingerprint
        self.event('model_macro_construction_acknowledged',**public);return public

    def stop(self):
        self.stopped=True;self.budget.stop()
        if self.tracker and not self.tracker.policy_released:
            self.tracker.mark_policy_released('stopped')
            self.event('macro_production_preference_released',reason_code='stopped',feedback=self.tracker.public())
        if self.construction_busy:
            self.construction_tracker.mark_policy_released('stopped')
            self.event('macro_construction_preference_released',reason_code='stopped',feedback=self.construction_tracker.public())
