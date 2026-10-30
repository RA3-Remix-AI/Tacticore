"""Borrow a verified MacroSampler's read-only handle for explicit v3 costs.

This factory never opens a handle, attaches a runtime or calls a game function.
Bootstrap/data errors disable only the new cost-gated actions. Legacy actions
do not depend on the factory's result. Test dependencies are explicit and are
not reachable from a model/RPC payload.
"""
from dataclasses import asdict,dataclass,is_dataclass
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
import time

from .contracts import ContractError

ROOT=Path(__file__).resolve().parents[2]
PACKAGE_SHA256='d516540d3d51a48a2d385dd1534e329bd5139bc67a6a0bde3e59a3ea5b9690a5'
EXE_SHA256='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
SCOPE='current_owned_production_upgrade_queues_v3'
NEW_ACTIONS=('buildpower','buildbarracks','buildfactory','buildrefinery','buildbattlelab','producesickle','producebullfrog')
SOURCE_PINS={
    'native-ai/macro_cost_supplier.py':'353a35cbecb4b9229b19a5c060eef482a8edb8782d8124f75e639177ef26ddaf',
    'native-ai/macro_payment_observation.py':'f8bc8ae911a452cf19acc3b53a76cbf404bf29b8cca09933da500b45239d442a',
    'native-ai/macro_cost_observation.py':'726e87805bd50acd68dc2c5237d1ab7b64317f710f5483502e228876ab9904f7',
    'native-ai/macro_cost_upper_contract.py':'40b4f68edf8ea13a9522d51212493e5f30c5f94e81f7eb53d770f08949b92aa6',
    'native-ai/macro_cost_asset_audit.py':'ad500ea45396045167051be1318965d643c03b69232131f93daf7bce54a57370',
    'native-ai/readiness_dependency_contract.py':'7b80c594283631fa3cf31f616f63c4a38da32c1e8f29ee32e95fde988a3dee4b',
    'native-ai/macro_readiness_observation.py':'d9abb6c26e218f5a719a22bed1279a8b468ae0611ebbc506ad0f2678b5704989',
    'tactical/runtime/audit_near_weapon_asset.py':'212f1aae46726e10f02ab0f6284937ce7bb54a565cc2058d177f4297dbc2ec49',
    'reference/Ra3-Copilot/unit-codes/tools/sage_hash.py':'db2916f64ce75d12897e26b6e0b0e1e9f6fefe96d4a30824c1fab91f730cb99e'}


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _word(read,at):return struct.unpack('<I',read(at,4))[0]
def _emit(event,kind,**payload):
    if event is not None:
        try:event(kind,**payload)
        except Exception:pass  # diagnostics must not break the legacy lane


def read_existing_handle_identity(memory,*,_kernel=None):
    """Actual raw FILETIME, never Memory.start_timestamp's float conversion."""
    import ctypes as c
    from ctypes import wintypes as w
    if _kernel is None:
        from observe_production import k
    else:k=_kernel
    k.GetProcessId.argtypes=[w.HANDLE];k.GetProcessId.restype=w.DWORD
    k.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
    k.GetProcessTimes.restype=w.BOOL
    k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
    k.QueryFullProcessImageNameW.restype=w.BOOL
    handle=w.HANDLE(memory.handle)
    pid=int(k.GetProcessId(handle))
    if not pid:raise ValueError('macro_cost_existing_handle_pid_unavailable')
    times=[w.FILETIME() for _ in range(4)]
    if not k.GetProcessTimes(handle,*[c.byref(value) for value in times]):
        raise ValueError('macro_cost_existing_handle_creation_unavailable')
    creation=int(times[0].dwLowDateTime)|(int(times[0].dwHighDateTime)<<32)
    path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
    if not k.QueryFullProcessImageNameW(handle,0,path,c.byref(size)):
        raise ValueError('macro_cost_existing_handle_image_unavailable')
    return dict(pid=pid,process_creation_filetime=creation,image_path=path.value)


@dataclass(frozen=True)
class CostFactoryBoot:
    supplier:object|None
    reason:str
    output:str
    enabled:bool


@dataclass(frozen=True)
class _Dependencies:
    sampler_type:type
    scope_type:type
    dependency_type:type
    binding_type:type
    universe_type:type
    supplier_type:type
    identity_reader:object
    source_pins:dict
    expected_package_sha256:str=PACKAGE_SHA256
    expected_executable_sha256:str=EXE_SHA256
    reports_root:Path=ROOT/'reports'


def _dependencies():
    for name,expected in SOURCE_PINS.items():
        if _sha(ROOT/name)!=expected:raise ValueError('macro_cost_factory_source_pin_changed:'+name)
    folder=str(ROOT/'native-ai')
    if folder not in sys.path:sys.path.insert(0,folder)
    names=('macro_cost_supplier','macro_payment_observation','macro_cost_observation',
        'macro_cost_upper_contract','macro_cost_asset_audit','readiness_dependency_contract','macro_readiness_observation')
    modules={name:importlib.import_module(name) for name in names}
    if any(Path(module.__file__).resolve()!=ROOT/'native-ai'/(name+'.py') for name,module in modules.items()):
        raise ValueError('macro_cost_factory_import_source_mismatch')
    from .macro_live import MacroSampler
    from .macro_expansion_scope import ExpansionScope
    core=modules['macro_cost_supplier']
    return _Dependencies(MacroSampler,ExpansionScope,modules['readiness_dependency_contract'].DependencyObserver,
        core.CostSessionBinding,core.CompiledCostUniverse,core.StrictNativeCostSupplier,
        read_existing_handle_identity,SOURCE_PINS)


class _IsolatedSupplier:
    def __init__(self,delegate,output,event):self.delegate=delegate;self.output=output;self.event=event;self.last_failure=None
    def __call__(self,action,sample,game_seconds):
        try:
            fact=self.delegate(action,sample,game_seconds)
            evidence=dict(kind='macro_cost_current_queue_fact',action=action,game_seconds=game_seconds,
                fact=asdict(fact) if is_dataclass(fact) else None,
                native_observation=getattr(self.delegate,'last_observation',None),
                single_new_request_hard_limit_verified=False,field_qualification_granted=False)
            with (self.output/'cost-observations.jsonl').open('a',encoding='utf8') as stream:
                stream.write(json.dumps(evidence,ensure_ascii=False,allow_nan=False)+'\n')
            self.last_failure=None
            return fact
        except Exception as error:
            reason=getattr(error,'code',None) or str(error) or type(error).__name__
            self.last_failure=dict(reason=reason,error_type=type(error).__name__,action=action)
            _emit(self.event,'macro_cost_adapter_blocked',**self.last_failure,new_actions_only=True)
            try:
                with (self.output/'cost-observations.jsonl').open('a',encoding='utf8') as stream:
                    stream.write(json.dumps(dict(kind='macro_cost_adapter_blocked',**self.last_failure))+'\n')
            except OSError:pass
            raise ContractError('blocked_native_cost_reservation_unverified') from None


def boot_current_queue_cost_supplier(sampler,*,output,event=None,_test_dependencies=None):
    """Return a borrowed-handle v3 supplier or a diagnosed disabled boot.

    Parent Host wiring is only ``boot=...`` then ``cost_supplier=boot.supplier``.
    This function does not modify MacroSampler, Host or any native build.
    """
    output=Path(output).resolve();began=time.monotonic_ns();sources=[]
    was_present=output.exists();created=False;reports_root=ROOT/'reports'
    try:
        deps=_dependencies() if _test_dependencies is None else _test_dependencies
        if not isinstance(deps,_Dependencies):raise ValueError('macro_cost_factory_dependency_type')
        reports_root=Path(deps.reports_root).resolve()
        if not isinstance(sampler,deps.sampler_type):raise ValueError('macro_cost_factory_verified_sampler_required')
        if not isinstance(sampler.scope,deps.scope_type):raise ValueError('macro_cost_factory_expansion_scope_required')
        if not output.is_relative_to(Path(deps.reports_root).resolve()) or output.exists():
            raise ValueError('macro_cost_factory_fresh_host_output_required')
        output.mkdir(parents=True);created=True
        session=sampler.session
        if (type(session.get('pid')) is not int or session['pid']<=0
                or type(session.get('process_creation_filetime')) is not int or session['process_creation_filetime']<=0
                or session.get('mod_sha256')!=deps.expected_package_sha256
                or sampler.scope.package_sha256!=session['mod_sha256']):
            raise ValueError('macro_cost_factory_exact_session_required')
        if not isinstance(sampler.expansion_dependency,deps.dependency_type):
            raise ValueError('macro_cost_factory_verified_dependency_observer_required')
        observer=sampler.expansion_dependency
        owner=sampler.owner;game=observer.base.game;factory=observer.factory
        if (observer.owner!=owner or observer.base.owner!=owner or observer.base.owner_index!=3
                or sampler.proof['handshake']['player']!=owner
                or sampler.proof['handshake']['game_logic']!=game):
            raise ValueError('macro_cost_factory_sampler_proof_mismatch')
        memory=sampler.memory;handle=memory.handle
        game_path=Path(session['game']).resolve()
        if _sha(game_path)!=deps.expected_executable_sha256:
            raise ValueError('macro_cost_factory_executable_changed')
        manifest_path=Path(sampler.bundle['build'])/'build-manifest.json'
        manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        report_path=Path(manifest['package_report']).resolve()
        if (manifest.get('protocol_version')!=2 or manifest.get('package_sha256')!=session['mod_sha256']
                or _sha(report_path)!=manifest.get('package_report_sha256')):
            raise ValueError('macro_cost_factory_transport_package_changed')
        report=json.loads(report_path.read_text(encoding='utf-8-sig'))
        package=report_path.parent/'TFMacroProbe.big'
        if (report.get('variant')!='expanded_macro_policy_v2' or report.get('compiled') is not True
                or report.get('big_sha256')!=session['mod_sha256'] or _sha(package)!=session['mod_sha256']):
            raise ValueError('macro_cost_factory_compiled_package_changed')
        frozen_files=[(sampler.path,sampler.raw),(sampler.bundle_path,sampler.bundle_raw),
            (sampler.registry_path,sampler.registry_raw)]
        def identity_reader():
            if sampler.memory is not memory or memory.handle!=handle or sampler.owner!=owner:
                raise ValueError('macro_cost_factory_borrowed_handle_changed')
            process=deps.identity_reader(memory)
            if (process['pid']!=session['pid'] or process['pid']!=memory.pid
                    or process['process_creation_filetime']!=session['process_creation_filetime']
                    or str(Path(process['image_path']).resolve()).casefold()!=str(game_path).casefold()):
                raise ValueError('macro_cost_factory_pid_creation_or_image_changed')
            if any(Path(path).read_bytes()!=raw for path,raw in frozen_files):
                raise ValueError('macro_cost_factory_session_files_changed')
            read=memory.read
            if (_word(read,0xcd8ce4)!=game or _word(read,game)!=0xbeb630
                    or _word(read,owner)!=0xc5bce0 or _word(read,owner+0x20)!=3
                    or _word(read,0xce6c58)!=factory):
                raise ValueError('macro_cost_factory_native_identity_changed')
            ai=_word(read,owner+0x90)
            if (not 0x10000<=ai<=0x7ffe0000 or _word(read,ai)!=0xc60f60
                    or _word(read,ai+8)!=owner or _word(read,ai+0x8a8)!=owner):
                raise ValueError('macro_cost_factory_own_ai_identity_changed')
            return deps.binding_type(session['session_id'],process['pid'],process['process_creation_filetime'],
                deps.expected_executable_sha256,session['mod_sha256'],3,(hex(game),hex(owner),hex(factory)))
        identity=identity_reader()
        archive=output/'source';archive.mkdir()
        for index,name in enumerate(deps.source_pins):
            path=ROOT/name
            if _sha(path)!=deps.source_pins[name]:raise ValueError('macro_cost_factory_source_changed_during_boot')
            target=archive/(str(index)+'-'+path.name);target.write_bytes(path.read_bytes())
            sources.append(dict(path=str(path.resolve()),copy=target.name,sha256=_sha(target)))
        for index,path in enumerate([Path(__file__),manifest_path,report_path],start=len(sources)):
            target=archive/(str(index)+'-'+path.name);target.write_bytes(path.read_bytes())
            sources.append(dict(path=str(path.resolve()),copy=target.name,sha256=_sha(target)))
        universe=deps.universe_type.recompute(package=package,game_root=game_path.parent.parent,
            output=output/'compiled-universe')
        # The raw held-handle identity and native globals are checked again
        # after archive work; it may have taken multiple game frames.
        if identity_reader()!=identity:raise ValueError('macro_cost_factory_identity_changed_during_boot')
        delegate=deps.supplier_type(memory.read,session=identity,identity_reader=identity_reader,
            universe=universe,product_scope=SCOPE)
        wrapped=_IsolatedSupplier(delegate,output,event)
        status=dict(schema_version=1,kind='macro_cost_factory_boot',enabled=True,reason='ready_current_queue_budget_v3',
            session_id=session['session_id'],pid=identity.pid,process_creation_filetime=identity.process_creation_filetime,
            game_identity=identity.game_identity,scope=SCOPE,sources=sources,
            handle_borrowed=True,new_handles_opened=0,native_calls=0,process_writes=0,
            field_qualification_granted=False,single_new_request_hard_limit_verified=False,
            began_monotonic_ns=began,ended_monotonic_ns=time.monotonic_ns())
        with (output/'boot.json').open('x',encoding='utf8') as stream:json.dump(status,stream,indent=2);stream.write('\n')
        _emit(event,'macro_cost_adapter_boot',enabled=True,reason=status['reason'],scope=SCOPE)
        return CostFactoryBoot(wrapped,status['reason'],str(output),True)
    except Exception as error:
        reason=getattr(error,'code',None) or str(error) or type(error).__name__
        status=dict(schema_version=1,kind='macro_cost_factory_boot',enabled=False,reason=reason,
            error_type=type(error).__name__,scope=SCOPE,new_actions_blocked=list(NEW_ACTIONS),
            legacy_actions_affected=False,new_handles_opened=0,native_calls=0,process_writes=0,
            sources=sources,began_monotonic_ns=began,ended_monotonic_ns=time.monotonic_ns())
        try:
            if not was_present and not output.exists() and output.is_relative_to(reports_root):
                output.mkdir(parents=True);created=True
            if created and output.is_dir() and not (output/'boot.json').exists():
                with (output/'boot.json').open('x',encoding='utf8') as stream:json.dump(status,stream,indent=2);stream.write('\n')
        except OSError:pass
        _emit(event,'macro_cost_adapter_boot',enabled=False,reason=reason,new_actions_only=True)
        return CostFactoryBoot(None,reason,str(output),False)
