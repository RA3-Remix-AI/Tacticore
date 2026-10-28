"""Original local native transport; addresses come only from a paid producer.

This module grants no field capability. The separately authorized diagnostic
entry point may collect first evidence; normal Host execution still needs its
independent capability verifier. A test transport is never accepted here.
"""
from __future__ import annotations
import ctypes as c
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'integration'))
from host_runtime.arbitration import ActorIdentity
from host_runtime.contracts import SessionBinding
from host_runtime.capabilities import CapabilityCatalog
from host_runtime.tactical_adapter import RuntimeSnapshot, RuntimeActor

spec = importlib.util.spec_from_file_location('tacticore_native_runtime_layout', HERE / 'layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)

PHASES = ('idle', 'borrowing', 'stance', 'braking', 'ready', 'moving', 'target_braking', 'holding',
          'returning', 'home_braking', 'restoring', 'releasing', 'released', 'uncertain', 'return_braking')
OPERATIONS = {'reserve': 1, 'commit': 2, 'return': 3, 'stop': 4, 'query_status': 5, 'reconcile_release': 6, 'reconcile_return_home': 7, 'diagnostic_foreign_move':8}


def _replace_saved_report(temporary, output):
    # Windows readers may briefly deny replacement. Retry only publication of
    # these already-fsynced bytes: never resample, republish or resend a command.
    for attempt in range(25):
        try:
            os.replace(temporary, output)
            return
        except PermissionError:
            if attempt == 24:
                raise
            time.sleep(.02)


def verify_build():
    manifest = json.loads((HERE / 'bin/build-manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('protocol') != 'tactical_runtime_v1' or manifest.get('architecture') != 'x86' or manifest.get('layout') != layout.inventory():
        raise ValueError('runtime_build_layout_unverified')
    for row in manifest['inputs']:
        file = HERE / row['file']
        if file.parent != HERE or hashlib.sha256(file.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('runtime_source_changed_since_build')
    expected = {}
    for row in manifest['outputs']:
        file = HERE / 'bin' / row['file']
        if row['file'] not in ('TacticoreRuntime1.dll', 'runtime_host.exe', 'atomic_publish.dll') or hashlib.sha256(file.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('runtime_binary_changed_since_build')
        expected[row['file']] = row['sha256']
    if set(expected) != {'TacticoreRuntime1.dll', 'runtime_host.exe', 'atomic_publish.dll'}:
        raise ValueError('runtime_binary_manifest_incomplete')
    actual = json.loads(subprocess.check_output([str(HERE / 'bin/runtime_host.exe'), '--layout'], text=True, timeout=5))
    if actual != layout.inventory():
        raise ValueError('runtime_actual_abi_mismatch')
    return manifest, expected


def _copy(value):
    return type(value).from_buffer_copy(bytes(value))


def _sample_public(sample):
    return dict(frame=sample.frame, monotonic_ms=sample.monotonic_ms, object_id=sample.actor.object_id,
                generation=sample.actor.generation, xyz=[sample.xyz.x, sample.xyz.y, sample.xyz.z],
                team=sample.team, default_team=sample.default_team, script_team=sample.script_team,
                stance=sample.stance, state_id=sample.state_id, path=sample.path,
                state_vtable=sample.state_vtable, state_flags=sample.state_flags, command_source=sample.command_source,
                foreign_epoch=sample.foreign_epoch, identity=bool(sample.identity),
                birth_verified=bool(sample.actor_birth_verified), live=bool(sample.live_list_member),
                grounded=bool(sample.grounded), paused=bool(sample.paused), settled=bool(sample.settled),
                normal_move_owned=bool(sample.normal_move_owned))


class NativeRuntimeClient:
    test_only = False

    def __init__(self, session_path, binding, producer, producer_command_id, output, *, diagnostic=False, yield_abort_experiment=False, handoff=None,reconcile_return_experiment=False,controlled_fault_experiment=False):
        if type(yield_abort_experiment) is not bool or (yield_abort_experiment and diagnostic is not True):
            raise ValueError('native_yield_experiment_requires_explicit_owned_diagnostic')
        self.yield_abort_experiment = yield_abort_experiment
        if type(reconcile_return_experiment) is not bool or (reconcile_return_experiment and diagnostic is not True):
            raise ValueError('recovery_return_requires_explicit_owned_diagnostic')
        self.reconcile_return_experiment=reconcile_return_experiment
        if type(controlled_fault_experiment) is not bool or (controlled_fault_experiment and (diagnostic is not True or reconcile_return_experiment is not True or yield_abort_experiment)):
            raise ValueError('controlled_fault_requires_separate_owned_recovery_experiment')
        self.controlled_fault_experiment=controlled_fault_experiment
        if os.name != 'nt' or not isinstance(binding, SessionBinding):
            raise ValueError('runtime_windows_binding_required')
        owner = sys.modules.get(type(producer).__module__)
        if type(producer).__name__ != 'ProductionExecutor' or owner is None or Path(owner.__file__).resolve() != ROOT / 'production/persistent/client.py':
            raise ValueError('runtime_original_paid_producer_required')
        self.session_path = Path(session_path).resolve()
        self.session_bytes = self.session_path.read_bytes()
        self.session = json.loads(self.session_bytes.decode('utf-8-sig'))
        if (binding.session_id != self.session['session_id'] or binding.game_process_id != self.session['pid']
                or binding.game_process_start != self.session['start_time'] or binding.game_sha256 != hashlib.sha256(Path(self.session['game']).read_bytes()).hexdigest()
                or binding.mod_sha256 != self.session['mod_sha256'] or binding.commander_id != producer.commander_id or binding.player_id != 3):
            raise ValueError('runtime_session_binding_changed')
        self.output = Path(output).resolve()
        if self.output.parent != Path(self.session['run_directory']).resolve() or self.output.exists():
            raise ValueError('runtime_output_must_be_new_owned_run_file')
        self.manifest, hashes = verify_build()
        self.executor_sha256, self.native_host_sha256 = hashes['TacticoreRuntime1.dll'], hashes['runtime_host.exe']
        self.binding, self.producer, self.producer_command_id = binding, producer, producer_command_id
        self.diagnostic = diagnostic is True
        self.handoff=handoff
        if handoff is not None:
            from host_runtime.runtime_rotation import validate_handoff
            if self.diagnostic or yield_abort_experiment:
                raise ValueError('runtime_rotation_requires_ordinary_reviewed_scope')
            validate_handoff(handoff,binding,producer_command_id)
        self.mapping = self.view = self.shared = self.host = None
        self.event_cursor = self.trace_cursor = self.command_generation = 0
        self.event_rows, self.command_rows, self.trace_rows = [], [], []
        self._targets = {}
        self._actor = None
        self._log = None
        self._stopped = False
        self.started_ms = int(time.monotonic() * 1000)
        self.k = c.WinDLL('kernel32', use_last_error=True)
        self.k.CreateFileMappingW.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_wchar_p]
        self.k.CreateFileMappingW.restype = c.c_void_p
        self.k.MapViewOfFile.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_size_t]
        self.k.MapViewOfFile.restype = c.c_void_p
        self.k.UnmapViewOfFile.argtypes = [c.c_void_p]
        self.k.CloseHandle.argtypes = [c.c_void_p]
        self.atomic = c.WinDLL(str(HERE / 'bin/atomic_publish.dll'))
        self.atomic.runtime_exchange.argtypes = [c.POINTER(c.c_int32), c.c_int32]
        self.atomic.runtime_exchange.restype = c.c_int32

    def _exchange(self, name, value):
        # A pinned host-only DLL compiles the actual Windows intrinsic;
        # kernel32 does not export it for the x64 Python host.
        if name not in ('command_generation', 'stop_requested'):
            raise ValueError('runtime_unreviewed_channel_publication')
        offset = getattr(layout.SharedChannel, name).offset
        if (self.view + offset) % 4 or type(value) is not int or not 0 <= value <= 0x7fffffff:
            raise ValueError('runtime_channel_publication_not_aligned_word')
        return self.atomic.runtime_exchange(c.cast(self.view + offset, c.POINTER(c.c_int32)), value)

    def _check(self):
        if self.session_path.read_bytes() != self.session_bytes:
            raise ValueError('runtime_session_file_changed')
        if self.shared is None or bytes(self.shared.bootstrap) != self.bootstrap_bytes:
            raise ValueError('runtime_private_bootstrap_changed')
        if (self.shared.magic_word, self.shared.protocol, self.shared.structure_size, self.shared.token) != (layout.MAGIC, layout.VERSION, c.sizeof(layout.SharedChannel), self.token):
            raise ValueError('runtime_channel_identity_changed')

    def _stable(self, field, generation):
        for _ in range(8):
            first = getattr(self.shared, generation)
            if first <= 0 or first & 1:
                time.sleep(.001)
                continue
            value = _copy(getattr(self.shared, field))
            second = _copy(getattr(self.shared, field))
            if first == getattr(self.shared, generation) and bytes(value) == bytes(second):
                return value
        raise ValueError('runtime_native_snapshot_incomplete')

    def _field_admission(self, capabilities):
        if not isinstance(capabilities, CapabilityCatalog) or capabilities.binding != self.binding:
            raise ValueError('runtime_field_capability_required')
        grant = capabilities.require('tactics.move_hold_return', self.binding)
        scope = grant.public()['execution_constraints']
        if (scope.get('runtime_family') != 'tactical' or scope.get('executor_directory') != 'tactical/runtime'
                or scope.get('purpose') != 'move_hold_return' or scope.get('actor_roles') != ['infantry']
                or scope.get('mission_protocol') != 'tactical_runtime_v1' or scope.get('execution_ready') is not True
                or grant.executor_sha256 != self.executor_sha256 or scope.get('native_host_sha256') != self.native_host_sha256):
            raise ValueError('runtime_field_scope_unverified')
        # Qualification is independently recomputed by build_catalog before this
        # host-only call. Native source/binary checks still run on every attach.
        self.field_evidence_id = grant.evidence_id
        self._field_capabilities=capabilities

    def _first_home_admission(self):
        catalog=getattr(self,'_field_capabilities',None)
        if not isinstance(catalog,CapabilityCatalog) or catalog.binding!=self.binding:
            raise ValueError('recovery_return_requires_explicit_owned_diagnostic_or_verified_scope')
        grant=catalog.require('tactics.reconcile_return_home',self.binding)
        scope=grant.public()['execution_constraints']
        if (scope.get('runtime_family')!='tactical' or scope.get('executor_directory')!='tactical/runtime'
                or scope.get('purpose')!='reconcile_return_home' or scope.get('module')!='runtime_first_home_recovery_v1'
                or scope.get('actor_roles')!=['infantry'] or scope.get('mission_protocol')!='tactical_runtime_v1'
                or scope.get('execution_ready')is not True or grant.executor_sha256!=self.executor_sha256
                or scope.get('native_host_sha256')!=self.native_host_sha256):
            raise ValueError('runtime_first_home_scope_unverified')
        self.first_home_field_evidence_id=grant.evidence_id

    def attach(self, *, startup_timeout=8, capabilities=None):
        if self.handoff is None:
            return self._attach(startup_timeout=startup_timeout,capabilities=capabilities)
        from host_runtime.runtime_rotation import claim_handoff,finish_handoff
        self._field_admission(capabilities)
        request,record=claim_handoff(self.handoff,self.binding,self.producer_command_id)
        try:
            actor=self._attach(startup_timeout=startup_timeout,capabilities=capabilities)
            finish_handoff(self.handoff,request,self,actor)
            return actor
        except BaseException:
            journal=self.handoff.journal
            if journal.get_command(self.handoff.run_id,request)['status']=='dispatching':
                journal.record_outcome(self.handoff.run_id,request,'uncertain',
                    dict(reason_code='runtime_successor_attach_unknown_no_retry'))
            raise

    def _attach(self, *, startup_timeout=8, capabilities=None):
        if self.shared is not None:
            raise ValueError('runtime_already_attached')
        if not self.diagnostic:
            self._field_admission(capabilities)
        self.producer._verify_binding()
        shared = self.producer.shared
        if shared is None or shared.phase != 1 or shared.stop_requested or shared.error:
            raise ValueError('runtime_live_producer_required')
        selected = []
        for i in range(shared.count):
            item = _copy(shared.ledger[i])
            if layout.uuid_text(item.command.id) == self.producer_command_id:
                selected.append((i, item))
        if len(selected) != 1:
            raise ValueError('runtime_unique_paid_receipt_required')
        index, receipt = selected[0]
        if receipt.updates or not receipt.version or receipt.state != 2 or receipt.error or not receipt.completed or not receipt.created or receipt.paid != 85 or receipt.cost != 85 or receipt.object_hash != 0x19ab11af:
            raise ValueError('runtime_original_paid_conscript_required')
        boot = layout.Bootstrap()
        for name, value in [('session', self.binding.session_id), ('commander', self.binding.commander_id), ('host', self.binding.host_id)]:
            getattr(boot.binding, name)[:] = layout.uuid_words(value)
        boot.binding.binding_hash[:] = layout.digest_words(self.binding.binding_hash)
        boot.binding.player, boot.binding.pid, boot.binding.thread = 3, shared.pid, shared.thread
        boot.binding.process_start = (shared.start_high << 32) | shared.start_low
        memory = self.producer.memory
        boot.native.logic = memory.u32(0xcd8ce4)
        for name in ('owner', 'ai', 'personality', 'personality_id', 'player_template'):
            setattr(boot.native, name, getattr(shared, name))
        boot.native.default_team = memory.u32(shared.owner + 0xac)
        boot.native.script_team = memory.u32(memory.u32(shared.owner + 0x8c) + 0x10)
        boot.actor.object_id, boot.actor.thing, boot.actor.owner, boot.actor.type_hash = receipt.object_id, receipt.object, receipt.object_owner, receipt.object_hash
        boot.actor.template_ptr, boot.actor.update = memory.u32(receipt.object + 4), memory.u32(receipt.object + 0x374)
        boot.producer.command[:], boot.producer.task[:] = receipt.command.id[:], receipt.command.task[:]
        boot.producer.sequence, boot.producer.receipt_index = receipt.command.seq, index
        boot.persisted_sequence = self.handoff.persisted_sequence if self.handoff is not None else 0
        boot.experimental_flags = 2 if self.controlled_fault_experiment else int(self.yield_abort_experiment)
        self.producer_receipt = dict(command_id=self.producer_command_id, task_id=layout.uuid_text(receipt.command.task), sequence=receipt.command.seq,
                                     receipt_index=index, object_id=receipt.object_id, completion_frame=receipt.completion_frame, paid=receipt.paid,
                                     raw_hex=bytes(receipt).hex(), native_header_hex=c.string_at(c.addressof(shared), type(shared).ledger.offset).hex())
        self.token = secrets.randbelow(0x7ffffffe) + 1
        if self.handoff is not None:
            from host_runtime.runtime_rotation import validate_handoff
            old=validate_handoff(self.handoff,self.binding,self.producer_command_id)['facts']['previous_token']
            if self.token==old:
                raise ValueError('runtime_successor_nonce_collision_no_retry')
        name = f'Local\\TacticoreRuntime1_{self.binding.game_process_id}_{self.token}'
        self.mapping = self.k.CreateFileMappingW(c.c_void_p(-1), None, 4, 0, c.sizeof(layout.SharedChannel), name)
        if not self.mapping or c.get_last_error() == 183:
            raise ValueError('runtime_mapping_collision_or_failure')
        self.view = self.k.MapViewOfFile(self.mapping, 0xf001f, 0, 0, c.sizeof(layout.SharedChannel))
        if not self.view:
            self.k.CloseHandle(self.mapping)
            self.mapping = None
            raise ValueError('runtime_mapping_view_failed')
        c.memset(self.view, 0, c.sizeof(layout.SharedChannel))
        self.shared = layout.SharedChannel.from_address(self.view)
        self.shared.magic_word, self.shared.protocol, self.shared.structure_size, self.shared.token = layout.MAGIC, 1, c.sizeof(layout.SharedChannel), self.token
        self.shared.bootstrap = boot
        self.bootstrap_bytes = bytes(boot)
        self._log = self.output.with_suffix('.host.log').open('x', encoding='utf-8')
        self.host = subprocess.Popen([str(HERE / 'bin/runtime_host.exe'), str(self.binding.game_process_id), str(self.token)],
                                     stdout=self._log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + startup_timeout
        while time.monotonic() < deadline:
            self._check()
            if self.shared.state in (3, 4, 5) or self.host.poll() is not None:
                self.save()
                raise ValueError('runtime_native_attach_refused_or_unknown')
            if self.shared.state == 2 and self.shared.observation_generation > 0 and self.shared.admitted_actor.generation:
                actor = _copy(self.shared.admitted_actor)
                self._actor = RuntimeActor(ActorIdentity(self.binding.session_id, 3, actor.object_id, actor.generation), actor.born_frame,
                                           self.producer_command_id, self.output.name + '#native_paid_birth')
                self.actor_bytes = bytes(actor)
                self.poll()
                return self._actor
            time.sleep(.02)
        self.save()
        raise ValueError('runtime_native_attach_timeout_unknown')

    def _raw_receipt(self, receipt, sample=None):
        phase = PHASES[receipt.phase] if receipt.phase < len(PHASES) else 'unknown'
        status = ('rejected' if not receipt.accepted else 'uncertain' if phase == 'uncertain'
                  else 'released' if phase == 'released' else 'completed' if phase == 'ready' else 'started')
        if sample is None:
            sample = self._stable('current_observation', 'observation_generation')
        return dict(command_id=layout.uuid_text(receipt.command), task_id=layout.uuid_text(receipt.task), lease_id=layout.uuid_text(receipt.lease),
                    seq=receipt.sequence, binding_hash=self.binding.binding_hash,
                    object_id=self.shared.admitted_actor.object_id, generation=self.shared.admitted_actor.generation,
                    status=status, phase=phase, reason_code=bytes(receipt.reason).split(b'\0')[0].decode('ascii', errors='replace'),
                    game_frame=receipt.frame, monotonic_ms=receipt.monotonic_ms,
                    physical_home=bool(receipt.physical_home), control_released=bool(receipt.control_released),
                    stance_restored=bool(receipt.stance_restored), held=bool(receipt.held), sdk_calls=list(receipt.sdk_calls),
                    source_reference=self.output.name + '#native_receipts', observation=_sample_public(sample))

    def poll(self):
        self._check()
        written = self.shared.events_written
        if written < self.event_cursor or written < 0:
            raise ValueError('runtime_event_clock_regressed')
        first = max(self.event_cursor + 1, written - layout.CAPACITY + 1)
        for ticket in range(first, written + 1):
            slot = self.shared.events[(ticket - 1) % layout.CAPACITY]
            row = _copy(slot)
            if row.ticket != ticket or slot.ticket != ticket:
                raise ValueError('runtime_event_torn_or_overwritten')
            self.event_rows.append(dict(ticket=ticket, event_type=bytes(row.event_type).split(b'\0')[0].decode('ascii', errors='replace'),
                                        raw_hex=bytes(row).hex(), receipt=self._raw_receipt(row.receipt, row.observation), observation=_sample_public(row.observation)))
        self.event_cursor = written
        traced = self.shared.traces_written
        if traced < self.trace_cursor or traced < 0 or self.shared.traces_overwritten:
            raise ValueError('runtime_hook_trace_lost_or_regressed')
        for ticket in range(self.trace_cursor + 1, traced + 1):
            for _ in range(8):
                slot = self.shared.traces[(ticket - 1) % layout.TRACE_CAPACITY]
                row = _copy(slot)
                if row.ticket == ticket and slot.ticket == ticket and bytes(row) == bytes(slot):
                    break
                time.sleep(.001)
            else:
                raise ValueError('runtime_hook_trace_snapshot_incomplete')
            self.trace_rows.append(dict(ticket=ticket, raw_hex=bytes(row).hex()))
        self.trace_cursor = traced
        receipt = self._stable('receipt', 'receipt_generation')
        terminal_sample = None
        if receipt.accepted and receipt.phase == 12:
            # The effect's own game-thread observation is authoritative. A
            # later ambient sample may already show ordinary AI recruitment.
            for row in reversed(self.event_rows):
                event = layout.WireEvent.from_buffer_copy(bytes.fromhex(row['raw_hex']))
                if bytes(event.receipt) == bytes(receipt):
                    terminal_sample = event.observation
                    break
        self.current = self._raw_receipt(receipt, terminal_sample)
        if receipt.accepted and receipt.phase == 12 and terminal_sample is None:
            self.current.update(status='started', reason_code='terminal_event_observation_pending')
        self.save()
        return self.current

    def admit(self, binding):
        if binding != self.binding:
            raise ValueError('runtime_binding_changed')
        self._check()
        sample = self._stable('current_observation', 'observation_generation')
        return RuntimeSnapshot(self.binding.binding_hash, sample.frame, sample.monotonic_ms, bool(sample.paused),
                               self.shared.native_last_sequence, self.executor_sha256, self.native_host_sha256,
                               self.output.name + '#native_current_observation')

    def resolve_actor(self, object_id, generation):
        self._check()
        if self._actor is None or (self._actor.identity.object_id, self._actor.identity.generation) != (object_id, generation):
            raise ValueError('runtime_actor_not_registered')
        if bytes(self.shared.admitted_actor) != self.actor_bytes:
            raise ValueError('runtime_actor_incarnation_changed')
        return self._actor

    def observe_actor(self, binding):
        """Fresh actor state for planning, separate from an effect receipt."""
        sample=self._actor_observation(binding)
        if (not sample.identity or not sample.actor_birth_verified or not sample.live_list_member
                or not sample.grounded or sample.paused):
            raise ValueError('runtime_actor_observation_not_admissible')
        return _sample_public(sample)

    def _actor_observation(self,binding):
        if binding != self.binding:
            raise ValueError('runtime_binding_changed')
        self._check()
        sample = self._stable('current_observation', 'observation_generation')
        if (bytes(sample.binding) != bytes(self.shared.bootstrap.binding)
                or bytes(sample.actor) != self.actor_bytes
                or sample.current_thread != self.shared.bootstrap.binding.thread):
            raise ValueError('runtime_actor_observation_binding_changed')
        return sample

    def observe_planning_actor(self,binding):
        """Read-only availability, including ground/liveness refusal facts.

        This does not admit Reserve, Ready, Commit or recovery. A paid actor can
        enter an ordinary native garrison while no actor lease exists; report
        unavailable instead of treating the planner's refusal as a Host fault.
        Identity of the channel, incarnation bytes and thread stays mandatory.
        """
        sample=self._actor_observation(binding)
        return _sample_public(sample)

    def targets(self):
        self._check()
        for _ in range(8):
            generation = self.shared.targets_generation
            if generation <= 0 or generation & 1:
                continue
            count = self.shared.targets_count
            if count > 64:
                raise ValueError('runtime_native_target_count_invalid')
            points = [tuple(float(getattr(self.shared.approved_targets[i], axis)) for axis in ('x', 'y', 'z')) for i in range(count)]
            if generation == self.shared.targets_generation:
                self._targets = {str(uuid.uuid5(uuid.NAMESPACE_OID, 'tacticore_runtime_v1:ground:' + json.dumps(point, separators=(',', ':'), allow_nan=False))): point for point in points}
                return dict(self._targets)
        raise ValueError('runtime_target_snapshot_incomplete')

    def planning_actor(self):
        """Trusted own-identity copy for independent home planning, never model data."""
        self._check()
        if self._actor is None or bytes(self.shared.admitted_actor)!=self.actor_bytes:
            raise ValueError('runtime_actor_incarnation_changed')
        return layout.Actor.from_buffer_copy(self.actor_bytes)

    def approved_target(self, point_id):
        self.targets()
        if point_id not in self._targets:
            raise ValueError('runtime_target_not_native_approved')
        return self._targets[point_id]

    def reserved_home(self, task_id, lease_id):
        """Return the Reserve event's actual private home, never ambient xyz."""
        self._check()
        task, lease = layout.uuid_words(task_id), layout.uuid_words(lease_id)
        selected = []
        for row in self.event_rows:
            event = layout.WireEvent.from_buffer_copy(bytes.fromhex(row['raw_hex']))
            if (tuple(event.receipt.task) != task or tuple(event.receipt.lease) != lease
                    or event.receipt.phase != 1 or not event.receipt.accepted
                    or bytes(event.event_type).split(b'\0')[0] != b'phase'):
                continue
            sample = event.observation
            if (event.ticket != row['ticket'] or bytes(sample.actor) != self.actor_bytes
                    or bytes(sample.binding) != bytes(self.shared.bootstrap.binding)
                    or not sample.identity or not sample.actor_birth_verified or not sample.live_list_member
                    or not sample.grounded or sample.paused or sample.frame != event.receipt.frame):
                raise ValueError('runtime_reserve_home_event_unverified')
            selected.append(dict(xyz=[float(getattr(sample.xyz, axis)) for axis in ('x', 'y', 'z')],
                                 frame=sample.frame, event_ticket=event.ticket,
                                 source_reference=self.output.name + '#reserve_event_' + str(event.ticket)))
        if len(selected) != 1:
            raise ValueError('runtime_reserve_home_event_missing_or_ambiguous')
        return selected[0]

    def submit(self, wire, *, acknowledgement_seconds=3):
        if wire.get('operation')=='diagnostic_foreign_move' and (getattr(self,'diagnostic',False) is not True or getattr(self,'controlled_fault_experiment',False) is not True or getattr(self,'reconcile_return_experiment',False) is not True):
            raise ValueError('controlled_fault_requires_separate_owned_recovery_experiment')
        if wire.get('operation')=='reconcile_return_home' and (getattr(self,'_field_capabilities',None)is not None or getattr(self,'diagnostic',False) is not True or getattr(self,'reconcile_return_experiment',False) is not True):
            self._first_home_admission()
        self._check()
        if wire.get('binding_hash') != self.binding.binding_hash or wire.get('host_id') != self.binding.host_id or wire.get('protocol') != 'tactical_runtime_v1':
            raise ValueError('runtime_wire_binding_invalid')
        if self.shared.command_generation != self.shared.command_acknowledged:
            raise ValueError('runtime_previous_command_unacknowledged')
        actor = self.resolve_actor(wire['actor']['object_id'], wire['actor']['generation'])
        if wire['actor']['born_frame'] != actor.born_frame:
            raise ValueError('runtime_actor_birth_changed')
        operation = wire['operation']
        if operation not in OPERATIONS:
            raise ValueError('runtime_operation_unreviewed')
        sequence = wire['seq']
        if type(sequence) is not int or not 1 <= sequence <= 0xffffffff or sequence <= self.shared.native_last_sequence:
            raise ValueError('runtime_sequence_invalid')
        command = layout.Command()
        for name, value in [('command', wire['command_id']), ('task', wire['task_id']), ('lease', wire['lease_id'])]:
            getattr(command, name)[:] = layout.uuid_words(value)
        command.sequence, command.operation = sequence, OPERATIONS[operation]
        command.actor = _copy(self.shared.admitted_actor)
        payload = wire['payload']
        command.expires_frame, command.expires_monotonic_ms = payload['expires_frame'], payload['expires_monotonic_ms']
        command.lease_deadline_frame = payload.get('deadline_frame', getattr(self, 'lease_deadline_frame', 0))
        command.hold_frames = payload.get('hold_frames', 0)
        if operation == 'reserve':
            self.lease_deadline_frame = command.lease_deadline_frame
        if operation in ('commit','diagnostic_foreign_move'):
            command.target = layout.Point(*self.approved_target(payload['target_point_id']))
        self.command_generation += 2
        if self.command_generation > 0x7ffffffe:
            raise ValueError('runtime_command_generation_exhausted')
        self._exchange('command_generation', self.command_generation - 1)
        self.shared.command = command
        self._exchange('command_generation', self.command_generation)
        self.command_rows.append(dict(wire=wire, wire_hex=bytes(command).hex(), published_generation=self.command_generation))
        self.save()
        deadline = time.monotonic() + acknowledgement_seconds
        while time.monotonic() < deadline:
            self._check()
            self.poll()
            if self.shared.command_acknowledged == self.command_generation:
                native_ack = self._stable('command_receipt', 'command_receipt_generation')
                raw = self._raw_receipt(native_ack)
                self.command_rows[-1]['acknowledged'] = raw
                self.command_rows[-1]['acknowledged_hex'] = bytes(native_ack).hex()
                self.command_rows[-1]['acknowledgement_generation'] = int(self.shared.command_receipt_generation)
                self.save()
                return raw
            if self.host.poll() is not None:
                break
            time.sleep(.02)
        raise TimeoutError('runtime_delivery_unknown_no_retry')

    def save(self):
        if self.shared is None:
            return
        before = c.string_at(self.view, layout.SharedChannel.events.offset)
        after = c.string_at(self.view, layout.SharedChannel.events.offset)
        record = dict(schema_version=1, protocol='tactical_runtime_v1_diagnostic', diagnostic=self.diagnostic,
                      reconcile_return_home_experiment=getattr(self,'reconcile_return_experiment',False),
                      controlled_native_move_experiment=getattr(self,'controlled_fault_experiment',False),
                      first_home_field_evidence_id=getattr(self,'first_home_field_evidence_id',None),
                      binding=self.binding.public(), bootstrap_hex=self.bootstrap_bytes.hex(),
                      header_before_hex=before.hex(), header_after_hex=after.hex(),
                      terminal_headers=[before.hex(), after.hex()] if self._stopped else [],
                      admitted_actor_hex=bytes(self.shared.admitted_actor).hex(),
                      native_layout=layout.inventory(), terminal_entries=getattr(self, 'terminal_entries', None),
                      producer_receipt=getattr(self, 'producer_receipt', None), build_manifest=self.manifest,
                      executor_sha256=self.executor_sha256, native_host_sha256=self.native_host_sha256,
                      state=int(self.shared.state), reason=bytes(self.shared.reason).split(b'\0')[0].decode('ascii', errors='replace'),
                      hooks_restored=int(self.shared.hooks_restored), active_callbacks=int(self.shared.active_callbacks),
                      events_written=int(self.shared.events_written), events_overwritten=int(self.shared.events_overwritten),
                      traces_written=int(self.shared.traces_written), traces_overwritten=int(self.shared.traces_overwritten),
                      trace_counters_before_hex=c.string_at(self.view + layout.SharedChannel.traces_written.offset, 8).hex(),
                      trace_counters_after_hex=c.string_at(self.view + layout.SharedChannel.traces_written.offset, 8).hex(),
                      hook_traces=self.trace_rows,
                      commands=self.command_rows, events=self.event_rows, last_receipt=getattr(self, 'current', None),
                      ordinary_execution_granted=False, field_verified=False, host_exit=self.host.poll() if self.host else None)
        record['field_scope_admitted'] = hasattr(self, 'field_evidence_id')
        record['field_evidence_id'] = getattr(self, 'field_evidence_id', None)
        if self.handoff is not None:
            record['native_channel_handoff']=dict(manifest=str(self.handoff.manifest_path),
                manifest_sha256=self.handoff.manifest_sha256,persisted_sequence=self.handoff.persisted_sequence,
                new_binding_epoch=True)
        temporary = self.output.with_suffix('.pending')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(record, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        _replace_saved_report(temporary, self.output)

    def stop(self, *, timeout=12):
        if self.shared is None:
            return None
        self._check()
        self._exchange('stop_requested', 1)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self.poll()
            except ValueError:
                self.save()
            if self.shared.state in (3, 4) and self.shared.hooks_restored and not self.shared.active_callbacks and not self.shared.receipt.held:
                if self.host:
                    self.host.wait(timeout=max(.1, deadline - time.monotonic()))
                self._stopped = True
                self.terminal_entries = self._entry_proof()
                self.save()
                return getattr(self, 'current', None)
            time.sleep(.05)
        self.save()
        raise TimeoutError('runtime_control_release_unknown')

    def _entry_proof(self):
        """Independent process reads after target-side hook restoration."""
        source = (HERE / 'hooks.cpp').read_text(encoding='utf-8')
        found = re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2}|\\0)+)",(\d+),', source)
        if len(found) != 13:
            raise ValueError('runtime_hook_signature_inventory_changed')
        rows = []
        for address, signature, count in found:
            expected = signature.encode('ascii').decode('unicode_escape').encode('latin1')
            if len(expected) != int(count):
                raise ValueError('runtime_hook_signature_size_changed')
            actual = self.producer.memory.read(int(address, 16), int(count))
            rows.append(dict(address=address, expected=expected.hex(), actual=actual.hex()))
        return rows

    def close(self):
        if self.shared is not None and not self._stopped:
            self.stop()
        if self.view:
            self.shared = None
            self.k.UnmapViewOfFile(self.view)
            self.view = None
        if self.mapping:
            self.k.CloseHandle(self.mapping)
            self.mapping = None
        if self._log:
            self._log.close()
