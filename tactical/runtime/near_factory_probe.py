"""Owned paid-birth factory qualification only. Never publishes a game command.

The game DLL can host controlled work, but this diagnostic client exposes only
attach/observe/stop. An incomplete shot/range qualification grants no attack.
"""
import ctypes as c
import hashlib,json,os,re,secrets,subprocess,time,sys
from pathlib import Path
from tactical.runtime import client as legacy
from tactical.runtime import near_layout as n
layout=legacy.layout
_copy=legacy._copy
RuntimeActor=legacy.RuntimeActor
ActorIdentity=legacy.ActorIdentity
ROOT=legacy.ROOT
HERE=legacy.HERE

def verify_build(build,expected):
    build=Path(build).resolve()
    if not build.is_relative_to(ROOT/'reports')or hashlib.sha256((build/'manifest.json').read_bytes()).hexdigest()!=expected:
        raise ValueError('near_probe_build_pin_required')
    m=json.loads((build/'manifest.json').read_text(encoding='utf-8-sig'))
    if m.get('kind')!='isolated_near_native_channel2'or m.get('layout')!=n.inventory():
        raise ValueError('near_probe_layout_unverified')
    for row in m['sources']:
        path=(build/'source'/row['file']).resolve()
        if not path.is_relative_to(build/'source')or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('near_probe_frozen_source_changed')
    outputs={}
    for row in m['outputs']:
        path=build/row['file']
        if path.parent!=build or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('near_probe_binary_changed')
        outputs[row['file']]=row['sha256']
    if not {'TacticoreNear2.dll','near_runtime_host.exe'}<=outputs.keys():raise ValueError('near_probe_outputs_missing')
    actual=json.loads(subprocess.check_output([str(build/'near_runtime_host.exe'),'--layout'],text=True,timeout=5))
    if actual!=n.inventory():raise ValueError('near_probe_actual_layout_changed')
    return m,outputs

class NearFactoryProbe(legacy.NativeRuntimeClient):
    def __init__(self,session_path,binding,producer,producer_command_id,output,*,build,build_sha256):
        session=json.loads(Path(session_path).read_text(encoding='utf-8-sig'));scenario=session['scenario']
        if(scenario.get('trial_kind')!='near_factory_channel2_readonly'or scenario.get('diagnostic_only')is not True
            or scenario.get('model_requests_enabled')is not False or scenario.get('full_match_acceptance')is not False
            or scenario.get('lobby_verified')is not True):raise ValueError('near_probe_explicit_owned_readonly_session_required')
        self.build=Path(build).resolve();self.full=None;self.combat_rows=[];self.combat_cursor=0
        self.build_pin=build_sha256
        manifest,outputs=verify_build(self.build,build_sha256)
        super().__init__(session_path,binding,producer,producer_command_id,output,diagnostic=True)
        self.manifest=manifest;self.executor_sha256=outputs['TacticoreNear2.dll'];self.native_host_sha256=outputs['near_runtime_host.exe']
        modules=[__file__,legacy.__file__,n.__file__,n.base.__file__,sys.modules[type(producer).__module__].__file__]
        self.source_snapshot={str(Path(path).resolve()):hashlib.sha256(Path(path).read_bytes()).hexdigest()for path in modules}
    def submit(self,*args,**kwargs):raise ValueError('near_factory_probe_never_publishes_commands')
    def _field_admission(self,*args,**kwargs):raise ValueError('near_factory_probe_has_no_field_capability')
    def _initial_snapshot_ready(self):
        # An observation is published before endpoint scanning and the first
        # receipts.  Seeing that observation alone does not complete startup.
        generations=(self.shared.observation_generation,self.shared.receipt_generation,self.full.near_receipt_generation)
        return self.shared.state==2 and bool(self.shared.admitted_actor.generation) and all(value>0 and not value&1 for value in generations)
    def _check(self):
        if self.session_path.read_bytes()!=self.session_bytes:raise ValueError('near_probe_session_changed')
        if self.shared is None or self.full is None or bytes(self.shared.bootstrap)!=self.bootstrap_bytes or bytes(self.full.bootstrap)!=self.near_bootstrap_bytes:
            raise ValueError('near_probe_bootstrap_changed')
        if(self.shared.magic_word,self.shared.protocol,self.shared.structure_size,self.shared.token)!=(n.MAGIC,n.VERSION,c.sizeof(n.Shared),self.token):
            raise ValueError('near_probe_channel_identity_changed')
        if self.shared.command_generation or self.full.near_command_generation:raise ValueError('near_probe_unexpected_command_publication')
        for path,digest in getattr(self,'source_snapshot',{}).items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('near_probe_source_changed_during_run')
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
        name = f'Local\\TacticoreNear2_{self.binding.game_process_id}_{self.token}'
        self.mapping = self.k.CreateFileMappingW(c.c_void_p(-1), None, 4, 0, c.sizeof(n.Shared), name)
        if not self.mapping or c.get_last_error() == 183:
            raise ValueError('runtime_mapping_collision_or_failure')
        self.view = self.k.MapViewOfFile(self.mapping, 0xf001f, 0, 0, c.sizeof(n.Shared))
        if not self.view:
            self.k.CloseHandle(self.mapping)
            self.mapping = None
            raise ValueError('runtime_mapping_view_failed')
        c.memset(self.view, 0, c.sizeof(n.Shared))
        self.full = n.Shared.from_address(self.view)
        self.shared = layout.SharedChannel.from_address(self.view)
        self.shared.magic_word, self.shared.protocol, self.shared.structure_size, self.shared.token = n.MAGIC, n.VERSION, c.sizeof(n.Shared), self.token
        self.shared.bootstrap = boot
        self.bootstrap_bytes = bytes(boot)
        near_boot=n.NativeBootstrap();near_boot.schema=2
        near_boot.original=n.base.Bootstrap.from_buffer_copy(bytes(boot))
        near_boot.mod_path=str(Path(self.session['mod_big']).resolve())
        near_boot.visibility_path=str(ROOT/'visibility/build-capability-2d7873e1.json')
        near_boot.template_audit_path=str(ROOT/'visibility/template-safety-2d7873e1.json')
        self.full.bootstrap=near_boot;self.near_bootstrap_bytes=bytes(near_boot)
        self._log = self.output.with_suffix('.host.log').open('x', encoding='utf-8')
        self.host = subprocess.Popen([str(self.build/'near_runtime_host.exe'), str(self.binding.game_process_id), str(self.token)],
                                     stdout=self._log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + startup_timeout
        while time.monotonic() < deadline:
            self._check()
            if self.shared.state in (3, 4, 5) or self.host.poll() is not None:
                self.save()
                raise ValueError('runtime_native_attach_refused_or_unknown')
            if self._initial_snapshot_ready():
                actor = _copy(self.shared.admitted_actor)
                self._actor = RuntimeActor(ActorIdentity(self.binding.session_id, 3, actor.object_id, actor.generation), actor.born_frame,
                                           self.producer_command_id, self.output.name + '#native_paid_birth')
                self.actor_bytes = bytes(actor)
                self.poll()
                return self._actor
            time.sleep(.02)
        self.save()
        raise ValueError('runtime_native_attach_timeout_unknown')
    def save(self):
        if self.shared is None or self.full is None:return
        before=c.string_at(self.view,layout.SharedChannel.events.offset)
        near_offset=n.Shared.bootstrap.offset
        near_before=c.string_at(self.view+near_offset,n.Shared.combat.offset-near_offset)
        after=c.string_at(self.view,layout.SharedChannel.events.offset)
        near_after=c.string_at(self.view+near_offset,n.Shared.combat.offset-near_offset)
        record=dict(schema_version=2,protocol='tactical_near_runtime_v2_factory_probe',diagnostic=True,
            binding=self.binding.public(),native_layout=n.inventory(),build_manifest_sha256=self.build_pin,build_manifest=self.manifest,
            source_snapshot=self.source_snapshot,
            executor_sha256=self.executor_sha256,native_host_sha256=self.native_host_sha256,
            bootstrap_hex=self.near_bootstrap_bytes.hex(),movement_bootstrap_hex=self.bootstrap_bytes.hex(),
            header_before_hex=before.hex(),header_after_hex=after.hex(),near_header_before_hex=near_before.hex(),near_header_after_hex=near_after.hex(),
            terminal_headers=[before.hex(),after.hex()]if self._stopped else [],
            producer_receipt=getattr(self,'producer_receipt',None),admitted_actor_hex=bytes(self.shared.admitted_actor).hex(),
            state=int(self.shared.state),reason=bytes(self.shared.reason).split(b'\0')[0].decode('ascii',errors='replace'),
            hooks_restored=int(self.shared.hooks_restored),active_callbacks=int(self.shared.active_callbacks),
            events_written=int(self.shared.events_written),events_overwritten=int(self.shared.events_overwritten),
            traces_written=int(self.shared.traces_written),traces_overwritten=int(self.shared.traces_overwritten),
            combat_written=int(self.full.combat_written),combat_overwritten=int(self.full.combat_overwritten),
            movement_command_generation=int(self.shared.command_generation),near_command_generation=int(self.full.near_command_generation),
            movement_sdk_calls=list(self.shared.receipt.sdk_calls),near_attack_attempts=int(self.full.near_receipt.attack_attempts),
            movement_held=int(self.shared.receipt.held),combat_held=int(self.full.near_receipt.held),
            commands=self.command_rows,events=self.event_rows,hook_traces=self.trace_rows,
            terminal_entries=getattr(self,'terminal_entries',None),host_pid=self.host.pid if self.host else None,
            host_exit=self.host.poll()if self.host else None,ordinary_execution_granted=False,model_requests=0,
            capability_granted=False,attack_verified=False,full_goal_complete=False)
        temporary=self.output.with_suffix('.pending')
        with temporary.open('w',encoding='utf-8')as stream:
            json.dump(record,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        legacy._replace_saved_report(temporary,self.output)
        if self._stopped:
            raw=c.string_at(self.view,c.sizeof(n.Shared));binary=self.output.with_suffix('.native-shared.bin')
            if binary.exists():
                if binary.read_bytes()!=raw:raise ValueError('near_probe_terminal_raw_changed')
            else:
                with binary.open('xb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    def stop(self,*,timeout=12):
        if self.shared is None:return None
        self._check();self._exchange('stop_requested',1);deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:self.poll()
            except ValueError:self.save()
            m=self.shared
            closed=(m.state==3 and m.hooks_restored==32767)or(m.state==4 and m.hooks_restored==1)
            if closed and not m.active_callbacks and not m.receipt.held and not self.full.near_receipt.held:
                if self.host:self.host.wait(timeout=max(.1,deadline-time.monotonic()))
                self.terminal_entries=self._entry_proof()
                if any(row['actual']!=row['expected']for row in self.terminal_entries):raise ValueError('near_probe_restore_bytes_mismatch')
                self._stopped=True;self.save();return getattr(self,'current',None)
            time.sleep(.05)
        self.save();raise TimeoutError('near_probe_quiescence_unknown_no_restart')
    def _entry_proof(self):
        source=(self.build/'source/tactical/runtime/near_native_hooks.cpp').read_text()
        found=re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2}|\\0)+)",(\d+),',source)
        if len(found)!=15:raise ValueError('near_probe_signature_inventory_changed')
        rows=[]
        for address,signature,count in found:
            expected=signature.encode('ascii').decode('unicode_escape').encode('latin1')
            if len(expected)!=int(count):raise ValueError('near_probe_signature_size_changed')
            actual=self.producer.memory.read(int(address,16),int(count))
            rows.append(dict(address=address,expected=expected.hex(),actual=actual.hex()))
        return rows
    def close(self):
        super().close();self.full=None
