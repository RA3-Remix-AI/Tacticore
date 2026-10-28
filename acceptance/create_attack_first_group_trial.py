"""Create a separately reviewed fixed trial, retaining the earlier driver."""
from pathlib import Path

folder=Path(__file__).resolve().parent;target=folder/'macro_group_role_attack_first_trial.py'
if target.exists():raise ValueError('fresh_attack_first_group_trial_required')
source=(folder/'macro_group_role_trial.py').read_text(encoding='utf8')
changes={
    "PACKAGE_SHA='aec5131537d2852c5ccda55391e85a74a3457256859fc94a924832cacc0da756'":
        "PACKAGE_SHA='bf0bb3105dc9d1124173ff8aa6ccfa15e494ceb550f78e05600092356970c260'",
    "STEPS=(('regroup',900,65),('deployattack',1800,125),('withdraw',900,65),('reinforce',900,65))":
        "STEPS=(('deployattack',1800,125),('withdraw',900,65),('reinforce',900,65),('regroup',900,65))",
    "package.get('group_roles_candidate_revision')!=1":"package.get('group_roles_candidate_revision')!=2",
    "out/'group-role-driver.py'":"out/'group-role-attack-first-driver.py'",
    "kind='fixed_original_native_group_roles_trial'":"kind='fixed_original_native_group_roles_attack_first_trial'",
}
for before,after in changes.items():
    if source.count(before)!=1:raise ValueError('attack_first_group_driver_anchor')
    source=source.replace(before,after)
target.write_text(source,encoding='utf8')
print(target)
