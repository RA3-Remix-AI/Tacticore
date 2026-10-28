"""Create versioned research readers without altering qualified older readers."""
from pathlib import Path
from verify_group_role_observer import expected_source,verify

folder=Path(__file__).resolve().parent
new=folder/'macro_group_role_observation.py'
client=folder/'macro-policy-runtime/client_group_roles.py'
if new.exists() or client.exists():raise ValueError('fresh_versioned_group_readers_required')
src=(folder/'macro-policy-runtime/client_area_defense.py').read_text(encoding='utf8')
replacements={
    'from macro_area_defense_observation import MacroObserver':'from macro_group_role_observation import MacroObserver',
    'from verify_area_defense_observer import verify as verify_observer_extension':'from verify_group_role_observer import verify as verify_observer_extension',
    "'client_area_defense.py'":"'client_group_roles.py'",
    "ROOT/'native-ai/macro_area_defense_observation.py',ROOT/'native-ai/verify_area_defense_observer.py'":
        "ROOT/'native-ai/macro_area_defense_observation.py',ROOT/'native-ai/verify_area_defense_observer.py',ROOT/'native-ai/macro_group_role_observation.py',ROOT/'native-ai/verify_group_role_observer.py'",
}
for before,after in replacements.items():
    if src.count(before)!=1:raise ValueError('research_reader_source_anchor')
    src=src.replace(before,after)
new.write_text(expected_source(folder),encoding='utf8');client.write_text(src,encoding='utf8')
print(verify())
