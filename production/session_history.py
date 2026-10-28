"""Read the current local unknown-session denylist; never copy it into a release.

A manifest-bound companion may reference its registered source root for safety
metadata. Code and native executors remain inside the immutable companion.
"""
import json
from pathlib import Path
import uuid


def unknown_session(session_id, *, bridge_root=None):
    root=Path(bridge_root or Path(__file__).resolve().parent.parent)
    ident=str(uuid.UUID(session_id))
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('duplicate_history_key')
            value[key]=item
        return value
    def read(path, maximum):
        with path.open('rb') as stream:raw=stream.read(maximum+1)
        if len(raw)>maximum:raise ValueError('history_too_large')
        return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs)
    try:
        layout=root/'companion-layout.json'
        if layout.exists():
            registered=read(layout,16384)
            if (set(registered)!={'schema_version','source_root'} or type(registered['schema_version']) is not int
                or registered['schema_version']!=1):raise ValueError('invalid_companion_history_root')
            root=Path(registered['source_root'])
            if not root.is_absolute() or str(root).startswith('\\\\') or root.is_symlink():
                raise ValueError('invalid_companion_history_root')
        records=read(root/'production/unknown_sessions.json',1024*1024)
        if not isinstance(records,dict) or any(str(uuid.UUID(key))!=key or not isinstance(value,dict) for key,value in records.items()):
            raise ValueError('invalid_session_history')
        return ident in records
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        raise RuntimeError('session_history_unavailable') from None
