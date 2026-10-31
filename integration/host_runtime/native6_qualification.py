"""Manifest-anchored Native6 bounded trials; never an inherited product pass.

The native launcher supplies the compiled companion pin. A descriptor, UI
field or self-reported qualification bit cannot establish that authority.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re

from .contracts import ContractError
from .native6_paths import plain_local
from .native6_runtime_contract import ACTIONS, FLAGS, GAME_SHA, PACKAGE_SHA, FIELD_KIND, read, sha, verify_build, verify_inventory
from .strategic_unified_bundle_v5 import UnifiedStrategicScopeV5

KIND='native6_manifest_bound_trial'
CAPABILITY_SHA='fbe66a3c7a638d035022f92c50ec3cf0207cb613069c03d852454619e19a63ef'
SAFETY_SHA='9367086686916a2b6a640cb7380fc719dc869baef9a904dad8e822a88114912f'
PACKAGE_REPORT_SHA='81ac4d4890ebe8bda7d0541ae8799bca324acd8e9fbffece564a4993fab052da'
REGISTRY_SHA='b404ec9c369a27673e2cbd4c7bcc05702740f89d683707ec3cbd469f0c2184c4'
REGIONS=(('deployattack','region_1_3'),('deploydefense','region_8_3'),('regroup','region_8_3'),('reinforce','region_8_3'),('withdraw','region_8_3'))
COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'
MAP_ID='map_mp_2_black1b'  # TemplePrime is the UI display name, not the engine map ID.
VISIBILITY_CHECKS={'own_view_differs_from_observer','native_cached_clear_agrees_with_full_footprint',
    'lazy_cache_zero_requires_reconstruction','center_clear_does_not_imply_footprint_clear','observed_first_sighting','observed_loss'}
VISIBILITY_SIGNATURES={hex(value) for value in (0x992130,0x9912f0,0x98fef0,0x9903b0,0x990493,0x993264,0x844680,0x504e10,0x6fda40)}


def fail():raise ContractError('native6_trial_not_qualified')


def runtime_root():
    root=Path(__file__).resolve().parents[3]
    if Path(__file__).resolve()!=root/'app/integration/host_runtime/native6_qualification.py':fail()
    return plain_local(root)


def verify_qualification(root,expected):
    """Pure file verification; no Game, compiler, source XML or old reports."""
    if type(expected) is not str or re.fullmatch('[0-9a-f]{64}',expected) is None:fail()
    root=plain_local(root);inventory=verify_inventory(root,expected=expected)
    build=verify_build(root/'native/strategic6')
    if build['kind']!=FIELD_KIND or build['compile_only'] or not build['admission_ready']:fail()
    cap=verify_capsule(root,inventory)
    return inventory,build,cap


def verify_capsule(root,inventory):
    cap=read(root/'qualification/native6-trial.json')
    fields={'schema_version','kind','game_sha256','package_sha256','boundary','formal_games','product_acceptance_verified',
            'provenance','expected_signatures','checks','safety','implementation_sha256','registry_sha256','package_report_sha256'}
    if (type(cap) is not dict or set(cap)!=fields or type(cap['schema_version']) is not int or cap['schema_version']!=1
            or cap['kind']!='native6_bounded_trial_qualification' or cap['game_sha256']!=GAME_SHA or cap['package_sha256']!=PACKAGE_SHA
            or cap['boundary']!='native_ai_details_v1' or type(cap['formal_games']) is not int or cap['formal_games']!=0
            or cap['product_acceptance_verified'] is not False
            or cap['provenance'].get('visibility_capability_sha256')!=CAPABILITY_SHA
            or cap['provenance'].get('visibility_safety_sha256')!=SAFETY_SHA
            or cap['provenance'].get('package_report_sha256')!=PACKAGE_REPORT_SHA
            or cap['provenance'].get('registry_sha256')!=REGISTRY_SHA
            or type(cap['checks']) is not dict or set(cap['checks'])!=VISIBILITY_CHECKS or any(value is not True for value in cap['checks'].values())):fail()
    safety=cap['safety']
    if (safety.get('package_sha256')!=PACKAGE_SHA or safety.get('detection_verified') is not False
            or type(safety.get('schema_version')) is not int or safety['schema_version']!=1 or safety.get('source_audit_only') is not True
            or safety.get('runtime_invisibility_must_still_be_excluded') is not True
            or not safety.get('templates') or any(row.get('source_audited_no_intrinsic_stealth') is not True for row in safety['templates'].values())):fail()
    if sha(root/'qualification/registry.json')!=cap['registry_sha256'] or sha(root/'qualification/package.json')!=cap['package_report_sha256']:fail()
    if cap['registry_sha256']!=REGISTRY_SHA:fail()
    if set(cap['implementation_sha256'])!={'native_read.py','collector.py','projection.py','audit_templates.py'}:fail()
    for name,pin in cap['implementation_sha256'].items():
        if inventory['files'].get('app/visibility/'+name)!=pin or sha(root/'app/visibility'/name)!=pin:fail()
    if (type(cap.get('expected_signatures')) is not dict or set(cap['expected_signatures'])!=VISIBILITY_SIGNATURES
            or any(type(value) is not str or re.fullmatch('[0-9a-f]{48}',value) is None for value in cap['expected_signatures'].values())):fail()
    return cap


def trusted_pin():
    pin=os.environ.get('TACTICORE_RUNTIME_MANIFEST_SHA256')
    if type(pin) is not str or re.fullmatch('[0-9a-f]{64}',pin) is None:fail()
    return pin


def current():
    root=runtime_root();pin=trusted_pin()
    inventory,build,cap=verify_qualification(root,pin)
    return root,pin,inventory,build,cap


@dataclass(frozen=True)
class Native6Scope(UnifiedStrategicScopeV5):
    native_transport_protocol:int=6
    native_transport_client:str='native6_transport.py'
    runtime_root:Path=Path()
    runtime_manifest_sha256:str=''
    def public(self):
        return dict(super().public(),native_transport_protocol=6,bounded_field_trial=True,
                    runtime_manifest_sha256=self.runtime_manifest_sha256,formal_natural_games=0,
                    product_model_and_client_acceptance_verified=False)


def header(value):
    if (type(value) is not dict or set(value)!={'schema_version','kind','runtime_root','runtime_manifest_sha256'}
            or type(value['schema_version']) is not int or value['schema_version']!=14 or value['kind']!=KIND):fail()


def load(path,session=None):
    value=read(path);header(value)
    root,pin,inventory,build,cap=current()
    if Path(value['runtime_root'])!=root or value['runtime_manifest_sha256']!=pin:fail()
    if session is not None:
        scenario=session.get('scenario',{})
        if (session.get('mod_sha256')!=PACKAGE_SHA or Path(session.get('registry',''))!=root/'qualification/registry.json'
                or scenario.get('map_id')!=MAP_ID or scenario.get('commander_id')!=COMMANDER
                or type(scenario.get('computer_player_index')) is not int or scenario['computer_player_index']!=3
                or type(scenario.get('opponent_player_index')) is not int or scenario['opponent_player_index']!=4
                or scenario.get('participant_count')!=2 or scenario.get('observer_player_index',2)!=2):fail()
    evidence=tuple(sorted([(str(root/name),digest) for name,digest in inventory['files'].items()]+[(str(root/'manifest.json'),pin)]))
    scope=Native6Scope(PACKAGE_SHA,tuple(zip(ACTIONS,FLAGS)),REGIONS,evidence,runtime_root=root,runtime_manifest_sha256=pin)
    bundle=dict(value,build=str(root/'native/strategic6'),visibility=str(root/'qualification'),pins=dict(evidence))
    return bundle,scope


def create(path):
    root,pin,_,_,_=current()
    value=dict(schema_version=14,kind=KIND,runtime_root=str(root),runtime_manifest_sha256=pin)
    import json
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,sort_keys=True);stream.write('\n')
    return value


def admit_sdk(build,session):
    root,_,_,manifest,_=current()
    if Path(build)!=root/'native/strategic6':fail()
    # Descriptor qualification plus live map/own/origin verification remains
    # the Host's job; the SDK independently refuses a different package/owner.
    scenario=session.get('scenario',{})
    if (session.get('mod_sha256')!=PACKAGE_SHA or scenario.get('computer_player_index')!=3
            or scenario.get('commander_id')!=COMMANDER or scenario.get('map_id')!=MAP_ID):fail()
    return manifest
