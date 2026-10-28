"""Trusted, explicit session-root bootstrap. Not exposed through WebView RPC."""
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3
from pathlib import Path
import uuid
from .contracts import ContractError, identifier, object_fields
from .journal import JournalError

NAME='session-root-registration.json'


def load_root(state_dir):
    path=Path(state_dir)/NAME
    if not path.exists():return None
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ContractError('session_root_invalid')
            value[key]=item
        return value
    try:
        with path.open('rb') as stream:raw=stream.read(16385)
        if len(raw)>16384:raise ValueError()
        record=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
        object_fields(record,{'schema_version','registration_id','session_root'})
        if type(record['schema_version']) is not int or record['schema_version']!=1:raise ValueError()
        identifier(record['registration_id'])
        root=Path(record['session_root'])
        if not root.is_absolute() or str(root).startswith('\\\\') or not root.is_dir() or root.is_symlink():raise ValueError()
        if getattr(root.lstat(),'st_file_attributes',0)&0x400:raise ValueError()
        if root.resolve(strict=True)!=root:raise ValueError()
        return dict(record,fingerprint=hashlib.sha256(raw).hexdigest())
    except (OSError,TypeError,ValueError,UnicodeError,RecursionError,ContractError):
        raise ContractError('session_root_invalid') from None


def register_root(root,state_dir):
    root=Path(root)
    if not root.is_absolute() or str(root).startswith('\\\\') or not root.is_dir() or root.is_symlink():
        raise ContractError('session_root_invalid')
    if getattr(root.lstat(),'st_file_attributes',0)&0x400:raise ContractError('session_root_invalid')
    root=root.resolve(strict=True);state_dir=Path(state_dir);state_dir.mkdir(parents=True,exist_ok=True)
    existing=load_root(state_dir)
    if existing:
        if existing['session_root']!=str(root):raise ContractError('session_root_conflict')
        return existing
    record=dict(schema_version=1,registration_id=str(uuid.uuid4()),session_root=str(root))
    try:
        with (state_dir/NAME).open('x',encoding='utf-8') as stream:
            json.dump(record,stream,ensure_ascii=False,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    except FileExistsError:raise ContractError('session_root_conflict') from None
    return load_root(state_dir)


def register_session_source(store,root,session,production=None,persistent=None,*,replace_stopped=False,runtime_report=None,runtime_sha256=None,
                            runtime_recovery_report=None,runtime_recovery_sha256=None,macro_bundle=None):
    # Validate every path before creating any registration. No game/model access.
    from .desktop_backend import DesktopBackend,SessionRegistration
    root=Path(root)
    if not root.is_absolute() or str(root).startswith('\\\\') or root.is_symlink():raise ContractError('session_root_invalid')
    root=root.resolve(strict=True)
    registration=SessionRegistration.trusted(session,production,persistent,root=root,
        runtime_report=runtime_report,runtime_sha256=runtime_sha256,
        runtime_recovery_report=runtime_recovery_report,runtime_recovery_sha256=runtime_recovery_sha256,macro_bundle=macro_bundle)
    existing_root=load_root(store.state_dir)
    if existing_root and existing_root['session_root']!=str(root):raise ContractError('session_root_conflict')
    backend=DesktopBackend(store,registration_root=root)
    try:
        rows=backend._db.execute('SELECT * FROM launches').fetchall()
        try:
            old=backend._registration() if backend.registration_path.exists() else None
        except ContractError:
            # Lobby verification legitimately changes the recorded session before
            # the first launch. Only an explicit trusted replacement can refresh
            # that pin, and every existing launch still needs verified release.
            if not replace_stopped:raise
            old=object()
        if old!=registration and (old is not None or rows):
            if not replace_stopped:raise ContractError('session_registration_conflict')
            for row in rows:
                status=backend._status(row)
                if (status.get('state') not in ('stopped','completed','fault','result_candidate') or status.get('native_release_verified') is not True
                    or backend.journal.unresolved(row['run_id'])):
                    raise ContractError('run_state_conflict')
        record=register_root(root,store.state_dir)
        backend.register_session(registration.session_path,registration.production_report,registration.persistent_status,
            runtime_report=registration.runtime_report,runtime_sha256=registration.runtime_sha256,
            runtime_recovery_report=registration.runtime_recovery_report,runtime_recovery_sha256=registration.runtime_recovery_sha256,macro_bundle=registration.macro_bundle)
        return dict(schema_version=1,registered=True,root_registration_id=record['registration_id'],root_fingerprint=record['fingerprint'],session_registration_sha256=hashlib.sha256(backend.registration_path.read_bytes()).hexdigest(),restart_required=True,game_access=False,credentials_copied=False)
    finally:backend.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('session-root','session'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('production-report','persistent-status','macro-bundle'):parser.add_argument('--'+name,type=Path)
    parser.add_argument('--runtime-report',type=Path)
    parser.add_argument('--runtime-sha256')
    parser.add_argument('--runtime-recovery-report',type=Path)
    parser.add_argument('--runtime-recovery-sha256')
    parser.add_argument('--replace-stopped',action='store_true')
    args=parser.parse_args(argv)
    from .desktop_registry import load_registration
    from .profile_store import ProfileStore
    store=None
    try:
        home=Path(os.environ['LOCALAPPDATA'])/'Tacticore';library=load_registration(home)
        store=ProfileStore(Path(library['library_path']),home/'desktop-runtime')
        result=register_session_source(store,args.session_root,args.session,args.production_report,args.persistent_status,
            replace_stopped=args.replace_stopped,runtime_report=args.runtime_report,runtime_sha256=args.runtime_sha256,
            runtime_recovery_report=args.runtime_recovery_report,runtime_recovery_sha256=args.runtime_recovery_sha256,macro_bundle=args.macro_bundle)
        print(json.dumps(result));return 0
    except (ContractError,OSError,ValueError,KeyError,sqlite3.Error,JournalError) as error:
        print(json.dumps(dict(registered=False,reason_code=error.code if isinstance(error,ContractError) else 'session_registration_unavailable')));return 2
    finally:
        if store is not None:store.close()


if __name__=='__main__':raise SystemExit(main())
