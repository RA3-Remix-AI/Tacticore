"""Read-only replay of existing legacy return contracts across installation roots.

No arbitrary old script is executed, no source global is patched, no record is
rewritten, no orphan collector runs. Existing contracts retain their exact-hash
passive capture verifier requirement. The old report root is derived from the independently
hashed frozen Host source index, never from a WebView/model request.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from types import MethodType,ModuleType,FunctionType,SimpleNamespace
import builtins
import importlib
import importlib.util
import importlib.abc
import sys
import os

from .contracts import ContractError,SessionBinding


def host_ended(receipt):
    from .native5_helper_identity_v1 import process_identity
    from .session_discovery_native import Win32ReadOnly
    pid=receipt.get('host_pid');start=receipt.get('host_start_time')
    if type(pid) is not int or not isinstance(start,str):raise ContractError('run_history_unverifiable')
    # All historical NativeHostSpawner versions execute python.exe. The
    # complete OS snapshot also handles an old PID now belonging to System,
    # whose query/synchronize handle is intentionally inaccessible.
    if pid not in Win32ReadOnly().process_ids('python.exe'):return
    try:actual=process_identity(pid)
    except OSError as error:
        if getattr(error,'winerror',None)==87:return
        raise ContractError('run_history_unverifiable') from None
    from .session_discovery_native import require_creation
    try:require_creation(start,actual['process_creation_filetime'])
    except ContractError:return  # exact old ISO interval differs from current OS incarnation
    if actual['alive']:raise ContractError('beta_existing_run_unreleased')


def source_root(row):
    from .session_discovery_native import read_object,_local_path
    output=_local_path(Path(row['output_path']),directory=True)
    sources=read_object(_local_path(output/'sources.json'))[0]
    if sources.get('kind')!='pre_execution_macro_host_sources':raise ContractError('run_history_unverifiable')
    entry=sources['sources'][0];path=Path(entry['path'])
    if (path.name!='macro_host.py' or path.parent.name!='integration' or entry['copy']!='0-macro_host.py'
            or hashlib.sha256(_local_path(output/'source'/entry['copy']).read_bytes()).hexdigest()!=entry['sha256']):
        raise ContractError('run_history_unverifiable')
    return _local_path(path.parent.parent,directory=True)


class FileReviewContext:
    """Copies of trusted pure verifier functions with historical file context.

    Their bytecode is the installed, pinned verifier, never old input code.
    __file__/ROOT are file identities used by existing SHA/provenance checks;
    actual old bytes are still read and hashed by those original contracts.
    This leaves imported live modules/globals untouched and never dispatches.
    """
    def __init__(self,root):
        self.root=root;self.modules={};self.package=Path(__file__).resolve().parents[2]
        self.util=SimpleNamespace(**dict(vars(importlib.util),spec_from_file_location=self.spec))
        self.importlib=SimpleNamespace(**dict(vars(importlib),util=self.util,import_module=self.dynamic_import))
    def allowed_origin(self,path):
        try:
            path=Path(path).absolute()
            if '..' in path.parts:return False
            return any(path.is_relative_to(root) for root in (self.package,Path(sys.prefix),Path(sys.base_prefix)))
        except (OSError,ValueError,TypeError):return False
    def safe_paths(self):return [entry for entry in sys.path if self.allowed_origin(entry or '.')]
    def allowed_module(self,module):
        if getattr(module,'_tacticore_review_context',None) is self:return True
        paths=getattr(module,'__path__',None)
        if paths is not None and (not list(paths) or not all(self.allowed_origin(p) for p in paths)):return False
        spec=getattr(module,'__spec__',None)
        if getattr(spec,'origin',None) in ('built-in','frozen'):return True
        origin=getattr(module,'__file__',None)
        if origin:return self.allowed_origin(origin)
        return paths is not None and bool(list(paths)) and all(self.allowed_origin(p) for p in paths)
    def check_cached(self,name,fromlist):
        fromlist=fromlist or ()
        # Python resolves dotted/from imports using cached parent __path__,
        # independently of sys.path. Validate every parent and preloaded child
        # before asking its importer to execute anything.
        names=['.'.join(name.split('.')[:i]) for i in range(1,len(name.split('.'))+1)]
        names.extend(name+'.'+item for item in fromlist if isinstance(item,str) and item!='*')
        for item in names:
            module=sys.modules.get(item)
            if module is not None and not self.allowed_module(module):raise ContractError('run_history_unverifiable')
        parent=sys.modules.get(name)
        if parent is not None:
            for item in fromlist:
                child=vars(parent).get(item)
                if isinstance(child,ModuleType) and not self.allowed_module(child):raise ContractError('run_history_unverifiable')
    def dynamic_import(self,name,package=None):
        name=importlib.util.resolve_name(name,package) if name.startswith('.') else name
        if name.startswith('host_runtime.'):return self.module(name)
        return self.import_module(name,None,None,('*',),0)
    def trusted_source(self,path):
        relative=Path(path).relative_to(self.root)
        if '..' in relative.parts:raise ContractError('run_history_unverifiable')
        source=self.package/relative;raw=source.read_bytes()
        if self.package.name=='app':
            manifest=self.package.parent/'manifest.json';data=manifest.read_bytes()
            from .native6_qualification import trusted_pin
            if hashlib.sha256(data).hexdigest()!=trusted_pin():raise ContractError('run_history_unverifiable')
            expected=json.loads(data)['files'].get('app/'+relative.as_posix())
            if expected!=hashlib.sha256(raw).hexdigest():raise ContractError('run_history_unverifiable')
        return raw
    def spec(self,name,path,*args,**kwargs):
        context=self;logical=Path(path)
        # Explicit builder/SDK loaders must execute installed pinned code,
        # never bytes from an old developer tree before their hash checks.
        class Loader(importlib.abc.Loader):
            def create_module(self,spec):return None
            def exec_module(self,module):
                module.__file__=str(logical)
                module.__dict__['__builtins__']=dict(vars(builtins),__import__=context.import_module)
                module.__dict__['importlib']=context.importlib
                module.__dict__['_tacticore_review_context']=context
                exec(compile(context.trusted_source(logical),str(logical),'exec'),module.__dict__)
        return importlib.util.spec_from_loader(name,Loader(),origin=str(logical))
    def module(self,name):
        if name in self.modules:return self.modules[name]
        original=list(sys.path)
        try:
            sys.path[:]=self.safe_paths()
            actual=importlib.import_module(name)
        finally:sys.path[:]=original
        if Path(actual.__file__).parent!=Path(__file__).parent:raise ContractError('run_history_unverifiable')
        values=dict(vars(actual));proxy=SimpleNamespace();self.modules[name]=proxy
        values['__file__']=str(self.root/'integration/host_runtime'/Path(actual.__file__).name)
        if 'ROOT' in values:values['ROOT']=self.root
        for key,value in list(values.items()):
            if value is importlib:values[key]=self.importlib
            elif value is importlib.util:values[key]=self.util
            elif isinstance(value,ModuleType) and value.__name__.startswith('host_runtime.'):
                values[key]=self.module(value.__name__)
            elif isinstance(value,Path) and value.is_relative_to(Path(__file__).resolve().parents[2]):
                values[key]=self.root/value.relative_to(Path(__file__).resolve().parents[2])
        values['__builtins__']=dict(vars(builtins),__import__=self.import_module)
        for key,value in list(values.items()):
            if isinstance(value,FunctionType) and value.__module__==name:
                clone=FunctionType(value.__code__,values,value.__name__,value.__defaults__,value.__closure__)
                clone.__kwdefaults__=value.__kwdefaults__;values[key]=clone
        proxy.__dict__.update(values);return proxy
    def import_module(self,name,globals=None,locals=None,fromlist=(),level=0):
        if level==1 and globals and globals.get('__package__')=='host_runtime':
            if name:return self.module('host_runtime.'+name)
            return SimpleNamespace(**{item:self.module('host_runtime.'+item) for item in fromlist})
        if level==0 and name=='importlib.util':return self.importlib if not fromlist else self.util
        if level==0 and name=='importlib':return self.importlib
        self.check_cached(name,fromlist)
        # A ported SDK can import sibling readers after inserting the old
        # directory into sys.path. Resolve app modules from this companion;
        # remove old search paths for all other imports. No old source fallback.
        if level==0 and name not in sys.modules:
            parts=Path(*name.split('.'))
            for folder in ('production','native-ai','strategy','integration','visibility',''):
                relative=Path(folder)/parts.with_suffix('.py')
                if (self.package/relative).is_file():
                    spec=self.spec(name,self.root/relative);module=importlib.util.module_from_spec(spec)
                    sys.modules[name]=module
                    try:spec.loader.exec_module(module)
                    except BaseException:sys.modules.pop(name,None);raise
                    return module
        original=list(sys.path)
        try:
            sys.path[:]=self.safe_paths()
            return builtins.__import__(name,globals,locals,fromlist,level)
        finally:sys.path[:]=original


def closed_status(backend,row):
    from .session_discovery_native import read_object,_local_path
    binding=SessionBinding.from_dict(json.loads(row['binding_json']))
    start=backend.journal.get_command(row['run_id'],row['request_id']);receipt=start.get('receipt') or {}
    if (start['operation']=='host_start' and start['status']=='cancelled'
            and receipt.get('reason_code')=='host_launch_cancelled_before_dispatch'
            and receipt.get('host_spawn_attempted') is False and receipt.get('native_delivery_attempted') is False
            and len(backend.journal.commands_for_run(row['run_id']))==1):
        return dict(run_id=row['run_id'],session_id=binding.session_id,state='stopped',native_release_verified=True,no_native_execution_started=True)
    host_ended(receipt)
    status,_=read_object(_local_path(Path(row['output_path'])/'host-status.json'),1024*1024)
    macro=start['payload'].get('capabilities',{}).get('native_macro') is True
    runtime=status.get('runtime_macro' if macro else 'runtime_production',{})
    if (runtime.get('run_id')!=row['run_id'] or runtime.get('binding_hash')!=binding.binding_hash
            or status.get('session_id')!=binding.session_id or status.get('pid')!=binding.game_process_id
            or status.get('process_start')!=binding.game_process_start
            or any(status.get(k)!=receipt.get(k) for k in ('host_pid','host_start_time'))):raise ContractError('run_history_unverifiable')
    if macro:
        backend.historical_report_root=source_root(row)
        cache=getattr(backend,'_file_review_contexts',{})
        if backend.historical_report_root not in cache:cache[backend.historical_report_root]=FileReviewContext(backend.historical_report_root)
        backend._file_review_contexts=cache
        original=list(sys.path)
        try:verified=cache[backend.historical_report_root].module('host_runtime.macro_desktop').released(backend,row['run_id'],binding,receipt)
        finally:sys.path[:]=original
    else:verified=backend._release_receipt(row['run_id'],binding,receipt)
    state=status['state']
    if (verified and macro and (Path(row['output_path'])/'native-orphan-return.json').exists()
            and receipt.get('reason_code')=='host_process_lost_control_returned'):
        state='fault'  # same read-only lost-Host projection as the original backend
    return dict(run_id=row['run_id'],session_id=binding.session_id,state=state,native_release_verified=verified)


def open_history(state):
    from .session_history_review import open_offline_backend
    backend=open_offline_backend(state)
    backend._db.execute('PRAGMA query_only=ON');backend.journal._db.execute('PRAGMA query_only=ON')
    backend._status=MethodType(closed_status,backend)
    return backend
