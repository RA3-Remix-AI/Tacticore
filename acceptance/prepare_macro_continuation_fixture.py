"""Report why the current native runtime cannot resume an already-used epoch.

This is an intentionally blocked draft, not a fixture creator. It reads frozen
local evidence only, never opens a live process/object, and never changes the
ledger, creates a run, starts/stops a process, injects, or dispatches.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration')]
from host_runtime.contracts import SessionBinding,identifier
from host_runtime.macro_policy_runtime import trial,COMMANDER

NATIVE_STOP=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def plain(path):
    path=Path(path)
    for item in (path,*path.parents):
        if item.is_symlink():raise ValueError('continuation_reparse_path')
        if item.exists() and getattr(item.lstat(),'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
            raise ValueError('continuation_reparse_path')
    return path


def read(path,pins):
    path=plain(plain(Path(path).absolute()).resolve(strict=True))
    if not path.is_file() or path.stat().st_size>128*1024*1024:raise ValueError('continuation_input_bounds')
    raw=path.read_bytes();pins[str(path)]=digest(raw);return raw


def obj(path,pins):return json.loads(read(path,pins).decode('utf-8-sig'))


def prepare(source,output,ledger=None,*,dry_run=False,root=ROOT,probe=None):
    """Compatibility report only. ledger/probe are deliberately never used.

    The retained arguments keep old draft callers fail-closed. Even complete
    clean-stop evidence cannot authorize reattachment of this pinned runtime.
    """
    root=Path(root).resolve();runs=plain(root/'acceptance/runs').resolve(strict=True)
    source=plain(plain(Path(source).absolute()).resolve(strict=True));old=source.parent
    output=plain(plain(Path(output).absolute()).resolve())
    if (not old.is_relative_to(runs) or old==runs or source.name not in ('session.json','desktop-session.json')
            or output.parent!=runs or output.exists()):raise ValueError('continuation_fresh_owned_run_required')
    pins={};session=obj(source,pins);host=old/'battle-host';status=obj(host/'host-status.json',pins)
    release=obj(host/'macro-release.json',pins)
    if Path(session.get('run_directory','')).resolve()!=old:raise ValueError('continuation_source_directory_mismatch')
    if (status.get('state') not in ('stopped','fault') or release.get('native_release_verified') is not True
            or status.get('pid')!=session.get('pid') or status.get('process_start')!=session.get('start_time')
            or status.get('session_id')!=session.get('session_id')):raise ValueError('continuation_verified_host_stop_required')
    binding=SessionBinding(**release['binding']);run_id=identifier(release['run_id'])
    if (binding.player_id!=3 or binding.commander_id!=COMMANDER or binding.session_id!=session['session_id']
            or binding.game_process_id!=session['pid'] or binding.game_process_start!=session['start_time']
            or binding.mod_sha256!=session['mod_sha256']
            or status.get('runtime_macro')!={'run_id':run_id,'binding_hash':binding.binding_hash}
            or any(status.get(k)!=release.get(k) for k in ('host_pid','host_start_time'))):
        raise ValueError('continuation_release_binding')
    transport=root/'reports'/('macro-desktop-'+run_id)
    for name in ('preflight.json','final-state.json','policy-probe.jsonl'):read(transport/name,pins)
    pre,final,manifest,records,evidence=trial(transport)
    if (release.get('final_state_sha256')!=pins[str((transport/'final-state.json').resolve())]
            or final.get('session_id')!=session['session_id'] or final.get('pid')!=session['pid']
            or final.get('process_creation_filetime')!=session['process_creation_filetime']
            or final.get('mod_sha256')!=session['mod_sha256'] or final.get('unknown_command_ids')!=[]
            or final.get('cleanup_verified') is not True
            or any(type(final['native'].get(k)) is not int or final['native'][k]!=v for k,v in NATIVE_STOP.items())):
        raise ValueError('continuation_native_cleanup_required')
    if manifest.get('kind')!='native_macro_policy_transport_candidate':raise ValueError('continuation_runtime_unreviewed')
    prefix=manifest.get('mapping_prefix');epoch=manifest.get('epoch')
    if type(prefix) is not str or not prefix or type(epoch) is not int or epoch<1:
        raise ValueError('continuation_runtime_epoch_identity_missing')
    mapping=prefix+str(session['pid'])
    attaches=[row for row in records if row.get('kind')=='attach_prepared' and row.get('mapping_name')==mapping]
    events=[json.loads(line) for line in read(host/'host-events.jsonl',pins).decode('utf8').splitlines()]
    if not events or any(row.get('session_id')!=session['session_id'] for row in events):
        raise ValueError('continuation_event_session_binding')
    counts=dict(requests_started=sum(row['kind']=='commander_model_call_started' for row in events),
        responses_returned=sum(row['kind']=='commander_model_response_returned' for row in events),
        plans_applied=sum(row['kind']=='plan_applied' for row in events))
    if any(digest(Path(path).read_bytes())!=sha for path,sha in pins.items()):
        raise ValueError('continuation_input_changed_during_check')
    # Cleanup returns semaphore ownership (lease_held=0), not object absence.
    # The game-pinned DLL retains static p/phase2 and its mapping reference;
    # client attach rejects ERROR_ALREADY_EXISTS for the same mapping epoch.
    # No current transport contract qualifies a reset/re-arm operation.
    return dict(kind='macro_research_continuation_runtime_compatibility',ready=False,created=False,dry_run=dry_run,
        reason_code='macro_runtime_same_epoch_reattach_unsupported',source_run=str(old),requested_new_run=str(output),
        session_id=session['session_id'],pid=session['pid'],process_creation_filetime=session['process_creation_filetime'],
        runtime_epoch=epoch,previously_used_mapping_name=mapping,previous_attach_recorded=bool(attaches),
        mapping_live_existence_verified=False,lease_object_type='semaphore',lease_object_existence='not_queried',
        recorded_lease_held=final['native']['lease_held'],recorded_native_cleanup_verified=True,
        requires_new_owned_game_process=True,research_continuation=False,fresh_match=False,formal_G7_eligible=False,
        previous_run_model_counts=counts,ledger_read=False,live_process_read=False,kernel_object_calls=0,
        process_writes=0,model_calls=0,native_dispatches=0,game_started=False,game_stopped=False,input_sha256=pins)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--dry-run',action='store_true');args=p.parse_args()
    value=prepare(args.session,args.output,dry_run=args.dry_run)
    print(json.dumps({k:v for k,v in value.items() if k!='input_sha256'},ensure_ascii=False))
    return 2  # A compatibility refusal is never a successful preparation.


if __name__=='__main__':raise SystemExit(main())
