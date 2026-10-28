"""Prepare a native-bootstrap fixture from the current public desktop profile.

No credentials, game memory, model request or native execution is accessed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration')]
from host_runtime.desktop_registry import load_registration
from host_runtime.profile_store import ProfileStore
from host_runtime.macro_bundle import create_bundle
from host_runtime.macro_policy_runtime import COMMANDER


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--map-id',default='map_mp_2_black1b');parser.add_argument('--map-display-name',default='TemplePrime')
    parser.add_argument('--production',action='store_true',help='Include independently qualified two-queue Flak preference')
    parser.add_argument('--production-choice',type=Path,action='append',help='Additional fixed field evidence; requires --production')
    parser.add_argument('--construction',action='store_true',help='Include independently qualified reactor preference; requires --production')
    parser.add_argument('--technology-budget',type=Path,help='Fixed native technology budget evidence; requires --construction')
    parser.add_argument('--scouting',type=Path,help='Qualified original-AI scout preference; requires --technology-budget')
    parser.add_argument('--regional',type=Path,help='Qualified fixed-public-region trial; requires --scouting')
    parser.add_argument('--regional-static',type=Path,help='Reviewed compiled regional preservation audit')
    parser.add_argument('--qualification-build',type=Path,help='Original qualified build for preserved budget/build/production/scout consumers')
    parser.add_argument('--visibility',type=Path,help='Exact-package visibility derivation, required for regional package')
    parser.add_argument('--regional-build',type=Path,help='Preserved regional qualification build, required for base defense')
    parser.add_argument('--base-defense',type=Path,help='Qualified original native own-infrastructure defense trial')
    parser.add_argument('--base-defense-static',type=Path,help='Reviewed one-state base-defense preservation audit')
    parser.add_argument('--base-defense-build',type=Path,help='Preserved qualification build for own infrastructure defense')
    parser.add_argument('--group-role-field',type=Path,action='append',help='Fixed role evidence with independently replayed native effects')
    parser.add_argument('--group-roles-static',type=Path,help='Reviewed group-role package preservation audit')
    parser.add_argument('--group-role-revision-static',type=Path,help='Reviewed unchanged-role bridge between qualification packages')
    args=parser.parse_args()
    if args.production_choice and not args.production:parser.error('--production-choice requires --production')
    if args.construction and not args.production:parser.error('--construction requires --production')
    if args.technology_budget and not args.construction:parser.error('--technology-budget requires --construction')
    if args.scouting and not args.technology_budget:parser.error('--scouting requires --technology-budget')
    if any(v is not None for v in (args.regional,args.regional_static,args.qualification_build)) and (
            args.scouting is None or any(v is None for v in (args.regional,args.regional_static,args.qualification_build,args.visibility))):
        parser.error('regional scope requires scouting, regional trial/static audit, qualification build and exact-package visibility')
    if any(v is not None for v in (args.regional_build,args.base_defense,args.base_defense_static)) and (
            args.regional is None or any(v is None for v in (args.regional_build,args.base_defense,args.base_defense_static))):
        parser.error('base defense requires regional scope, regional build, defense field and preservation audit')
    if any(v is not None for v in (args.base_defense_build,args.group_role_field,args.group_roles_static,args.group_role_revision_static)) and (
            args.base_defense is None or any(v is None for v in (args.base_defense_build,args.group_role_field,args.group_roles_static,args.group_role_revision_static))):
        parser.error('group roles require base defense, preserved build, fixed role evidence and both preservation audits')
    source=args.session.resolve();run=source.parent
    if not run.is_relative_to(ROOT/'acceptance/runs'):raise ValueError('explicit_macro_fixture_required')
    session=json.loads(source.read_text(encoding='utf-8-sig'))
    if Path(session['run_directory']).resolve()!=run:raise ValueError('macro_fixture_directory_mismatch')
    home=Path(os.environ['LOCALAPPDATA'])/'Tacticore';config=load_registration(home)
    store=ProfileStore(Path(config['library_path']),home/'desktop-runtime')
    try:record=store.get_profile(COMMANDER)['profile']
    finally:store.close()
    if record['validation']['ok'] is not True or record['library_changed']:raise ValueError('current_profile_invalid')
    package=json.loads(Path(session['macro_package_report']).read_text(encoding='utf8'))
    asset=next(row for row in package['assets'] if row['name'].startswith('AIPersonalityDefinition:'))
    if (package['compiled'] is not True or package['big_sha256']!=session['mod_sha256']
            or package['commander_id']!=COMMANDER or asset['instance_id']!='0x799613e0'
            or hashlib.sha256(Path(session['mod_big']).read_bytes()).hexdigest()!=session['mod_sha256']):
        raise ValueError('macro_fixture_package_not_bound')
    registry=dict(identity_revision=1,registry_revision=record['revision'],compiled_ids_verified=True,
        package_sha256=session['mod_sha256'],macro_integration_fixture=True,
        commanders=[dict(id=COMMANDER,name=record['name'],connection_id=record['connection_id'],assets=[dict(
            asset_id=package['personality'],instance_id=asset['instance_id'],side='Soviet')])])
    with (run/'macro-registry.json').open('x',encoding='utf8') as stream:json.dump(registry,stream,ensure_ascii=False,indent=2)
    session.pop('real_model_calls',None)
    session.update(registry=str(run/'macro-registry.json'),registry_revision=record['revision'],real_model_calls_at_launch=0,
        scenario=dict(commander_id=COMMANDER,computer_player_index=3,opponent_player_index=4,observer_player_index=2,
            participant_count=2,map_id=args.map_id,map_display_name=args.map_display_name,seed_controlled=False),
        phase='desktop_macro_budget_integration')
    with (run/'desktop-session.json').open('x',encoding='utf8') as stream:json.dump(session,stream,ensure_ascii=False,indent=2)
    scope=create_bundle(run/'macro-budget-bundle.json',build=args.build,
        visibility=args.visibility or ROOT/'reports/macro-visibility-2bb7bb23-derived-20261028-v1',
        normal=ROOT/'reports/macro-policy-budget-73924-20261028-v3',
        host_loss=ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',
        expiry=ROOT/'reports/macro-policy-expiry-71320-20261028-v1',
        **(dict(production=ROOT/'reports/macro-production-count-69152-20261028-v1',
                production_static=ROOT/'reports/macro-builder-static-20261028-v2') if args.production else {}),
        **(dict(production_choices=args.production_choice) if args.production_choice else {}),
        **(dict(construction=ROOT/'reports/macro-early-build-69152-20261028-v1') if args.construction else {}),
        **(dict(technology_budget=args.technology_budget) if args.technology_budget else {}),
        **(dict(scouting=args.scouting) if args.scouting else {}),
        **(dict(regional=args.regional,regional_static=args.regional_static,qualification_build=args.qualification_build) if args.regional else {}),
        **(dict(regional_build=args.regional_build,base_defense=args.base_defense,base_defense_static=args.base_defense_static) if args.base_defense else {}),
        **(dict(base_defense_build=args.base_defense_build,group_roles=args.group_role_field,group_roles_static=args.group_roles_static,
            group_role_revision_static=args.group_role_revision_static) if args.group_role_field else {}))
    print(json.dumps(dict(session=str(run/'desktop-session.json'),profile_revision=record['revision'],
        effective_hash=record['effective']['effective_hash'],scope=scope,game_access=False,credentials_accessed=False)))


if __name__=='__main__':main()
