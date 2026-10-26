"""Host-owned reviewed paid-pair supply/controller lifecycle. No execution on import.

Only an accepted MODEL balanced-build task can authorize paid preparation.
Live Native facts come exclusively from Runtime.verified_facts/release; no
Header masks or enqueue ACK can grant readiness, success or actor release.
"""
from __future__ import annotations
import asyncio
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import uuid
from held_formations import HeldFormationRegistry, SCOPE

ROOT=Path(__file__).resolve().parents[1]
CONTROLLER_DIRECTORIES=('mission-formation-v13','mission-formation-v14','mission-formation-v15','mission-formation-v16','mission-formation-v17','mission-formation-v18')

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8');temp.replace(path)

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def runtime_path(directory='mission-formation-v13',wrapper_filename='lease.py'):
    if type(directory) is not str or directory not in CONTROLLER_DIRECTORIES:raise ValueError('reserve_untrusted_runtime_directory')
    allowed=('lease.py','lease_v2.py') if directory=='mission-formation-v16' else ('lease.py',)
    if type(wrapper_filename) is not str or wrapper_filename not in allowed:raise ValueError('reserve_untrusted_wrapper_filename')
    return ROOT/'tactical'/directory/wrapper_filename


def runtime_type(directory='mission-formation-v13',wrapper_filename='lease.py'):
    path=runtime_path(directory,wrapper_filename);name='host_paid_pair_runtime_'+directory.replace('-','_')+'_'+path.stem
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module.ControllerRuntime

class ReserveController:
    def __init__(self,host,grant,*,runtime_factory=None):
        if grant.get('executor_directory') not in CONTROLLER_DIRECTORIES or (grant.get('module'),grant.get('purpose'))!=('combined_arms','coordinate_force'):
            raise ValueError('reserve_requires_verified_paid_pair_grant')
        self.host=host;self.grant=copy.deepcopy(grant);self.directory=grant['executor_directory'];self.runtime_factory=runtime_factory
        stop_schema=grant.get("stop_schema",{})
        if type(stop_schema) is not dict:raise ValueError("reserve_untrusted_clock_schema")
        self.wrapper_filename=stop_schema.get("wrapper_filename","lease.py")
        self.wrapper_path=runtime_path(self.directory,self.wrapper_filename)
        self.reserve_duration_frames=stop_schema.get("reserve_duration_frames",300)
        self.held_registry=HeldFormationRegistry(host.binding.session_id,host.binding.commander_id,host.binding.player_id,executor_directory=self.directory,reserve_duration_frames=self.reserve_duration_frames)
        self.output=host.output/'reserve-controller';self.path=self.output/'coordinator.json'
        self.runtime=None;self.config=None;self.record=None;self.attempted=False;self.last_facts=None;self.ready_epoch=None;self.closed=False;self.stopping=False
        self.host.collector.held_formations=self.held_registry

    def persist(self):
        atomic(self.path,dict(protocol='host_paid_pair_coordinator_v1',executor_directory=self.directory,wrapper_filename=self.wrapper_filename,authorization=self.record,held=self.held_registry.audit(),ready_epoch=self.ready_epoch,attempted=self.attempted,runtime_closed=self.closed,physical_capability_verified=False))

    def event(self,kind,**fields):self.host.event(kind,**fields)
    def owns_channel(self):return self.held_registry.channel_owner is not None
    def owns_formation(self,fid):return fid in self.held_registry.private_formations()
    def hard_deadline(self,fid):
        data=self.held_registry.private_formations().get(fid)
        if data is None or data['hard_deadline_frame'] is None:raise ValueError('reserve_original_clock_unavailable')
        return data['hard_deadline_frame']
    def private_formation(self,fid):
        data=getattr(self.host.collector,'private_held_formations',{}).get(fid)
        if data is None:raise ValueError('reserve_current_own_overlay_unavailable')
        return copy.deepcopy(data)
    def formation(self,fid):
        rows=self.host.last_snapshot.get('battlefield',{}).get('formations',[])
        matches=[r for r in rows if r.get('formation_id')==fid]
        if len(matches)!=1 or not self.owns_formation(fid):raise ValueError('reserve_public_formation_unavailable')
        return copy.deepcopy(matches[0])
    def blocks_build(self):
        return bool(self.record and any(order['state']=='pending' for order in self.record['orders']) and self.owns_channel())
    def reserved_budget(self):
        return sum(order['command']['budget'] for order in self.record['orders'] if order['state']=='pending') if self.record else 0

    def _factory(self):
        path=self.host.output/'own-state.json'
        if not path.exists():return None
        own=json.loads(path.read_text(encoding='utf-8-sig'));producer=self.host.executor
        address=producer.factory_address;candidate=producer.candidate
        rows=[row for row in own.get('factories',[]) if int(row['address'],0)==address and row.get('production_interface_available') is True]
        if len(rows)!=1:return None
        return dict(factory=address,factory_id=candidate['object_id'],iface=int(rows[0]['interface'],0),xyz=rows[0].get('xyz'))

    def _opportunity(self,factory,frame):
        point=factory.get('xyz')
        if not isinstance(point,(list,tuple)) or len(point)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in point):return None
        contacts=self.host.last_snapshot.get('battlefield',{}).get('contacts',[])
        positions=getattr(self.host.collector,'private_targets',{})
        candidates=[]
        for contact in contacts:
            if contact.get('relation')!='enemy' or contact.get('currently_visible') is not True:continue
            target=positions.get(contact.get('contact_id'));xyz=target.get('xyz') if target else None
            at=target.get('observed_frame') if target else None
            if type(at) is not int or not 0<=frame-at<=45 or not isinstance(xyz,(list,tuple)) or len(xyz)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in xyz):return None
            distance=math.dist(point[:2],xyz[:2])
            if distance<=500:return None
            if contact.get('role') in ('infantry','armor','structure','economy') and 600<=distance<=2600:
                candidates.append(dict(contact_id=contact['contact_id'],distance_from_owned_factory=distance,observed_frame=at))
        return dict(candidates=candidates,selection_only=True,safety_verified=False,target_committed=False) if candidates else None

    async def maybe_prepare(self):
        h=self.host
        if self.attempted or not h.executor_ready or h.last_snapshot['paused'] or h.phase!='running' or not h.args.execute:return False
        if any(not row.get('terminal') for row in getattr(h.tactical,'sent',{}).values()):return False
        plan=h.engine.current
        if plan is None or plan.origin!='model' or plan.production_focus!='balanced' or h.last_snapshot.get('source')!='game_bridge':return False
        now=h.last_snapshot['game_time_seconds'];frame=round(now*15)
        if now>=plan.expires_at_game_seconds or plan.expires_at_game_seconds*15-frame<180:return False
        if 'balanced' not in h.evidence['supported_foci']:return False
        jobs=[job for job in h.agent.jobs()['jobs'] if job.get('module')=='build' and job.get('focus')=='balanced' and job.get('host_dispatch_candidate') is True and job.get('plan_id')==plan.plan_id and job.get('task_id') not in h.sent and type(job.get('generation')) is int and job['generation']>0]
        if len(jobs)!=1:return False
        job=jobs[0];budget=min(1000,h.remaining_budget,int(h.last_snapshot['resources']['credits']*job['budget']['fraction']))
        if budget<305 or h.args.reserve<1000:return False
        factory=self._factory()
        if factory is None:return False
        opportunity=self._opportunity(factory,frame)
        if opportunity is None:return False
        tactical=getattr(h.tactical,'executor',None)
        if tactical is None:return False
        controller=str(uuid.uuid4());lease=str(uuid.uuid5(uuid.UUID(controller),'lease'));formation=str(uuid.uuid5(uuid.UUID(controller),'paid_pair'))
        if await asyncio.to_thread(tactical.claim_controller_channel,controller) is not True:return False
        sequence=h.sequence;h.sequence+=2
        slots=[];orders=[]
        for role,(unit,cost) in enumerate((('conscript',85),('flak',220))):
            command=str(uuid.uuid5(uuid.UUID(controller),unit+'-production-command'));task=str(uuid.uuid5(uuid.UUID(job['task_id']),controller+'-'+unit))
            seq=sequence+role+1
            slots.append(dict(role=role,command_id=command,task_id=task,seq=seq,unit=unit,cost=cost,**{key:factory[key] for key in ('factory','factory_id','iface')}))
            wire=dict(session_id=h.binding.session_id,player_id=3,commander_id=h.binding.commander_id,command_id=command,task_id=task,seq=seq,unit=unit,budget=cost,reserve=max(1000,h.args.reserve),expires_frame=int(job['expires_at_game_seconds']*15))
            orders.append(dict(command=wire,state='pending',receipt=None))
        self.config=dict(schema_version=1,controller_id=controller,lease_id=lease,formation_uuid=formation,formation_version=1,seq=1,startup_deadline_frame=frame+900,startup_wall_ms=60000,slots=slots)
        self.record=dict(controller_id=controller,lease_id=lease,model_plan_id=plan.plan_id,model_plan_generation=job['generation'],parent_build_task_id=job['task_id'],plan_snapshot_id=plan.snapshot_id,model_plan_expires_game_seconds=plan.expires_at_game_seconds,build_budget=budget,allocated_paid_budget=305,observed_credits=h.last_snapshot['resources']['credits'],authorization_kind='accepted_model_balanced_build_and_verified_combined_arms_capability',opportunity=opportunity,orders=orders,parent_started=False,parent_terminal=False,mission_mapping=None,terminal_recorded=False,release_verified=False)
        self.held_registry.prearm_controller(dict(session_id=h.binding.session_id,commander_id=h.binding.commander_id,player_id=3,controller_id=controller,lease_id=lease,allocation_scope=SCOPE,max_paid=305,reserve_floor=1000,reserve_offset_frames=self.reserve_duration_frames,hard_offset_frames=4500))
        self.attempted=True;h.sent[job['task_id']]=dict(kind='paid_pair_supply',controller_id=controller,plan_id=plan.plan_id,generation=job['generation'],terminal=False,child_commands=[o['command']['command_id'] for o in orders])
        atomic(h.output/'dispatch-ledger.json',h.sent);self.persist()
        self.event('paid_pair_model_preparation_authorized',controller_id=controller,plan_id=plan.plan_id,generation=job['generation'],parent_task_id=job['task_id'],maximum_paid=305,calibration=False)
        factory_type=self.runtime_factory or runtime_type(self.directory,self.wrapper_filename)
        self.runtime=factory_type(h.args.session,copy.deepcopy(self.config),self.output/(controller+'.json'),h.natural_path)
        arm_task=asyncio.create_task(asyncio.to_thread(self.runtime.arm))
        try:await asyncio.shield(arm_task)
        except BaseException:
            # Cancelling to_thread does not stop the worker. Do not certify a
            # transient pre-intent state while arm could still launch Native.
            if not arm_task.done():
                try:await asyncio.shield(arm_task)
                except BaseException:pass
            self.record['arm_failed']=True;self.persist()
            if arm_task.done():
                try:await self._rollback_verified_no_launch()
                except (ValueError,OSError,AttributeError,KeyError):
                    self.record['no_launch_unproved']=True;self.persist()
            raise
        await self._submit_due(frame)
        return True

    async def _rollback_verified_no_launch(self):
        proof=await asyncio.to_thread(self.runtime.verified_no_launch)
        expected=dict(session_id=self.host.binding.session_id,commander_id=self.host.binding.commander_id,pid=self.host.session['pid'],controller_id=self.config['controller_id'],lease_id=self.config['lease_id'])
        if any(proof.get(k)!=v for k,v in expected.items()) or any(proof.get(k) is not True for k in ('verified','never_attached','mapping_closed')) or any(proof.get(k) is not False for k in ('native_launch_intent_persisted','native_host_created','heartbeat_started','game_memory_writes')) or type(proof.get('sdk_calls')) is not int or proof['sdk_calls']!=0 or proof.get('scope')!='only_this_unlaunched_controller_code_path':raise ValueError('reserve_no_launch_certificate_binding')
        path=Path(proof['source_report']).resolve()
        if not path.is_relative_to(self.output.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=proof['source_sha256']:raise ValueError('reserve_no_launch_certificate_file')
        body=json.loads(path.read_text(encoding='utf-8'))
        if any(body.get(k)!=v for k,v in proof.items() if k not in ('source_report','source_sha256')) or proof.get('controller_config_sha256')!=digest(self.runtime.config) or proof.get('wrapper_sha256')!=hashlib.sha256(self.wrapper_path.read_bytes()).hexdigest() or proof.get('session_source',{}).get('sha256')!=hashlib.sha256(Path(self.host.args.session).read_bytes()).hexdigest():raise ValueError('reserve_no_launch_source_changed')
        state=self.held_registry.controller(self.config['controller_id'])
        if state['lease_clock_bound'] or state['slots'] or self.held_registry.claimed_actor_ids():raise ValueError('reserve_no_launch_after_claim')
        frame=round(self.host.last_snapshot['game_time_seconds']*15)
        self.held_registry.record_terminal(self.config['controller_id'],dict(self._binding(),status='failed',reason_code='verified_no_launch',observed_frame=frame,proof_sha256=proof['source_sha256']))
        self.held_registry.record_verified_release(self.config['controller_id'],dict(self._binding(),object_ids=[],observed_frame=frame,proof_sha256=proof['source_sha256'],independently_verified=True,channel_release_verified=True))
        await asyncio.to_thread(self.host.tactical.executor.release_controller_channel,self.config['controller_id'],independently_verified=True)
        for order in self.record['orders']:
            if order['state']=='pending':order['state']='abandoned'
        self.record.update(no_launch_certificate=proof,release_kind='verified_no_launch_only',release_verified=True,terminal_recorded=True,parent_terminal=True)
        self.host.sent[self.record['parent_build_task_id']]['terminal']=True
        self.host.feedback(self.record['parent_build_task_id'],'failed','execution_error',self.host.last_snapshot['game_time_seconds'])
        atomic(self.host.output/'dispatch-ledger.json',self.host.sent)
        await asyncio.to_thread(self.runtime.close);self.closed=True;self.persist()
        self.event('paid_pair_unlaunched_controller_released',controller_id=self.config['controller_id'],source_sha256=proof['source_sha256'],sdk_calls=0,physical_return_claim=False)

    async def _submit_due(self,frame):
        if not self.record or not self.owns_channel() or self.stopping:return
        orders=self.record['orders'];pending=next((o for o in orders if o['state']=='pending'),None)
        if pending is None:return
        previous=orders[0]
        if pending is orders[1]:
            if previous['state']!='accepted':return
            issued=previous['receipt'].get('enqueue_frame')
            if type(issued) is not int:raise ValueError('reserve_original_enqueue_frame_missing')
            if frame-issued<max(150,getattr(self.host.executor,'min_interval',150)):return
        if frame>=pending['command']['expires_frame']:
            pending['state']='expired';self.persist();await asyncio.to_thread(self.runtime.request_retreat);return
        pending['state']='dispatch_pending';self.persist()
        receipt=await asyncio.to_thread(self.host.executor.submit,pending['command'])
        pending['receipt']=receipt;self.host.counters['dispatches']+=1
        if receipt.get('accepted') is True and receipt.get('command_id')==pending['command']['command_id'] and receipt.get('seq')==pending['command']['seq'] and type(receipt.get('queue_id')) is int and receipt['queue_id']>0:
            pending['state']='accepted'
            if not self.record['parent_started']:
                self.host.feedback(self.record['parent_build_task_id'],'started','ok',self.host.last_snapshot['game_time_seconds']);self.record['parent_started']=True
        else:
            pending['state']='failed'
            for order in orders:
                if order['state']=='pending':order['state']='abandoned'
            self.record['production_failure']=True
            await asyncio.to_thread(self.runtime.request_retreat)
            if receipt.get('status')=='unknown':self.persist();raise RuntimeError('dispatch_outcome_unknown')
        self.persist()

    async def receive_production(self):
        if self.record is None:return
        from battle_host import verified_completion
        status=await asyncio.to_thread(self.host.executor.status)
        by_command={row['command_id']:row for row in status.get('ledger',[])}
        for order in self.record['orders']:
            actual=by_command.get(order['command']['command_id'])
            if actual is not None:order['latest_receipt']=actual
        if not self.record['parent_terminal']:
            complete=all(order['state']=='accepted' and verified_completion(order.get('latest_receipt',{}),dict(command_id=order['command']['command_id'],seq=order['command']['seq'],queue_id=order['receipt']['queue_id'])) for order in self.record['orders'])
            failed=any(order['state'] in ('failed','expired','abandoned') or order.get('latest_receipt',{}).get('status') in ('failed','rejected','no_dispatch_rejected') for order in self.record['orders'])
            if complete or failed:
                self.host.feedback(self.record['parent_build_task_id'],'completed' if complete else 'failed','ok' if complete else 'execution_error',self.host.last_snapshot['game_time_seconds'])
                self.host.sent[self.record['parent_build_task_id']]['terminal']=True;self.record['parent_terminal']=True
                atomic(self.host.output/'dispatch-ledger.json',self.host.sent)
        self.persist()

    def _binding(self):return dict(session_id=self.host.binding.session_id,controller_id=self.config['controller_id'],lease_id=self.config['lease_id'])

    def normalize(self,facts):
        """Runtime has source-pinned/requalified these facts; never read masks."""
        if self.record is None:return
        self.last_facts=copy.deepcopy(facts);controller=self.config['controller_id'];state=self.held_registry.controller(controller)
        clock=facts.get('clock',{})
        if clock.get('verified') is True:
            values=dict(reserve_start_frame=clock['start'],reserve_deadline_frame=clock['reserve_deadline'],hard_deadline_frame=clock['hard_deadline'])
            if not state['lease_clock_bound']:
                self.held_registry.bind_lease_clock(controller,dict(self._binding(),**values,observed_frame=clock['start'],proof_sha256=facts['source_sha256'],validated_before_first_borrow=True))
            elif any(state[k]!=v for k,v in values.items()):raise ValueError('reserve_live_clock_changed')
        for claim in facts.get('claims',[]):
            if claim.get('verified') is not True:continue
            role=claim['role'];name=('front','support')[role];state=self.held_registry.controller(controller)
            old=state['slots'].get(name)
            if old is not None:
                if old['object_id']!=claim['object_id'] or old['type_hash']!=claim['type_hash'] or old['proof_sha256']!=claim['proof_sha256']:raise ValueError('reserve_original_claim_changed')
                continue
            expected=self.config['slots'][role]
            self.held_registry.claim_slot(controller,dict(self._binding(),slot=name,object_id=claim['object_id'],type_hash=claim['type_hash'],paid=claim['paid_cost'],producer_reserve=1000,production_command_id=expected['command_id'],production_task_id=expected['task_id'],receipt_sha256=digest(self.runtime.report['native']['slots'][role]['receipt']),proof_sha256=claim['proof_sha256'],observed_frame=claim['borrow_frame']))
            self.event('paid_pair_original_actor_claimed',controller_id=controller,role=role,object_id=claim['object_id'],frame=claim['borrow_frame'],source_sha256=facts['source_sha256'])
        ready=facts.get('ready',{})
        if ready.get('verified') is True:
            for role in ready['roles']:
                name=('front','support')[role['role']];state=self.held_registry.controller(controller);slot=state['slots'].get(name)
                if slot is None:raise ValueError('reserve_ready_without_claim')
                prior=slot['ready']
                if prior and prior['observed_frame']>=role['latest_hold_frame']:continue
                self.held_registry.mark_slot_ready(controller,dict(self._binding(),slot=name,object_id=slot['object_id'],observed_frame=role['latest_hold_frame'],proof_sha256=role['proof_sha256'],validated_ready=True,region_id=self.host.collector.region_of(role['anchor'])))
        self.persist()

    async def poll(self):
        if self.runtime is None:return
        if not self.closed:
            await asyncio.to_thread(self.runtime.poll)
            self.normalize(await asyncio.to_thread(self.runtime.verified_facts))
            native=self.runtime.report.get('native',{})
            if self.runtime.report.get('status')=='finished':
                proof=await asyncio.to_thread(self.runtime.verified_release)
                scene=None
                if proof.get('scene_release') is not None:
                    if proof['scene_release'].get('scene_disposed_control_release') is True:
                        scene=await asyncio.to_thread(self._verify_scene_release,proof['scene_release'])
                        proof=dict(proof,control_release_verified=True,actors=scene['actors'])
                    else:
                        if proof.get('control_release_verified') is True:raise ValueError('reserve_scene_failed_proof_cannot_release')
                        self.record['scene_release_wait']=copy.deepcopy(proof['scene_release'])
                self.record['native_terminal_seen']=dict(source_sha256=proof.get('source_sha256'),release_verified=proof.get('control_release_verified') is True,has_model_task=self.record['mission_mapping'] is not None)
                self.persist()
                if proof.get('control_release_verified') is True:
                    if not self.record['terminal_recorded']:
                        mission=self.held_registry.controller(self.config['controller_id'])['mission_commit']
                        frame=max([0]+[e['frame'] for e in self.runtime.report.get('events',[])])
                        self.held_registry.record_terminal(self.config['controller_id'],dict(self._binding(),status='completed' if scene is None and mission and self.runtime.report.get('assessment',{}).get('effect_verified') is True else 'failed',reason_code='scene_closed' if scene else 'native_terminal',observed_frame=frame,proof_sha256=scene['sidecar_sha256'] if scene else proof['source_sha256']))
                        self.record['terminal_recorded']=True
                    expected=sorted(self.held_registry.claimed_actor_ids());actual=sorted(a['object_id'] for a in proof.get('actors',[]) if not a.get('never_held') and a.get('released') is True)
                    if expected!=actual:raise ValueError('reserve_release_actor_set_changed')
                    self.held_registry.record_verified_release(self.config['controller_id'],dict(self._binding(),object_ids=expected,observed_frame=max([0]+[e['frame'] for e in self.runtime.report.get('events',[])]),proof_sha256=scene['sidecar_sha256'] if scene else proof['source_sha256'],independently_verified=True,channel_release_verified=True))
                    for order in self.record['orders']:
                        if order['state']=='pending':order['state']='abandoned'
                    await asyncio.to_thread(self.host.tactical.executor.release_controller_channel,self.config['controller_id'],independently_verified=True)
                    if scene:
                        self.record.update(scene_release=copy.deepcopy(scene),release_kind='scene_closed_exclusive_control_only')
                        self.event('paid_pair_scene_closed_control_release',controller_id=self.config['controller_id'],evidence_sha256=scene['sidecar_sha256'],restoration_verified=False,return_verified=False,goal_observed=False)
                    self.record['release_verified']=True;self.persist();await asyncio.to_thread(self.runtime.close);self.closed=True
        if self.record.get('release_kind')!='scene_closed_exclusive_control_only':await self.receive_production()
        if not self.closed:await self._submit_due(round(self.host.last_snapshot['game_time_seconds']*15))
        self.update_scope()

    def _verify_scene_release(self,proof):
        if self.directory not in ('mission-formation-v17','mission-formation-v18') or type(proof) is not dict:raise ValueError('reserve_scene_unapproved_family')
        path=Path(proof['sidecar_path']).resolve()
        if not path.is_relative_to(self.output.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=proof.get('sidecar_sha256'):raise ValueError('reserve_scene_sidecar_binding')
        spec=importlib.util.spec_from_file_location('host_'+self.directory.replace('-','_')+'_scene_release',ROOT/'tactical'/self.directory/'scene_terminal_release.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        verified=reader.verify_path(path,self.runtime.output)
        if any(verified.get(k)!=v for k,v in dict(controller_id=self.config['controller_id'],lease_id=self.config['lease_id'],session_id=self.host.binding.session_id,pid=self.host.session['pid'],source_sha256=hashlib.sha256(Path(self.runtime.output).read_bytes()).hexdigest(),sidecar_sha256=proof['sidecar_sha256']).items()) or verified.get('scene_closed_verified') is not True or verified.get('scene_disposed_control_release') is not True or verified.get('control_release_verified') is not True or any(verified.get(k) is not False for k in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')):raise ValueError('reserve_scene_exclusive_release_unproven')
        expected=sorted(self.held_registry.claimed_actor_ids());actual=sorted(a['object_id'] for a in verified.get('actors',[]) if not a.get('never_held') and a.get('released') is True)
        if expected!=actual:raise ValueError('reserve_scene_original_actor_set_changed')
        return verified

    def update_scope(self):
        private=self.held_registry.private_formations()
        available={row['formation_id'] for row in self.host.last_snapshot.get('battlefield',{}).get('formations',[]) if row.get('available') is True}
        mapping={fid:row['version'] for fid,row in private.items() if fid in available or self.record.get('mission_mapping') is not None}
        self.host.agent.set_prebound_paid_pairs(mapping)

    def urgent_ready_epoch(self):
        if self.ready_epoch is not None or not self.last_facts or self.last_facts.get('ready',{}).get('verified') is not True or self.record.get('mission_mapping') is not None:return None
        fid=next(iter(self.held_registry.private_formations()),None)
        descriptor=next((f for f in self.host.last_snapshot.get('battlefield',{}).get('formations',[]) if f.get('formation_id')==fid and f.get('available') is True),None)
        contacts=self.host.last_snapshot.get('battlefield',{}).get('contacts',[])
        visible=any(c.get('currently_visible') is True and c.get('relation')=='enemy' and c.get('role') in ('infantry','armor','structure','economy') for c in contacts)
        if descriptor and visible:
            self.ready_epoch=self.config['controller_id']+'-ready';self.persist();return self.ready_epoch
        return None

    async def commit(self,request,formation,visibility_proof_path,*,public_command_source=None,combat_frames=60):
        if self.runtime is None or self.closed:raise ValueError('reserve_no_active_runtime')
        if self.record.get('mission_mapping') is not None:
            expected_source=str(Path(public_command_source).resolve()) if public_command_source is not None else None
            if self.record.get('public_mission_command')!=request or self.record.get('mission_formation')!=formation or self.record.get('mission_visibility_proof_path')!=str(Path(visibility_proof_path).resolve()) or self.record.get('mission_public_source')!=expected_source:raise ValueError('reserve_write_once_request_conflict')
            if self.record.get('mission_publication_state')!='published':raise ValueError('reserve_ambiguous_commit_cannot_retry')
            return await asyncio.to_thread(self.runtime.commit,request,formation,visibility_proof_path,public_command_source=public_command_source,combat_frames=combat_frames)
        fid=formation['formation_id'];private=self.private_formation(fid);deadline=self.hard_deadline(fid)
        if request.get('expires_frame')!=deadline:raise ValueError('reserve_commit_must_keep_original_deadline')
        target=self.host.collector.private_targets.get(request.get('target_contact_id'))
        contact=next((c for c in self.host.last_snapshot['battlefield']['contacts'] if c['contact_id']==request.get('target_contact_id')),None)
        if not target or not contact:raise ValueError('reserve_current_target_missing')
        proof=Path(visibility_proof_path);source_sha=hashlib.sha256(proof.read_bytes()).hexdigest();frame=round(self.host.last_snapshot['game_time_seconds']*15)
        record=dict(self._binding(),task_id=request['task_id'],command_id=request['command_id'],seq=request['seq'],formation_id=fid,formation_version=formation['version'],object_ids=list(private['object_ids']),module=request['module'],purpose=request['purpose'],request_force_fraction=request['force_fraction'],allocation_scope=SCOPE,hard_deadline_frame=deadline,reserve_deadline_frame=private['reserve_deadline_frame'],commit_frame=frame,target=dict(contact_id=request['target_contact_id'],object_id=target['object_id'],type_hash=target['type_hash'],owner_player_id=contact['owner_player_id'],role=contact['role'],observed_frame=target['observed_frame'],proof_sha256=source_sha,currently_visible_verified=contact['currently_visible'] is True))
        mapping=self.held_registry.commit_mission(self.config['controller_id'],record)
        self.record.update(mission_mapping=mapping,public_mission_command=copy.deepcopy(request),mission_formation=copy.deepcopy(formation),mission_visibility_proof_path=str(Path(visibility_proof_path).resolve()),mission_public_source=str(Path(public_command_source).resolve()) if public_command_source is not None else None,mission_publication_state='intent')
        self.persist();self.event('paid_pair_mission_mapping_persisted',controller_id=self.config['controller_id'],task_id=request['task_id'],expires_frame=deadline)
        try:result=await asyncio.to_thread(self.runtime.commit,request,formation,visibility_proof_path,public_command_source=public_command_source,combat_frames=combat_frames)
        except BaseException:
            self.record['mission_publication_state']='failed_or_unknown';self.persist();raise
        self.record['mission_publication_state']='published';self.persist();return result

    async def stop(self):
        self.stopping=True
        if self.record:
            for order in self.record['orders']:
                if order['state']=='pending':order['state']='abandoned'
            self.persist()
        if self.runtime is not None and not self.closed:
            await asyncio.to_thread(self.runtime.stop)
            await self.poll()
            if self.owns_channel():raise ValueError('reserve_control_release_unverified')

    def public_status(self):
        return dict(attempted=self.attempted,executor_directory=self.directory,wrapper_filename=self.wrapper_filename,controller_id=self.config['controller_id'] if self.config else None,channel_claimed=self.owns_channel(),runtime_closed=self.closed,original_deadlines={k:self.held_registry.controller(self.config['controller_id'])[k] for k in ('reserve_start_frame','reserve_deadline_frame','hard_deadline_frame')} if self.config else None,mission_task_id=self.record['mission_mapping']['task_id'] if self.record and self.record['mission_mapping'] else None,release_verified=bool(self.record and self.record['release_verified']),physical_capability_verified=False)
