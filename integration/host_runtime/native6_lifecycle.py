"""Native6 Host freeze and STOP/return contract. No command replay or history upgrade."""
import hashlib
import json
from pathlib import Path
import shutil

from .contracts import ContractError
from .native6_paths import Native6Paths
from .native6_runtime_contract import read,sha,GAME_SHA,PACKAGE_SHA,FIELD_KIND
from .native6_qualification import runtime_root,trusted_pin
from .strategic_unified_unknown_return_v5 import covered_unknown_ownership

KIND='native6_frozen_host_v1'


def report_directory(session):return Native6Paths.current().report(session['session_id'])


def freeze(host):
    root=host.native6_scope.runtime_root;source=host.output/'source';source.mkdir()
    files=[root/'app/integration/macro_host.py',host.args.session,host.args.macro_bundle,host.args.commander_draft,host.args.binding,
           root/'manifest.json',root/'native/strategic6/build-manifest.json',root/'qualification/native6-trial.json']
    rows=[]
    for index,path in enumerate(files):
        path=Path(path);target=source/(str(index)+'-'+path.name);shutil.copyfile(path,target)
        rows.append(dict(path=str(path),copy=target.name,sha256=sha(target)))
    from .desktop_backend import _atomic
    _atomic(host.output/'sources.json',dict(kind='pre_execution_macro_host_sources',sources=rows))
    _atomic(host.output/'profile.json',host.profile)
    _atomic(host.output/'native6-context.json',dict(kind=KIND,run_id=host.run_id,binding=host.binding.public(),
        runtime_root=str(root),runtime_manifest_sha256=host.native6_scope.runtime_manifest_sha256,
        report=str(report_directory(host.session)),sources_sha256=sha(host.output/'sources.json')))


def context(row,session,binding):
    output=Path(row['output_path']);value=read(output/'native6-context.json')
    if (set(value)!={'kind','run_id','binding','runtime_root','runtime_manifest_sha256','report','sources_sha256'}
            or value['kind']!=KIND or value['run_id']!=row['run_id'] or value['binding']!=binding.public()
            or value['runtime_manifest_sha256']!=trusted_pin()
            or Path(value['runtime_root'])!=runtime_root() or Path(value['report'])!=report_directory(session)
            or sha(output/'sources.json')!=value['sources_sha256']):raise ContractError('native6_frozen_context_changed')
    rows=read(output/'sources.json')['sources']
    if len(rows)!=8:raise ContractError('native6_frozen_context_changed')
    copies=[]
    for entry in rows:
        name=entry['copy']
        if Path(name).name!=name or sha(output/'source'/name)!=entry['sha256']:raise ContractError('native6_frozen_source_changed')
        copies.append(output/'source'/name)
    inventory=read(copies[5]);manifest=read(copies[6]);descriptor=read(copies[2]);root=Path(value['runtime_root'])
    if (sha(copies[5])!=value['runtime_manifest_sha256'] or descriptor!={
            'schema_version':14,'kind':'native6_manifest_bound_trial','runtime_root':str(root),'runtime_manifest_sha256':value['runtime_manifest_sha256']}
            or rows[0]['sha256']!=inventory['files'].get('app/integration/macro_host.py')
            or rows[6]['sha256']!=inventory['files'].get('native/strategic6/build-manifest.json')
            or rows[7]['sha256']!=inventory['files'].get('qualification/native6-trial.json')
            or sha(__file__)!=inventory['files'].get('app/integration/host_runtime/native6_lifecycle.py')
            or manifest.get('kind')!=FIELD_KIND or type(manifest.get('protocol_version')) is not int or manifest['protocol_version']!=6
            or manifest['package_sha256']!=binding.mod_sha256 or binding.game_sha256!=GAME_SHA
            or manifest['package_sha256']!=PACKAGE_SHA or read(copies[1])!=session):
        raise ContractError('native6_frozen_context_changed')
    return value,manifest,inventory


def finish(host):
    from .desktop_backend import _atomic
    from .native6_release import KIND as RELEASE_KIND,verified_final
    stop=host.journal.reserve_command(host.run_id,'macro-stop','macro_policy_stop',dict(binding_hash=host.binding.binding_hash))
    if not stop['created']:raise ContractError('macro_stop_already_claimed')
    host.journal.mark_dispatching(host.run_id,'macro-stop')
    try:
        if host.transport is None:
            from .native6_no_attachment import capture,KIND as contract
            proof=capture(host.sampler.memory if host.sampler else None,host.session,host.binding,host.run_id)
            path=host.output/'native-no-attachment.json';_atomic(path,proof)
            publication=dict(native_release_contract=contract,no_attachment_sha256=sha(path));verified=True
        else:
            if host.controller:host.controller.stop()
            else:host.transport.close()
            path=report_directory(host.session)/'final-state.json';final=read(path)
            verified=verified_final(final,path.with_name('independent-release.json'),host.session,host.binding,host.transport.manifest,
                runtime_root=host.native6_scope.runtime_root,runtime_manifest_sha256=host.native6_scope.runtime_manifest_sha256)
            stop=host.journal.get_command(host.run_id,'macro-stop')
            def own_start(row):
                r=row.get('receipt') or {}
                return (row['operation']=='host_start' and row['status']=='started'
                    and row['payload'].get('capabilities',{}).get('native_transport_protocol')==6
                    and r.get('host_pid')==host.host_pid and r.get('host_start_time')==host.host_start)
            verified=verified and covered_unknown_ownership([row for row in host.journal.unresolved(host.run_id)
                if row['request_id']!='macro-stop' and not own_start(row)],
                host.journal.commands_for_run(host.run_id),stop)
            publication=dict(native_release_contract=RELEASE_KIND,final_state_sha256=sha(path),
                             independent_release_sha256=final['independent_release_sha256'])
        proof=dict(kind='macro_policy_native_release',binding=host.binding.public(),run_id=host.run_id,
            host_pid=host.host_pid,host_start_time=host.host_start,native_release_verified=verified,**publication)
        _atomic(host.output/'macro-release.json',proof)
        host.journal.record_outcome(host.run_id,'macro-stop','released' if verified else 'uncertain',dict(
            binding_hash=host.binding.binding_hash,host_pid=host.host_pid,host_start_time=host.host_start,
            native_release_verified=verified,release_sha256=sha(host.output/'macro-release.json'),**publication))
        if not verified:raise ContractError('macro_stop_unverified')
        if getattr(host,'strategy_runtime',None) is not None:
            at=max(host.latest['game_time_seconds'],host.transport.native_status()['last_frame']/15) if host.transport else host.latest['game_time_seconds']
            host.strategy_runtime.finish(at,release_verified=True)
    except BaseException:
        if host.journal.get_command(host.run_id,'macro-stop')['status']=='dispatching':
            host.journal.record_outcome(host.run_id,'macro-stop','uncertain',dict(native_release_verified=False))
        raise


def verified_return(backend,row,binding,host_receipt):
    try:
        if (Path(row['output_path'])/'native6-orphan-return.json').exists():
            from .native6_orphan_return import verified_return as orphan_verified
            return orphan_verified(backend,row,binding,host_receipt)
        session=read(Path(row['session_path']));value,manifest,inventory=context(row,session,binding)
        output=Path(row['output_path']);release=read(output/'macro-release.json')
        stop=backend.journal.get_command(row['run_id'],'macro-stop');receipt=stop['receipt'] or {}
        if (stop['status']!='released' or release.get('kind')!='macro_policy_native_release'
                or release.get('run_id')!=row['run_id'] or release.get('binding')!=binding.public()
                or receipt.get('binding_hash')!=binding.binding_hash or receipt.get('release_sha256')!=sha(output/'macro-release.json')
                or release.get('native_release_verified') is not True or receipt.get('native_release_verified') is not True
                or any(release.get(k)!=host_receipt.get(k) or receipt.get(k)!=host_receipt.get(k) for k in ('host_pid','host_start_time'))):return False
        from .native6_no_attachment import KIND as NO_ATTACH,verified_capture
        if receipt.get('native_release_contract')==NO_ATTACH:
            proof=read(output/'native-no-attachment.json')
            events=[json.loads(line) for line in (output/'host-events.jsonl').read_text().splitlines()]
            forbidden={'macro_native_transport_constructor_begin','macro_native_transport_constructor_returned',
                       'commander_model_call_started','model_macro_dispatch_prepared','plan_applied'}
            return (not backend.journal.unresolved(row['run_id']) and release.get('native_release_contract')==NO_ATTACH
                and receipt.get('no_attachment_sha256')==sha(output/'native-no-attachment.json')==release.get('no_attachment_sha256')
                and proof.get('capture_code_sha256')==inventory['files'].get('app/integration/host_runtime/native6_no_attachment.py')
                and verified_capture(proof,session,binding,row['run_id']) and events and events[-1]['kind']=='host_stopped'
                and not any(event['kind'] in forbidden for event in events)
                and all(command['operation'] in {'host_start','host_stop','macro_policy_stop'} and command['status'] in {'completed','released'}
                        for command in backend.journal.commands_for_run(row['run_id'])))
        from .native6_release import KIND as RELEASE_KIND,verified_final
        if receipt.get('native_release_contract')!=RELEASE_KIND or release.get('native_release_contract')!=RELEASE_KIND:return False
        final_path=Path(value['report'])/'final-state.json';final=read(final_path)
        return (receipt.get('final_state_sha256')==sha(final_path)==release.get('final_state_sha256')
            and receipt.get('independent_release_sha256')==final['independent_release_sha256']==release.get('independent_release_sha256')
            and verified_final(final,final_path.with_name('independent-release.json'),session,binding,manifest,
                runtime_root=Path(value['runtime_root']),runtime_manifest_sha256=value['runtime_manifest_sha256'])
            and covered_unknown_ownership(backend.journal.unresolved(row['run_id']),backend.journal.commands_for_run(row['run_id']),stop))
    except (OSError,ValueError,KeyError,TypeError,OverflowError,ContractError):return False
