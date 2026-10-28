"""Host-owned single-actor lifecycle over the existing journal and adapter.

No model/UI object can construct its transport or grant. Native receipts remain
the only source of readiness and release; polling never dispatches a command.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import math
import time
import uuid

from .arbitration import ControlArbiter
from .capabilities import CapabilityCatalog
from .contracts import ContractError, SessionBinding, content_hash, identifier, integer
from .gateway import ExecutionGateway
from .journal import CommandJournal
from .host_supervisor import pending_native_commands,supervisor_for_host
from .tactical_adapter import TacticalRuntimeAdapter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SingleActorTask:
    task_id: str
    generation: int
    lease_id: str
    object_id: int
    actor_generation: int
    deadline_frame: int


class HostTactical:
    def __init__(self, journal: CommandJournal, run_id: str, binding: SessionBinding,
                 capabilities: CapabilityCatalog, *, transport=None, test_transport=None,supervisor=None):
        if not isinstance(binding, SessionBinding) or not isinstance(capabilities, CapabilityCatalog) or capabilities.binding != binding:
            raise ContractError("host_tactical_binding_required")
        self.journal, self.run_id, self.binding = journal, identifier(run_id), binding
        if pending_native_commands(journal,binding,supervisor,exclude_run_id=run_id):
            raise ContractError("prior_host_commands_require_recovery")
        journal.register_run(run_id, binding.public())
        # An interrupted owner is never reconstructed from a fresh empty arbiter.
        cursor = 0
        while True:
            events = journal.events(run_id, after=cursor)
            if any(e['event_type'] == 'tactical_owner_created' for e in events):
                raise ContractError("tactical_owner_requires_explicit_recovery")
            if not events:
                break
            cursor = events[-1]['seq']
        self.arbiter = ControlArbiter(binding.session_id, binding.player_id)
        self.adapter = TacticalRuntimeAdapter(binding, run_id=run_id, journal=journal,
            capabilities=capabilities, arbiter=self.arbiter, transport=transport, test_transport=test_transport)
        self.transport = self.adapter.transport
        if not callable(getattr(self.transport, 'poll', None)):
            raise ContractError("native_tactical_poll_required")
        journal.append_event(run_id, 'tactical_owner_created', {'binding_hash':binding.binding_hash,
            'transport_mode':'injected_test' if self.adapter.test_only else 'original_native'})
        self.gateway = ExecutionGateway(run_id, binding, journal, capabilities, self.adapter)
        self._tasks, self._requests, self._by_command = {}, {}, {}
        self._active = None

    def _id(self, task_id, operation):
        return str(uuid.uuid5(uuid.UUID(self.run_id), task_id + ':' + operation))

    def _send(self, task: SingleActorTask, operation, **details):
        request_id = self._id(task.task_id, operation)
        fingerprint = content_hash(dict(operation=operation, task_id=task.task_id, **details))
        if request_id in self._requests:
            if self._requests[request_id] != fingerprint:
                raise ContractError("tactical_intent_changed")
            return self.journal.get_command(self.run_id, request_id)
        snap = self.transport.admit(self.binding)
        payload = dict(task_id=task.task_id, generation=task.generation, lease_id=task.lease_id,
            expires_frame=snap.game_frame + 120, expires_monotonic_ms=snap.monotonic_ms + 5000, **details)
        if operation in ('reserve', 'commit'):
            payload['purpose'] = 'move_hold_return'
            payload['expires_frame'] = min(payload['expires_frame'], task.deadline_frame)
        if operation == 'reserve':
            payload.update(actor=dict(object_id=task.object_id, generation=task.actor_generation), deadline_frame=task.deadline_frame)
        self._requests[request_id] = fingerprint
        record = self.gateway.submit(request_id, operation, payload)
        self._by_command[record['command_id']] = request_id
        return record

    def reserve(self, task_id, *, object_id, actor_generation, generation=1, lease_frames=750):
        identifier(task_id)
        integer(object_id, 1, 0xffffffff); integer(actor_generation, 1, 2**63-1)
        integer(generation, 1, 0xffffffff); integer(lease_frames, 1, 900)
        existing = self._tasks.get(task_id)
        if existing:
            if (existing.object_id, existing.actor_generation, existing.generation) != (object_id, actor_generation, generation):
                raise ContractError("tactical_task_identity_changed")
            return self._send(existing, 'reserve')
        if self._active is not None:
            prior = self._tasks[self._active]
            result = self.journal.get_command(self.run_id, self._id(prior.task_id, 'reserve'))
            if result['status'] != 'rejected' and self.arbiter.snapshot(prior.lease_id)['state'] != 'released':
                raise ContractError("active_tactical_control_not_released")
            if any(row['payload'].get('task_id') == prior.task_id for row in self.journal.unresolved(self.run_id)):
                raise ContractError("prior_tactical_commands_require_recovery")
        snap = self.transport.admit(self.binding)
        task = SingleActorTask(task_id, generation, self._id(task_id, 'lease'), object_id, actor_generation, snap.game_frame + lease_frames)
        self.journal.append_event(self.run_id, 'single_actor_task_created', dict(task_id=task_id,
            generation=generation, lease_id=task.lease_id, object_id=object_id, actor_generation=actor_generation,
            deadline_frame=task.deadline_frame), game_frame=snap.game_frame, monotonic_ns=snap.monotonic_ms*1000000)
        self._tasks[task_id], self._active = task, task_id
        return self._send(task, 'reserve')

    def commit(self, task_id, *, target_point_id, hold_frames=15):
        identifier(target_point_id); integer(hold_frames, 0, 900)
        return self._send(self._task(task_id), 'commit', target_point_id=target_point_id, hold_frames=hold_frames)

    def return_home(self, task_id):
        return self._send(self._task(task_id), 'return')

    def stop(self, task_id):
        return self._send(self._task(task_id), 'stop')

    def reconcile_release(self, task_id, *, uncertain_command_id):
        """One NEW release-only intent; polling and old requests never retry.

        Called by trusted Host recovery code, never model/UI receipt data.
        Native independent quiescence and current actor/lease admission remain
        mandatory, even after this bounded read-only preparation succeeds.
        """
        return self._reconcile(task_id,uncertain_command_id=uncertain_command_id,operation='reconcile_release')

    def reconcile_return_home(self, task_id, *, uncertain_command_id):
        """One separately authorized first-home intent; never retry a home Move."""
        return self._reconcile(task_id,uncertain_command_id=uncertain_command_id,operation='reconcile_return_home')

    def _reconcile(self, task_id, *, uncertain_command_id, operation):
        identifier(uncertain_command_id)
        task=self._task(task_id)
        details=dict(recovery_of_command_id=uncertain_command_id)
        if self._id(task_id,operation) in self._requests:
            return self._send(task,operation,**details)
        if operation=='reconcile_return_home':self.adapter.require_first_home_scope()
        request=self._by_command.get(uncertain_command_id)
        if request is None or self._active!=task_id:
            raise ContractError('tactical_recovery_unknown_command_unbound')
        prior=self.journal.get_command(self.run_id,request)
        allowed=('commit',) if operation=='reconcile_return_home' else ('reserve','commit','return','stop','reconcile_return_home')
        if (prior['status']!='uncertain' or prior['operation'] not in allowed
                or any(prior['payload'].get(k)!=v for k,v in
                    dict(task_id=task.task_id,lease_id=task.lease_id,generation=task.generation).items())):
            raise ContractError('tactical_recovery_prior_unknown_required')
        if not callable(getattr(self.transport,'observe_actor',None)):
            raise ContractError('tactical_recovery_fresh_observation_required')
        frames=set();previous=None;observations=[];deadline=time.monotonic()+8
        while len(frames)<4 and time.monotonic()<deadline:
            current=self.transport.poll()
            if (not isinstance(current,Mapping) or current.get('command_id')!=uncertain_command_id
                    or current.get('phase')!='uncertain' or current.get('held') is not True):
                raise ContractError('tactical_recovery_current_unknown_unverified')
            if operation=='reconcile_return_home':
                calls=current.get('sdk_calls')
                if not isinstance(calls,list) or len(calls)!=6 or any(type(v)is not int or v<0 for v in calls) or calls[3]!=1:
                    raise ContractError('tactical_recovery_return_requires_unattempted_home')
            sample=self.transport.observe_actor(self.binding)
            if (type(sample.get('frame'))is not int or type(sample.get('monotonic_ms'))is not int
                    or sample['frame']<current.get('game_frame',0) or sample['monotonic_ms']<current.get('monotonic_ms',0)):
                raise ContractError('tactical_recovery_clock_regressed')
            idle=(sample['state_id'],sample['state_vtable'],sample['command_source'])==(16,0xc55130,2) and sample['stance'] in (0,2)
            # Source2 Stop94 is unowned quiescence for a new release command.
            # It does not satisfy private Stop3, Ready or a physical-home proof.
            stopped=(sample['state_id'],sample['state_vtable'],sample['stance'])==(94,0xc551a0,2) and sample['command_source'] in (1,2)
            quiet=((idle or stopped) and not sample['path'] and not sample['state_flags']&0xffff
                and sample['team']==sample['script_team'] and sample['identity'] is True
                and sample['birth_verified'] is True and sample['live'] is True
                and sample['grounded'] is True and sample['paused'] is False
                and (sample['object_id'],sample['generation'])==(task.object_id,task.actor_generation))
            if previous is not None:
                if sample['frame']<previous['frame'] or sample['monotonic_ms']<previous['monotonic_ms']:raise ContractError('tactical_recovery_clock_regressed')
                quiet=(quiet and sample['foreign_epoch']==previous['foreign_epoch']
                    and math.dist(sample['xyz'][:2],previous['xyz'][:2])<=1
                    and abs(sample['xyz'][2]-previous['xyz'][2])<=.5)
            if quiet:frames.add(sample['frame'])
            else:frames.clear()
            observations.append(sample);previous=sample
            time.sleep(.06)
        if len(frames)<4:raise ContractError('tactical_recovery_no_quiescent_window')
        distinct={s['frame']:s for s in observations if s['frame']in frames}
        self.journal.append_event(self.run_id,'tactical_recovery_quiescence_observed',
            dict(recovery_of_command_id=uncertain_command_id,recovery_operation=operation,frames=sorted(frames),observations=[distinct[f]for f in sorted(frames)]),
            command_id=uncertain_command_id,game_frame=sample['frame'])
        return self._send(task,operation,**details)

    def _task(self, task_id):
        identifier(task_id)
        if task_id not in self._tasks:
            raise ContractError("unknown_tactical_task")
        return self._tasks[task_id]

    def poll(self):
        if not self._by_command:return None
        raw = self.transport.poll()
        if not isinstance(raw, Mapping) or raw.get('command_id') not in self._by_command:
            raise ContractError("unbound_tactical_observation")
        request = self._by_command[raw['command_id']]
        prior = self.journal.get_command(self.run_id, request)
        if prior['status'] == 'uncertain':
            # Reading does not reconcile an unknown effect or send recovery.
            return prior
        return self.adapter.observe(request, raw)

    def snapshot(self):
        tasks = []
        for task in self._tasks.values():
            try: control = self.arbiter.snapshot(task.lease_id)
            except KeyError: control = None
            tasks.append(dict(task_id=task.task_id, generation=task.generation, lease_id=task.lease_id, control=control))
        return dict(run_id=self.run_id, binding_hash=self.binding.binding_hash,
            tasks=tasks, unresolved=self.journal.unresolved(self.run_id),
            field_evidence_eligible=not self.adapter.test_only, physical_evidence_granted=False)

    def shutdown(self):
        """Request bounded release; unknown delivery remains explicit recovery."""
        error = None
        try:
            if self._active is not None:
                task = self._tasks[self._active]
                control = self.arbiter.snapshot(task.lease_id)
                if control['state'] != 'released':
                    if any(row['status'] == 'uncertain' and row['payload'].get('task_id') == task.task_id
                           for row in self.journal.unresolved(self.run_id)):
                        raise ContractError('tactical_unknown_requires_reconciliation')
                    outcome = self.stop(task.task_id)
                    if outcome['status'] != 'released':
                        raise ContractError('tactical_control_release_unverified')
        except Exception as exc:
            error = exc
        finally:
            # Native safety stop is not journal reconciliation or a success claim.
            # Preserve the mapping/raw evidence when cleanup itself is unknown.
            try:self.transport.close()
            except Exception:
                if error is None:raise
        if error is not None:raise error


def from_host(host, production_request_id, *, test_transport=None):
    """Attach only to a completed journaled original paid Conscript command.

    This constructor is called by trusted Host code, never RPC/model data. It
    exposes movement only and does not manufacture old battle-agent combat jobs.
    """
    runtime = host.runtime_production
    if runtime is None or runtime.gateway is None:
        raise ContractError('runtime_production_not_attached')
    runtime.evidence.catalog.require('tactics.move_hold_return', runtime.binding)
    record = runtime.journal.get_command(runtime.run_id, production_request_id)
    if record['operation'] != 'produce' or record['payload'].get('unit') != 'conscript' or record['status'] != 'completed':
        raise ContractError('runtime_completed_conscript_required')
    if runtime.evidence.test_only != (test_transport is not None):
        raise ContractError('runtime_field_evidence_required')
    def checked_actor(actor):
        paid = (record.get('receipt') or {}).get('facts', {})
        if (actor.producer_command_id != record['command_id'] or actor.identity.object_id != paid.get('object_id')
                or actor.identity.session_id != runtime.binding.session_id or actor.identity.player_id != runtime.binding.player_id):
            raise ContractError('runtime_paid_actor_correlation_changed')
        return actor
    if test_transport is not None:
        actor = checked_actor(test_transport.actor)
        owner = HostTactical(runtime.journal, runtime.run_id, runtime.binding, runtime.evidence.catalog,
                            test_transport=test_transport)
        owner.actor = actor
        owner.producer_command_id = record['command_id']
        return owner
    from tactical_bridge import module
    client = module(ROOT / 'tactical/runtime/client.py', 'host_bound_tactical_runtime')
    transport = client.NativeRuntimeClient(host.args.session, runtime.binding, host.executor,
        record['command_id'], Path(host.session['run_directory']) / 'host-tactical-runtime.json')
    # Save the transport before attach: unknown attachment must remain reachable
    # for final cleanup; never silently create a second owner after an exception.
    host.runtime_tactical_transport = transport
    actor = checked_actor(transport.attach(capabilities=runtime.evidence.catalog))
    owner = HostTactical(runtime.journal, runtime.run_id, runtime.binding, runtime.evidence.catalog, transport=transport)
    owner.actor, owner.producer_command_id = actor, record['command_id']
    return owner


def _handoff_catalog(binding,source,digest,*,recovery_source=None,recovery_digest=None):
    from .runtime_evidence import verify_pinned_runtime
    if (recovery_source is None)!=(recovery_digest is None):raise ContractError('first_home_evidence_pin_required')
    grants=[verify_pinned_runtime(source,digest,binding)]
    if recovery_source is not None:
        from .runtime_first_home_evidence import verify_pinned_first_home
        grants.append(verify_pinned_first_home(Path(recovery_source).resolve(strict=True),recovery_digest,binding,
            baseline_report=source,baseline_sha256=digest))
    return CapabilityCatalog.verify(binding,grants,lambda candidate,current:candidate)


def renew_from_host(host, *, test_transport=None,production_request_id=None):
    """Explicit trusted Host lifecycle step after fully released ownership.

    This is not a model/RPC operation. Production must also be at a durable
    admission barrier. Unknown renewal is kept reachable and never retried.
    """
    from .runtime_rotation import retire_channel
    runtime=host.runtime_production;previous=host.runtime_tactical
    if runtime is None or previous is None:
        raise ContractError('runtime_tactical_not_attached')
    if runtime.evidence.test_only!=(test_transport is not None) or previous.adapter.test_only!=(test_transport is not None):
        raise ContractError('runtime_field_evidence_required')
    if getattr(host,'runtime_tactical_rotation_attempted',False):
        raise ContractError('tactical_owner_requires_explicit_recovery')
    supervisor=supervisor_for_host(host)
    if pending_native_commands(runtime.journal,runtime.binding,supervisor):
        raise ContractError('runtime_tactical_waiting_production_or_control_barrier')
    if any(t['control'] is None or t['control']['state']!='released' for t in previous.snapshot()['tasks']):
        raise ContractError('runtime_tactical_control_not_released')
    paid=(runtime.journal.get_command_by_id(runtime.run_id,previous.producer_command_id) if production_request_id is None
        else runtime.journal.get_command(runtime.run_id,production_request_id))
    if paid['operation']!='produce' or paid['status']!='completed' or paid['payload'].get('unit')!='conscript':
        raise ContractError('runtime_completed_conscript_required')
    if test_transport is None:
        # Verify the independently pinned scope before closing the old channel.
        source=Path(host.args.runtime_report).resolve(strict=True)
        digest=host.args.runtime_sha256
        recovery_source=getattr(host.args,'runtime_recovery_report',None)
        recovery_digest=getattr(host.args,'runtime_recovery_sha256',None)
        if recovery_source is None and any(g['capability_id']=='tactics.reconcile_return_home'for g in previous.adapter.catalog.describe()['grants']):
            raise ContractError('first_home_handoff_pin_required')
        before_catalog=_handoff_catalog(previous.binding,source,digest,recovery_source=recovery_source,recovery_digest=recovery_digest)
        runtime.journal.append_event(previous.run_id,'tactical_handoff_scope_reverified',dict(phase='before_retire',
            binding_hash=previous.binding.binding_hash,evidence_ids=[g['evidence_id']for g in before_catalog.describe()['grants']]))
    host.runtime_tactical_rotation_attempted=True
    run=Path(host.session['run_directory'])
    handoff=retire_channel(previous,session_path=host.args.session,
        capture_path=run/('host-tactical-retired-'+previous.run_id+'.json'),
        manifest_path=run/('host-tactical-handoff-'+previous.run_id+'.json'),supervisor=supervisor,
        successor_producer_command_id=paid['command_id'])
    epochs=getattr(host,'runtime_tactical_epochs',[])
    epochs.append(dict(run_id=previous.run_id,binding_hash=previous.binding.binding_hash,
        state='retired',successor_run_id=handoff.run_id,manifest_sha256=handoff.manifest_sha256))
    host.runtime_tactical_epochs=epochs
    if getattr(host,'stop_path',None) is not None and host.stop_requested():
        raise ContractError('runtime_tactical_stopping_before_successor_attach')
    if test_transport is not None:
        ids={g['capability_id']for g in previous.adapter.catalog.describe()['grants']}
        grants=[previous.adapter.catalog.require('tactics.move_hold_return',previous.binding)]
        if 'tactics.reconcile_return_home'in ids:grants.append(previous.adapter.catalog.require('tactics.reconcile_return_home',previous.binding))
        catalog=CapabilityCatalog.verify(handoff.binding,grants,lambda candidate,binding:candidate)
        transport=test_transport;actor=transport.actor
    else:
        catalog=_handoff_catalog(handoff.binding,source,digest,recovery_source=recovery_source,recovery_digest=recovery_digest)
    return _attach_successor(host,handoff,paid,catalog,supervisor,test_transport=test_transport)


def _attach_successor(host,handoff,paid,catalog,supervisor,*,test_transport=None):
    runtime=host.runtime_production;run=Path(host.session['run_directory'])
    if getattr(host,'stop_path',None) is not None and host.stop_requested():
        raise ContractError('runtime_tactical_stopping_before_successor_attach')
    if test_transport is not None:transport=test_transport;actor=transport.actor
    else:
        runtime.journal.register_run(handoff.run_id,handoff.binding.public())
        runtime.journal.append_event(handoff.run_id,'tactical_handoff_scope_reverified',dict(phase='before_successor_attach',
            binding_hash=handoff.binding.binding_hash,evidence_ids=[g['evidence_id']for g in catalog.describe()['grants']]))
        from tactical_bridge import module
        client=module(ROOT/'tactical/runtime/client.py','host_bound_tactical_runtime')
        transport=client.NativeRuntimeClient(host.args.session,handoff.binding,host.executor,
            paid['command_id'],run/('host-tactical-runtime-'+handoff.run_id+'.json'),handoff=handoff)
        host.runtime_tactical_transport=transport
        actor=transport.attach(capabilities=catalog)
    if (actor.producer_command_id!=paid['command_id']
            or actor.identity.object_id!=(paid.get('receipt') or {}).get('facts',{}).get('object_id')
            or actor.identity.session_id!=handoff.binding.session_id
            or actor.identity.player_id!=handoff.binding.player_id):
        raise ContractError('runtime_paid_actor_correlation_changed')
    owner=HostTactical(runtime.journal,handoff.run_id,handoff.binding,catalog,
        supervisor=supervisor,**({'test_transport':transport} if test_transport is not None else {'transport':transport}))
    owner.actor=actor;owner.producer_command_id=paid['command_id']
    host.runtime_tactical_transport=transport
    host.runtime_tactical_rotation_attempted=False
    return owner


def suspend_from_host(host):
    """Close a released/idle channel without authorizing any successor yet."""
    from .runtime_rotation import retire_for_later
    runtime=host.runtime_production;previous=host.runtime_tactical
    if runtime is None or previous is None:raise ContractError('runtime_tactical_not_attached')
    if runtime.evidence.test_only or previous.adapter.test_only:raise ContractError('runtime_field_evidence_required')
    if getattr(host,'runtime_tactical_rotation_attempted',False):raise ContractError('tactical_owner_requires_explicit_recovery')
    supervisor=supervisor_for_host(host)
    if pending_native_commands(runtime.journal,runtime.binding,supervisor):
        raise ContractError('runtime_tactical_waiting_production_or_control_barrier')
    if any(t['control'] is None or t['control']['state']!='released'for t in previous.snapshot()['tasks']):
        raise ContractError('runtime_tactical_control_not_released')
    source=Path(host.args.runtime_report).resolve(strict=True);digest=host.args.runtime_sha256
    recovery_source=getattr(host.args,'runtime_recovery_report',None);recovery_digest=getattr(host.args,'runtime_recovery_sha256',None)
    if recovery_source is None and any(g['capability_id']=='tactics.reconcile_return_home'for g in previous.adapter.catalog.describe()['grants']):
        raise ContractError('first_home_handoff_pin_required')
    catalog=_handoff_catalog(previous.binding,source,digest,recovery_source=recovery_source,recovery_digest=recovery_digest)
    runtime.journal.append_event(previous.run_id,'tactical_handoff_scope_reverified',dict(phase='before_deferred_retire',
        binding_hash=previous.binding.binding_hash,evidence_ids=[g['evidence_id']for g in catalog.describe()['grants']]))
    host.runtime_tactical_rotation_attempted=True
    run=Path(host.session['run_directory'])
    retirement=retire_for_later(previous,session_path=host.args.session,
        capture_path=run/('host-tactical-retired-'+previous.run_id+'.json'),
        manifest_path=run/('host-tactical-deferred-'+previous.run_id+'.json'),supervisor=supervisor)
    host.runtime_tactical_retirement=retirement;host.runtime_tactical_resume_attempted=False
    epochs=getattr(host,'runtime_tactical_epochs',[])
    epochs.append(dict(run_id=previous.run_id,binding_hash=previous.binding.binding_hash,state='retired_waiting_successor',
        manifest_sha256=retirement.manifest_sha256))
    host.runtime_tactical_epochs=epochs
    return retirement


def resume_from_host(host,*,production_request_id):
    """One later paid actor selection, requalified before native attachment."""
    from .runtime_rotation import authorize_deferred_successor
    runtime=host.runtime_production;previous=host.runtime_tactical
    retirement=getattr(host,'runtime_tactical_retirement',None)
    if runtime is None or previous is None or retirement is None:raise ContractError('runtime_deferred_retirement_required')
    if runtime.evidence.test_only or previous.adapter.test_only:raise ContractError('runtime_field_evidence_required')
    if getattr(host,'runtime_tactical_resume_attempted',False):raise ContractError('tactical_owner_requires_explicit_recovery')
    paid=runtime.journal.get_command(runtime.run_id,production_request_id)
    if paid['operation']!='produce' or paid['status']!='completed' or paid['payload'].get('unit')!='conscript':
        raise ContractError('runtime_completed_conscript_required')
    if paid['command_id']!=previous.producer_command_id:
        selected_seq=runtime.journal.get_native_sequence(runtime.run_id,paid['command_id'])
        previous_seq=runtime.journal.get_native_sequence(runtime.run_id,previous.producer_command_id)
        if selected_seq<=previous_seq:
            raise ContractError('runtime_successor_requires_later_paid_producer')
    source=Path(host.args.runtime_report).resolve(strict=True);digest=host.args.runtime_sha256
    recovery_source=getattr(host.args,'runtime_recovery_report',None);recovery_digest=getattr(host.args,'runtime_recovery_sha256',None)
    if recovery_source is None and any(g['capability_id']=='tactics.reconcile_return_home'for g in previous.adapter.catalog.describe()['grants']):
        raise ContractError('first_home_handoff_pin_required')
    _handoff_catalog(previous.binding,source,digest,recovery_source=recovery_source,recovery_digest=recovery_digest)
    if getattr(host,'stop_path',None) is not None and host.stop_requested():
        raise ContractError('runtime_tactical_stopping_before_successor_attach')
    host.runtime_tactical_resume_attempted=True
    handoff=authorize_deferred_successor(retirement,producer_command_id=paid['command_id'],
        manifest_path=Path(host.session['run_directory'])/('host-tactical-handoff-'+previous.run_id+'.json'))
    catalog=_handoff_catalog(handoff.binding,source,digest,recovery_source=recovery_source,recovery_digest=recovery_digest)
    owner=_attach_successor(host,handoff,paid,catalog,retirement.supervisor)
    host.runtime_tactical_retirement=None
    host.runtime_tactical_epochs[-1].update(state='retired',successor_run_id=handoff.run_id,successor_manifest_sha256=handoff.manifest_sha256)
    return owner
