"""Trusted model-intent scheduling over the existing paid actor/SQLite owner.

The model chooses a local opportunity, never a grant, actor, native sequence or
coordinates. Unknown dispatch stays unknown; this scheduler cannot replay it.
"""
from __future__ import annotations
import asyncio
from collections import deque
import math
import time
import uuid

from .contracts import ContractError


def paid_actor_available(host,record):
    """Read-only prefilter before installing any native channel, no authority."""
    from live_state import Memory,own_candidates,mobility_status
    object_id=(record.get('receipt')or{}).get('facts',{}).get('object_id')
    memory=Memory(host.session['pid'],host.session)
    try:
        census=own_candidates(memory,host.binding.player_id,{})
        if census['frame_start']!=census['frame_end']:return False
        row=next((r for r in census['candidates']if r['object_id']==object_id and r['type_hash']=='0x19ab11af'),None)
        if row is None:return False
        thing=int(row['address'],0)
        if not mobility_status(memory,thing)['independently_movable'] or memory.u32(thing+0x238):return False
        body=memory.u32(thing+0x33c);hp=memory.f32(body+4);height=memory.f32(thing+0x5c)
        return bool(math.isfinite(hp) and hp>0 and math.isfinite(height) and abs(height)<=.5)
    except (OSError,ValueError,RuntimeError):
        # Read-only preselection can be refused; it cannot hide an SDK result.
        return False
    finally:memory.close()


def native_choices(host, owner):
    """Brief read-only own-home filter. Native admission remains authoritative."""
    from battle_host import Memory, ROOT
    from tactical_bridge import module
    preborrow=module(ROOT.parent/'tactical/runtime/preborrow.py','host_runtime_model_preborrow')
    memory=Memory(host.session['pid'],host.session)
    record={}
    try:
        window=preborrow.HomeWindow(memory,owner.binding.player_id,owner.transport.planning_actor())
        window.begin(record,require_stationary=True)
        until=time.monotonic()+.6
        while time.monotonic()<until:
            sample=owner.transport.observe_planning_actor(owner.binding)
            if (any(sample[k] is not True for k in ('identity','birth_verified','live','grounded'))
                    or sample['paused']):
                record['actor_unavailable']=dict(frame=sample['frame'],reason_code='local_actor_not_available_for_borrow',
                    **{k:sample[k]for k in ('identity','birth_verified','live','grounded','paused','state_id','command_source')})
                return []
            current=owner.transport.poll()
            if current.get('phase')=='released' and sample['frame']<=current['game_frame']:
                time.sleep(.05);continue
            ready=window.observe(sample)
            points=owner.transport.targets()
            if ready:
                choices=[]
                for key,point in points.items():
                    distance=math.dist(sample['xyz'][:2],point[:2])
                    if 30<=distance<=120 and abs(point[2]-sample['xyz'][2])<=2:
                        bearing=math.degrees(math.atan2(point[1]-sample['xyz'][1],point[0]-sample['xyz'][0]))%360
                        choices.append(dict(target_point_id=key,bearing_degrees=bearing,distance_units=distance))
                return sorted(choices,key=lambda t:(t['bearing_degrees'],t['target_point_id']))[:8]
            time.sleep(.05)
        return []
    finally:
        memory.close()
        host.event('runtime_model_planning_observed',planning=record,tactical_commands=0)


def commit_point_current(owner, task_id, lease_id, point_id):
    """Keep the exact model choice; never silently substitute another endpoint."""
    sample=owner.transport.observe_actor(owner.binding)
    home=owner.transport.reserved_home(task_id,lease_id)
    point=owner.transport.targets().get(point_id)
    return bool(point is not None and sample['settled'] and sample['stance']==2
        and sample['team']==sample['script_team']
        and 30<=math.dist(sample['xyz'][:2],point[:2])<=120
        and 20<=math.dist(home['xyz'][:2],point[:2])<=120
        and abs(point[2]-sample['xyz'][2])<=2 and abs(point[2]-home['xyz'][2])<=2)


class ModelRuntimeTasks:
    def __init__(self,host,*,clock_ms=None):
        self.host=host;self.opportunity=None;self.production_task_id=None
        self.generation=1;self.active=None;self.seen=set();self.history=deque(maxlen=16)
        self.clock_ms=clock_ms or (lambda:int(time.monotonic()*1000))
        self.channel_since=None;self.no_opportunity_since=None;self.retirement_due=False
        self.exhausted=set();self.preparation=None
        self.last_clock=None
        self.candidate_since={}

    def public(self):
        return dict(opportunity=self.opportunity,active=dict(self.active) if self.active else None,
            history=list(self.history),preparation=self.preparation,scope='single_infantry_local_move_hold_return')

    def blocks_production(self):return self.retirement_due

    def now_ms(self):
        current=self.clock_ms()
        if type(current)is not int or current<0 or self.last_clock is not None and current<self.last_clock:
            raise ContractError('runtime_model_clock_regressed')
        self.last_clock=current;return current

    def channel_age(self):return 0 if self.channel_since is None else self.now_ms()-self.channel_since

    def preparation_state(self,snapshot,state,reason,count=0):
        self.preparation=dict(state=state,reason_code=reason,paid_units_available=count)
        snapshot['runtime_preparation']=self.preparation

    def paid_candidates(self,runtime):
        rows=[]
        floor=None
        if getattr(self.host,'runtime_tactical_retirement',None) is not None:
            # A different paid actor is a successor only when its original
            # producer sequence advances. Older unused soldiers cannot satisfy
            # the native handoff's monotone payment/incarnation contract.
            previous=self.host.runtime_tactical.producer_command_id
            floor=runtime.journal.get_native_sequence(runtime.run_id,previous)
        for task_id,entry in self.host.sent.items():
            if entry.get('kind')!='runtime_production' or entry.get('command_id')in self.exhausted:continue
            row=runtime.journal.get_command(runtime.run_id,entry['request_id'])
            if row['status']=='completed' and row['payload'].get('unit')=='conscript':
                if floor is not None and runtime.journal.get_native_sequence(runtime.run_id,row['command_id'])<=floor:continue
                rows.append((task_id,row))
        return list(reversed(rows))

    async def suspend(self,snapshot,reason):
        self.retirement_due=True
        try:await asyncio.to_thread(self.host.suspend_runtime_tactical)
        except ContractError as error:
            if str(error)!='runtime_tactical_waiting_production_or_control_barrier':raise
            self.preparation_state(snapshot,'waiting_production_barrier','production_or_control_barrier');return
        self.exhausted.add(self.host.runtime_tactical.producer_command_id)
        self.retirement_due=False;self.channel_since=None;self.no_opportunity_since=None;self.generation+=1
        self.preparation_state(snapshot,'retired_waiting_paid_unit',reason)

    def feedback(self,status,reason,**facts):
        task=self.active
        task['status']=status;task['reason_code']=reason
        payload=dict(task_id=task['task_id'],plan_id=task['plan_id'],purpose='move_hold_return',
            status=status,reason_code=reason,**facts)
        self.host.event('runtime_model_task_feedback',**payload)
        self.host.agent.record_runtime_feedback(payload,self.host.last_snapshot['game_time_seconds'])

    def finish(self,status,reason,receipt):
        facts=(receipt.get('receipt') or {}).get('facts',{})
        self.feedback(status,reason,physical_home=facts.get('physical_home') is True,
            control_released=facts.get('control_released') is True,
            mission_effect_verified=status=='completed' and facts.get('mission_effect_verified') is True)
        self.history.append(dict(self.active,status=status,reason_code=reason,receipt_command_id=receipt['command_id'],
            updated_at_game_seconds=self.host.last_snapshot['game_time_seconds'],physical_home=facts.get('physical_home')is True,
            control_released=facts.get('control_released')is True,mission_effect_verified=status=='completed' and facts.get('mission_effect_verified')is True))
        self.active=None;self.generation+=1;self.opportunity=None

    def jobs(self):
        rows=([self.active]if self.active else [])+list(reversed(self.history))
        public=[]
        for row in rows:
            public.append(dict(module='local_maneuver',purpose='move_hold_return',
                **{k:row[k]for k in ('task_id','plan_id','status','reason_code','expires_at_game_seconds','updated_at_game_seconds',
                    'physical_home','control_released','mission_effect_verified')if k in row}))
        return public

    async def fresh_snapshot(self):
        owner=self.host.runtime_tactical
        sample=await asyncio.to_thread(owner.transport.admit,owner.binding)
        if (sample.binding_hash!=owner.binding.binding_hash or type(sample.game_frame)is not int
                or not 0<=sample.game_frame<=0xffffffff or type(sample.paused)is not bool):
            raise ContractError('runtime_model_fresh_clock_unverified')
        return sample

    def on_host_stop(self):
        """Project saved receipts after cleanup; no game IO or implicit retry."""
        if self.active is None:return
        owner=self.host.runtime_tactical
        rows=[r for r in owner.journal.commands_for_run(owner.run_id) if r['payload'].get('task_id')==self.active['task_id']]
        if rows and rows[-1]['status']=='released':self.finish('failed','host_stopped',rows[-1])
        elif not self.active.get('unknown_notified'):
            self.active['unknown_notified']=True
            self.feedback('uncertain','control_release_unknown')

    async def advance(self,receipt=None):
        if self.active is None:return
        if (self.host.last_snapshot['paused'] or self.host.phase!='running'
                or self.host.stop_requested()):return
        owner=self.host.runtime_tactical
        receipt=receipt or await asyncio.to_thread(owner.poll)
        if receipt is None:raise ContractError('runtime_model_receipt_missing')
        for _ in range(3):
            status=receipt['status'];task=self.active
            if status=='uncertain':
                if not task.get('unknown_notified'):
                    task['unknown_notified']=True;self.feedback('uncertain','control_release_unknown')
                raise ContractError('tactical_unknown_requires_reconciliation')
            if status=='released':
                effect=(receipt.get('receipt')or{}).get('facts',{}).get('mission_effect_verified') is True
                ok=task['stage']=='commit' and effect and not task.get('abort_reason')
                self.finish('completed' if ok else 'failed', 'local_maneuver_verified' if ok else task.get('abort_reason','local_maneuver_not_completed'),receipt)
                return
            fresh=await self.fresh_snapshot()
            if fresh.paused:return
            abort=None
            if task['stage']!='stopping' and self.channel_age()>=120000:
                task['abort_reason']='native_channel_budget';task['stage']='stopping'
                self.feedback('stopping','native_channel_budget')
                receipt=await asyncio.to_thread(owner.stop,task['task_id']);continue
            if status in ('rejected','failed'):
                if task['stage']=='reserve':
                    self.finish('failed','reserve_rejected',receipt);return
                if task['stage']=='stopping':raise ContractError('tactical_control_release_unverified')
                abort='commit_rejected'
            elif task['stage']=='reserve' and status=='completed':
                if max(self.host.last_snapshot['game_time_seconds'],fresh.game_frame/15)>=task['expires_at_game_seconds']:abort='plan_expired_before_commit'
                elif not await asyncio.to_thread(commit_point_current,owner,task['task_id'],receipt['payload']['lease_id'],task['target_point_id']):abort='model_endpoint_no_longer_approved'
                else:
                    task['stage']='commit'
                    self.feedback('active','ready_committing_exact_model_endpoint')
                    receipt=await asyncio.to_thread(self.host.commit_runtime_task,task['task_id'],target_point_id=task['target_point_id'],hold_frames=task['hold_frames'])
                    continue
            if abort:
                task['abort_reason']=abort;task['stage']='stopping'
                self.feedback('stopping',abort)
                receipt=await asyncio.to_thread(owner.stop,task['task_id']);continue
            return

    async def prepare(self,snapshot):
        self.opportunity=None
        snapshot['runtime_opportunity']=None
        snapshot['runtime_preparation']=None
        runtime=getattr(self.host,'runtime_production',None)
        if runtime is None:return
        if self.active is not None:
            await self.advance()
            self.preparation_state(snapshot,'active','local_task_in_progress')
            return
        if snapshot['paused'] or not self.host.executor_ready or self.host.phase!='running' or self.host.stop_requested():return
        try:runtime.evidence.catalog.require('tactics.move_hold_return',runtime.binding)
        except ContractError as error:
            if str(error)=='capability_unsupported':return
            raise
        owner=getattr(self.host,'runtime_tactical',None)
        retirement=getattr(self.host,'runtime_tactical_retirement',None)
        if owner is None or retirement is not None:
            candidates=self.paid_candidates(runtime)
            self.preparation_state(snapshot,'retired_waiting_paid_unit' if retirement is not None else 'waiting_paid_unit','completed_paid_unit_required',len(candidates))
            chosen=None
            for task_id,row in candidates:
                if await asyncio.to_thread(paid_actor_available,self.host,row):chosen=task_id;break
                command=row['command_id'];self.candidate_since.setdefault(command,self.now_ms())
                if self.now_ms()-self.candidate_since[command]>=30000:
                    self.exhausted.add(command);self.candidate_since.pop(command,None)
                    self.host.event('runtime_model_preparation_exhausted',producer_command_id=command,
                        reason_code='readiness_wait_elapsed',tactical_commands=0)
            if chosen is None:
                count=sum(row['command_id']not in self.exhausted for _,row in candidates)
                if count:self.preparation_state(snapshot,'waiting_native_readiness','native_readiness_required',count)
                else:self.preparation_state(snapshot,'retired_waiting_paid_unit' if retirement is not None else 'waiting_paid_unit','readiness_wait_elapsed',0)
                return
            self.production_task_id=chosen
            owner=await asyncio.to_thread(self.host.resume_runtime_tactical if retirement is not None else self.host.attach_runtime_actor,chosen)
            self.channel_since=getattr(owner.transport,'started_ms',self.now_ms())
            self.no_opportunity_since=None
        if getattr(self.host,'runtime_tactical_rotation_attempted',False):return
        if self.channel_since is None:self.channel_since=getattr(owner.transport,'started_ms',self.now_ms())
        if self.retirement_due or self.channel_age()>=90000:
            await self.suspend(snapshot,'native_channel_budget');return
        self.preparation_state(snapshot,'waiting_native_readiness','native_readiness_required',1)
        targets=await asyncio.to_thread(native_choices,self.host,owner)
        if not targets:
            if self.no_opportunity_since is None:self.no_opportunity_since=self.now_ms()
            if self.now_ms()-self.no_opportunity_since>=30000:await self.suspend(snapshot,'readiness_wait_elapsed')
            return
        self.no_opportunity_since=None
        self.opportunity=dict(opportunity_id=str(uuid.uuid5(uuid.UUID(owner.run_id),'model-local:'+str(self.generation))),
            targets=targets,max_hold_frames=450)
        snapshot['runtime_opportunity']=self.opportunity
        self.preparation_state(snapshot,'available','safe_opportunity_available',1)

    async def dispatch(self):
        if self.active is not None:return
        if self.channel_age()>=90000:self.retirement_due=True;return
        plan=self.host.engine.current
        if (self.opportunity is None or plan is None or plan.origin!='model' or plan.runtime_task is None
                or plan.plan_id in self.seen or self.host.last_snapshot['paused'] or self.host.stop_requested()
                or self.host.phase!='running' or self.host.last_snapshot['game_time_seconds']>=plan.expires_at_game_seconds):return
        intent=plan.runtime_task
        if (intent.opportunity_id!=self.opportunity['opportunity_id']
                or intent.target_point_id not in {t['target_point_id']for t in self.opportunity['targets']}):return
        fresh=await self.fresh_snapshot()
        if fresh.paused or fresh.game_frame/15>=plan.expires_at_game_seconds:return
        if len(self.seen)>=4096:raise ContractError('runtime_model_task_capacity')
        self.seen.add(plan.plan_id)
        self.active=dict(task_id=str(uuid.uuid5(uuid.UUID(self.host.runtime_tactical.run_id),'model-plan:'+plan.plan_id)),
            plan_id=plan.plan_id,opportunity_id=intent.opportunity_id,target_point_id=intent.target_point_id,
            hold_frames=intent.hold_frames,stage='reserve',expires_at_game_seconds=plan.expires_at_game_seconds)
        self.opportunity=None
        self.feedback('dispatch_pending','accepted_model_local_intent')
        receipt=await asyncio.to_thread(self.host.reserve_runtime_task,self.active['task_id'],self.production_task_id,lease_frames=900)
        await self.advance(receipt)
