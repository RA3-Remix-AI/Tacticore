"""Read-only desktop admission and terminal release checks for native macro policy."""
import hashlib
import json
from pathlib import Path

from .contracts import ContractError,SessionBinding,content_hash
from .macro_live import MacroSampler,ROOT
from .macro_bundle import load_bundle,digest


def observe(registration,profile_id,state_dir):
    from .macro_policy_runtime import COMMANDER
    if profile_id!=COMMANDER:raise ContractError('session_mismatch')
    sampler=MacroSampler(registration.session_path,registration.macro_bundle)
    try:
        raw=sampler.collect();session=sampler.session
        summary=dict(id=session['session_id'],map=session['scenario']['map_id'],player_name=profile_id,faction='Soviet')
        return session,raw,sampler.footprint(),summary
    finally:sampler.close()


def check(checks,registration,profile,host_id,state_dir,library_path,limits):
    from .desktop_backend import Admission,_module
    session,raw,footprint,summary=observe(registration,profile['profile_id'],state_dir)
    bundle,scope=load_bundle(registration.macro_bundle,session)
    if raw['paused']:raise ContractError('session_not_ready')
    output=Path(session['run_directory'])/'battle-host'
    if output.exists() and any(output.iterdir()):raise ContractError('run_state_conflict')
    # No protected loader at preflight: actual credentials are loaded only when
    # the bound host is ready to make provider requests.
    if hashlib.sha256(Path(library_path).read_bytes()).hexdigest()!=profile['library_hash']:
        raise ContractError('effective_profile_changed')
    if getattr(scope,'native_transport_protocol',None)==5:
        from .profiles import normalize_profile
        from .native5_capacity_preflight_v1 import check_native5_capacity
        from macro_policy import public_descriptions
        provider=profile.get('provider')
        if provider not in ('DeepSeek','OpenAI','自定义'):
            raise ContractError('model_context_capacity_provider_unavailable')
        effective=normalize_profile(dict(profile['draft'],model=profile['effective']['model']))
        if effective.effective_hash!=profile['effective']['effective_hash']:
            raise ContractError('effective_profile_changed')
        catalog=public_descriptions(scope.available_actions,region_targets=scope.regional_action_regions.items())
        catalog.update(scope.model_catalog_overrides())
        capacity=check_native5_capacity(effective,provider,raw,catalog)
        if not capacity['fits']:raise ContractError(capacity['reason_code'])
    _module('model_backend',ROOT/'strategy').check_backend_available('pydantic')
    from .macro_native_presence import require_unused_macro_process
    manifest=json.loads((Path(bundle['build'])/'build-manifest.json').read_text(encoding='utf-8-sig'))
    presence_manifest=manifest
    if getattr(scope,'native_transport_protocol',1)==5:
        from .strategic_native_presence_v5 import require_unused_macro_process
        presence_manifest=dict(manifest,mapping_prefix='Local\\RA3StrategicCommanderV5_')
    require_unused_macro_process(session['pid'],presence_manifest)
    binding=SessionBinding(1,session['session_id'],3,profile['profile_id'],session['pid'],session['start_time'],host_id,
        digest(session['game']),session['mod_sha256'])
    summary['player_name']=profile['name']
    from .macro_delegation_boundary_v1 import strategic_actions
    capabilities=dict(control_mode='macro_native',native_macro=True,available_macro_actions=list(strategic_actions(scope.available_actions)),
        supported_units=[],supported_foci=['native_baseline'],tactics_supported=False,runtime_tactical_supported=False,
        runtime_recovery_supported=False,runtime_purposes=[],model_response_received=False)
    if hasattr(scope,'available_counts'):
        capabilities['macro_production_counts']={}
    if getattr(scope,'native_transport_protocol',1)==5:
        capabilities['native_transport_protocol']=5
    if hasattr(scope,'model_catalog_overrides'):
        capabilities.update(base_defense_granted=True,base_defense_goal='original_native_defense_of_own_infrastructure')
    if getattr(scope,'native_transport_client',None)=='client_group_roles.py':
        capabilities['group_roles_granted']=['regroup','reinforce','withdraw']
    fingerprint=content_hash(dict(binding=binding.public(),footprint=footprint,profile_revision=profile['revision'],
        effective_hash=profile['effective']['effective_hash'],library_hash=profile['library_hash'],scope=scope.public(),limits=limits.public()))
    return Admission(binding,fingerprint,summary,capabilities,False)


def released(backend,run_id,binding,host_receipt):
    try:
        unresolved=backend.journal.unresolved(run_id)
        row=backend._launch(run_id);output=Path(row['output_path'])
        if (output/'native-orphan-return.json').exists():
            from .native5_orphan_return_v1 import verified_return
            return verified_return(backend,row,binding,host_receipt)
        from .macro_catalog_release_route_v1 import requires_v5,reviewed_v5_trial
        from .journal import JournalError
        try:stop=backend.journal.get_command(run_id,'macro-stop')
        except JournalError:stop=None
        release_path=output/'macro-release.json'
        proof=json.loads(release_path.read_text()) if release_path.exists() else None
        needs_v5=requires_v5(output,journal=backend.journal,run_id=run_id,release=proof,
            receipt=(stop.get('receipt') or {}) if stop is not None else None)
        from .macro_before_attach_review import projection_verified
        if not unresolved and not needs_v5 and projection_verified(backend,run_id,binding,host_receipt):return True
        if stop is None:return False
        receipt=stop['receipt'] or {}
        if stop['status']!='released' or receipt.get('native_release_verified') is not True:return False
        if receipt.get('binding_hash')!=binding.binding_hash:return False
        if any(receipt.get(key)!=host_receipt.get(key) for key in ('host_pid','host_start_time')):return False
        if proof is None:return False
        if receipt.get('native_release_contract')=='strategic_unified_no_attachment_v5':
            from .strategic_no_attachment_v5 import verified_return
            session=json.loads(Path(row['session_path']).read_bytes())
            return (not needs_v5 and proof.get('binding')==binding.public()
                and digest(release_path)==receipt.get('release_sha256')
                and verified_return(backend,row,binding,session,proof,receipt,host_receipt))
        needs_v5=needs_v5 or requires_v5(output,journal=backend.journal,run_id=run_id,release=proof,receipt=receipt)
        final=ROOT/'reports'/('macro-desktop-'+run_id)/'final-state.json'
        if (digest(final)!=receipt.get('final_state_sha256') or digest(output/'macro-release.json')!=receipt.get('release_sha256')
                or proof.get('binding')!=binding.public() or proof.get('native_release_verified') is not True):return False
        native=json.loads(final.read_text())
        from .session_discovery_native import frozen_manifest,require_creation
        session=json.loads(Path(row['session_path']).read_text(encoding='utf-8-sig'))
        ticks=session.get('process_creation_filetime');require_creation(binding.game_process_start,ticks)
        manifest=frozen_manifest(row,session,binding);flags=manifest.get('flags')
        protocol=manifest.get('protocol_version',1)
        if type(protocol) is int and protocol==5:
            from .strategic_unified_release_v5 import KIND,verified_final
            from .strategic_unified_unknown_return_v5 import covered_unknown_ownership
            if (manifest.get('kind')!='strategic_unified_transport_v5_candidate' or needs_v5
                    or proof.get('native_release_contract')!=KIND or receipt.get('native_release_contract')!=KIND
                    or proof.get('independent_release_sha256')!=native.get('independent_release_sha256')
                    or receipt.get('independent_release_sha256')!=native.get('independent_release_sha256')):return False
            return (proof.get('kind')=='macro_policy_native_release' and proof.get('run_id')==run_id
                and all(proof.get(k)==host_receipt.get(k) for k in ('host_pid','host_start_time'))
                and verified_final(native,final.with_name('independent-release.json'),session,binding,manifest)
                and covered_unknown_ownership(unresolved,backend.journal.commands_for_run(run_id),stop))
        if unresolved:return False
        if (type(protocol) is not int or protocol not in (1,2)
                or manifest.get('kind')!=('native_macro_policy_transport_v2_candidate' if protocol==2 else 'native_macro_policy_transport_candidate')
                or type(flags) is not list or len(flags)!=(20 if protocol==2 else 13)
                or any(type(flag) is not str or not flag for flag in flags) or len(set(flags))!=len(flags)):
            return False
        required=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0)
        contract=output/'publication-v4-contract.json'
        extension_keys=('native_release_contract','publication_v4_contract_sha256','publication_v4_release_review_sha256')
        from .macro_release_review_v4 import publication_v4_was_selected
        has_extension=not needs_v5 and (publication_v4_was_selected(output,journal=backend.journal,run_id=run_id)
            or any(key in proof or key in receipt for key in extension_keys))
        if needs_v5:
            if protocol!=2:return False
            reviewed_v5_trial(final.parent,output=output,release=proof,receipt=receipt,journal=backend.journal,expected=manifest,
                expected_binding=binding,expected_run_id=run_id)
        elif has_extension:
            # A marker selects the new grammar even if it is invalid. Never
            # fall back to old scalar cleanup after a failed V4 replay.
            if protocol!=2 or not contract.is_file():return False
            from .macro_release_review_v4 import KIND,projection_proof_v4
            review_path=output/'publication-v4-release-review.json'
            if (proof.get('native_release_contract')!=KIND or receipt.get('native_release_contract')!=KIND
                    or proof.get('publication_v4_contract_sha256')!=digest(contract)
                    or receipt.get('publication_v4_contract_sha256')!=digest(contract)
                    or proof.get('publication_v4_release_review_sha256')!=digest(review_path)
                    or receipt.get('publication_v4_release_review_sha256')!=digest(review_path)):return False
            reviewed,_=projection_proof_v4(final.parent,contract_path=contract,expected=manifest,
                expected_binding=binding,expected_run_id=run_id)
            if json.loads(review_path.read_text(encoding='utf-8-sig'))!=reviewed:return False
        return (native['session_id']==binding.session_id and native['pid']==binding.game_process_id
            and native.get('process_creation_filetime')==ticks and type(native.get('process_creation_filetime')) is int
            and native['native'].get('version')==protocol and type(native['native'].get('version')) is int
            and native['native'].get('start_low')==ticks&0xffffffff and native['native'].get('start_high')==ticks>>32
            and proof.get('kind')=='macro_policy_native_release' and proof.get('run_id')==run_id
            and all(proof.get(key)==host_receipt.get(key) for key in ('host_pid','host_start_time'))
            and native['mod_sha256']==binding.mod_sha256 and native['cleanup_verified'] is True
            and native['unknown_command_ids']==[] and type(native['host_returncode']) is int and native['host_returncode']==0
            and all(type(native['native'].get(key)) is int and native['native'][key]==value for key,value in required.items())
            and type(native['independent_flags']['flags']) is list and len(native['independent_flags']['flags'])==len(flags)
            and {row['name'] for row in native['independent_flags']['flags']}==set(flags)
            and all(type(row['present']) is bool and (not row['present'] or row['value'] is False)
                for row in native['independent_flags']['flags']))
    except (OSError,ValueError,KeyError,TypeError,ContractError):return False
