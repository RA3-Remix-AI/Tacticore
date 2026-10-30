"""Read-only observation borrowed from an already admitted Native5 Probe.

Never constructs a Probe/Memory/WinDLL, opens a process, verifies a build,
dispatches an action, or calls a model. Source/build admission remains the
owning controller's job. These checks are observation evidence, not authority.
"""
import copy
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import time
import uuid

MAGIC=0x53434735
VERSION=5
BINDING_SIZE=1180
SHARED_SIZE=1440
FLAGS=tuple('/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_'+suffix for suffix in
    ('build_airfield','scout','buildtech','economyrefinery','budgeteconomy',
     'budgetarmy','budgettech','deployattack','deploydefense','expand'))
_BINDING_FIELDS=('pid','thread','start_low','start_high','owner','ai','personality',
    'personality_data','player_template','game','engine','session','lease','package','sources','deployment')
_STABLE=('magic','version','size','binding','request','ack','phase','active','error','kind','gate',
    'frames','wall_ms','result','stop','lease_held','hook_held','cleanup_verified','journal_records','gates',
    'requested_mask','applied_mask','flag_deadline','flag_phase','flag_attempted','callback_serial','not_after_frame')


class Native5ObservationUnavailable(ValueError):
    """Admission/readiness/identity is unproven; no command should follow."""


def _require(value,reason):
    if not value:raise Native5ObservationUnavailable(reason)


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _project(value):
    if isinstance(value,c.Array):return [_project(v) for v in value]
    if isinstance(value,c.Structure):return {name:_project(getattr(value,name)) for name,_ in value._fields_}
    return value


def _handle_value(value):
    raw=value.value if isinstance(value,c.c_void_p) else value
    _require(type(raw) is int and raw>0,'native5_held_process_handle_required')
    return raw


def _read_key(method):return (getattr(method,'__self__',None),getattr(method,'__func__',method))


def _default_observer_factory(*args,**kwargs):
    # The controller's admitted SDK has already arranged its native-ai imports.
    # Keep importing this adapter itself free of Probe/WinDLL initialization.
    from strategic_unified_observation_v5 import RootedStrategicObserverV5
    return RootedStrategicObserverV5(*args,**kwargs)


def _default_binding_checker(read,owner,ai,identity,expected):
    # Only recheck own metadata; do not resample scores/tasks or call Native.
    from strategic_unified_observation_v5 import _check_current_binding,inspect_player
    return _check_current_binding(read,owner,ai,identity,expected,inspect_player)


def _same_semantic_state(before,after):
    # Native increments this counter on every callback, including idle ticks.
    # Keep all control/binding state exact; only this counter may advance.
    return (type(before['callback_serial']) is int and type(after['callback_serial']) is int
            and 0<=before['callback_serial']<=after['callback_serial']<0xffffffff
            and all(before[key]==after[key] for key in _STABLE if key!='callback_serial'))


def _unknown(reason):
    return dict(source='native_macro_read_only',observation_complete=False,observation_readiness='unknown',
        observation_error=str(reason),frame=None,runtimes=[],state_scores={},budget_feedback=None,
        native_calls=0,process_writes=0,targets_read=False,enemy_details_read=False,
        strategic_success_verified=False,sample_atomic=False,product_capability_granted=False)


class Native5StrategicObserver:
    """Borrow one admitted Probe for bounded observations; never own/close it."""
    product_capability_granted=False

    def __init__(self,probe,*,observer_factory=None,binding_checker=None,clock_ns=time.monotonic_ns):
        self._probe=probe;self._clock=clock_ns;self._serial_highwater=0
        self._binding_checker=binding_checker or _default_binding_checker
        self._lock=probe.command_lock
        _require(self._lock.acquire(blocking=False),'native5_observer_busy')
        try:
            self._memory=probe.memory;self._kernel=probe.kernel;self._state=probe.state
            _require(self._memory is not None and self._state is not None,'native5_attached_probe_required')
            self._state_type=type(self._state);self._binding_type=type(self._state.binding)
            _require(issubclass(self._state_type,c.Structure) and c.sizeof(self._state_type)==SHARED_SIZE,
                     'native5_shared_layout_required')
            _require(issubclass(self._binding_type,c.Structure) and c.sizeof(self._binding_type)==BINDING_SIZE
                     and tuple(name for name,_ in self._binding_type._fields_)==_BINDING_FIELDS,'native5_binding_layout_required')
            _require(type(probe.binding) is bytes and len(probe.binding)==BINDING_SIZE,'native5_immutable_binding_required')
            self._sealed=probe.binding;self._bound=self._binding_type.from_buffer_copy(self._sealed)
            self._binding=_project(self._bound)
            self._session_raw=probe.session_raw
            _require(type(self._session_raw) is bytes,'native5_immutable_session_required')
            self._session=json.loads(self._session_raw)
            self._manifest=_canonical(probe.manifest)
            self._flags=tuple(probe.manifest['flags'])
            _require(self._flags==FLAGS,'native5_fixed_ten_flags_required')
            _require(probe.manifest['version']==5 and probe.manifest['protocol_version']==5,'native5_manifest_schema_required')
            self._context=dict(pid=int(self._bound.pid),
                process_creation_filetime=int(self._bound.start_low)|(int(self._bound.start_high)<<32),
                session_id=str(uuid.UUID(bytes=bytes(self._bound.session))))
            _require(type(self._session['pid']) is int and type(self._session['process_creation_filetime']) is int
                     and self._session['pid']==self._context['pid']
                     and self._session['process_creation_filetime']==self._context['process_creation_filetime']
                     and self._session['session_id']==self._context['session_id'],'native5_session_wire_incarnation_mismatch')
            _require(self._context['pid']>0 and self._context['process_creation_filetime']>0 and any(bytes(self._bound.lease)),
                     'native5_bound_epoch_required')
            _require(bytes(self._bound.package).hex()==self._session['mod_sha256']==probe.manifest['package_sha256']
                     and bytes(self._bound.sources).hex()==probe.manifest['source_closure_sha256'],
                     'native5_package_or_source_binding_mismatch')
            self._handle=_handle_value(self._memory.handle);self._read=_read_key(self._memory.read)
            self._pid_fn=self._kernel.GetProcessId;self._times_fn=self._kernel.GetProcessTimes
            self._pid_fn.argtypes=[w.HANDLE];self._pid_fn.restype=w.DWORD
            self._times_fn.argtypes=[w.HANDLE,*[c.POINTER(w.FILETIME)]*4];self._times_fn.restype=w.BOOL
            started=self._clock();self._read_deadline=started+250_000_000
            before,os_before=self._guard()
            frame=self._frame()
            factory=observer_factory or _default_observer_factory
            self._observer=factory(self._memory,int(self._bound.owner),self._flags,caller_binding=copy.deepcopy(self._context))
            self._check_observer_binding()
            self._observer_binding=_canonical(self._observer._expected_binding)
            after,os_after=self._guard();self._tail_current_own_binding();frame_after=self._frame();self._current_roots()
            self._references();final=self._ready_snapshot();elapsed=self._clock()-started
            _require(_same_semantic_state(after,final),'native5_state_changed_during_final_frame_read')
            self._coherent(before,after,frame,frame_after,elapsed)
            self._constructor_evidence=dict(before=os_before,after=os_after)
        finally:self._lock.release()

    @property
    def identity(self):return copy.deepcopy(self._observer.identity)

    def _frame(self):
        raw=self._memory.read(int(self._bound.game)+0x50,4)
        _require(type(raw) is bytes and len(raw)==4,'native5_frame_unavailable')
        frame=int.from_bytes(raw,'little');_require(frame>0,'native5_no_current_simulation');return frame

    def _current_roots(self):
        for address,expected in ((0xcd8ce4,int(self._bound.game)),(0xcdd190,int(self._bound.engine))):
            raw=self._memory.read(address,4)
            _require(type(raw) is bytes and len(raw)==4 and int.from_bytes(raw,'little')==expected,
                     'native5_current_game_or_engine_changed')

    def _references(self):
        p=self._probe
        _require(p.memory is self._memory and p.kernel is self._kernel and p.state is self._state
                 and p.command_lock is self._lock,'native5_borrowed_objects_changed')
        _require(p.view is not None and p.view!=0 and not p.stopped.is_set() and not p.unknown,'native5_probe_stopped_or_unknown')
        _require(p.host is not None and p.host.poll() is None,'native5_host_not_running')
        _require(type(p.binding) is bytes and p.binding==self._sealed and p.session_raw==self._session_raw
                 and _canonical(p.session)==_canonical(self._session) and _canonical(p.manifest)==self._manifest,
                 'native5_bound_inputs_changed')
        _require(type(self._memory.pid) is int and self._memory.pid==self._context['pid']
                 and _handle_value(self._memory.handle)==self._handle and _read_key(self._memory.read)==self._read,
                 'native5_held_memory_substitution')
        _require(self._kernel.GetProcessId is self._pid_fn and self._kernel.GetProcessTimes is self._times_fn,
                 'native5_borrowed_kernel_changed')

    def _ready_snapshot(self):
        from .native5_callback_snapshot_v1 import completed_snapshot
        current=completed_snapshot(self._state)
        # A healthy callback may still be executing after attach ACK. Wait
        # only for a read of its completed publication, within this sample's
        # original total wall bound. No new callback or Native command is sent.
        while current is None and self._clock()<self._read_deadline:
            _require(self._state.phase==1 and not self._state.stop and not self._state.error,
                     'native5_transport_not_ready')
            time.sleep(.001);self._references();current=completed_snapshot(self._state)
        _require(current is not None,'native5_callback_not_completed')
        _require(current.magic==MAGIC and current.version==VERSION and current.size==SHARED_SIZE
                 and bytes(current.binding)==self._sealed,'native5_wire_header_or_binding_changed')
        _require(current.phase==1 and not current.active and not current.stop and not current.error
                 and current.lease_held==1 and current.hook_held==1 and not current.cleanup_verified
                 and current.request==current.ack,'native5_transport_not_ready')
        _require(current.flag_phase in (0,1,4) and all(g.phase in (0,1,4) for g in current.gates),
                 'native5_native_outcome_unknown')
        serial=int(current.callback_serial)
        _require(self._serial_highwater<=serial<0xffffffff,'native5_callback_serial_regressed_or_exhausted')
        self._serial_highwater=serial
        return {key:_project(getattr(current,key)) for key in _STABLE}

    def _guard(self):
        self._references();before=self._ready_snapshot()
        created=[w.FILETIME() for _ in range(4)]
        _require(self._pid_fn(self._handle)==self._context['pid']
                 and self._times_fn(self._handle,*[c.byref(v) for v in created]),'native5_actual_OS_identity_unavailable')
        ticks=int(created[0].dwLowDateTime)|(int(created[0].dwHighDateTime)<<32)
        _require(ticks==self._context['process_creation_filetime'],'native5_actual_OS_incarnation_changed')
        # OS queries can yield while the game callback or controller changes.
        # Do not return a status copy taken before those queries as a new fact.
        self._references();after=self._ready_snapshot()
        _require(_same_semantic_state(before,after),'native5_state_changed_during_OS_read')
        return after,dict(pid=self._context['pid'],process_creation_filetime=ticks)

    def _check_observer_binding(self):
        e=self._observer._expected_binding;b=self._binding
        _require(e['kind']=='strategic_own_observer_binding_v1' and e['caller_context']==self._context
                 and all(e[key]==b[key] for key in ('owner','ai','game','engine')),'native5_observer_roots_differ_from_admitted_binding')
        identity=self._observer.identity
        _require(e['identity']==identity and identity['player_index']==3
                 and int(identity['instance_id'],0)==0x799613e0,'native5_observer_personality_mismatch')
        names=dict(player='owner',ai_player='ai',personality_wrapper='personality',personality_data='personality_data',player_template='player_template')
        _require(all(int(identity[key],0)==b[field] for key,field in names.items()),'native5_observer_own_chain_differ_from_admitted_binding')

    def _tail_current_own_binding(self):
        # Last OS calls may yield after the inner observer has completed.
        # Recheck the CURRENT registered own chain, not the old sealed frame.
        self._check_observer_binding()
        _require(_canonical(self._observer._expected_binding)==self._observer_binding,'native5_observer_binding_changed')
        self._binding_checker(self._memory.read,int(self._bound.owner),int(self._bound.ai),
                              self._observer.identity,self._observer._expected_binding)

    @staticmethod
    def _coherent(before,after,frame,frame_after,elapsed):
        _require(_same_semantic_state(before,after) and 0<=frame_after-frame<=2 and 0<=elapsed<=250_000_000,
                 'native5_state_or_observation_window_changed')

    def sample(self,*,include_trace=False):
        if not self._lock.acquire(blocking=False):return _unknown('native5_observer_busy')
        try:
            started=self._clock();self._read_deadline=started+250_000_000
            before,os_before=self._guard();frame=self._frame()
            self._check_observer_binding()
            _require(_canonical(self._observer._expected_binding)==self._observer_binding,'native5_observer_binding_changed')
            value=self._observer.sample(include_trace=include_trace)
            self._check_observer_binding()
            _require(_canonical(self._observer._expected_binding)==self._observer_binding,'native5_observer_binding_changed')
            after,os_after=self._guard();self._tail_current_own_binding();frame_after=self._frame();self._current_roots()
            self._references();final=self._ready_snapshot();elapsed=self._clock()-started
            _require(_same_semantic_state(after,final),'native5_state_changed_during_final_frame_read')
            self._coherent(before,after,frame,frame_after,elapsed)
            _require(type(value) is dict and value.get('observation_complete') is True,'native5_observer_incomplete')
            _require(value.get('native')==self._observer.identity and value.get('caller_session_binding')==self._context,
                     'native5_observation_identity_substitution')
            _require(type(value.get('frame')) is int and type(value.get('frame_after')) is int
                     and frame<=value['frame']<=value['frame_after']<=frame_after
                     and type(value.get('sample_elapsed_ns')) is int and 0<=value['sample_elapsed_ns']<=250_000_000,
                     'native5_observation_frame_substitution')
            result=copy.deepcopy(value)
            result['native5_read_only_binding']=dict(protocol_version=5,pid=self._context['pid'],
                process_creation_filetime=self._context['process_creation_filetime'],session_id=self._context['session_id'],
                sealed_binding_sha256=hashlib.sha256(self._sealed).hexdigest(),OS_before=os_before,OS_after=os_after,
                frame_before=frame,frame_after=frame_after,total_elapsed_ns=elapsed)
            result['product_capability_granted']=False
            return result
        except (ValueError,RuntimeError,KeyError,TypeError,AttributeError,OSError) as error:return _unknown(error)
        finally:self._lock.release()


def create_native5_strategic_observer(probe,*,observer_factory=None,binding_checker=None,clock_ns=time.monotonic_ns):
    """Borrow an admitted actual Probe; caller owns its lifecycle and authority."""
    try:return Native5StrategicObserver(probe,observer_factory=observer_factory,binding_checker=binding_checker,clock_ns=clock_ns)
    except Native5ObservationUnavailable:raise
    except (ValueError,RuntimeError,KeyError,TypeError,AttributeError,OSError) as error:
        raise Native5ObservationUnavailable('native5_observer_admission_unavailable:'+str(error)) from error
