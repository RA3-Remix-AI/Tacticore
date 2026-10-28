"""Grant technology account preferences only after replaying native adoption."""
from dataclasses import replace
from pathlib import Path

from .contracts import ContractError
from .macro_policy_runtime import BudgetScope,PRESETS,load,sha,trial,ratios_match

DRIVER='1f50eca14b7507e86034388c1187247836c5f0c79d5330ea31e79b6a15678f34'
ACTION='budgettech'


def extend_technology_budget_scope(scope,directory):
    if not isinstance(scope,BudgetScope):raise ContractError('macro_technology_budget_scope_required')
    folder=Path(directory).resolve();driver=load(folder/'driver-preflight.json')
    if (driver.get('driver_sha256')!=DRIVER or sha(folder/'technology-driver.py')!=DRIVER
            or driver.get('policy')!=[ACTION] or driver.get('model_calls')!=0
            or not ratios_match(driver.get('desired_native_account_shares'),PRESETS[ACTION])
            or driver.get('payment_verified') is not False or driver.get('technology_upgrade_verified') is not False):
        raise ContractError('macro_technology_budget_field_driver')
    pre,final,manifest,rows,evidence=trial(folder/'transport')
    if (manifest['package_sha256']!=scope.package_sha256 or manifest['sources']!=scope.native_sources
            or tuple(manifest['flags'])!=scope.flags or driver.get('session_id')!=final['session_id']
            or driver.get('pid')!=final['pid']):raise ContractError('macro_technology_budget_transport')
    flags=[row['flag'] for row in manifest['consumers'] if row['action']==ACTION]
    if len(flags)!=1:raise ContractError('macro_technology_budget_consumer')
    flag=flags[0];mask=1<<manifest['flags'].index(flag)
    acks=[row for row in rows if row['kind']=='command_acknowledged']
    if len(acks)!=3 or [row['native']['applied_mask'] for row in acks]!=[mask,0,0]:
        raise ContractError('macro_technology_budget_gate_sequence')
    begin=acks[0]['native']['last_frame'];end=acks[1]['native']['last_frame']
    if not begin<end<=acks[0]['native']['deadline_frame']:
        raise ContractError('macro_technology_budget_window')
    observations=[row for row in rows if row['kind']=='macro_observation' and 'observation' in row]
    adopted=[row['observation']['frame'] for row in observations
        if row.get('label')=='technology_budget_held'
        and begin<=row['observation']['frame']<=end
        and row['observation'].get('budget_feedback',{}).get('selected_macro_flag')==flag
        and ratios_match(row['observation']['budget_feedback'].get('account_shares'),PRESETS[ACTION])]
    if len(set(adopted))<2:raise ContractError('macro_technology_budget_native_adoption_missing')
    if not any(row.get('label')=='after_technology_budget_release' and row['observation']['frame']>=end
            and row['observation'].get('budget_feedback',{}).get('selected_macro_flag') is None
            for row in observations):raise ContractError('macro_technology_budget_delegation_missing')
    for name in ('driver-preflight.json','technology-driver.py'):evidence[str(folder/name)]=sha(folder/name)
    return replace(scope,available_actions=tuple(dict.fromkeys((*scope.available_actions,ACTION))),
        action_flags={**scope.action_flags,ACTION:flag},evidence={**scope.evidence,**evidence})
