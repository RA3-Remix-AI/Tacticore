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
    _module('model_backend',ROOT/'strategy').check_backend_available('pydantic')
    win=_module('observe_production',ROOT/'production')
    win.k.OpenMutexW.argtypes=[win.w.DWORD,win.w.BOOL,win.w.LPCWSTR];win.k.OpenMutexW.restype=win.w.HANDLE
    lease=win.k.OpenMutexW(0x100000,False,'Local\\RA3MacroPolicyLease_'+str(session['pid']))
    if lease:win.k.CloseHandle(lease);raise ContractError('run_already_active')
    binding=SessionBinding(1,session['session_id'],3,profile['profile_id'],session['pid'],session['start_time'],host_id,
        digest(session['game']),session['mod_sha256'])
    summary['player_name']=profile['name']
    capabilities=dict(control_mode='macro_native',native_macro=True,available_macro_actions=list(scope.available_actions),
        supported_units=[],supported_foci=['native_baseline'],tactics_supported=False,runtime_tactical_supported=False,
        runtime_recovery_supported=False,runtime_purposes=[],model_response_received=False)
    if hasattr(scope,'available_counts'):
        capabilities['macro_production_counts']={action:list(counts) for action,counts in scope.production_counts.items()}
    if hasattr(scope,'model_catalog_overrides'):
        capabilities.update(base_defense_granted=True,base_defense_goal='original_native_defense_of_own_infrastructure')
    if getattr(scope,'native_transport_client',None)=='client_group_roles.py':
        capabilities['group_roles_granted']=['regroup','reinforce','withdraw']
    fingerprint=content_hash(dict(binding=binding.public(),footprint=footprint,profile_revision=profile['revision'],
        effective_hash=profile['effective']['effective_hash'],library_hash=profile['library_hash'],scope=scope.public(),limits=limits.public()))
    return Admission(binding,fingerprint,summary,capabilities,False)


def released(backend,run_id,binding,host_receipt):
    try:
        if backend.journal.unresolved(run_id):return False
        stop=backend.journal.get_command(run_id,'macro-stop')
        receipt=stop['receipt'] or {}
        if stop['status']!='released' or receipt.get('native_release_verified') is not True:return False
        if receipt.get('binding_hash')!=binding.binding_hash:return False
        if any(receipt.get(key)!=host_receipt.get(key) for key in ('host_pid','host_start_time')):return False
        row=backend._launch(run_id);output=Path(row['output_path']);proof=json.loads((output/'macro-release.json').read_text())
        final=ROOT/'reports'/('macro-desktop-'+run_id)/'final-state.json'
        if (digest(final)!=receipt.get('final_state_sha256') or digest(output/'macro-release.json')!=receipt.get('release_sha256')
                or proof.get('binding')!=binding.public() or proof.get('native_release_verified') is not True):return False
        native=json.loads(final.read_text())
        required=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0)
        return (native['session_id']==binding.session_id and native['pid']==binding.game_process_id
            and native['mod_sha256']==binding.mod_sha256 and native['cleanup_verified'] is True
            and native['unknown_command_ids']==[] and native['host_returncode']==0
            and all(native['native'].get(key)==value for key,value in required.items())
            and len(native['independent_flags']['flags'])==13
            and all(not row['present'] or row['value'] is False for row in native['independent_flags']['flags']))
    except (OSError,ValueError,KeyError,TypeError):return False
