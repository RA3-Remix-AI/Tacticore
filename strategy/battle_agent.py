"""Persistent typed battle memory and non-executing capability coordinator.

Only validated snapshots, accepted plans, and trusted bounded executor feedback
enter memory. Compression is deterministic and never asks a model to invent facts.
"""
from __future__ import annotations
from collections import Counter,deque
from dataclasses import asdict,dataclass
import json
import math
from pathlib import Path
import uuid

from engine import ContractError,FOCI,Snapshot,StrategyEngine
from battlefield import PURPOSES as TACTICAL_PURPOSES,validate_intents
from missions import MissionBoard,MissionEvidence,MissionProgress,MissionObservations

MODULES=("build","raid","attack","combined_arms")
IN_FLIGHT=frozenset({"dispatch_pending","active"})
LOCKS=frozenset({"production_queue","main_force","raid_force"})
PURPOSES={"build":frozenset({"production_focus","native_baseline"}),"raid":frozenset({"harass_economy","recon"}),"attack":frozenset({"main_attack"}),"combined_arms":frozenset({"coordinate_force","defend_base"})}
FEEDBACK=frozenset({"started","completed","failed","blocked","cancelled"})
FEEDBACK_REASONS=frozenset({"ok","insufficient_funds","prerequisite_missing","no_route","target_lost","not_verified","execution_error","expired","lease_lost","native_interference","formation_changed","restoration_unverified","visibility_lost","goal_unobserved"})
POST_RESPONSE_GUARDS=frozenset({"context_objective","context_tactical_task","context_formation","context_contact","context_tactical_region","tactical_actor_roles","tactical_single_actor_role","tactical_air_target_requires_anti_air","model_size","model_json","duplicate_key","nonfinite_json","model_object","mission_target","mission_ground_target","mission_economy_target"})


@dataclass(frozen=True)
class BuildEvidence:
    """Created by a trusted host AFTER its capability experiment, never by LLM JSON.

    This record is an application assertion, not cryptographic proof. No CLI
    flag imports or creates it; it still does not enable execution in this module.
    """
    evidence_id:str
    session_id:str
    player_id:int
    source:str
    supported_foci:tuple[str,...]=("anti_air",)


@dataclass(frozen=True)
class TacticalEvidence:
    """Purpose-level host assertion after real dispatch/outcome/restoration tests."""
    evidence_id:str
    session_id:str
    player_id:int
    source:str
    supported_purposes:tuple[tuple[str,tuple[str,...]],...]=()
    actor_roles:tuple[tuple[str,str,tuple[str,...]],...]=()


@dataclass(frozen=True)
class RestorationEvidence:
    """Trusted host assertion after restoring the exact quarantined formation."""
    evidence_id:str
    session_id:str
    player_id:int
    source:str
    formation_versions:tuple[tuple[str,int],...]


@dataclass(frozen=True)
class TaskRequest:
    module:str
    purpose:str
    target_region:str|None
    focus:str|None
    spend_fraction:float
    force_fraction:float
    resource_locks:tuple[str,...]
    priority:int
    target_contact_id:str|None=None
    formation_ids:tuple[str,...]=()
    formation_versions:tuple[tuple[str,int],...]=()
    required_roles:tuple[str,...]=()

    def key(self):return (self.module,self.purpose,self.target_region,self.focus,self.target_contact_id,self.formation_ids,self.formation_versions,self.required_roles)


@dataclass
class ModuleTask:
    task_id:str
    request:TaskRequest
    status:str
    reason_code:str
    updated_at_game_seconds:float
    plan_id:str=""
    generation:int=0
    expires_at_game_seconds:float=0
    execution_start:dict|None=None

    def public(self):
        return {"task_id":self.task_id,"plan_id":self.plan_id,"generation":self.generation,"expires_at_game_seconds":self.expires_at_game_seconds,**asdict(self.request),"status":self.status,"reason_code":self.reason_code,"updated_at_game_seconds":self.updated_at_game_seconds}


class TaskCoordinator:
    def __init__(self,engine:StrategyEngine,build_evidence:BuildEvidence|None=None,tactical_evidence:TacticalEvidence|None=None):
        self.engine=engine;self.build_evidence=build_evidence;self.tactical_evidence=tactical_evidence;self.tasks=[];self.failures={};self.history=deque(maxlen=16);self.generation=0;self.quarantined_formations={}
        if build_evidence is not None:
            b=engine.binding
            if build_evidence.session_id!=b.session_id or build_evidence.player_id!=b.player_id or build_evidence.source not in {"simulated","game_bridge"}:
                raise ContractError("build_evidence_binding")
            try:uuid.UUID(build_evidence.evidence_id)
            except (ValueError,AttributeError):raise ContractError("build_evidence_id") from None
            if not isinstance(build_evidence.supported_foci,tuple) or not build_evidence.supported_foci or any(not isinstance(focus,str) or focus not in FOCI or focus=="native_baseline" for focus in build_evidence.supported_foci) or len(set(build_evidence.supported_foci))!=len(build_evidence.supported_foci):raise ContractError("build_evidence_focus")
        if tactical_evidence is not None:
            b=engine.binding
            if tactical_evidence.session_id!=b.session_id or type(tactical_evidence.player_id) is not int or tactical_evidence.player_id!=b.player_id or tactical_evidence.source not in {"simulated","game_bridge"}:raise ContractError("tactical_evidence_binding")
            try:uuid.UUID(tactical_evidence.evidence_id)
            except (ValueError,AttributeError):raise ContractError("tactical_evidence_id") from None
            if not isinstance(tactical_evidence.supported_purposes,tuple):raise ContractError("tactical_evidence_purposes")
            modules=set()
            for pair in tactical_evidence.supported_purposes:
                if not isinstance(pair,tuple) or len(pair)!=2:raise ContractError("tactical_evidence_purposes")
                module,purposes=pair
                if not isinstance(module,str) or module not in TACTICAL_PURPOSES or module in modules or not isinstance(purposes,tuple) or not purposes or any(not isinstance(p,str) or p not in TACTICAL_PURPOSES[module] for p in purposes) or len(set(purposes))!=len(purposes):raise ContractError("tactical_evidence_purposes")
                modules.add(module)
            from battlefield import ROLES
            if not isinstance(tactical_evidence.actor_roles,tuple):raise ContractError("tactical_evidence_actor_roles")
            constrained=set()
            for entry in tactical_evidence.actor_roles:
                if not isinstance(entry,tuple) or len(entry)!=3:raise ContractError("tactical_evidence_actor_roles")
                module,purpose,roles=entry
                if not isinstance(module,str) or not isinstance(purpose,str) or purpose not in dict(tactical_evidence.supported_purposes).get(module,()) or (module,purpose) in constrained or not isinstance(roles,tuple) or not roles or any(not isinstance(role,str) or role not in ROLES for role in roles) or len(set(roles))!=len(roles):raise ContractError("tactical_evidence_actor_roles")
                constrained.add((module,purpose))

    def verified_tactical(self,module,purpose,source):
        return self.tactical_evidence is not None and self.tactical_evidence.source==source and purpose in dict(self.tactical_evidence.supported_purposes).get(module,())

    def allowed_actor_roles(self,module,purpose,source):
        if not self.verified_tactical(module,purpose,source):return None
        return next((roles for name,goal,roles in self.tactical_evidence.actor_roles if (name,goal)==(module,purpose)),None)

    def validate_actor_roles(self,module,purpose,formation_ids,required_roles,battlefield,source,target_role=None):
        allowed=self.allowed_actor_roles(module,purpose,source)
        if allowed is None:return  # Legacy trusted evidence has no role restriction.
        if not isinstance(required_roles,(list,tuple)) or not required_roles or any(not isinstance(role,str) or role not in allowed for role in required_roles):raise ContractError("tactical_actor_roles")
        if purpose in {"recon","main_attack","harass_economy"} and len(required_roles)!=1:raise ContractError("tactical_single_actor_role")
        if purpose in {"main_attack","harass_economy"} and target_role=="air" and tuple(required_roles)!=("anti_air",):raise ContractError("tactical_air_target_requires_anti_air")
        formations={f.formation_id:f for f in battlefield.formations} if battlefield else {}
        for ident in formation_ids:
            formation=formations.get(ident)
            if formation is None:raise ContractError("tactical_actor_roles")
            present={role for role,count in formation.roles if count}
            if purpose in {"recon","main_attack","harass_economy"}:
                # The trusted allocator selects ONE actor of the requested role;
                # other members of this roster are not assigned to this task.
                if not set(required_roles).issubset(present):raise ContractError("tactical_actor_roles")
            elif not present or not present.issubset(allowed):raise ContractError("tactical_actor_roles")

    def capability_manifest(self,source):
        available=self.build_evidence is not None and self.build_evidence.source==source
        result={module:{"state":"planned_only" if module=="build" and available else "unavailable","reason_code":"host_evidence_present" if module=="build" and available else "not_verified",**({"verified_production_focus":list(self.build_evidence.supported_foci)} if module=="build" and available else {})} for module in MODULES}
        for module in TACTICAL_PURPOSES:
            purposes=[purpose for purpose in sorted(TACTICAL_PURPOSES[module]) if self.verified_tactical(module,purpose,source)]
            if purposes:
                result[module]={"state":"planned_only","reason_code":"host_evidence_present","verified_purposes":purposes}
                constraints={purpose:list(roles) for purpose in purposes if (roles:=self.allowed_actor_roles(module,purpose,source)) is not None}
                if constraints:result[module]["purpose_actor_roles"]=constraints
        return result

    def reconcile(self,requests,at,regions,spend_cap,force_cap,source,plan_id="",expires_at_game_seconds=0):
        if len(requests)>8:raise ContractError("too_many_module_tasks")
        old={task.request.key():task for task in self.tasks};locks=set();claimed_formations=set();spend=force=0;result=[];keys=set()
        requested={request.key() for request in requests}
        # In-flight work survives strategic changes so its result can be recorded.
        for task in self.tasks:
            if task.status in IN_FLIGHT:
                # Reserve every acknowledged task before sorting new intent.
                # Repeating its request must not let a higher-priority new task
                # claim the same roster or budget ahead of the existing lease.
                if task.request.key() not in requested:result.append(task)
                locks.update(task.request.resource_locks);claimed_formations.update(task.request.formation_ids);spend+=task.request.spend_fraction;force+=task.request.force_fraction
            elif task.request.key() not in requested:self.history.append(task.public())
        for request in sorted(requests,key=lambda x:-x.priority):
            if request.module not in MODULES or request.purpose not in PURPOSES[request.module] or request.key() in keys:
                raise ContractError("module_request")
            keys.add(request.key())
            if request.target_region is not None and request.target_region not in regions:raise ContractError("module_target")
            if request.focus is not None and request.focus not in FOCI:raise ContractError("module_focus")
            if type(request.priority) is not int or not 0<=request.priority<=100:raise ContractError("module_priority")
            for value in [request.spend_fraction,request.force_fraction]:
                if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not 0<=value<=1:raise ContractError("module_budget")
            if set(request.resource_locks)-LOCKS or len(set(request.resource_locks))!=len(request.resource_locks):raise ContractError("module_locks")
            from battlefield import ident,ROLES
            if not isinstance(request.formation_ids,tuple) or len(request.formation_ids)>4 or len(set(request.formation_ids))!=len(request.formation_ids):raise ContractError("module_formations")
            for formation_id in request.formation_ids:ident(formation_id,"module_formation_id")
            if request.target_contact_id is not None:ident(request.target_contact_id,"module_contact_id")
            if not isinstance(request.required_roles,tuple) or any(not isinstance(role,str) or role not in ROLES for role in request.required_roles) or len(set(request.required_roles))!=len(request.required_roles):raise ContractError("module_roles")
            if not isinstance(request.formation_versions,tuple) or len(request.formation_versions)!=len(request.formation_ids) or any(not isinstance(pair,tuple) or len(pair)!=2 or pair[0]!=request.formation_ids[i] or type(pair[1]) is not int or pair[1]<1 for i,pair in enumerate(request.formation_versions)):raise ContractError("module_formation_versions")
            if request.module=="build" and (request.formation_ids or request.target_contact_id is not None or request.required_roles):raise ContractError("module_request")
            task=old.get(request.key())
            if task is not None and task.plan_id!=plan_id and task.status not in IN_FLIGHT:
                self.history.append(task.public());task=None
            if task is None:
                self.generation+=1;task=ModuleTask(uuid.uuid4().hex,request,"planned","plan_only",at,plan_id,self.generation,expires_at_game_seconds)
            if task.status in IN_FLIGHT:request=task.request
            else:task.request=request
            if task.status in IN_FLIGHT|{"completed","failed","cancelled"}:status,reason=task.status,task.reason_code
            elif locks & set(request.resource_locks):status,reason="blocked","resource_conflict"
            elif claimed_formations & set(request.formation_ids):status,reason="blocked","formation_conflict"
            elif set(request.formation_ids)&set(self.quarantined_formations):status,reason="blocked","restoration_unverified"
            elif spend+request.spend_fraction>spend_cap+1e-6 or force+request.force_fraction>force_cap+1e-6:status,reason="blocked","budget_conflict"
            elif self.failures.get(request.key(),{}).get("retry_after",0)>at:status,reason="blocked","failure_backoff"
            elif request.module=="build" and request.purpose=="native_baseline":status,reason="planned","passive_native_ai"
            elif request.module=="build" and self.build_evidence is not None and self.build_evidence.source==source and request.focus in self.build_evidence.supported_foci:status,reason="planned","awaiting_host_dispatch"
            elif request.formation_ids and self.verified_tactical(request.module,request.purpose,source):status,reason="planned","awaiting_host_dispatch"
            else:status,reason="unavailable","not_verified"
            # Abstract planning allocation only, never an allocation of real units.
            if status!="blocked" and status not in IN_FLIGHT:
                spend+=request.spend_fraction;force+=request.force_fraction;locks.update(request.resource_locks);claimed_formations.update(request.formation_ids)
            if status!=task.status or reason!=task.reason_code:task.updated_at_game_seconds=at
            task.status,task.reason_code=status,reason;result.append(task)
        self.tasks=result
        # Only a bounded latest failure record per semantic request is retained.
        if len(self.failures)>16:
            oldest=sorted(self.failures,key=lambda key:self.failures[key]["at"])
            for key in oldest[:-16]:del self.failures[key]
        return result


class BattleAgent:
    def __init__(self,engine:StrategyEngine,*,event_capacity=32,dialogue_turns=2,context_budget_bytes=8192,enemy_ttl_game_seconds=60,build_evidence=None,tactical_evidence=None,mission_evidence=None,memory_path:Path|None=None,jobs_path:Path|None=None):
        if type(event_capacity) is not int or not 4<=event_capacity<=64 or type(dialogue_turns) is not int or not 0<=dialogue_turns<=4 or type(context_budget_bytes) is not int or not 4096<=context_budget_bytes<=16384:
            raise ContractError("agent_limits")
        if not isinstance(enemy_ttl_game_seconds,(float,int)) or not 5<=enemy_ttl_game_seconds<=300:raise ContractError("enemy_ttl")
        self.engine=engine;self.events=deque();self.event_capacity=event_capacity;self.dialogue=deque(maxlen=dialogue_turns)
        self.context_budget=context_budget_bytes;self.enemy_ttl=enemy_ttl_game_seconds;self.enemy_facts={};self.latest=None
        self.feedback=deque(maxlen=8);self.goals=TaskCoordinator(engine,build_evidence,tactical_evidence);self.memory_path=memory_path;self.jobs_path=jobs_path;self.contact_facts={}
        self.missions=MissionBoard(engine.binding,mission_evidence)
        self.summary={"events_compacted":0,"counts_by_kind":{},"completed_tasks":{m:0 for m in MODULES},"failed_tasks":{m:0 for m in MODULES},"last_compacted_game_time":None}
        self.event_id=0;self.last_prompt_event=0;self.last_prompt_snapshot=None;self.last_intent=None
        self.last_failures={}
        self.context_audit_path=Path(memory_path).with_name(Path(memory_path).stem+'.context-audit.jsonl') if memory_path is not None else None
        self.metrics={"context_builds":0,"compactions":0,"max_payload_bytes":0,"expired_enemy_facts":0,"context_rejections":0,"post_response_guard_rejections":0}

    def _event(self,kind,at,**facts):
        self.event_id+=1
        record={"event_id":self.event_id,"kind":kind,"at_game_seconds":at,**facts}
        if len(self.events)==self.event_capacity:
            old=self.events.popleft();self.summary["events_compacted"]+=1;self.summary["last_compacted_game_time"]=old["at_game_seconds"]
            counts=self.summary["counts_by_kind"];counts[old["kind"]]=counts.get(old["kind"],0)+1
            if old["kind"]=="execution_feedback" and old.get("status") in {"completed","failed"}:
                key="completed_tasks" if old["status"]=="completed" else "failed_tasks"
                self.summary[key][old["module"]]+=1
            self.metrics["compactions"]+=1
        self.events.append(record)

    def observe(self,raw):
        snapshot=self.engine.observe(raw)
        if self.latest is not None and snapshot==self.latest:return snapshot
        previous=self.latest;self.latest=snapshot;at=snapshot.game_time_seconds
        for fact in self.enemy_facts.values():fact["currently_visible"]=False
        for role,count,seen,visible in snapshot.enemy_observations:
            if at-seen>self.enemy_ttl:continue
            old=self.enemy_facts.get(role)
            if old is None or seen>=old["observed_at_game_seconds"]:
                if old is None or old["count"]!=count:self._event("enemy_observation",at,role=role,count=count,observed_at_game_seconds=seen)
                self.enemy_facts[role]={"role":role,"count":count,"observed_at_game_seconds":seen,"currently_visible":bool(visible and at-seen<=3)}
        for role,fact in list(self.enemy_facts.items()):
            if at-fact["observed_at_game_seconds"]>self.enemy_ttl:
                del self.enemy_facts[role];self.metrics["expired_enemy_facts"]+=1;self._event("intel_expired",at,role=role)
        for fact in self.contact_facts.values():fact["currently_visible"]=False
        if snapshot.battlefield is not None and snapshot.battlefield.visibility_verified:
            for contact in snapshot.battlefield.contacts:
                old=self.contact_facts.get(contact.contact_id)
                if at-contact.observed_at_game_seconds>self.enemy_ttl:continue
                if old is not None and (old["owner_player_id"]!=contact.owner_player_id or old["relation"]!=contact.relation or old["role"]!=contact.role):raise ContractError("contact_identity_changed")
                if old is None and not contact.currently_visible:raise ContractError("unseen_contact_history")
                if old is None or contact.observed_at_game_seconds>=old["observed_at_game_seconds"]:
                    if old is not None and not contact.currently_visible and (contact.region_id!=old["region_id"] or contact.observed_at_game_seconds!=old["observed_at_game_seconds"]):raise ContractError("hidden_contact_updated")
                    value=contact.public();value["currently_visible"]=bool(contact.currently_visible and at-contact.observed_at_game_seconds<=3)
                    self.contact_facts[contact.contact_id]=value
                    if old is None:self._event("contact_observed",at,role=contact.role,relation=contact.relation,region_id=contact.region_id)
        for contact_id,fact in list(self.contact_facts.items()):
            if at-fact["observed_at_game_seconds"]>self.enemy_ttl:
                del self.contact_facts[contact_id];self._event("contact_expired",at,role=fact["role"])
        if len(self.contact_facts)>64:
            oldest=sorted(self.contact_facts,key=lambda key:(self.contact_facts[key]["observed_at_game_seconds"],key))
            for contact_id in oldest[:-64]:del self.contact_facts[contact_id]
        for event in snapshot.events:self._event("game_event",at,event=event)
        if previous is None:self._event("session_observed",at)
        elif abs(snapshot.credits-previous.credits)>=500:self._event("economy_change",at,credits_delta=snapshot.credits-previous.credits)
        for task_id,reason in self.missions.observe(snapshot,self.engine.current):self._event('mission_retreat_requested',at,task_id=task_id,reason_code=reason)
        return snapshot

    def _requests(self,plan):
        budget=dict(plan.budget);target=plan.objective_region;requests=[]
        if plan.production_focus=="native_baseline":requests.append(TaskRequest("build","native_baseline",None,"native_baseline",0,0,(),80))
        else:requests.append(TaskRequest("build","production_focus",None,plan.production_focus,budget["economy"]+budget["army"]+budget["tech"],0,("production_queue",),80))
        field=max(0,1-budget["reserve"])
        if plan.stance in {"raid","scout"}:requests.append(TaskRequest("raid","harass_economy" if plan.stance=="raid" else "recon",target,None,0,field*.4,("raid_force",),60))
        if plan.stance=="pressure":requests.append(TaskRequest("attack","main_attack",target,None,0,field,("main_force",),60))
        requests.append(TaskRequest("combined_arms","defend_base" if plan.stance=="defend" else "coordinate_force",target,None,0,0,(),40))
        if plan.tactical_tasks:
            modules={task.module for task in plan.tactical_tasks};requests=[r for r in requests if r.module not in modules]
            for task in plan.tactical_tasks:
                # Versions are host observation data, never a model-selected value.
                versions=task.formation_versions
                locks=("raid_force",) if task.module=="raid" else ("main_force",)
                requests.append(TaskRequest(task.module,task.purpose,task.target_region,None,0,task.force_fraction,locks,70 if task.module=="combined_arms" else 60,task.target_contact_id,task.formation_ids,versions,task.required_roles))
        return requests

    def _synchronize_goals(self):
        plan=self.engine.current
        if self.latest is not None:
            for task_id,reason in self.missions.observe(self.latest,plan):self._event('mission_retreat_requested',self.latest.game_time_seconds,task_id=task_id,reason_code=reason)
        if plan is None or self.latest is None or self.latest.game_time_seconds>=plan.expires_at_game_seconds or plan.production_focus not in self.latest.available_foci or (plan.objective_region is not None and plan.objective_region not in self.latest.regions):
            for task in self.goals.tasks:
                if task.status not in IN_FLIGHT:self.goals.history.append(task.public())
            self.goals.tasks=[task for task in self.goals.tasks if task.status in IN_FLIGHT];return
        budget=dict(plan.budget);cap=1-budget["reserve"]
        requests=[request for request in self._requests(plan) if request.target_region is None or request.target_region in self.latest.regions]
        self.goals.reconcile(requests,self.latest.game_time_seconds,self.latest.regions,cap,cap,self.latest.source,plan.plan_id,plan.expires_at_game_seconds)
        for task in self.goals.tasks:
            if task.request.module=="build" or not task.request.formation_ids or task.status in IN_FLIGHT|{"completed","failed","cancelled","unavailable"}:continue
            battlefield=self.latest.battlefield
            formations={f.formation_id:f for f in battlefield.formations} if battlefield else {}
            reason=None
            if self.missions.blocked_by_failure(task.request,self.latest.game_time_seconds):reason='failure_backoff'
            if any(ident not in formations or not formations[ident].available or formations[ident].version!=version for ident,version in task.request.formation_versions):reason="formation_changed"
            target_role=next((c.role for c in battlefield.contacts if c.contact_id==task.request.target_contact_id),None) if battlefield else None
            try:self.goals.validate_actor_roles(task.request.module,task.request.purpose,task.request.formation_ids,task.request.required_roles,battlefield,self.latest.source,target_role)
            except ContractError:reason="formation_changed"
            if task.request.target_contact_id:
                contact=next((c for c in battlefield.contacts if c.contact_id==task.request.target_contact_id),None) if battlefield else None
                if contact is None or contact.relation!="enemy" or not contact.currently_visible or contact.stealth_state=="unknown" or self.latest.game_time_seconds-contact.observed_at_game_seconds>3:reason="target_lost"
            if task.request.purpose=="defend_base":
                region=next((r for r in battlefield.regions if r.region_id==task.request.target_region),None) if battlefield else None
                if region is None or region.relation not in {"self","ally"}:reason="target_lost"
            if reason:task.status="blocked";task.reason_code=reason;task.updated_at_game_seconds=self.latest.game_time_seconds

    def host_commit_task(self,task_id,*,mission_deadline_game_seconds=None,retreat_region=None):
        """Pin an acknowledged host dispatch, without claiming native issuance.

        Trusted host only: persist its exactly-once ledger/reservation first,
        then commit before crossing an asynchronous submit boundary. A queued
        transport ACK is not a started receipt. No model/CLI calls this method.
        """
        self._synchronize_goals()
        task=next((task for task in self.goals.tasks if task.task_id==task_id),None)
        if task is None or self.latest is None or self.engine.stopped:raise ContractError("host_commit_unknown_task")
        if task.status in IN_FLIGHT:
            if mission_deadline_game_seconds is not None:
                if task_id not in self.missions.active:raise ContractError('mission_commit_after_dispatch')
                self.missions.commit(task,self.latest,mission_deadline_game_seconds,retreat_region)
            return self._task_with_mission(task)
        if task.status!="planned" or task.reason_code!="awaiting_host_dispatch" or self.latest.paused or self.latest.game_time_seconds>=task.expires_at_game_seconds:raise ContractError("host_commit_not_dispatchable")
        if mission_deadline_game_seconds is not None:self.missions.commit(task,self.latest,mission_deadline_game_seconds,retreat_region)
        elif retreat_region is not None:raise ContractError('mission_deadline_required')
        task.status="dispatch_pending";task.reason_code="host_accepted_awaiting_native";task.updated_at_game_seconds=self.latest.game_time_seconds
        self._event("host_commit",self.latest.game_time_seconds,module=task.request.module,task_id=task.task_id,status="dispatch_pending")
        self._write_memory()
        return self._task_with_mission(task)

    def _task_with_mission(self,task):
        result=task.public();mission=self.missions.active.get(task.task_id)
        if mission:result['mission']=mission.public()
        return result

    def request_mission_retreat(self,task_id,reason):
        if self.latest is None:raise ContractError('no_agent_snapshot')
        if self.missions.request_retreat(task_id,reason):self._event('mission_retreat_requested',self.latest.game_time_seconds,task_id=task_id,reason_code=reason)
        self._write_memory()

    def pending_mission_retreats(self):
        return [{'task_id':m.task_id,'mission_id':m.mission_id,'reason':m.retreat_requested_reason} for m in self.missions.active.values() if m.retreat_requested_reason and m.phase!='restored']

    def capability_manifest(self):
        source=self.latest.source if self.latest else 'simulated';manifest=self.goals.capability_manifest(source)
        for module,value in manifest.items():
            purposes=[p for p in value.get('verified_purposes',[]) if self.missions.permits(module,p,source)]
            if purposes:value.update(mission_protocol='continuous_tactical_v1',verified_mission_purposes=purposes,mission_max_duration_game_seconds=self.missions.evidence.max_duration_game_seconds)
        return manifest

    def record_mission_progress(self,task_id,raw,*,observations,evidence_sha256,verified_terminal_clock=None):
        """Trusted host only, AFTER raw phase/identity/damage verification.

        The native lease owns all subcommands; recording a new revision does
        not dispatch anything. No model/CLI can grant a mission or report this.
        """
        fields={'mission_id','stage','revision','observed_frame','deadline_frame','approach_distance','own_hp','damage','reason'}
        if not isinstance(raw,dict) or set(raw)!=fields or self.latest is None:raise ContractError('mission_progress_fields')
        mission=self.missions.active.get(task_id)
        if mission is None:raise ContractError('mission_progress_binding')
        if type(raw['observed_frame']) is not int or raw['observed_frame']<0 or type(raw['deadline_frame']) is not int or raw['deadline_frame']!=round(mission.deadline_game_seconds*15):raise ContractError('mission_progress_frame')
        if type(raw['revision']) is not int or raw['stage'] not in {'approach','prepare','engage','retreat','restored'}:raise ContractError('mission_progress_sequence')
        if raw['observed_frame']>raw['deadline_frame']+(90 if raw['stage']=='restored' else 0):raise ContractError('mission_progress_frame')
        from missions import number
        number(raw['own_hp'],0,1e7,'mission_progress_hp')
        if raw['approach_distance'] is not None:number(raw['approach_distance'],0,1e7,'mission_progress_distance')
        number(raw['damage'],0,1e8,'mission_progress_damage')
        from missions import NATIVE_REASONS
        if not isinstance(raw['reason'],str) or raw['reason'] not in NATIVE_REASONS:raise ContractError('mission_progress_reason')
        if not isinstance(observations,MissionObservations) or observations.source_damage_amount>raw['damage'] or raw['approach_distance']!=observations.distance_to_goal:raise ContractError('mission_progress_observations')
        now=self.latest.game_time_seconds
        if verified_terminal_clock is not None:
            if raw['stage']!='restored' or observations.restoration_verified is not True:raise ContractError('mission_terminal_clock_guard')
            number(verified_terminal_clock,raw['observed_frame']/15,(raw['deadline_frame']+90)/15,'mission_terminal_clock')
            now=max(now,verified_terminal_clock)
        b=self.engine.binding
        value=MissionProgress(b.session_id,b.player_id,b.commander_id,self.latest.source,task_id,raw['mission_id'],raw['revision'],raw['observed_frame']/15,raw['stage'],mission.target_contact_id,mission.formation_versions,evidence_sha256,observations)
        if raw['revision']==mission.progress_seq and raw!=mission.native_progress:raise ContractError('mission_progress_duplicate_changed')
        if raw['damage']<mission.reported_damage:raise ContractError('mission_reported_damage_regression')
        changed=self.missions.progress(value,now)
        if changed:
            mission.reported_damage=raw['damage']
            mission.native_progress=dict(raw)
        if changed:self._event('mission_progress',value.at_game_seconds,module=mission.module,task_id=task_id,phase=value.phase,revision=value.progress_seq,source_damage=observations.source_damage_amount,reason_code=raw['reason'])
        self._write_memory();return changed

    def certify_mission_result(self,task_id,*,observations,evidence_sha256):
        self.missions.certify(task_id,observations,evidence_sha256)
        self._event('mission_result_verified',self.latest.game_time_seconds,task_id=task_id,source_damage=observations.source_damage_amount)
        self._write_memory()

    def certify_mission_not_dispatched(self,task_id,*,evidence_sha256):
        task=next((t for t in self.goals.tasks if t.task_id==task_id),None)
        if task is None or task.status!='dispatch_pending' or task.execution_start is not None:raise ContractError('mission_not_dispatched_lifecycle')
        self.missions.certify_not_dispatched(task_id,evidence_sha256)
        self._event('mission_dispatch_rejected',self.latest.game_time_seconds,task_id=task_id,reason_code='no_dispatch_verified')
        self._write_memory()

    def certify_mission_disposed(self,task_id,*,evidence_sha256):
        task=next((t for t in self.goals.tasks if t.task_id==task_id),None)
        if task is None or task.status not in IN_FLIGHT:raise ContractError('mission_disposed_lifecycle')
        self.missions.certify_disposed(task_id,evidence_sha256)
        self._event('mission_actor_disposed',self.latest.game_time_seconds,task_id=task_id,reason_code='disposed_verified')
        self._write_memory()

    def record_feedback(self,raw):
        allowed={"session_id","player_id","commander_id","task_id","status","reason_code","at_game_seconds","source"}
        if isinstance(raw,dict) and "execution" in raw:allowed.add("execution")
        if not isinstance(raw,dict) or set(raw)!=allowed or self.latest is None:raise ContractError("feedback_fields")
        binding=self.engine.binding
        if raw["session_id"]!=binding.session_id or raw["commander_id"]!=binding.commander_id or type(raw["player_id"]) is not int or raw["player_id"]!=binding.player_id or raw["source"]!=self.latest.source:raise ContractError("feedback_binding")
        if not isinstance(raw["status"],str) or not isinstance(raw["reason_code"],str) or raw["status"] not in FEEDBACK or raw["reason_code"] not in FEEDBACK_REASONS:raise ContractError("feedback_enum")
        at=raw["at_game_seconds"]
        if isinstance(at,bool) or not isinstance(at,(int,float)) or not math.isfinite(at) or not 0<=at<=self.latest.game_time_seconds:raise ContractError("feedback_time")
        task=next((task for task in self.goals.tasks if task.task_id==raw["task_id"]),None)
        if task is None:raise ContractError("feedback_unverified_capability")
        if task.request.module=="build":
            if task.request.purpose=="native_baseline" or self.goals.build_evidence is None or self.goals.build_evidence.source!=self.latest.source or task.request.focus not in self.goals.build_evidence.supported_foci or "execution" in raw:raise ContractError("feedback_unverified_capability")
        elif not self.goals.verified_tactical(task.request.module,task.request.purpose,self.latest.source):raise ContractError("feedback_unverified_capability")
        else:self._validate_tactical_feedback(raw,task)
        self.missions.validate_terminal(task.task_id,raw['status'],raw.get('execution',{}).get('restoration_verified',False))
        if at<task.updated_at_game_seconds or task.status in {"completed","failed","cancelled","unavailable","blocked"}:raise ContractError("feedback_lifecycle")
        status={"started":"active","blocked":"blocked"}.get(raw["status"],raw["status"])
        if task.request.module!="build" and raw["status"]=="started":task.execution_start={**raw["execution"],"formation_versions":dict(raw["execution"]["formation_versions"])}
        if task.request.module!="build" and "execution" in raw and not raw["execution"]["restoration_verified"] and raw["status"] in {"failed","blocked","cancelled"}:
            self.goals.quarantined_formations.update(dict(task.request.formation_versions))
        task.status=status;task.reason_code=raw["reason_code"];task.updated_at_game_seconds=at
        if status in {"failed","blocked"}:
            self.goals.failures[task.request.key()]={"at":at,"retry_after":at+20,"reason_code":raw["reason_code"]}
            self.last_failures[task.request.module]={"module":task.request.module,"purpose":task.request.purpose,"focus":task.request.focus,"reason_code":raw["reason_code"],"at_game_seconds":at,"retry_after_game_seconds":at+20}
            if task.request.target_contact_id:self.last_failures[task.request.module].update(target_contact_id=task.request.target_contact_id,target_region=task.request.target_region)
            mission=self.missions.active.get(task.task_id)
            if mission and mission.native_progress:self.last_failures[task.request.module]['mission_reason']=mission.native_progress['reason']
            self.engine.request_reassessment("execution_failure")
        record={"task_id":task.task_id,"module":task.request.module,"status":raw["status"],"reason_code":raw["reason_code"],"at_game_seconds":at,"source":self.latest.source}
        if "execution" in raw:record["execution"]={**raw["execution"],"formation_versions":dict(raw["execution"]["formation_versions"])}
        self.feedback.append(record);self._event("execution_feedback",at,module=task.request.module,status=raw["status"],reason_code=raw["reason_code"])
        if raw['status'] in {'completed','failed','blocked','cancelled'}:self.missions.finish(task.task_id,raw['status'],at)
        self._write_memory()

    def _validate_tactical_feedback(self,raw,task):
        from battlefield import keys,integer,boolean,enum
        if task.status!="active" and raw["status"] in {"failed","blocked","cancelled"} and "execution" not in raw:
            if task.status=="dispatch_pending" and raw["reason_code"] in {"execution_error","native_interference","restoration_unverified","goal_unobserved"}:raise ContractError("pending_outcome_requires_native_evidence")
            return
        execution=keys(raw.get("execution"),{"formation_versions","issued_frame","expires_frame","command_source","interference","goal_observed","restoration_verified"},"tactical_feedback_fields")
        versions=execution["formation_versions"]
        if type(versions) is not dict or set(versions)!=set(task.request.formation_ids) or any(type(v) is not int for v in versions.values()) or versions!=dict(task.request.formation_versions):raise ContractError("tactical_feedback_formations")
        issued=integer(execution["issued_frame"],0,2**32-1,"tactical_feedback_frame")
        mission=self.missions.active.get(task.task_id)
        maximum=round(mission.deadline_game_seconds*15) if mission else issued+900
        integer(execution["expires_frame"],issued+1,min(maximum,issued+(4500 if mission else 900),2**32-1),"tactical_feedback_frame")
        if mission and execution['expires_frame']!=maximum:raise ContractError('mission_feedback_deadline')
        expected="game_thread_bridge" if self.latest.source=="game_bridge" else "simulated"
        enum(execution["command_source"],{expected},"tactical_feedback_source")
        enum(execution["interference"],{"none","native_ai_override","unknown"},"tactical_feedback_interference")
        boolean(execution["goal_observed"],"tactical_feedback_observed");boolean(execution["restoration_verified"],"tactical_feedback_restoration")
        if task.execution_start is not None and raw["status"] in {"started","completed"}:
            if any(execution[field]!=task.execution_start[field] for field in ["formation_versions","issued_frame","expires_frame","command_source"]):raise ContractError("tactical_feedback_command_changed")
        if raw["status"]=="completed" and (task.status!="active" or task.execution_start is None):raise ContractError("tactical_feedback_lifecycle")
        if raw["status"]=="completed" and (not execution["goal_observed"] or not execution["restoration_verified"] or execution["interference"]!="none"):raise ContractError("tactical_completion_unverified")
        if raw["status"] in {"failed","blocked","cancelled"} and not execution["restoration_verified"] and len(set(self.goals.quarantined_formations)|set(task.request.formation_ids))>64:raise ContractError("quarantine_capacity")

    def confirm_restoration(self,evidence:RestorationEvidence):
        binding=self.engine.binding
        if not isinstance(evidence,RestorationEvidence) or evidence.session_id!=binding.session_id or type(evidence.player_id) is not int or evidence.player_id!=binding.player_id or self.latest is None or evidence.source!=self.latest.source:raise ContractError("restoration_evidence_binding")
        try:uuid.UUID(evidence.evidence_id)
        except (ValueError,AttributeError):raise ContractError("restoration_evidence_id") from None
        if not isinstance(evidence.formation_versions,tuple) or not evidence.formation_versions:raise ContractError("restoration_evidence_formations")
        restored={}
        for pair in evidence.formation_versions:
            if not isinstance(pair,tuple) or len(pair)!=2:raise ContractError("restoration_evidence_formations")
            ident,version=pair
            if not isinstance(ident,str) or ident in restored or type(version) is not int or self.goals.quarantined_formations.get(ident)!=version:raise ContractError("restoration_evidence_formations")
            restored[ident]=version
        for ident in restored:del self.goals.quarantined_formations[ident]
        self._event("formation_restored",self.latest.game_time_seconds,count=len(restored))
        self.engine.request_reassessment("capability_changed");self._write_memory()

    def _intent(self):
        plan=self.engine.current
        if plan is None or (self.latest is not None and self.latest.game_time_seconds>=plan.expires_at_game_seconds):return None
        return {"stance":plan.stance,"production_focus":plan.production_focus,"economy_policy":plan.economy_policy,"tech_policy":plan.tech_policy,"budget":dict(plan.budget),"objective_region":plan.objective_region,"expires_at_game_seconds":plan.expires_at_game_seconds,"origin":plan.origin,"tactical_tasks":[task.public() for task in plan.tactical_tasks]}

    def context(self,request,*,commit=True,wire_size=None,wire_limit=None):
        """Build a bounded summary+delta, never raw objects, addresses, or full map."""
        self._synchronize_goals();snapshot=self.latest
        if snapshot is None:raise ContractError("no_agent_snapshot")
        priority=[]
        if self.engine.current and self.engine.current.objective_region in snapshot.regions:priority.append(self.engine.current.objective_region)
        priority.extend(task.request.target_region for task in self.goals.tasks if task.request.target_region)
        priority.extend(snapshot.regions)
        regions=list(dict.fromkeys(priority))[:12]
        known=[]
        for fact in self.enemy_facts.values():
            known.append({**fact,"age_game_seconds":snapshot.game_time_seconds-fact["observed_at_game_seconds"],"certainty":"visible" if fact["currently_visible"] else "last_seen"})
        delta=[dict(event) for event in self.events if event["event_id"]>self.last_prompt_event][-8:]
        battlefield=snapshot.battlefield
        priority_contacts={task.target_contact_id for task in self.engine.current.tactical_tasks} if self.engine.current else set()
        facts=sorted(self.contact_facts.values(),key=lambda fact:(fact["contact_id"] not in priority_contacts,-fact["observed_at_game_seconds"],fact["contact_id"]))
        selected=[fact for fact in facts if fact["currently_visible"]][:12]+[fact for fact in facts if not fact["currently_visible"]][:4]
        battlefield_context={"viewer_player_id":snapshot.player_id,"visibility_verified":bool(battlefield and battlefield.visibility_verified),"regions":[region.public() for region in battlefield.regions if region.region_id in regions] if battlefield else [],"contacts":[{**fact,"age_game_seconds":snapshot.game_time_seconds-fact["observed_at_game_seconds"],"certainty":"visible" if fact["currently_visible"] else "last_seen"} for fact in selected],"formations":[formation.public() for formation in battlefield.formations][:8] if battlefield else []}
        manifest=self.capability_manifest()
        payload={
            "schema_version":1,"agent_protocol":"battle_agent_v1",
            **{key:request[key] for key in ["commander_id","session_id","player_id","snapshot_id","game_time_seconds","paused","allowed_production_focus"]},
            "allowed_regions":regions,
            "working_memory":{"current_strategy":self._intent(),"verified_enemy_facts":known,"economy":{"credits":snapshot.credits,"power_balance":snapshot.power_balance,"queued_count":snapshot.queued_count,"idle_producers":snapshot.idle_producers,"own_roles":dict(snapshot.own_roles)},"active_goals":[self._task_with_mission(task) for task in self.goals.tasks],"recent_execution_feedback":list(self.feedback),"failure_memory":list(self.last_failures.values()),"compressed_history":json.loads(json.dumps(self.summary)),"battlefield":battlefield_context,"unrestored_formation_count":len(self.goals.quarantined_formations)},
            "delta":{"since_snapshot_id":self.last_prompt_snapshot,"through_event_id":self.event_id,"verified_events":delta,"older_events_compressed":self.summary["events_compacted"]},
            "pending_decisions":[{"module":module,"question":"choose_bound_tactical_task" if manifest[module].get("verified_purposes") else question} for module,question in [("build","production_direction"),("raid","harassment_intent_only"),("attack","attack_intent_only"),("combined_arms","composition_intent_only")]],
            "capability_manifest":manifest,
            "conversation_tail":list(self.dialogue),
            "context_limits":{"maximum_bytes":self.context_budget,"regions_omitted":len(snapshot.regions)-len(regions),"contacts_omitted":len(self.contact_facts)-len(selected),"formations_omitted":len(battlefield.formations)-len(battlefield_context["formations"]) if battlefield else 0,"details_truncated":bool(len(self.contact_facts)>len(selected) or (battlefield and len(battlefield.formations)>len(battlefield_context["formations"])))},
        }
        if self.missions.evidence is not None:payload['working_memory']['persistent_missions']=self.missions.context()
        def length():return len(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode("utf-8"))
        while length()>self.context_budget or (wire_size is not None and wire_limit is not None and wire_size(payload)>wire_limit):
            payload["context_limits"]["details_truncated"]=True
            if payload["conversation_tail"]:payload["conversation_tail"].pop(0)
            elif payload["working_memory"]["recent_execution_feedback"]:payload["working_memory"]["recent_execution_feedback"].pop(0)
            elif len(payload["delta"]["verified_events"])>1:payload["delta"]["verified_events"].pop(0)
            elif payload["working_memory"]["active_goals"]:payload["working_memory"]["active_goals"].pop()
            elif payload["working_memory"]["battlefield"]["contacts"]:payload["working_memory"]["battlefield"]["contacts"].pop();payload["context_limits"]["contacts_omitted"]+=1
            elif payload["working_memory"]["battlefield"]["regions"]:payload["working_memory"]["battlefield"]["regions"].pop()
            elif payload["working_memory"]["battlefield"]["formations"]:payload["working_memory"]["battlefield"]["formations"].pop();payload["context_limits"]["formations_omitted"]+=1
            elif len(payload["allowed_regions"])>1:payload["allowed_regions"].pop();payload["context_limits"]["regions_omitted"]+=1
            elif payload["working_memory"]["verified_enemy_facts"]:payload["working_memory"]["verified_enemy_facts"].pop(0)
            elif len(payload["working_memory"]["failure_memory"])>1:payload["working_memory"]["failure_memory"].pop(0)
            elif payload["working_memory"]["current_strategy"] and payload["working_memory"]["current_strategy"]["tactical_tasks"]:payload["working_memory"]["current_strategy"]["tactical_tasks"].pop(0)
            else:raise ContractError("context_budget_exceeded")
        if commit:self._commit_context(payload)
        return payload

    def _commit_context(self,payload):
        length=len(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode("utf-8"))
        self.metrics["context_builds"]+=1;self.metrics["max_payload_bytes"]=max(self.metrics["max_payload_bytes"],length)
        self.last_prompt_event=max(self.last_prompt_event,payload["delta"]["through_event_id"]);self.last_prompt_snapshot=payload["snapshot_id"]

    async def decide(self,raw,adapter):
        snapshot=self.observe(raw)
        requests_before=self.engine.metrics["requests"]
        context_error=None
        try:
            frozen_payload=self.context(snapshot.model_context(self.engine.binding),commit=False,wire_size=getattr(adapter,"input_size",None),wire_limit=getattr(adapter,"max_input_bytes",None))
        except ContractError as error:
            context_error=str(error);frozen_payload=None;self.metrics["context_rejections"]+=1
            self._event("context_rejected",snapshot.game_time_seconds,reason_code=context_error)
        async def session_adapter(request):
            if context_error:raise ContractError(context_error)
            payload=frozen_payload
            self._commit_context(payload)
            from mission_audit import append_context
            append_context(self.context_audit_path,payload,self.metrics,snapshot.source)
            result=await adapter(payload)
            # Typed engine validation remains authoritative for the response.
            # Also constrain any model-selected objective to the limited IDs it saw.
            from engine import parse_model_json
            try:
                parsed=parse_model_json(result) if isinstance(result,(str,bytes)) else result
                if isinstance(parsed,dict) and parsed.get("objective_region") is not None and parsed.get("objective_region") not in payload["allowed_regions"]:raise ContractError("context_objective")
                if isinstance(parsed,dict) and isinstance(parsed.get("tactical_tasks"),list):
                    forms={f["formation_id"] for f in payload["working_memory"]["battlefield"]["formations"]}
                    contacts={c["contact_id"] for c in payload["working_memory"]["battlefield"]["contacts"]}
                    for task in parsed["tactical_tasks"]:
                        if not isinstance(task,dict):raise ContractError("context_tactical_task")
                        if not isinstance(task.get("formation_ids"),list) or any(not isinstance(i,str) or i not in forms for i in task["formation_ids"]):raise ContractError("context_formation")
                        if task.get("target_contact_id") is not None and (not isinstance(task["target_contact_id"],str) or task["target_contact_id"] not in contacts):raise ContractError("context_contact")
                        if task.get("target_region") not in payload["allowed_regions"]:raise ContractError("context_tactical_region")
                        if isinstance(task.get("module"),str) and isinstance(task.get("purpose"),str):
                            for observed in (snapshot,self.latest):
                                target_role=next((c.role for c in observed.battlefield.contacts if c.contact_id==task.get("target_contact_id")),None) if observed.battlefield else None
                                self.goals.validate_actor_roles(task["module"],task["purpose"],task["formation_ids"],task.get("required_roles"),observed.battlefield,observed.source,target_role)
                                self.missions.validate_intent(task['module'],task['purpose'],task.get('target_contact_id'),observed)
                return parsed
            except ContractError as error:
                # Adapter transport errors occur above this block. Never copy
                # model text, exception values or HTTP response bodies to audit.
                code=str(error) if str(error) in POST_RESPONSE_GUARDS else "post_response_contract"
                self.metrics["post_response_guard_rejections"]+=1
                self._event("policy_guard_rejected",snapshot.game_time_seconds,reason_code=code,snapshot_id=snapshot.snapshot_id)
                self.engine.audit.emit(self.engine.binding,event="policy_guard_rejected",reason_code=code,snapshot_id=snapshot.snapshot_id,game_time_seconds=snapshot.game_time_seconds)
                raise
        result=await self.engine.decide(snapshot,session_adapter)
        self._synchronize_goals()
        if self.engine.metrics["requests"]>requests_before:
            self._event("decision",self.latest.game_time_seconds,status=result.status,reason_code=result.reason_code)
            if result.status=="accepted":
                intent=self._intent()
                self.dialogue.append({"snapshot_id":snapshot.snapshot_id,"at_game_seconds":snapshot.game_time_seconds,"accepted_strategy":intent})
        self._write_memory()
        return result

    def public_memory(self):
        return {"schema_version":1,"agent_protocol":"battle_agent_v1","binding":{"session_id":self.engine.binding.session_id,"player_id":self.engine.binding.player_id,"commander_id":self.engine.binding.commander_id},"source":self.latest.source if self.latest else "simulated","current_strategy":self._intent(),"verified_enemy_facts":list(self.enemy_facts.values()),"contact_facts":list(self.contact_facts.values()),"quarantined_formations":dict(self.goals.quarantined_formations),"active_goals":[self._task_with_mission(task) for task in self.goals.tasks],"task_history":list(self.goals.history),"missions":self.missions.public(),"recent_execution_feedback":list(self.feedback),"failure_memory":list(self.last_failures.values()),"event_ring":list(self.events),"compressed_history":self.summary,"conversation_tail":list(self.dialogue),"metrics":dict(self.metrics),"execution":{"enabled":False,"dry_run":True},"capability_manifest":self.capability_manifest()}

    def jobs(self):
        """Proposals only. Host must independently authorize and deduplicate task_id."""
        self._synchronize_goals();binding=self.engine.binding
        return {"schema_version":1,"agent_protocol":"battle_agent_v1","binding":{"session_id":binding.session_id,"player_id":binding.player_id,"commander_id":binding.commander_id},"source":self.latest.source if self.latest else "simulated","snapshot_id":self.latest.snapshot_id if self.latest else None,"execution_authorized":False,"jobs":[{**self._task_with_mission(task),"budget":{"unit":"fraction_of_observed_credits","fraction":task.request.spend_fraction},"host_dispatch_candidate":bool(self.latest and not self.latest.paused and not self.engine.stopped and task.status=="planned" and task.reason_code=="awaiting_host_dispatch")} for task in self.goals.tasks]}

    def _write_memory(self):
        if self.memory_path is not None or self.jobs_path is not None:
            from service import atomic_json
            if self.memory_path is not None:atomic_json(self.memory_path,self.public_memory())
            if self.jobs_path is not None:atomic_json(self.jobs_path,self.jobs())

    def stop(self):
        self.engine.stop()
        for task in self.goals.tasks:
            if task.task_id in self.missions.active and not(self.missions.active[task.task_id].observations and self.missions.active[task.task_id].observations.restoration_verified):
                self.missions.request_retreat(task.task_id,'host_stop');task.reason_code='mission_restoration_pending'
                self.goals.quarantined_formations.update(dict(task.request.formation_versions))
            elif task.status not in {"completed","failed"}:
                task.status="cancelled";task.reason_code="service_stopped"
                self.missions.finish(task.task_id,'cancelled',self.latest.game_time_seconds if self.latest else None)
        self._write_memory()
