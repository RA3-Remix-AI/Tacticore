"""Bounded region objectives; native AI recruits and operates combat groups."""
import math
import uuid

from .contracts import ContractError
from .macro_policy_runtime import COMMANDER,PRESETS
from .macro_scouting import MacroScoutingController,scout_sample
from .macro_region_scope import RegionalScope
from .macro_infrastructure import TEMPLATES
from .macro_group_role_contract import ROLE_GOALS,ROLE_FAMILIES
from .macro_forces import NAMED_UNITS

POINT_GOAL='native_combat_group_to_fixed_public_waypoint'
DEFENSE_GOAL='original_native_defense_of_own_infrastructure'

class RegionalFeedback:
    def __init__(self,observation,view,target,*,family='simple_attack',goal=POINT_GOAL):
        self.action,self.region,self.flag,self.x,self.y=target
        role=self.action in ROLE_GOALS
        if ((family,goal) not in (('simple_attack',POINT_GOAL),('static_defense',DEFENSE_GOAL)) and not
                (role and family==ROLE_FAMILIES[self.action] and goal==ROLE_GOALS[self.action])
                or family=='static_defense' and (self.action,self.region)!=('deploydefense','region_8_3')):
            raise ContractError('macro_region_goal_family_binding')
        if role and (self.region!='region_8_3' or family!=ROLE_FAMILIES[self.action] or goal!=ROLE_GOALS[self.action]):
            raise ContractError('macro_region_goal_family_binding')
        self.family=family;self.goal=goal;self.near_infrastructure=set()
        self.home_groups=set();self.withdrawing_groups=set();self.native_start_frame=None;self.capture_deadline=None
        self.first={};self.moved=set();self.progressed=set();self.ever_active=False
        self.policy_released=False;self.release_reason=None;self.observe(observation,view)

    def observe(self,observation,view):
        frame,view_frame,score,active,groups,_=scout_sample(observation,view,self.flag)
        state=observation['state_scores'][self.flag]
        if any(t.get('native_tactic_family')!=self.family for t in observation['runtimes']
                if t['group']==state['group'] and t['native_execution_active']):
            raise ContractError('macro_region_native_tactic_type')
        if hasattr(self,'frame') and (frame<self.frame or view_frame<self.view_frame):raise ContractError('macro_region_frame_regression')
        self.frame=frame;self.view_frame=view_frame;self.active=active;self.group_count=len({key[0] for key in groups})
        end_frame=max(frame,view_frame,observation.get('construction_feedback',{}).get('frame',frame))
        in_window=(self.native_start_frame is None or frame>=self.native_start_frame) and (self.capture_deadline is None or end_frame<self.capture_deadline)
        if score and active and in_window:self.ever_active=True
        if score and not self.policy_released and in_window:
            for key,point in groups.items():
                first=self.first.setdefault(key,point)
                if math.dist(first,point)>10:self.moved.add(key[0])
                if self.family=='simple_attack' and math.dist(first[:2],(self.x,self.y))-math.dist(point[:2],(self.x,self.y))>50:self.progressed.add(key[0])
                if self.action in ROLE_GOALS:
                    if math.dist(point[:2],(self.x,self.y))<=500:self.home_groups.add(key[0])
                    if (self.action=='withdraw' and math.dist(first[:2],(self.x,self.y))>750
                            and math.dist(first[:2],(self.x,self.y))-math.dist(point[:2],(self.x,self.y))>50):self.withdrawing_groups.add(key[0])
            if self.family in ('static_defense','reactive_defense'):
                census=observation.get('construction_feedback',{})
                if (census.get('enemy_details_read') is not False or type(census.get('frame')) is not int
                        or abs(census['frame']-frame)>15):raise ContractError('macro_base_defense_own_census_required')
                structures=[r for r in census['own_objects'] if r['type_hash'] in TEMPLATES.values() and r['hp']>0]
                if any(len(r['xyz'])!=3 or any(not math.isfinite(v) for v in r['xyz']) for r in structures):
                    raise ContractError('macro_base_defense_infrastructure_position')
                for key,point in groups.items():
                    if structures and min(math.dist(point[:2],r['xyz'][:2]) for r in structures)<=500:
                        self.near_infrastructure.add(key[0])
        return self.public()

    def bind_native_window(self,begin,deadline):
        self.native_start_frame=begin if type(begin) is int else self.frame+1
        self.capture_deadline=deadline if type(deadline) is int else None
        self.first={};self.moved=set();self.progressed=set();self.near_infrastructure=set()
        self.home_groups=set();self.withdrawing_groups=set();self.ever_active=False

    def public(self):
        return dict(source='native_regional_group_observation',action=self.action,target_region=self.region,
            observed_frame=self.frame,view_frame=self.view_frame,active_native_tactics=self.active,
            allocated_native_groups=self.group_count,native_execution_observed=self.ever_active,
            moved_native_groups=len(self.moved),groups_progressing_toward_region=len(self.progressed),
            policy_released=self.policy_released,release_reason=self.release_reason,
            unit_operation_policy='native_ai',goal=self.goal,
            **(dict(native_tactic_family=self.family,defender_groups_near_infrastructure=len(self.near_infrastructure),
                target_policy='original_native_friendly_land_structure') if self.family=='static_defense' else {}),
            **(dict(native_tactic_family=self.family,groups_near_home_region=len(self.home_groups),
                withdrawing_native_groups=len(self.withdrawing_groups),
                defender_groups_near_infrastructure=len(self.near_infrastructure),
                target_policy='original_native_most_recently_attacked_own_base' if self.action=='reinforce'
                    else 'fixed_public_own_home_start_waypoint') if self.action in ROLE_GOALS else {}),
            arrival_verified=False,mission_success_verified=False,arbitrary_xy_control=False)

def compact_regional_feedback(value,game_seconds):
    if (type(value) is not dict or value.get('source')!='native_regional_group_observation'
            or (value.get('action'),value.get('target_region')) not in (('deployattack','region_1_3'),('deploydefense','region_8_3'),
                *((a,'region_8_3') for a in ROLE_GOALS))
            or any(type(value.get(k)) is not int or not 0<=value[k]<=8192 for k in
                ('active_native_tactics','allocated_native_groups','moved_native_groups','groups_progressing_toward_region'))
            or any(type(value.get(k)) is not bool for k in ('native_execution_observed','policy_released'))
            or value.get('release_reason') not in (None,'expired','native_execution_inactive','stopped')
            or any(type(value.get(k)) is not int or not 0<value[k]<=0xffffffff
                or not -15<=game_seconds*15-value[k]<=30 for k in ('observed_frame','view_frame'))):
        raise ContractError('macro_region_feedback_invalid_or_stale')
    keys=('source','action','target_region','observed_frame','view_frame','active_native_tactics','allocated_native_groups',
        'native_execution_observed','moved_native_groups','groups_progressing_toward_region','policy_released','release_reason')
    goal=value.get('goal',POINT_GOAL);extra={}
    if goal==DEFENSE_GOAL:
        if (value['action']!='deploydefense' or value.get('native_tactic_family')!='static_defense'
                or type(value.get('defender_groups_near_infrastructure')) is not int
                or not 0<=value['defender_groups_near_infrastructure']<=8192
                or value.get('target_policy')!='original_native_friendly_land_structure'):
            raise ContractError('macro_base_defense_feedback_invalid')
        extra=dict(native_tactic_family='static_defense',defender_groups_near_infrastructure=value['defender_groups_near_infrastructure'],
            target_policy='original_native_friendly_land_structure')
    elif value.get('action') in ROLE_GOALS:
        action=value['action'];policy='original_native_most_recently_attacked_own_base' if action=='reinforce' else 'fixed_public_own_home_start_waypoint'
        counts=('groups_near_home_region','withdrawing_native_groups','defender_groups_near_infrastructure')
        if (goal!=ROLE_GOALS[action] or value.get('native_tactic_family')!=ROLE_FAMILIES[action]
                or value.get('target_policy')!=policy or any(type(value.get(k)) is not int or not 0<=value[k]<=8192 for k in counts)):
            raise ContractError('macro_group_role_feedback_invalid')
        extra=dict(native_tactic_family=ROLE_FAMILIES[action],target_policy=policy,**{k:value[k] for k in counts})
    elif goal!=POINT_GOAL:raise ContractError('macro_region_goal_invalid')
    return dict(**{key:value[key] for key in keys},unit_operation_policy='native_ai',
        goal=goal,**extra,arrival_verified=False,mission_success_verified=False,arbitrary_xy_control=False)

class MacroRegionalController(MacroScoutingController):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not isinstance(self.scope,RegionalScope):raise ContractError('macro_region_scope_required')
        self.regional_tracker=None;self.regional_plan=None;self.regional_sent={};self.regional_fingerprints={};self.regional_latest={}

    @property
    def sent(self):return {**super().sent,**self.regional_sent}
    @property
    def regional_busy(self):return self.regional_tracker is not None and not self.regional_tracker.policy_released
    @property
    def busy(self):return super().busy or self.regional_busy

    def regional_observer(self,observation,target):
        family=self.scope.regional_family_for(target[0]) if hasattr(self.scope,'regional_family_for') else 'simple_attack'
        goal=self.scope.regional_goal_for(target[0]) if hasattr(self.scope,'regional_goal_for') else POINT_GOAL
        return RegionalFeedback(observation,self.scout_view,target,family=family,goal=goal)

    def refresh(self,sample):
        super().refresh(sample);self.regional_latest={}
        if 'observation' not in sample or self.scout_view is None:return
        observation=sample['observation']
        if self.regional_tracker:
            try:self.regional_tracker.observe(observation,self.scout_view)
            except ContractError:pass
        for target in self.scope.regional_targets:
            try:
                self.regional_observer(observation,target)
                self.regional_latest[target[0]]=observation
            except ContractError:pass

    def available_actions(self,game_seconds):
        result=super().available_actions(game_seconds)
        if not self.busy and not self.stopped:
            available=list(self.regional_latest)
            if 'withdraw' in available:
                obs=self.regional_latest['withdraw'];census=obs.get('construction_feedback',{})
                known={v[0] for v in NAMED_UNITS.values()}
                target=next(t for t in self.scope.regional_targets if t[0]=='withdraw')
                if (census.get('enemy_details_read') is not False or abs(census.get('frame',-999)-obs['frame'])>15
                        or not any(r['type_hash'] in known and r['hp']>0 and math.dist(r['xyz'][:2],target[3:5])>750
                            for r in census.get('own_objects',[]))):available.remove('withdraw')
            result+=tuple(available)
        return result

    def dispatch(self,plan,game_seconds,*,effective_hash,paused=False):
        regional=[action for action in plan.macro_actions if action in self.scope.regional_action_regions]
        if not regional:
            if plan.plan_id in self.regional_sent:raise ContractError('macro_plan_id_conflict')
            return super().dispatch(plan,game_seconds,effective_hash=effective_hash,paused=paused)
        actions=tuple(plan.macro_actions)
        if (self.stopped or effective_hash!=self.effective_hash or paused or plan.origin!='model'
                or plan.session_id!=self.session_id or plan.commander_id!=COMMANDER or plan.player_id!=3
                or not plan.based_on_game_time_seconds<=game_seconds<plan.expires_at_game_seconds
                or plan.tactical_tasks or plan.runtime_task is not None or getattr(plan,'macro_production',None) is not None
                or len(regional)!=1 or len(actions)!=len(set(actions)) or len(actions)>2
                or any(a!=regional[0] and a not in self.scope.budget.available_actions for a in actions)
                or plan.objective_region!=self.scope.regional_action_regions[regional[0]]):
            raise ContractError('macro_region_plan_binding')
        fingerprint=(actions,plan.objective_region,plan.based_on_game_time_seconds,plan.expires_at_game_seconds,effective_hash)
        if plan.plan_id in self.regional_sent:
            if self.regional_fingerprints[plan.plan_id]!=fingerprint:raise ContractError('macro_plan_id_conflict')
            return self.regional_sent[plan.plan_id]
        if plan.plan_id in super().sent:raise ContractError('macro_plan_id_conflict')
        action=regional[0]
        if action not in self.available_actions(game_seconds):raise ContractError('macro_region_not_currently_available')
        target=next(target for target in self.scope.regional_targets if target[0]==action)
        tracker=self.regional_observer(self.regional_latest[action],target)
        duration=max(1,min(900,math.floor((plan.expires_at_game_seconds-game_seconds)*15)))
        command_id=str(uuid.uuid5(uuid.UUID(self.session_id),plan.plan_id+':region:'+effective_hash))
        self.event('model_macro_region_prepared',plan_id=plan.plan_id,command_id=command_id,actions=list(actions),
            target_region=plan.objective_region,duration_frames=duration)
        try:receipt=self.transport.apply(list(actions),duration,command_id)
        except Exception:
            self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
        if type(receipt.get('native_start_frame')) is int and type(receipt.get('native_deadline_frame')) is int:
            tracker.bind_native_window(receipt['native_start_frame'],receipt['native_deadline_frame'])
        elif action in ROLE_GOALS:
            self.stopped=True;raise ContractError('macro_region_native_window_missing')
        self.regional_tracker=tracker;self.regional_plan=(plan.plan_id,game_seconds+duration/15)
        self.budget.current_actions=tuple(a for a in actions if a in PRESETS)
        public=dict(plan_id=plan.plan_id,command_id=command_id,actions=list(actions),target_region=plan.objective_region,
            seq=receipt['seq'],native_gate_acknowledged=True,native_effect_verified=False,
            **(dict(goal=tracker.goal) if tracker.goal==DEFENSE_GOAL or action in ROLE_GOALS else {}))
        self.regional_sent[plan.plan_id]=public;self.regional_fingerprints[plan.plan_id]=fingerprint
        self.event('model_macro_region_acknowledged',**public);return public

    def tick(self,game_seconds):
        if self.regional_busy:
            tracker=self.regional_tracker
            if not self.stopped and (game_seconds>=self.regional_plan[1] or tracker.ever_active and tracker.active==0):
                reason='expired' if game_seconds>=self.regional_plan[1] else 'native_execution_inactive'
                command_id=str(uuid.uuid5(uuid.UUID(self.session_id),self.regional_plan[0]+':region-release:'+self.effective_hash))
                try:self.transport.apply([],1,command_id)
                except Exception:
                    self.stopped=True;raise ContractError('macro_dispatch_outcome_unknown') from None
                tracker.policy_released=True;tracker.release_reason=reason;self.budget.current_actions=()
                self.event('macro_region_preference_released',reason_code=reason,feedback=tracker.public())
            return
        super().tick(game_seconds)

    def regional_feedback(self):return self.regional_tracker.public() if self.regional_tracker else None

    def stop(self):
        super().stop()
        if self.regional_busy:
            self.regional_tracker.policy_released=True;self.regional_tracker.release_reason='stopped'
            self.event('macro_region_preference_released',reason_code='stopped',feedback=self.regional_tracker.public())
