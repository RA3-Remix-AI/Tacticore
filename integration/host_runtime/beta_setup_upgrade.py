"""Replace setup metadata only after every original control owner returned."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import os
import uuid

from .contracts import ContractError
from .native6_paths import plain_local
from .native6_runtime_contract import sha

DATABASES=('desktop-launch-index.sqlite3','host-runtime.sqlite3')

def require_indexes(state):
    if not all((state/name).is_file() for name in DATABASES):
        raise ContractError('beta_setup_changed_requires_migration')

def no_game():
    from .session_discovery_native import Win32ReadOnly
    api=Win32ReadOnly()
    if any(api.process_ids(name) for name in ('RA3_1.12.game','RA3.exe')):
        raise ContractError('beta_game_already_running')

@contextmanager
def returned(state):
    require_indexes(state);no_game();connections=[]
    try:
        for name in DATABASES:
            path=plain_local(state/name)
            db=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,isolation_level=None,timeout=5)
            connections.append(db);db.execute('BEGIN IMMEDIATE')
        bindings={row[0]:json.loads(row[1]) for row in connections[0].execute('SELECT run_id,binding_json FROM launches')}
        runs={row[0]:json.loads(row[1]) for row in connections[1].execute('SELECT run_id,binding FROM runs')}
        ids=set(bindings)
        if bindings!=runs:raise ContractError('beta_setup_changed_requires_migration')
        counts={'launches':len(ids)}
        for table in ('commands','events','native_sequences'):
            rows=connections[1].execute('SELECT run_id FROM '+table).fetchall()
            if any(row[0] not in ids for row in rows):raise ContractError('beta_setup_changed_requires_migration')
            counts[table]=len(rows)
        from .beta_setup import quiet
        quiet(state,require_process_exit=True)
        no_game()
        yield dict(kind='independently_returned_setup_preserved' if ids else 'never_started_setup_preserved',
            original_rows=counts,records_deleted=False,records_rewritten=False)
    except ContractError:raise
    except (sqlite3.Error,ValueError,TypeError):raise ContractError('beta_setup_changed_requires_migration') from None
    finally:
        for db in reversed(connections):
            if db.in_transaction:db.execute('ROLLBACK')
            db.close()

def preserve(state,policy_path,old,expected_sha,*,history=None):
    if sha(policy_path)!=expected_sha:raise ContractError('discovery_source_changed')
    if old.get('schema_version')!=2 or old.get('kind')!='native6_installed_discovery_v1':
        raise ContractError('beta_setup_changed_requires_migration')
    bundle=plain_local(old['files']['macro_bundle'])
    if (bundle.parent!=state/'sessions' or not re.fullmatch(r'native6-trial(?:-[0-9a-f]{64})?\.json',bundle.name)
            or sha(bundle)!=old['files']['macro_bundle_sha256']):
        raise ContractError('beta_setup_changed_requires_migration')
    from .contracts import identifier
    identifier(old['policy_id'])
    paths=[policy_path,bundle]
    for name in ('game-launch.json','game-launch-'+old['policy_id']+'.json'):
        path=state/name
        if path.exists():paths.append(plain_local(path))
    archive=plain_local(state/'setup-history'/expected_sha,existing=False)
    archive.mkdir(parents=True,exist_ok=True);plain_local(archive)
    pins={}
    for path in paths:
        raw=path.read_bytes();target=plain_local(archive/path.name,existing=False);pins[path.name]=sha(path)
        try:
            with target.open('xb') as output:output.write(raw);output.flush();os.fsync(output.fileno())
        except FileExistsError:
            if target.read_bytes()!=raw:raise ContractError('beta_owned_file_conflict')
        if sha(path)!=pins[path.name] or sha(target)!=pins[path.name]:raise ContractError('discovery_source_changed')
    index=archive/'preservation.json'
    raw=(json.dumps(dict(history or dict(kind='never_started_setup_preserved',launch_rows=0,host_command_rows=0,
        records_deleted=False),old_policy_sha256=expected_sha,files=pins),sort_keys=True)+'\n').encode()
    try:
        with index.open('xb') as output:output.write(raw);output.flush();os.fsync(output.fileno())
    except FileExistsError:
        if index.read_bytes()!=raw:raise ContractError('beta_owned_file_conflict')

def replace_policy(path,raw,expected_sha):
    temporary=path.parent/(uuid.uuid4().hex+'.setup.partial')
    with temporary.open('xb') as output:output.write(raw);output.flush();os.fsync(output.fileno())
    if sha(path)!=expected_sha:raise ContractError('discovery_source_changed')
    os.replace(temporary,path)
