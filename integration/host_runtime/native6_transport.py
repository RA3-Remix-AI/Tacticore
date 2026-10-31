"""Product-shaped adapter around the frozen Native6 transport.

Adds read-only task roots and receipts. It adds no physical action, parameter
or fallback to an older transport. Detailed build feedback is always refused.
"""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

from host_runtime.contracts import ContractError

ROOT=Path(__file__).resolve().parents[2]
_IMPORT_LOCK=threading.RLock()

def native_module():
    directory=ROOT/'native-ai/strategic-portable-runtime-v6'
    with _IMPORT_LOCK:
        spec=importlib.util.spec_from_file_location('product_portable_builder_v6',directory/'build.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        previous=sys.modules.get('build');sys.modules['build']=builder
        try:
            spec=importlib.util.spec_from_file_location('product_portable_native_client_v6',directory/'client.py')
            client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
        finally:
            if previous is None:sys.modules.pop('build',None)
            else:sys.modules['build']=previous
        return builder,client

def flat_status(raw):
    b=raw['binding']
    return dict(raw,**{key:b[key] for key in ('pid','thread','start_low','start_high','owner','ai','personality','player_template','engine')},
        personality_id=0x799613e0,self_hook_installed=raw['hook_held'],deadline_frame=raw['flag_deadline'],
        native_schema='unified_flags_and_managers_v6',raw_binding=b)

class MacroPolicyProbe:
    def __init__(self,session_path,owner,build,output,*,build_feedback=False):
        if build_feedback:raise ContractError('strategic_precise_builder_feedback_refused')
        self._lifecycle_lock=threading.RLock()
        self._probe=None;self.final_raw=None;self.observer=None;self.samples=0
        builder,client=native_module();builder.verify(build);self._projection=client.projection
        self._probe=client.Probe.__new__(client.Probe)
        try:
            self._probe.__init__(session_path,build,output)
            if self._probe.owner!=owner:raise ContractError('strategic_current_owner_changed')
            self.session=self._probe.session;self.owner=owner;self.build=Path(build);self.output=Path(output)
            self.manifest=self._probe.manifest;self.memory=self._probe.memory
            self.creation=self.session['process_creation_filetime'];self.seq=0
            self._native_state=self._probe.state;self._native_view=self._probe.view
            self._native_binding=self._probe.binding
            from host_runtime.native6_strategic_observer import create_native6_strategic_observer
            self.observer=create_native6_strategic_observer(self._probe)
            self.native=self.observer.identity
        except BaseException:
            self._probe.close();raise
    def native_status(self):
        with self._lifecycle_lock:return self._native_status()
    def _native_status(self):
        raw=self._probe.status() if self._probe.view is not None else self.final_raw
        if raw is None:raise ContractError('strategic_native_state_unavailable')
        return flat_status(raw)
    def configure_stop_gate(self,gate):
        if gate.session_id!=self.session['session_id']:raise ContractError('strategic_stop_binding_changed')
        self._stop_gate=gate
    def stop_batch(self,*,plan_id,effective_hash):
        if not hasattr(self,'_stop_gate'):raise ContractError('strategic_stop_gate_not_bound')
        import uuid
        parent=str(uuid.uuid5(uuid.UUID(self.session['session_id']),plan_id+':'+effective_hash))
        return self._stop_gate.admit('native_batch',command_id=parent,plan_id=plan_id)
    def completed_native_status(self):
        from host_runtime.native6_callback_snapshot import completed_snapshot
        with self._lifecycle_lock:
            if (self._probe.view is None or self._probe.view!=self._native_view
                    or self._probe.state is not self._native_state
                    or self._probe.binding!=self._native_binding):
                raise ContractError('strategic_native_state_unavailable')
            value=completed_snapshot(self._native_state)
            if value is None:return None
            if (value.magic!=0x53434736 or value.version!=6 or value.size!=4592
                    or bytes(value.binding)!=self._native_binding):
                raise ContractError('strategic_native_state_unavailable')
            return flat_status(self._projection(value))
    def apply(self,actions,duration_frames,command_id=None,*,not_after_frame=None):
        with self._lifecycle_lock:
            native=self._probe.apply(actions,duration_frames,command_id,not_after_frame=not_after_frame)
            return self._receipt(native,command_id)
    def manager(self,gate,enabled,duration_frames,command_id,*,not_after_frame,release=False):
        with self._lifecycle_lock:
            operation='release' if release else 'enable' if enabled else 'pause'
            native=self._probe.command(operation,gate,duration_frames,min(120000,max(1,duration_frames*1000//15)),command_id=command_id,not_after_frame=not_after_frame)
            return self._receipt(native,command_id)
    def _receipt(self,native,command_id):
        # SDK ACK publication precedes callback active=0. Wait only for a
        # completed read of that same ACK; never repeat a Native operation.
        expected=native['ack'];until=time.monotonic()+.25
        while True:
            completed=self.completed_native_status()
            if completed is not None:
                if (completed['request']!=expected or completed['ack']!=expected
                        or completed['phase']!=1 or completed['error'] or completed['result']!=native['result']):
                    raise ContractError('strategic_native_ack_generation_changed')
                native=completed;break
            if time.monotonic()>=until:raise ContractError('strategic_native_ack_completion_unobserved')
            time.sleep(.001)
        self.seq=native['ack']
        receipt=dict(command_id=command_id,seq=self.seq,native=native,
            native_gate_acknowledged=native['result'] not in (0,4,5),native_effect_verified=False,
            result=native['result'])
        if native['result']==0:raise ContractError('strategic_native_intent_refused')
        return receipt
    def observe(self,label):
        with self._lifecycle_lock:return self._observe(label)
    def _observe(self,label):
        from host_runtime.native6_observation import sample_controls
        before=self.native_status();observation=self.observer.sample(include_trace=self.samples<3);controls=None
        try:controls=sample_controls(self)
        except (ValueError,RuntimeError):observation=dict(observation,observation_complete=False,observation_error='unified_control_sample_unknown')
        after=self.native_status();self.samples+=1
        stable=('raw_binding','phase','request','ack','applied_mask','flag_phase','flag_deadline','gates')
        if before['active'] or after['active'] or any(before[key]!=after[key] for key in stable):
            observation=dict(source='native_macro_read_only',observation_complete=False,
                observation_error='strategic_transport_changed_during_sample',frame=None,
                runtimes=[],state_scores={},budget_feedback=None,native_calls=0,process_writes=0)
        self._probe.event('product_rooted_observation',label=label,observation=observation,independent_controls=controls)
        return dict(kind='macro_observation',label=label,observation=observation,unified_native=after,independent_controls=controls)
    def close(self):
        with self._lifecycle_lock:return self._close()
    def _close(self):
        if self._probe is None:return
        self._probe.close()
        proof_path=self.output/'independent-release.json' if hasattr(self,'output') else None
        if proof_path is None or not proof_path.exists():return
        proof=json.loads(proof_path.read_text(encoding='utf8'));self.final_raw=proof['native'];self.memory=None
        final=dict(session_id=self.session['session_id'],pid=self.session['pid'],
            process_creation_filetime=self.creation,mod_sha256=self.session['mod_sha256'],
            native=flat_status(self.final_raw),raw_native=self.final_raw,
            independent_flags=proof['flags'],cleanup_verified=proof['native_release_verified'],
            unknown_command_ids=[key for key,value in self._probe.receipts.items() if value.get('unknown')],
            host_returncode=proof['host_returncode'],native_release_contract='native6_unified_release_v1')
        final.update(runtime_root=self.final_raw['binding']['runtime_root'],
            runtime_manifest_sha256=bytes(self.final_raw['binding']['runtime_manifest']).hex())
        final['independent_release_sha256']=__import__('hashlib').sha256(proof_path.read_bytes()).hexdigest()
        journal=self._probe.paths.journal(self.session['session_id'])
        journal_bytes=journal.read_bytes()
        archived=self.output/'native-journal.bin'
        if archived.exists():
            if archived.read_bytes()!=journal_bytes:raise ContractError('unified_native_journal_changed_after_return')
        else:
            with archived.open('xb') as stream:stream.write(journal_bytes)
        final['native_journal_sha256']=__import__('hashlib').sha256(journal_bytes).hexdigest()
        (self.output/'final-state.json').write_text(json.dumps(final,indent=2)+'\n',encoding='utf8')
