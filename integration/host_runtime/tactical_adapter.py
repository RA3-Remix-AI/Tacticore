"""Single paid Conscript runtime boundary; never accepts native addresses from UI.

Native transport owns the private actor and endpoint registries. Injected test
transports are explicitly labelled and cannot become field capability evidence.
"""
from dataclasses import dataclass
from pathlib import Path
import sys
from collections.abc import Mapping
import math

from .arbitration import ActorIdentity, ControlArbiter, ArbitrationError
from .capabilities import CapabilityCatalog
from .contracts import ContractError, SessionBinding, identifier, integer, object_fields, sha256, text
from .gateway import AdmissionRefused, NativeReceipt

CLIENT = Path(__file__).resolve().parents[2] / 'tactical/runtime/client.py'
PROTOCOL = 'tactical_runtime_v1'


@dataclass(frozen=True)
class RuntimeSnapshot:
    binding_hash: str
    game_frame: int
    monotonic_ms: int
    paused: bool
    last_sequence: int
    executor_sha256: str
    native_host_sha256: str
    proof_reference: str


@dataclass(frozen=True)
class RuntimeActor:
    identity: ActorIdentity
    born_frame: int
    producer_command_id: str
    source_reference: str
    unit: str = 'conscript'


class TacticalRuntimeAdapter:
    def __init__(self, binding: SessionBinding, *, run_id, journal,
                 capabilities: CapabilityCatalog, arbiter: ControlArbiter,
                 transport=None, test_transport=None):
        if not isinstance(binding, SessionBinding) or not isinstance(capabilities, CapabilityCatalog) or not isinstance(arbiter, ControlArbiter):
            raise ContractError('tactical_runtime_contract_required')
        if transport is not None and test_transport is not None:
            raise ContractError('one_tactical_transport_required')
        self.test_only = test_transport is not None
        self.transport = test_transport if self.test_only else transport
        if self.transport is None:
            raise ContractError('attached_native_runtime_client_required')
        if not self.test_only:
            owner = sys.modules.get(type(self.transport).__module__)
            if (type(self.transport).__name__ != 'NativeRuntimeClient' or owner is None
                    or Path(owner.__file__).resolve() != CLIENT or getattr(self.transport, 'test_only', True)):
                raise ContractError('original_native_runtime_client_required')
        for method in ('admit', 'resolve_actor', 'approved_target', 'submit'):
            if not callable(getattr(self.transport, method, None)):
                raise ContractError('native_runtime_transport_incomplete')
        if (arbiter.session_id, arbiter.player_id) != (binding.session_id, binding.player_id):
            raise ContractError('tactical_arbiter_binding_mismatch')
        self.binding, self.run_id, self.journal = binding, identifier(run_id), journal
        self.catalog, self.arbiter = capabilities, arbiter
        self.executor_sha256 = sha256(self.transport.executor_sha256)
        self.native_host_sha256 = sha256(self.transport.native_host_sha256)
        self._sent, self._leases = set(), {}
        self._last_frame = self._last_ms = -1

    def _payload(self, command):
        operation = command['operation']
        required = {'task_id', 'generation', 'lease_id', 'expires_frame', 'expires_monotonic_ms'}
        extra = {'purpose'} if operation in ('reserve', 'commit') else set()
        if operation == 'reserve':extra |= {'actor', 'deadline_frame'}
        if operation == 'commit':extra |= {'target_point_id', 'hold_frames'}
        if operation in ('reconcile_release','reconcile_return_home'):extra |= {'recovery_of_command_id'}
        payload = object_fields(command['payload'], required | extra)
        for key in ('task_id', 'lease_id'):identifier(payload[key])
        integer(payload['generation'], 1, 0xffffffff)
        integer(payload['expires_frame'], 1, 0xffffffff)
        integer(payload['expires_monotonic_ms'], 1, 2**63-1)
        if operation in ('reserve', 'commit') and payload['purpose'] != 'move_hold_return':
            raise AdmissionRefused('tactical_runtime_purpose_unreviewed')
        if operation == 'reserve':
            actor = object_fields(payload['actor'], {'object_id', 'generation'})
            integer(actor['object_id'], 1, 0xffffffff);integer(actor['generation'], 1, 2**63-1)
            integer(payload['deadline_frame'], 1, 0xffffffff)
        if operation == 'commit':
            identifier(payload['target_point_id']);integer(payload['hold_frames'], 0, 900)
        if operation in ('reconcile_release','reconcile_return_home'):identifier(payload['recovery_of_command_id'])
        return payload

    def require_first_home_scope(self):
        grant=self.catalog.require('tactics.reconcile_return_home',self.binding)
        scope=grant.public()['execution_constraints']
        if (scope.get('runtime_family')!='tactical' or scope.get('executor_directory')!='tactical/runtime'
                or scope.get('purpose')!='reconcile_return_home' or scope.get('module')!='runtime_first_home_recovery_v1'
                or scope.get('actor_roles')!=['infantry'] or scope.get('mission_protocol')!=PROTOCOL
                or scope.get('execution_ready')is not True or grant.executor_sha256!=self.executor_sha256
                or scope.get('native_host_sha256')!=self.native_host_sha256):
            raise AdmissionRefused('first_home_recovery_scope_unverified')
        return grant

    def _metadata(self, command, binding):
        if binding != self.binding:
            raise AdmissionRefused('tactical_adapter_binding_changed')
        if command.get('operation') not in ('reserve', 'commit', 'return', 'stop', 'query_status', 'reconcile_release','reconcile_return_home'):
            raise AdmissionRefused('tactical_runtime_operation_unreviewed')
        for key, value in (('run_id', self.run_id), ('session_id', binding.session_id),
                           ('player_id', binding.player_id), ('commander_id', binding.commander_id)):
            if command.get(key) != value or key == 'player_id' and type(command[key]) is not int:
                raise AdmissionRefused('tactical_command_binding_changed')
        identifier(command['command_id']);identifier(command['request_id'])
        original = self.journal.get_command(self.run_id, command['request_id'])
        if original['command_id'] != command['command_id'] or original['operation'] != command['operation'] or original['payload'] != command['payload']:
            raise AdmissionRefused('tactical_journal_command_changed')

    def _admit(self, command, binding):
        self._metadata(command, binding);payload = self._payload(command)
        snapshot = self.transport.admit(binding)
        if not isinstance(snapshot, RuntimeSnapshot) or snapshot.binding_hash != binding.binding_hash:
            raise AdmissionRefused('native_runtime_binding_unverified')
        integer(snapshot.game_frame, 0, 0xffffffff);integer(snapshot.monotonic_ms, 0, 2**63-1)
        integer(snapshot.last_sequence, 0, 0xffffffff);text(snapshot.proof_reference, 200)
        if snapshot.executor_sha256 != self.executor_sha256 or snapshot.native_host_sha256 != self.native_host_sha256:
            raise AdmissionRefused('native_runtime_binary_changed')
        if snapshot.game_frame < self._last_frame or snapshot.monotonic_ms < self._last_ms:
            raise AdmissionRefused('tactical_observation_clock_regressed')
        self._last_frame, self._last_ms = snapshot.game_frame, snapshot.monotonic_ms
        if type(snapshot.paused) is not bool or snapshot.paused:
            raise AdmissionRefused('game_paused')
        if payload['expires_frame'] <= snapshot.game_frame or payload['expires_monotonic_ms'] <= snapshot.monotonic_ms:
            raise AdmissionRefused('tactical_command_expired')
        if command['operation'] in ('reserve', 'commit'):
            grant = self.catalog.require('tactics.move_hold_return', binding)
            scope = grant.public()['execution_constraints']
            if command.get('capability') != grant.public() or not scope or scope.get('runtime_family') != 'tactical' or scope.get('executor_directory') != 'tactical/runtime' or scope.get('mission_protocol') != PROTOCOL or scope.get('purpose') != 'move_hold_return' or scope.get('execution_ready') is not True or grant.executor_sha256 != snapshot.executor_sha256 or scope.get('native_host_sha256') != snapshot.native_host_sha256 or scope.get('actor_roles') != ['infantry']:
                raise AdmissionRefused('single_actor_runtime_scope_unverified')
        if command['operation']=='reconcile_return_home':
            if command.get('capability')!=self.require_first_home_scope().public():
                raise AdmissionRefused('first_home_recovery_scope_unverified')
        if command['operation'] == 'reserve':
            if payload['lease_id'] in self._leases:
                raise AdmissionRefused('tactical_lease_already_registered')
            if not snapshot.game_frame < payload['deadline_frame'] <= snapshot.game_frame + 900:
                raise AdmissionRefused('single_actor_lease_scope_invalid')
            actor = self.transport.resolve_actor(payload['actor']['object_id'], payload['actor']['generation'])
            if not isinstance(actor, RuntimeActor) or not isinstance(actor.identity, ActorIdentity) or actor.unit != 'conscript' or (actor.identity.session_id, actor.identity.player_id, actor.identity.object_id, actor.identity.generation) != (binding.session_id, binding.player_id, payload['actor']['object_id'], payload['actor']['generation']):
                raise AdmissionRefused('native_paid_actor_incarnation_unverified')
            integer(actor.born_frame, 1, snapshot.game_frame);identifier(actor.producer_command_id);text(actor.source_reference, 200)
        else:
            lease = self._leases.get(payload['lease_id'])
            if lease is None or (payload['task_id'], payload['generation']) != (lease['task_id'], lease['generation']):
                raise AdmissionRefused('tactical_lease_task_generation_changed')
            actor = lease['actor']
            fresh = self.transport.resolve_actor(actor.identity.object_id, actor.identity.generation)
            if fresh != actor:
                raise AdmissionRefused('native_actor_incarnation_changed')
            uncertain = [r for r in self.journal.unresolved(self.run_id)
                if r['status']=='uncertain' and all(r['payload'].get(k)==payload[k]
                    for k in ('task_id','lease_id','generation'))]
            if command['operation'] in ('reconcile_release','reconcile_return_home'):
                prior = next((r for r in uncertain if r['command_id']==payload['recovery_of_command_id']),None)
                allowed=('commit',) if command['operation']=='reconcile_return_home' else ('reserve','commit','return','stop','reconcile_return_home')
                if prior is None or prior['operation'] not in allowed:
                    raise AdmissionRefused('tactical_recovery_prior_unknown_required')
                current = self.transport.poll()
                expected = dict(command_id=prior['command_id'], task_id=payload['task_id'],
                    lease_id=payload['lease_id'], binding_hash=binding.binding_hash,
                    object_id=actor.identity.object_id,generation=actor.identity.generation,
                    seq=self.journal.get_native_sequence(self.run_id,prior['command_id']),
                    status='uncertain',phase='uncertain',held=True,control_released=False)
                if (not isinstance(current,Mapping) or any(current.get(k)!=v
                        or type(v) in (int,bool) and type(current.get(k)) is not type(v)
                        for k,v in expected.items()) or lease['state']=='released'):
                    raise AdmissionRefused('tactical_recovery_current_unknown_unverified')
                if command['operation']=='reconcile_return_home':
                    calls=current.get('sdk_calls')
                    if not isinstance(calls,list) or len(calls)!=6 or any(type(v)is not int or v<0 for v in calls) or calls[3]!=1:
                        raise AdmissionRefused('tactical_recovery_return_requires_unattempted_home')
            elif uncertain and command['operation'] != 'query_status':
                raise AdmissionRefused('tactical_unknown_requires_reconciliation')
            if command['operation'] == 'commit':
                if lease['state'] != 'ready':raise AdmissionRefused('native_actor_not_ready')
                point = self.transport.approved_target(payload['target_point_id'])
                if not isinstance(point, (tuple, list)) or len(point) != 3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in point):
                    raise AdmissionRefused('native_surface_endpoint_unverified')
        return snapshot, payload, actor

    def preflight(self, command, binding):
        try:self._admit(command, binding)
        except AdmissionRefused:raise
        except Exception:raise AdmissionRefused('tactical_native_preflight_refused') from None

    def dispatch(self, command, binding):
        snapshot, payload, actor = self._admit(command, binding)
        if command['command_id'] in self._sent:
            return self._receipt(command, 'uncertain', {'reason_code':'tactical_repeat_blocked'})
        sequence = self.journal.reserve_native_sequence(self.run_id, command['command_id'], snapshot.last_sequence)
        if command['operation'] == 'reserve':
            try:self.arbiter.claim(payload['lease_id'], payload['task_id'], (actor.identity,), issued_frame=snapshot.game_frame, deadline_frame=payload['deadline_frame'])
            except ArbitrationError:raise AdmissionRefused('tactical_actor_control_already_claimed') from None
            self._leases[payload['lease_id']] = dict(task_id=payload['task_id'],generation=payload['generation'],actor=actor,state='reserved',deadline_frame=payload['deadline_frame'])
            self.journal.append_event(self.run_id, 'tactical_lease_claimed', {'lease_id':payload['lease_id'],'object_id':actor.identity.object_id,'generation':actor.identity.generation}, command_id=command['command_id'],game_frame=snapshot.game_frame,monotonic_ns=snapshot.monotonic_ms*1000000)
        elif command['operation'] in ('commit', 'return', 'stop', 'reconcile_release','reconcile_return_home'):
            decision = self.arbiter.decide(payload['lease_id'],actor.identity,action='stop' if command['operation'] in ('return','stop','reconcile_release','reconcile_return_home') else 'task_command',game_frame=snapshot.game_frame,task_id=payload['task_id'],source_verified=True)
            if decision.outcome not in ('allow','stop'):
                raise AdmissionRefused('tactical_arbiter_refused')
        wire = dict(protocol=PROTOCOL,command_id=command['command_id'],task_id=payload['task_id'],lease_id=payload['lease_id'],seq=sequence,
                    operation=command['operation'],binding_hash=binding.binding_hash,host_id=binding.host_id,
                    actor=dict(object_id=actor.identity.object_id,generation=actor.identity.generation,born_frame=actor.born_frame),payload=payload)
        self._sent.add(command['command_id'])
        raw = self.transport.submit(wire)
        return self._normalize(command, actor, sequence, raw)

    def _receipt(self, command, status, facts):
        return NativeReceipt(command['command_id'],self.binding.binding_hash,status,
                 {**facts,'source':'injected_tactical_test_transport' if self.test_only else 'native_tactical_runtime_v1','field_evidence_eligible':not self.test_only})

    def _normalize(self, command, actor, sequence, raw):
        p=command['payload'];expected=dict(command_id=command['command_id'],task_id=p['task_id'],lease_id=p['lease_id'],seq=sequence,binding_hash=self.binding.binding_hash,object_id=actor.identity.object_id,generation=actor.identity.generation)
        if not isinstance(raw,Mapping) or any(raw.get(k)!=v or k in ('seq','object_id','generation') and type(raw.get(k)) is not int for k,v in expected.items()):
            return self._receipt(command,'uncertain',{'reason_code':'tactical_receipt_identity_changed'})
        if raw.get('status') not in ('accepted','started','completed','released','rejected','uncertain'):
            return self._receipt(command,'uncertain',{'reason_code':'tactical_receipt_status_unknown'})
        state=raw['status'];facts={k:raw.get(k) for k in (*expected,'phase','reason_code','game_frame','monotonic_ms','physical_home','control_released','stance_restored','held','source_reference','observation')}
        if command['operation'] in ('reconcile_release','reconcile_return_home'):
            facts['recovery_of_command_id']=p['recovery_of_command_id']
        integer(raw.get('game_frame'),0,0xffffffff);integer(raw.get('monotonic_ms'),0,2**63-1)
        if raw['game_frame']<self._last_frame or raw['monotonic_ms']<self._last_ms:
            return self._receipt(command,'uncertain',{'reason_code':'tactical_receipt_clock_regressed'})
        lease=self._leases[p['lease_id']]
        if state=='completed' and command['operation']=='reserve':
            if raw.get('phase')!='ready' or raw.get('held') is not True:
                return self._receipt(command,'uncertain',{'reason_code':'tactical_ready_not_observed'})
            lease['state']='ready'
        elif state=='completed' and command['operation'] not in ('query_status',):
            return self._receipt(command,'uncertain',{'reason_code':'tactical_task_finished_without_native_release'})
        if state=='released':
            if command['operation']=='reconcile_return_home' and (raw.get('physical_home')is not True or raw.get('reason_code')!='native_control_release_without_goal_effect'):
                return self._receipt(command,'uncertain',{'reason_code':'tactical_recovery_physical_home_unverified'})
            observation=raw.get('observation')
            if raw.get('control_released') is not True or raw.get('held') is not False or type(raw.get('physical_home')) is not bool or not isinstance(raw.get('source_reference'),str) or not raw['source_reference'] or not isinstance(observation,Mapping) or type(observation.get('team')) is not int or observation.get('team',0)<=0:
                return self._receipt(command,'uncertain',{'reason_code':'tactical_control_release_unverified'})
            if raw.get('reason_code')=='borrow_not_sent_no_control_transfer':
                calls=raw.get('sdk_calls')
                if (command['operation']!='reserve' or raw.get('phase')!='released' or raw.get('physical_home') is not False
                        or not isinstance(calls,list) or len(calls)!=6 or any(type(v) is not int or v!=0 for v in calls)
                        or type(observation.get('script_team')) is not int or observation.get('script_team',0)<=0
                        or observation['team']==observation['script_team']
                        or any(observation.get(k) is not True for k in ('identity','birth_verified','live','grounded'))):
                    return self._receipt(command,'uncertain',{'reason_code':'tactical_untransferred_claim_unverified'})
                facts.update(no_control_acquired=True,sdk_calls=calls)
            elif raw.get('stance_restored') is not True or observation['team']!=observation.get('default_team') or observation.get('stance')!=0:
                return self._receipt(command,'uncertain',{'reason_code':'tactical_control_release_unverified'})
            self.arbiter.confirm_release(p['lease_id'],(actor.identity,),game_frame=raw['game_frame'],source_reference=raw['source_reference'],independently_verified=True)
            lease['state']='released'
        facts['mission_effect_verified']=(state=='released' and raw.get('physical_home') is True
            and command['operation'] not in ('reconcile_release','reconcile_return_home') and raw.get('stance_restored') is True
            and raw.get('reason_code')=='native_control_release_observed')
        return self._receipt(command,state,facts)

    def observe(self, request_id, raw):
        """Trusted late receipt only; uncertainty still needs separate recovery."""
        record=self.journal.get_command(self.run_id,request_id)
        if record['status']=='uncertain':raise ContractError('tactical_unknown_requires_reconciliation')
        command=dict(command_id=record['command_id'],operation=record['operation'],payload=record['payload'])
        actor=self._leases[record['payload']['lease_id']]['actor']
        sequence=self.journal.get_native_sequence(self.run_id,record['command_id'])
        receipt=self._normalize(command,actor,sequence,raw)
        if receipt.status==record['status']:return record
        return self.journal.record_outcome(self.run_id,request_id,receipt.status,{'reason_code':'native_tactical_receipt_verified','facts':dict(receipt.facts)})
