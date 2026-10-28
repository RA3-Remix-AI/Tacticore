"""Bounded native scout preference; original AI selects targets and operates units."""
from dataclasses import dataclass,fields
import math
import json
from pathlib import Path
import uuid

from .contracts import ContractError
from .macro_policy_runtime import PRESETS,COMMANDER,sha,load,trial
from .macro_production_runtime import ProductionPreferenceScope,MacroProductionController

DRIVER_SHA='9a29fe85296d2754f8a529acd2ad089d9d2492c6b932778a4386afebfd773497'

def scout_sample(observation,battlefield,flag):
    """Only the flag-bound native state and current own-perspective public view."""
    at=battlefield['game_time_seconds'];frame=observation['frame']
    field=battlefield['battlefield']
    if (observation.get('source')!='native_macro_read_only' or observation.get('native_calls')!=0
            or observation.get('process_writes')!=0 or field.get('visibility_verified') is not True
            or field.get('viewer_player_id')!=3 or not -15<=at*15-frame<=30):
        raise ContractError('macro_scout_observation_invalid_or_stale')
    state=observation['state_scores'].get(flag)
    if not state or state['domain']!='strategic':raise ContractError('macro_scout_state_missing')
    groups={};active=0
    for runtime in observation['runtimes']:
        if runtime['group']!=state['group'] or not runtime['native_execution_active']:continue
        active+=1
        for group in runtime.get('owned_groups',[]):
            if not group.get('found') or not group.get('all_members_resolved'):continue
            for member in group['members']:
                if member['owner']!=observation['native']['player']:raise ContractError('macro_scout_foreign_member')
                xyz=member['xyz']
                if len(xyz)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in xyz):
                    raise ContractError('macro_scout_position')
                groups[(group['native_id'],member['thing_id'])]=tuple(xyz)
    contacts={c['contact_id'] for c in field['contacts'] if c['currently_visible'] is True and c['relation']=='enemy'}
    return frame,round(at*15),state['score']>0,active,groups,contacts

class ScoutFeedback:
    def __init__(self,observation,battlefield,flag):
        sample=scout_sample(observation,battlefield,flag)
        self.flag=flag;self.baseline_contacts=sample[-1];self.new_contacts=set();self.first_positions={}
        self.moved=set();self.ever_active=False;self.policy_released=False;self.release_reason=None
        self.observe(observation,battlefield)

    def observe(self,observation,battlefield):
        frame,view_frame,score,active,groups,contacts=scout_sample(observation,battlefield,self.flag)
        if hasattr(self,'frame') and (frame<self.frame or view_frame<self.view_frame):raise ContractError('macro_scout_frame_regression')
        self.frame=frame;self.view_frame=view_frame;self.score=score;self.active=active;self.group_count=len({k[0] for k in groups})
        if score and active:self.ever_active=True
        for key,point in groups.items():
            first=self.first_positions.setdefault(key,point)
            if math.dist(first,point)>10:self.moved.add(key[0])
        self.new_contacts.update(contacts-self.baseline_contacts)
        return self.public()

    def public(self):
        return dict(source='native_scout_and_lawful_view_observation',observed_frame=self.frame,view_frame=self.view_frame,
            native_state_positive=self.score,active_native_tactics=self.active,allocated_native_groups=self.group_count,
            native_execution_observed=self.ever_active,moved_native_groups=len(self.moved),
            new_legal_contacts_since_intent=len(self.new_contacts),policy_released=self.policy_released,release_reason=self.release_reason,
            target_policy='original_native_scout_target_selection',arbitrary_region_selected=False,
            intelligence_exclusively_attributed_to_scout=False,mission_success_verified=False,unit_operation_policy='native_ai')

def compact_scout_feedback(value,game_seconds):
    if (type(value) is not dict or value.get('source')!='native_scout_and_lawful_view_observation'
            or value.get('target_policy')!='original_native_scout_target_selection'
            or any(type(value.get(k)) is not int or not 0<=value[k]<=8192
                   for k in ('active_native_tactics','allocated_native_groups','moved_native_groups','new_legal_contacts_since_intent'))
            or any(type(value.get(k)) is not bool for k in ('native_state_positive','native_execution_observed','policy_released'))
            or value.get('release_reason') not in (None,'expired','native_execution_inactive','stopped')
            or any(type(value.get(k)) is not int or not 0<value[k]<=0xffffffff
                   or not -15<=game_seconds*15-value[k]<=30 for k in ('observed_frame','view_frame'))):
        raise ContractError('macro_scout_feedback_invalid_or_stale')
    keys=('source','observed_frame','view_frame','native_state_positive','active_native_tactics','allocated_native_groups',
          'native_execution_observed','moved_native_groups','new_legal_contacts_since_intent','policy_released','release_reason','target_policy')
    return dict(**{k:value[k] for k in keys},arbitrary_region_selected=False,intelligence_exclusively_attributed_to_scout=False,
        mission_success_verified=False,unit_operation_policy='native_ai')

@dataclass(frozen=True)
class ScoutingScope(ProductionPreferenceScope):
    scout_flag:str|None=None

    @property
    def available_actions(self):return super().available_actions+(('scout',) if self.scout_flag else ())

    def public(self):return dict(**super().public(),scouting_granted=bool(self.scout_flag),
        scouting_target_policy='original_native_scout_target_selection',arbitrary_region_selection_granted=False)

def extend_scouting_scope(base,directory):
    if not isinstance(base,ProductionPreferenceScope):raise ContractError('macro_scout_base_scope_required')
    directory=Path(directory);driver=load(directory/'driver-preflight.json')
    pre,final,manifest,rows,evidence=trial(directory/'transport')
    if (driver.get('driver_sha256')!=DRIVER_SHA or sha(directory/'scout-driver.py')!=DRIVER_SHA
            or driver.get('model_calls')!=0 or driver.get('unit_orders')!=0 or driver.get('policy')!=['scout']
            or driver.get('session_id')!=final['session_id'] or driver.get('pid')!=final['pid']
            or driver.get('process_creation_filetime')!=final['process_creation_filetime']
            or manifest['package_sha256']!=base.package_sha256 or manifest['sources']!=base.budget.native_sources
            or tuple(manifest['flags'])!=base.budget.flags):raise ContractError('macro_scout_field_scope_mismatch')
    flag=next(r['flag'] for r in manifest['consumers'] if r['action']=='scout')
    acks=[r for r in rows if r['kind']=='command_acknowledged'];mask=1<<manifest['flags'].index(flag)
    if len(acks)!=3 or [r['native']['applied_mask'] for r in acks]!=[mask,0,0]:raise ContractError('macro_scout_gate_sequence')
    legal=[r['snapshot'] for r in map(json.loads,(directory/'lawful-snapshots.jsonl').read_text().splitlines()) if 'snapshot' in r]
    if len(legal)<2:raise ContractError('macro_scout_legal_samples_missing')
    observations=[r['observation'] for r in rows if r['kind']=='macro_observation' and 'observation' in r]
    tracker=None;positive=set();released=False
    for obs in observations:
        view=min(legal,key=lambda s:abs(s['game_time_seconds']*15-obs['frame']))
        if not acks[0]['native']['last_frame']<=obs['frame']<=acks[0]['native']['deadline_frame']:continue
        if tracker is None:tracker=ScoutFeedback(obs,view,flag)
        else:tracker.observe(obs,view)
        if obs['frame']<acks[1]['native']['last_frame'] and tracker.score and tracker.active and tracker.group_count:
            positive.add(obs['frame'])
        if obs['frame']>acks[1]['native']['last_frame'] and not tracker.score and not tracker.active:released=True
    if tracker is None or len(positive)<2 or not tracker.moved or not tracker.new_contacts or not released:
        raise ContractError('macro_scout_native_effect_or_legal_feedback_missing')
    binding=load(directory/'visibility-binding.json')
    if (binding['owner']!=int(pre['native']['player'],0) or not binding['participants']['observer_separate_from_combatants']
            or not binding['participants']['two_ai_combatants_verified']):raise ContractError('macro_scout_visibility_binding')
    original=next(directory/'transport/source'/r['copy'] for r in pre['sources'] if r['sha256']==pre['session_sha256'])
    run=Path(load(original)['run_directory'])
    bound_paths=[run/'desktop-session.json',run/'macro-registry.json',run/'macro-budget-bundle.json']
    if any(sha(p)!=binding[k] for p,k in zip(bound_paths,('session_sha256','registry_sha256','bundle_sha256'))):
        raise ContractError('macro_scout_visibility_files_changed')
    visibility=Path(load(bound_paths[2])['visibility']);cap=load(visibility/'build-capability.json')
    if binding['visibility_build']!=cap['build_id']:raise ContractError('macro_scout_visibility_build')
    evidence.update({str(p.resolve()):sha(p) for p in [*bound_paths,visibility/'build-capability.json',visibility/'template-safety.json']})
    for name in ('driver-preflight.json','scout-driver.py','visibility-binding.json','lawful-snapshots.jsonl','driver-result.json'):
        evidence[str((directory/name).resolve())]=sha(directory/name)
    return ScoutingScope(**{f.name:getattr(base,f.name) for f in fields(ProductionPreferenceScope) if f.name!='evidence'},
        evidence={**base.evidence,**evidence},scout_flag=flag)

class MacroScoutingController(MacroProductionController):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.scout_tracker=None;self.scout_plan=None;self.scout_sent={};self.scout_fingerprints={}
        self.scout_latest=None;self.scout_view=None

    @property
    def sent(self):return {**super().sent,**self.scout_sent}
    @property
    def scout_busy(self):return self.scout_tracker is not None and not self.scout_tracker.policy_released
    @property
    def busy(self):return super().busy or self.scout_busy

    def observe_snapshot(self,snapshot):self.scout_view=snapshot

    def refresh(self,sample):
        super().refresh(sample);self.scout_latest=None
        if 'observation' not in sample or self.scout_view is None:return
        obs=sample['observation']
        try:
            scout_sample(obs,self.scout_view,self.scope.scout_flag)
            if self.scout_tracker:self.scout_tracker.observe(obs,self.scout_view)
            self.scout_latest=obs
        except ContractError:
            # No grant or fresh success from missing/stale strategic telemetry.
            pass

    def available_actions(self,game_seconds):
        result=super().available_actions(game_seconds)
        if not self.busy and not self.stopped and self.scout_latest is not None:result+=('scout',)
        return result

    def dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        if 'scout' not in plan.macro_actions:
            if plan.plan_id in self.scout_sent:raise ContractError('macro_plan_id_conflict')
            return super().dispatch(plan,game_seconds,effective_hash=effective_hash,paused=paused)
        actions=tuple(plan.macro_actions)
        if (self.stopped or effective_hash!=self.effective_hash or paused or plan.origin!='model'
                or plan.session_id!=self.session_id or plan.commander_id!=COMMANDER
                or plan.player_id!=3 or not plan.based_on_game_time_seconds<=game_seconds<plan.expires_at_game_seconds
                or plan.tactical_tasks or plan.runtime_task is not None or getattr(plan,'macro_production',None) is not None
                or len(actions)!=len(set(actions)) or len(actions)>2
                or any(a!='scout' and a not in self.scope.budget.available_actions for a in actions)):
            raise ContractError('macro_scout_plan_binding')
        fingerprint=(actions,plan.based_on_game_time_seconds,plan.expires_at_game_seconds,effective_hash)
        if plan.plan_id in self.scout_sent:
            if self.scout_fingerprints[plan.plan_id]!=fingerprint:raise ContractError('macro_plan_id_conflict')
            return self.scout_sent[plan.plan_id]
        if plan.plan_id in super().sent:raise ContractError('macro_plan_id_conflict')
        if 'scout' not in self.available_actions(game_seconds):raise ContractError('macro_scout_not_currently_available')
        tracker=ScoutFeedback(self.scout_latest,self.scout_view,self.scope.scout_flag)
        duration=max(1,min(1350,math.floor((plan.expires_at_game_seconds-game_seconds)*15)))
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':scout:'+effective_hash))
        self.event('model_macro_scout_prepared',plan_id=plan.plan_id,command_id=command_id,actions=list(actions),duration_frames=duration)
        try:receipt=self.transport.apply(list(actions),duration,command_id)
        except Exception:
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        self.scout_tracker=tracker;self.scout_plan=(plan.plan_id,game_seconds+duration/15)
        self.budget.current_actions=tuple(a for a in actions if a in PRESETS)
        public=dict(plan_id=plan.plan_id,command_id=command_id,actions=list(actions),seq=receipt['seq'],
            native_gate_acknowledged=True,native_effect_verified=False,target_policy='original_native_scout_target_selection')
        self.scout_sent[plan.plan_id]=public;self.scout_fingerprints[plan.plan_id]=fingerprint
        self.event('model_macro_scout_acknowledged',**public);return public

    def tick(self,game_seconds):
        if self.scout_busy:
            tracker=self.scout_tracker
            if not self.stopped and (game_seconds>=self.scout_plan[1] or tracker.ever_active and tracker.active==0):
                reason='expired' if game_seconds>=self.scout_plan[1] else 'native_execution_inactive'
                command_id=str(uuid.uuid5(uuid.UUID(self.session_id),self.scout_plan[0]+':scout-release:'+self.effective_hash))
                try:self.transport.apply([],1,command_id)
                except Exception:
                    self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
                tracker.policy_released=True;tracker.release_reason=reason;self.budget.current_actions=()
                self.event('macro_scout_preference_released',reason_code=reason,feedback=tracker.public())
            return
        super().tick(game_seconds)

    def scouting_feedback(self):return self.scout_tracker.public() if self.scout_tracker else None

    def stop(self):
        super().stop()
        if self.scout_busy:
            self.scout_tracker.policy_released=True;self.scout_tracker.release_reason='stopped'
            self.event('macro_scout_preference_released',reason_code='stopped',feedback=self.scout_tracker.public())
