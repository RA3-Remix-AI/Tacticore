"""Project a fully returned admission fault that never published Host status.

Caller first checks that the original Host incarnation ended. A present status
file, even malformed, still goes through the ordinary strict status reader.
This path writes no replacement file and never captures fresh return evidence.
"""
from pathlib import Path


def missing_status_projection(backend,row,binding,start):
    caps=(start.get('payload') or {}).get('capabilities',{})
    receipt=start.get('receipt') or {}
    if (start.get('operation')!='host_start' or start.get('status')!='completed'
            or caps.get('native_macro') is not True
            or type(caps.get('native_transport_protocol')) is not int or caps['native_transport_protocol']!=6
            or receipt.get('reason_code')!='host_process_lost_control_returned'):
        return None
    output=Path(row['output_path'])
    if not (output/'native6-context.json').is_file():return None
    try:(output/'host-status.json').lstat()
    except FileNotFoundError:pass
    else:return None
    from .native6_orphan_return import KIND as ORPHAN
    stop=backend.journal.get_command(row['run_id'],'macro-stop')
    if stop['status']!='released' or (stop.get('receipt') or {}).get('native_release_contract')!=ORPHAN:
        return None
    from .native6_history import verified_return
    if not verified_return(backend,row,binding,receipt):return None
    return dict(run_id=row['run_id'],session_id=binding.session_id,state='fault',native_release_verified=True)
