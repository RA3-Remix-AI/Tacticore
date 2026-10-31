"""Complete original normal/no-attachment proof, selected by ledger contract.

An unselected orphan artifact cannot replace a committed normal receipt. The
original lifecycle/capture sources stay byte-identical for historical replay;
this reader retains every normal-path check and never collects fresh evidence.
"""
import json
from pathlib import Path

from .contracts import ContractError
from .native6_runtime_contract import read,sha
from .strategic_unified_unknown_return_v5 import covered_unknown_ownership


def verified_return(backend,row,binding,host_receipt,*,context):
    try:
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
