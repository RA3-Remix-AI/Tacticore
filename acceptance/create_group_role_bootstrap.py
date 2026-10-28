"""Compose the reviewed schema9 native bootstrap; no game or provider access."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration')]
from host_runtime.macro_bundle import create_bundle


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_group_role_bootstrap_required')
    original=json.loads((ROOT/'reports/macro-base-defense-desktop-bootstrap-20261028-v2/macro-budget-bundle.json').read_text())
    args={k:v for k,v in original.items() if k not in ('pins','schema_version','kind')}
    args.update(build=ROOT/'native-ai/macro-policy-runtime/bin/policy-v37-group-roles-20261028',
        visibility=ROOT/'reports/macro-visibility-bf0bb310-derived-20261028-v1',
        base_defense_build=ROOT/'native-ai/macro-policy-runtime/bin/policy-v35-base-defense-20261028',
        group_roles=[ROOT/'reports/macro-group-roles-71388-20261028-v1',ROOT/'reports/macro-group-roles-82568-20261028-v1'],
        group_roles_static=ROOT/'reports/macro-group-roles-preservation-20261028-v2',
        group_role_revision_static=ROOT/'reports/macro-group-role-withdraw-revision-20261028-v1')
    out.mkdir();public=create_bundle(out/'macro-budget-bundle.json',**args)
    (out/'qualification.json').write_text(json.dumps(dict(kind='schema9_group_roles_native_bootstrap',scope=public,
        game_access=False,model_calls=0,unit_orders=0,formal_goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(output=str(out),scope=public,game_access=False,model_calls=0)))
