"""Trusted, persistent mission state; never issues game commands.

An executor owns one bounded native lease. Polling this board does not create
subcommands. Every progress record is a host assertion after independent raw
verification, not an LLM completion or an arbitrary status-file import.
"""
from collections import deque
from dataclasses import dataclass,asdict,field
import math
import uuid

from engine import ContractError

MISSION_PURPOSES={('attack','main_attack'),('raid','harass_economy'),('combined_arms','coordinate_force')}
PHASES=('reserved','approach','prepare','engage','retreat','restored')
RETREAT_REASONS={'deadline','target_lost','replan','progress_stalled','damage_limit','host_stop','native_interference','low_hp'}
NATIVE_REASONS={'active','source_damage','fov_lost','approach_stalled','approach_limit','low_hp','engage_limit','retreat_failed','deadline','cancelled','native_override','prepare_failed','heartbeat_lost','target_invalid','initial_binding'}


def number(value,minimum,maximum,code):
    if type(value) not in (float,int) or not math.isfinite(value) or not minimum<=value<=maximum:raise ContractError(code)
    return value


@dataclass(frozen=True)
class MissionEvidence:
    evidence_id:str
    session_id:str
    player_id:int
    commander_id:str
    source:str
    supported_purposes:tuple[tuple[str,tuple[str,...]],...]
    max_duration_game_seconds:float=300
    schema_version:int=1


@dataclass(frozen=True)
class MissionObservations:
    target_currently_visible:bool
    approach_verified:bool=False
    source_damage_amount:float=0
    coordination_verified:bool=False
    retreat_verified:bool=False
    restoration_verified:bool=False
    no_dispatch_verified:bool=False
    distance_to_goal:float|None=None
    interference:str='none'
    disposed_verified:bool=False
    scene_closed_verified:bool=False


@dataclass(frozen=True)
class MissionProgress:
    session_id:str
    player_id:int
    commander_id:str
    source:str
    task_id:str
    mission_id:str
    progress_seq:int
    at_game_seconds:float
    phase:str
    target_contact_id:str|None
    formation_versions:tuple[tuple[str,int],...]
    evidence_sha256:str
    observations:MissionObservations


@dataclass
class Mission:
    mission_id:str
    task_id:str
    module:str
    purpose:str
    target_contact_id:str|None
    target_role:str|None
    target_region:str
    retreat_region:str
    formation_versions:tuple[tuple[str,int],...]
    required_roles:tuple[str,...]
    force_fraction:float
    created_at_game_seconds:float
    deadline_game_seconds:float
    phase:str='reserved'
    progress_seq:int=0
    updated_at_game_seconds:float=0
    retreat_requested_reason:str|None=None
    observations:MissionObservations|None=None
    last_progress:MissionProgress|None=field(default=None,repr=False)
    terminal_status:str|None=None
    reported_damage:float=0
    last_evidence_sha256:str|None=None
    native_progress:dict|None=None

    def public(self):
        return {k:v for k,v in asdict(self).items() if k!='last_progress'}


class MissionBoard:
    def __init__(self,binding,evidence=None):
        self.binding=binding;self.evidence=evidence;self.active={};self.history=deque(maxlen=8);self.failures={}
        self.coverage={module:{'completed':0,'failed':0} for module in ('attack','raid','combined_arms')}
        if evidence is None:return
        if not isinstance(evidence,MissionEvidence) or (evidence.session_id,evidence.player_id,evidence.commander_id)!=(binding.session_id,binding.player_id,binding.commander_id) or type(evidence.player_id) is not int or evidence.source not in {'simulated','game_bridge'} or type(evidence.schema_version) is not int or evidence.schema_version!=1:raise ContractError('mission_evidence_binding')
        try:uuid.UUID(evidence.evidence_id)
        except (ValueError,AttributeError):raise ContractError('mission_evidence_id') from None
        number(evidence.max_duration_game_seconds,60,300,'mission_evidence_duration')
        if not isinstance(evidence.supported_purposes,tuple) or not evidence.supported_purposes:raise ContractError('mission_evidence_purposes')
        seen=set()
        for pair in evidence.supported_purposes:
            if not isinstance(pair,tuple) or len(pair)!=2:raise ContractError('mission_evidence_purposes')
            module,purposes=pair
            if module in seen or not isinstance(purposes,tuple) or not purposes or len(set(purposes))!=len(purposes) or any((module,purpose) not in MISSION_PURPOSES for purpose in purposes):raise ContractError('mission_evidence_purposes')
            seen.add(module)

    def permits(self,module,purpose,source):
        return bool(self.evidence and self.evidence.source==source and purpose in dict(self.evidence.supported_purposes).get(module,()))

    def blocked_by_failure(self,request,at):
        return self.failures.get((request.module,request.purpose,request.target_contact_id),0)>at

    def validate_intent(self,module,purpose,contact_id,snapshot):
        if not self.permits(module,purpose,snapshot.source):return
        target=next((c for c in snapshot.battlefield.contacts if c.contact_id==contact_id),None) if snapshot.battlefield else None
        if target is None or not target.currently_visible or target.relation!='enemy' or snapshot.game_time_seconds-target.observed_at_game_seconds>3 or target.stealth_state not in {'visible','detected'}:raise ContractError('mission_target')
        if target.role in {'air','naval'}:raise ContractError('mission_ground_target')
        if purpose=='harass_economy' and target.role!='economy':raise ContractError('mission_economy_target')

    def commit(self,task,snapshot,deadline,retreat_region):
        if not self.permits(task.request.module,task.request.purpose,snapshot.source):raise ContractError('mission_not_verified')
        existing=self.active.get(task.task_id)
        if existing:
            if deadline!=existing.deadline_game_seconds or retreat_region!=existing.retreat_region:raise ContractError('mission_commit_changed')
            return existing
        if self.blocked_by_failure(task.request,snapshot.game_time_seconds):raise ContractError('mission_failure_backoff')
        number(deadline,snapshot.game_time_seconds+15,snapshot.game_time_seconds+self.evidence.max_duration_game_seconds,'mission_deadline')
        if not isinstance(retreat_region,str) or retreat_region not in snapshot.regions:raise ContractError('mission_retreat_region')
        field=snapshot.battlefield
        region=next((r for r in field.regions if r.region_id==retreat_region),None) if field else None
        if region is None or region.relation not in {'self','ally'}:raise ContractError('mission_retreat_region')
        if len(self.active)>=3:raise ContractError('mission_capacity')
        target=next((c for c in field.contacts if c.contact_id==task.request.target_contact_id),None) if field else None
        self.validate_intent(task.request.module,task.request.purpose,task.request.target_contact_id,snapshot)
        # Same UUID remains stable across plan refresh, TTL expiry and progress polls.
        mission=Mission(str(uuid.UUID(task.task_id)),task.task_id,task.request.module,task.request.purpose,task.request.target_contact_id,target.role if target else None,task.request.target_region,retreat_region,task.request.formation_versions,task.request.required_roles,task.request.force_fraction,snapshot.game_time_seconds,deadline,updated_at_game_seconds=snapshot.game_time_seconds)
        self.active[task.task_id]=mission
        return mission

    def request_retreat(self,task_id,reason):
        mission=self.active.get(task_id)
        if mission is None or reason not in RETREAT_REASONS:raise ContractError('mission_retreat_request')
        if mission.observations and mission.observations.scene_closed_verified:return False
        if mission.retreat_requested_reason is None:mission.retreat_requested_reason=reason;return True
        return False

    def observe(self,snapshot,plan=None):
        changed=[]
        for task_id,mission in self.active.items():
            if mission.phase=='restored' or (mission.observations and mission.observations.scene_closed_verified):continue
            reason=None
            if snapshot.game_time_seconds>=mission.deadline_game_seconds:reason='deadline'
            # New strategic TTL alone does not cancel a mission. An explicit
            # replacement target requests withdrawal and never silently retargets.
            if plan is not None:
                for task in plan.tactical_tasks:
                    if task.module==mission.module and (task.purpose!=mission.purpose or task.target_contact_id!=mission.target_contact_id):reason=reason or 'replan'
            if reason and self.request_retreat(task_id,reason):changed.append((task_id,reason))
        return changed

    def progress(self,value,now):
        if not isinstance(value,MissionProgress) or not isinstance(value.observations,MissionObservations):raise ContractError('mission_progress_type')
        b=self.binding
        if (value.session_id,value.player_id,value.commander_id)!=(b.session_id,b.player_id,b.commander_id) or type(value.player_id) is not int:raise ContractError('mission_progress_binding')
        mission=self.active.get(value.task_id)
        if mission is None or value.mission_id!=mission.mission_id or value.source!=self.evidence.source:raise ContractError('mission_progress_binding')
        if mission.observations and mission.observations.disposed_verified:raise ContractError('mission_disposed_lifecycle')
        if mission.observations and mission.observations.scene_closed_verified:raise ContractError('mission_scene_closed_lifecycle')
        if value.target_contact_id!=mission.target_contact_id or value.formation_versions!=mission.formation_versions or not isinstance(value.formation_versions,tuple):raise ContractError('mission_progress_identity')
        if type(value.progress_seq) is not int or value.progress_seq<1:raise ContractError('mission_progress_sequence')
        if value.progress_seq==mission.progress_seq:
            if value!=mission.last_progress:raise ContractError('mission_progress_duplicate_changed')
            return False
        if value.progress_seq<mission.progress_seq:raise ContractError('mission_progress_sequence')
        number(value.at_game_seconds,mission.updated_at_game_seconds,now,'mission_progress_time')
        if not isinstance(value.evidence_sha256,str) or len(value.evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in value.evidence_sha256):raise ContractError('mission_progress_evidence')
        o=value.observations
        for field in ['target_currently_visible','approach_verified','coordination_verified','retreat_verified','restoration_verified','no_dispatch_verified','disposed_verified','scene_closed_verified']:
            if type(getattr(o,field)) is not bool:raise ContractError('mission_progress_boolean')
        if o.disposed_verified:raise ContractError('mission_disposal_requires_certificate')
        if o.scene_closed_verified:raise ContractError('mission_scene_closure_requires_certificate')
        number(o.source_damage_amount,0,1e8,'mission_progress_damage')
        if o.distance_to_goal is not None:number(o.distance_to_goal,0,1e7,'mission_progress_distance')
        if o.interference not in {'none','native_ai_override','unknown'}:raise ContractError('mission_progress_interference')
        # Polls may miss a short intermediate stage. Raw qualification must
        # independently prove the full chain; phase telemetry itself is no proof.
        allowed={phase:set(PHASES[i:]) for i,phase in enumerate(PHASES)}
        allowed['reserved'].discard('reserved')
        if value.phase not in allowed[mission.phase]:raise ContractError('mission_progress_phase')
        prior=mission.observations
        if prior and (o.source_damage_amount<prior.source_damage_amount or any(getattr(prior,k) and not getattr(o,k) for k in ['approach_verified','coordination_verified','retreat_verified','restoration_verified'])):raise ContractError('mission_progress_regression')
        previous_damage=prior.source_damage_amount if prior else 0
        if o.source_damage_amount>previous_damage and (value.phase not in {'engage','restored'} or value.phase=='engage' and not o.target_currently_visible):raise ContractError('mission_damage_phase')
        if o.retreat_verified and value.phase not in {'retreat','restored'}:raise ContractError('mission_retreat_phase')
        if o.restoration_verified and value.phase!='restored':raise ContractError('mission_restoration_phase')
        mission.phase=value.phase;mission.progress_seq=value.progress_seq;mission.updated_at_game_seconds=value.at_game_seconds;mission.observations=o;mission.last_progress=value;mission.last_evidence_sha256=value.evidence_sha256
        return True

    def certify(self,task_id,observations,evidence_sha256):
        """Enrich final telemetry only after the host independently requalifies raw.

        This is separate from revision deduplication: the same final native
        revision can become provable after hook cleanup/post-observation ends.
        """
        mission=self.active.get(task_id)
        if mission is None or mission.phase!='restored' or mission.last_progress is None:raise ContractError('mission_certification_phase')
        if not isinstance(observations,MissionObservations) or observations.source_damage_amount>mission.reported_damage:raise ContractError('mission_certification_damage')
        from dataclasses import replace
        old=mission.last_progress
        # Reuse strict fact validation without inventing a native revision.
        temporary=replace(old,progress_seq=old.progress_seq+1,observations=observations,evidence_sha256=evidence_sha256)
        self.progress(temporary,max(old.at_game_seconds,mission.updated_at_game_seconds))
        mission.progress_seq=old.progress_seq;mission.last_progress=old

    def certify_not_dispatched(self,task_id,evidence_sha256):
        mission=self.active.get(task_id)
        if mission is None or mission.phase!='reserved' or mission.progress_seq or mission.last_progress is not None or (mission.observations and mission.observations.scene_closed_verified):raise ContractError('mission_not_dispatched_lifecycle')
        if not isinstance(evidence_sha256,str) or len(evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in evidence_sha256):raise ContractError('mission_progress_evidence')
        mission.observations=MissionObservations(False,restoration_verified=True,no_dispatch_verified=True)
        mission.last_evidence_sha256=evidence_sha256

    def certify_disposed(self,task_id,evidence_sha256):
        mission=self.active.get(task_id)
        if mission is None or mission.phase=='restored' or (mission.observations and (mission.observations.no_dispatch_verified or mission.observations.scene_closed_verified)):raise ContractError('mission_disposed_lifecycle')
        if not isinstance(evidence_sha256,str) or len(evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in evidence_sha256):raise ContractError('mission_progress_evidence')
        from dataclasses import replace
        previous=mission.observations or MissionObservations(False)
        mission.observations=replace(previous,target_currently_visible=False,restoration_verified=True,disposed_verified=True)
        mission.last_evidence_sha256=evidence_sha256

    def certify_scene_closed(self,task_id,evidence_sha256):
        """Trusted host's independently requalified scene proof, never a return.

        No native phase/revision is invented, including when the first host poll
        missed issuance. The proof certifies loss of the scene's control scope.
        """
        mission=self.active.get(task_id)
        if mission is None or mission.phase=='restored' or (mission.observations and (mission.observations.no_dispatch_verified or mission.observations.disposed_verified or mission.observations.restoration_verified)):raise ContractError('mission_scene_closed_lifecycle')
        if not isinstance(evidence_sha256,str) or len(evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in evidence_sha256):raise ContractError('mission_progress_evidence')
        if mission.observations and mission.observations.scene_closed_verified:
            if mission.last_evidence_sha256!=evidence_sha256:raise ContractError('mission_scene_closed_certificate_changed')
            return False
        from dataclasses import replace
        previous=mission.observations or MissionObservations(False)
        mission.observations=replace(previous,target_currently_visible=False,scene_closed_verified=True)
        mission.last_evidence_sha256=evidence_sha256
        return True

    def validate_terminal(self,task_id,status,restored,goal_observed=False):
        mission=self.active.get(task_id)
        if mission is None:return
        if mission.observations and mission.observations.scene_closed_verified:
            if status not in {'failed','cancelled'} or restored is not False or goal_observed is not False:raise ContractError('mission_scene_closure_is_not_completion')
            return
        if mission.observations and mission.observations.disposed_verified:
            if status not in {'failed','cancelled'} or not restored:raise ContractError('mission_disposal_is_not_completion')
            return
        if mission.phase=='reserved' and mission.observations and mission.observations.no_dispatch_verified:
            if status not in {'failed','blocked','cancelled'}:raise ContractError('mission_not_dispatched_lifecycle')
            return
        if status in {'failed','blocked','cancelled','completed'} and (mission.phase!='restored' or not mission.observations or not mission.observations.restoration_verified or not(restored or mission.observations.no_dispatch_verified)):raise ContractError('mission_terminal_requires_restoration')
        if status=='completed':
            o=mission.observations
            effect=o.source_damage_amount>0 and (mission.purpose!='coordinate_force' or o.coordination_verified)
            if not o.approach_verified or not o.retreat_verified or not effect or o.interference!='none' or mission.retreat_requested_reason in {'deadline','native_interference'}:raise ContractError('mission_goal_unverified')

    def finish(self,task_id,status,at=None):
        mission=self.active.pop(task_id,None)
        if mission is not None:
            mission.terminal_status=status;self.history.append(mission.public())
            if status in {'completed','failed'}:self.coverage[mission.module][status]+=1
            if status=='failed':
                self.failures[(mission.module,mission.purpose,mission.target_contact_id)]=(at if at is not None else mission.updated_at_game_seconds)+20
                if len(self.failures)>16:
                    oldest=min(self.failures,key=self.failures.get);del self.failures[oldest]

    def public(self):return {'active':[m.public() for m in self.active.values()],'recent_history':list(self.history),'effect_coverage':{m:dict(v) for m,v in self.coverage.items()},'execution_enabled':False}

    def context(self):
        fields=('mission_id','task_id','module','purpose','target_contact_id','target_role','target_region','retreat_region','deadline_game_seconds','phase','progress_seq','retreat_requested_reason')
        active=[{**{key:getattr(m,key) for key in fields},'verified_source_damage':m.observations.source_damage_amount if m.observations else 0} for m in self.active.values()]
        for value,mission in zip(active,self.active.values()):
            if mission.native_progress:value['telemetry']={k:mission.native_progress[k] for k in ('reason','approach_distance','own_hp','damage')}
            if mission.observations and mission.observations.scene_closed_verified:value['scene_closed_verified']=True
        result={'protocol':'continuous_tactical_v1','active':active,'effect_coverage':{m:dict(v) for m,v in self.coverage.items()}}
        closed=[m for m in self.history if (m.get('observations') or {}).get('scene_closed_verified')]
        if closed:result['recent_scene_closures']=[{**{k:m[k] for k in ('mission_id','task_id','module','purpose','phase','terminal_status')},'scene_closed_verified':True,'verified_source_damage':m['observations']['source_damage_amount']} for m in closed[-3:]]
        return result
