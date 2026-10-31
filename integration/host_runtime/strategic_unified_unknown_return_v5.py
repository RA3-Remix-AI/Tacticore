"""Separate returned ownership from historical unknown strategic delivery.

Caller must first verify the complete Native5 epoch return. This pure check
only permits its own high-level parent/child records created before STOP;
it never edits those records, grants effects, or permits a command retry.
"""
from .strategic_contract_v5 import split_intents
import uuid


def unresolved_ownership(backend,row,status):
    """Project outstanding control; retain original uncertain delivery rows."""
    unresolved=backend.journal.unresolved(row['run_id'])
    if not unresolved or status.get('native_release_verified') is not True:return unresolved
    # Never apply this exception to an older/fine-control channel.
    import json
    from pathlib import Path
    from .contracts import SessionBinding
    from .session_discovery_native import frozen_epoch
    try:
        binding=SessionBinding.from_dict(json.loads(row['binding_json']))
        session=json.loads(Path(row['session_path']).read_bytes())
        if (frozen_epoch(row,session,binding) in (5,6) and covered_unknown_ownership(unresolved,
                backend.journal.commands_for_run(row['run_id']),backend.journal.get_command(row['run_id'],'macro-stop'))):return []
    except (ValueError,KeyError,TypeError,OSError):pass
    return unresolved


def covered_unknown_ownership(unresolved,commands,stop):
    try:
        parents={r['request_id']:r for r in commands if r['operation']=='macro_policy'}
        def parent_ok(row):
            p=row['payload']
            expected=set(('actions','plan_id','native_command_id','duration_frames','not_after_frame','unit_operation_policy'))
            if (set(p) not in (expected,expected|{'admission_id'})
                    or p['native_command_id']!=row['request_id'] or p['unit_operation_policy']!='native_ai'):return False
            if 'admission_id' in p and str(uuid.UUID(p['admission_id']))!=p['admission_id']:return False
            split_intents(p['actions']);return True
        for row in unresolved:
            if row['status']!='uncertain' or row['created_at']>stop['created_at']:return False
            if row['operation']=='macro_policy':
                if not parent_ok(row):return False
            elif row['operation']=='native_strategic_v5':
                p=row['payload'];parent=parents.get(p.get('parent_command_id'))
                if parent is None or not parent_ok(parent) or parent['created_at']>row['created_at']:return False
                if 'actions' in p:
                    if set(p)!=set(('parent_command_id','actions','duration_frames','not_after_frame')):return False
                    split_intents(p['actions'])
                elif (set(p)!=set(('parent_command_id','gate','enabled','release','duration_frames','not_after_frame'))
                        or type(p['gate']) is not int or p['gate'] not in (0,1)
                        or type(p['release']) is not bool
                        or (p['enabled'] is not None and type(p['enabled']) is not bool)):return False
            else:return False
        return True
    except (KeyError,TypeError,ValueError):return False
