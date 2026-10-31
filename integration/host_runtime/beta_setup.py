"""Native-owned beta installation preparation, without a fabricated match.

Only the native file picker supplies input paths. Nothing here opens Game
memory, calls a provider or grants an execution capability. A real session is
created later by the existing discover/prepare broker and live admission.
"""
from dataclasses import asdict,fields
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from .contracts import ContractError,identifier,object_fields
from .native6_paths import known_folder,LOCAL_APP_DATA,DOCUMENTS,plain_local
from .native6_qualification import current,create,COMMANDER,MAP_ID
from .native6_runtime_contract import GAME_SHA,PACKAGE_SHA,read,sha
from .session_discovery import DiscoveryPolicy,TrustedFiles,TERMINAL

VERSION='0.1.0-beta.1'
KIND='native6_installed_discovery_v1'


def locations():
    # MSIX desktop callers can see an ordinary-looking directory whose final
    # physical path is LocalCache. Reject reparse points first, then use the
    # OS-resolved directory identity consistently for metadata/SQLite paths.
    legacy=plain_local(known_folder(LOCAL_APP_DATA)/'Tacticore',existing=False).resolve()
    home=legacy/'beta1';state=home/'desktop-runtime'
    mods=known_folder(DOCUMENTS)/'Red Alert 3/Mods/Tacticore-beta1'
    return home,state,mods,legacy


def quiet(state,*,require_process_exit=False,legacy=False):
    """Check every recorded run with existing independent return contracts.

    Never erase a ledger to make a new namespace look idle. Unknown return is
    a blocker. The old and beta states are both checked before source changes.
    """
    state=plain_local(state,existing=False).resolve()
    if not state.exists():return
    plain_local(state)
    if not any((state/name).exists() for name in ('desktop-launch-index.sqlite3','host-runtime.sqlite3')):return
    from .desktop_backend import DesktopBackend
    from .session_discovery_native import run_records
    from types import SimpleNamespace
    if legacy:
        from .beta_history import open_history
        backend=open_history(state)
    else:backend=DesktopBackend(SimpleNamespace(state_dir=state))
    try:
        for row in run_records(backend):
            if row.state not in TERMINAL or not row.native_release_verified or row.unresolved_count:
                raise ContractError('beta_existing_run_unreleased')
        if require_process_exit:
            from .native5_helper_identity_v1 import process_identity
            from .session_discovery_native import require_creation
            from .session_discovery_native import Win32ReadOnly
            current_games=set(Win32ReadOnly().process_ids('RA3_1.12.game'))
            for row in backend._db.execute('SELECT * FROM launches').fetchall():
                binding=json.loads(row['binding_json'])
                game_pid=binding['game_process_id']
                if game_pid not in current_games:continue
                try:actual=process_identity(game_pid)
                except OSError as error:
                    if getattr(error,'winerror',None)==87:continue
                    raise ContractError('beta_process_exit_unknown') from None
                if actual['alive']:
                    try:require_creation(binding['game_process_start'],actual['process_creation_filetime'])
                    except ContractError:continue  # a different OS incarnation
                    raise ContractError('beta_exit_game_before_update')
    finally:backend.close()


def guard_states(*,require_process_exit=False):
    home,state,mods,legacy=locations()
    quiet(legacy/'desktop-runtime',require_process_exit=require_process_exit,legacy=True)
    quiet(state,require_process_exit=require_process_exit)


def exact_file(path,raw):
    path=plain_local(path,existing=False)
    path.parent.mkdir(parents=True,exist_ok=True)
    plain_local(path.parent)
    try:
        with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes()!=raw:raise ContractError('beta_owned_file_conflict')


def prepare(game,mod):
    root,pin,inventory,build,cap=current()
    game,mod=plain_local(game),plain_local(mod)
    if game.name.lower()!='ra3_1.12.game' or sha(game)!=GAME_SHA:raise ContractError('beta_game_unsupported')
    if mod.suffix.lower()!='.big' or sha(mod)!=PACKAGE_SHA:raise ContractError('beta_mod_unsupported')
    launcher=plain_local(game.parent.parent/'RA3.exe')
    guard_states()
    home,state,mods,legacy=locations()
    for folder in (home,state,mods,state/'sessions'):
        plain_local(folder,existing=False);folder.mkdir(parents=True,exist_ok=True);plain_local(folder)
    destination=mods/'TFCommander.big'
    if destination.exists():
        if sha(destination)!=PACKAGE_SHA:raise ContractError('beta_owned_file_conflict')
    else:
        # An interrupted copy is kept separate; it is never accepted as the Mod.
        temporary=mods/(uuid.uuid4().hex+'.partial')
        with mod.open('rb') as source,temporary.open('xb') as target:
            shutil.copyfileobj(source,target);target.flush();os.fsync(target.fileno())
        if sha(temporary)!=PACKAGE_SHA or sha(mod)!=PACKAGE_SHA:raise ContractError('beta_mod_changed')
        # Rename without replacing unrelated or concurrently created content.
        temporary.rename(destination)
    config=mods/'TFCommander_1.0.SkuDef'
    exact_file(config,b'mod-game 1.12\nadd-big TFCommander.big\n')
    descriptor=state/'sessions/native6-trial.json'
    if descriptor.exists():
        from .native6_qualification import load
        load(descriptor)
    else:create(descriptor)
    from .session_discovery_native import SCOPE,NAME
    values=dict(game=game,mod_config=config,mod_big=destination,registry=root/'qualification/registry.json',
        macro_bundle=descriptor,package_report=root/'qualification/package.json')
    pins={}
    for key,path in values.items():
        pins[key]=str(path);pins['mod_sha256' if key=='mod_big' else key+'_sha256']=sha(path)
    record=dict(schema_version=2,kind=KIND,policy_id=str(uuid.uuid4()),session_root=str(state/'sessions'),
        runtime_manifest_sha256=pin,files=pins,scope=dict(SCOPE,native_epoch=6))
    target=state/NAME
    if target.exists():
        old=read(target)
        if {k:v for k,v in old.items() if k!='policy_id'}!={k:v for k,v in record.items() if k!='policy_id'}:
            raise ContractError('beta_setup_changed_requires_migration')
        record=old
    else:
        from .desktop_session_registry import register_root
        register_root(state/'sessions',state)
        exact_file(target,(json.dumps(record,sort_keys=True)+'\n').encode())
    exact_file(state/'game-launch.json',(json.dumps(dict(schema_version=1,launcher=str(launcher),launcher_sha256=sha(launcher),
        game=str(game),game_sha256=GAME_SHA,mod_config=str(config),mod_config_sha256=sha(config)),sort_keys=True)+'\n').encode())
    return dict(schema_version=1,prepared=True,version=VERSION,game_verified=True,mod_verified=True,
        requires_live_discovery=True,host_started=False,native_commands_issued=0,model_requests=0)


def load_policy(state,record):
    root,pin,inventory,build,cap=current()
    home,expected,mods,legacy=locations()
    if Path(state)!=expected:raise ContractError('discovery_policy_invalid')
    object_fields(record,{'schema_version','kind','policy_id','session_root','runtime_manifest_sha256','files','scope'})
    from .session_discovery_native import SCOPE,validate_mod_file
    if (type(record['schema_version']) is not int or record['schema_version']!=2 or record['kind']!=KIND
            or record['runtime_manifest_sha256']!=pin or record['scope']!=dict(SCOPE,native_epoch=6)
            or Path(record['session_root'])!=expected/'sessions'):raise ContractError('discovery_policy_invalid')
    identifier(record['policy_id'])
    object_fields(record['files'],{field.name for field in fields(TrustedFiles)})
    cooked={key:plain_local(value) if field.type is Path else value for field in fields(TrustedFiles)
            for key,value in ((field.name,record['files'][field.name]),)}
    files=TrustedFiles(**cooked)
    # dataclasses may retain postponed type names in the shared broker.
    for key in ('game','mod_config','mod_big','registry','macro_bundle','package_report'):
        object.__setattr__(files,key,plain_local(getattr(files,key)))
        digest='mod_sha256' if key=='mod_big' else key+'_sha256'
        if sha(getattr(files,key))!=getattr(files,digest):raise ContractError('discovery_source_changed')
    if (files.game.name.lower()!='ra3_1.12.game' or files.game_sha256!=GAME_SHA or files.mod_sha256!=PACKAGE_SHA
            or files.mod_big!=mods/'TFCommander.big' or files.mod_config!=mods/'TFCommander_1.0.SkuDef'
            or files.registry!=root/'qualification/registry.json' or files.package_report!=root/'qualification/package.json'
            or files.macro_bundle!=expected/'sessions/native6-trial.json'):raise ContractError('discovery_policy_invalid')
    from .native6_qualification import load
    load(files.macro_bundle);validate_mod_file(files.mod_config,files.mod_big)
    return record,DiscoveryPolicy(files,plain_local(expected/'sessions'),plain_local(expected),**record['scope'])


def status():
    home,state,mods,legacy=locations()
    from .session_discovery_native import NAME
    target=state/NAME
    if not target.exists():return dict(schema_version=1,prepared=False,version=VERSION)
    load_policy(state,read(target))
    return dict(schema_version=1,prepared=True,version=VERSION,game_verified=True,mod_verified=True,
        requires_live_discovery=True,host_started=False)


def launch():
    guard_states();home,state,mods,legacy=locations()
    from .session_discovery_native import NAME,Win32ReadOnly
    _,policy=load_policy(state,read(state/NAME))
    if Win32ReadOnly().process_ids('RA3_1.12.game'):raise ContractError('beta_game_already_running')
    record=read(state/'game-launch.json');launcher=plain_local(record['launcher'])
    if (launcher!=policy.files.game.parent.parent/'RA3.exe' or sha(launcher)!=record['launcher_sha256']
            or record['game']!=str(policy.files.game) or record['game_sha256']!=policy.files.game_sha256
            or record['mod_config']!=str(policy.files.mod_config) or record['mod_config_sha256']!=policy.files.mod_config_sha256):
        raise ContractError('beta_game_launcher_changed')
    # User's explicit native button; fixed arguments only. Discovery later
    # validates the actual Game image/incarnation, package, map and own UUID.
    subprocess.Popen([str(launcher),'-modconfig',str(policy.files.mod_config)],cwd=launcher.parent,
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    return dict(schema_version=1,game_launch_requested=True,host_started=False,model_requests=0)


def main():
    # This pipe is launched only by the native command; it is not a WebView
    # RPC operation. Native owns both paths; output never exposes them.
    import sys
    from .bridge_service import decode_request
    request=decode_request(sys.stdin.buffer.readline(65537));operation=request.get('operation')
    try:
        if operation=='status':object_fields(request,{'operation'});result=status()
        elif operation=='prepare':object_fields(request,{'operation','game','mod'});result=prepare(request['game'],request['mod'])
        elif operation=='launch':object_fields(request,{'operation'});result=launch()
        elif operation=='guard':object_fields(request,{'operation'});guard_states(require_process_exit=True);result={'quiet':True}
        else:raise ContractError('operation_unsupported')
        print(json.dumps(dict(ok=True,result=result)))
        return 0
    except ContractError as error:
        print(json.dumps(dict(ok=False,error=dict(code=error.code))));return 2
    except (OSError,ValueError,KeyError,TypeError):
        print(json.dumps(dict(ok=False,error=dict(code='beta_setup_unavailable'))));return 2


if __name__=='__main__':raise SystemExit(main())
