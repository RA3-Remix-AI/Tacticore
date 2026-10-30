"""Explicit schema13 strategic scope; no upgrade of old precision bundles.

Underlying research qualification permits bounded product trials only. Real
model/GUI/natural acceptance must be proved separately for the frozen product.
"""
from dataclasses import dataclass
import json
from pathlib import Path

from .contracts import ContractError
from .strategic_unified_release_v5 import verified_proof
from .strategic_contract_v5 import FLAG_ACTIONS,GATE_ACTIONS,STRATEGIC_ACTIONS

ROOT=Path(__file__).resolve().parents[2]
KIND='verified_macro_strategic_unified_bootstrap'
FIELDS={'schema_version','kind','legacy_bundle','build','visibility','normal','host_loss','natural_stop','pins'}
PACKAGE='66025609e788ed18f8eb55b1722e6c197a373f387137b69e6b04118d0a5278f0'
REPORT_SHA='81ac4d4890ebe8bda7d0541ae8799bca324acd8e9fbffece564a4993fab052da'

def refuse():raise ContractError('strategic_unified_bundle_not_qualified')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):return __import__('hashlib').sha256(Path(path).read_bytes()).hexdigest()

@dataclass(frozen=True)
class UnifiedStrategicScopeV5:
    package_sha256:str
    flag_pairs:tuple
    region_pairs:tuple
    evidence:tuple
    native_transport_protocol:int=5
    native_transport_client:str='strategic_unified_transport_v5.py'
    required_origin_region:str='region_8_3'
    @property
    def available_actions(self):return FLAG_ACTIONS+tuple(GATE_ACTIONS)
    @property
    def action_flags(self):return dict(self.flag_pairs)
    @property
    def regional_action_regions(self):return dict(self.region_pairs)
    @property
    def production_counts(self):return {}
    def model_catalog_overrides(self):
        from .macro_group_role_contract import group_role_catalog_overrides
        return group_role_catalog_overrides()
    def public(self):
        return dict(available_actions=list(self.available_actions),package_sha256=self.package_sha256,
            native_transport_protocol=5,details_owner='native_ai',exact_templates_quantities_or_unit_orders=False,
            construction_and_production='bounded_native_scheduling_gate_with_baseline_return',
            expansion='stock_native_preference_with_stock_guards',required_origin_region=self.required_origin_region,
            regional_action_regions=self.regional_action_regions,formal_natural_games=0,
            research_qualification_only=True,product_model_and_client_acceptance_verified=False)

def header(value):
    if type(value) is not dict or set(value)!=FIELDS or type(value['schema_version']) is not int or value['schema_version']!=13 or value['kind']!=KIND:refuse()
    for key in FIELDS-{'schema_version','kind','pins'}:
        path=Path(value[key])
        if not path.is_absolute() or str(path).startswith('\\\\') or not path.exists():refuse()

def inputs(value):
    from .macro_bundle import load_bundle,required_files
    from .strategic_unified_transport_v5 import native_module
    header(value);legacy=read(value['legacy_bundle'])
    if type(legacy.get('schema_version')) is not int or legacy['schema_version']!=9:refuse()
    _,base=load_bundle(value['legacy_bundle'])
    if not set(FLAG_ACTIONS)-{'expand'}<=set(base.available_actions):refuse()
    builder,_=native_module();build=Path(value['build']);manifest=builder.verify(build)
    if manifest['package_sha256']!=PACKAGE or tuple(manifest['actions'])!=FLAG_ACTIONS:refuse()
    report_path=Path(manifest['package_report'])
    if digest(report_path)!=REPORT_SHA:refuse()
    report=read(report_path)
    if report['big_sha256']!=PACKAGE or tuple(report['strategic_actions'])!=FLAG_ACTIONS:refuse()
    pairs=tuple((r['action'],r['flag']) for r in report['consumers'])
    if tuple(a for a,f in pairs)!=FLAG_ACTIONS or tuple(f for a,f in pairs)!=tuple(manifest['flags']):refuse()
    reinforce=next(r for r in report['consumers'] if r['action']=='reinforce')
    if (reinforce.get('target_policy')!='original_native_most_recently_attacked_own_base'
            or reinforce.get('required_own_origin_region')!='region_8_3'):refuse()
    regions=tuple(sorted([(r['action'],r['region_id']) for r in report['consumers'] if 'region_id' in r]
        +[('reinforce','region_8_3')]))
    if dict(regions)!=base.regional_action_regions:refuse()
    files={Path(value['legacy_bundle']),*required_files(legacy),build/'build-manifest.json',build/'profile.h',
        *(build/name for name in manifest['artifacts']),*(Path(name) for name in manifest['input_pins'])}
    for key in ('normal','host_loss','natural_stop'):
        directory=Path(value[key]);proof=read(directory/'independent-release.json')
        rows=[json.loads(line) for line in (directory/'commands.jsonl').read_text(encoding='utf8').splitlines()]
        attached=[r for r in rows if r['kind']=='attach_prepared']
        if len(attached)!=1 or attached[0]['manifest_sha256']!=digest(build/'build-manifest.json'):refuse()
        b=proof['native']['binding'];session_id=attached[0]['session_id'];ticks=b['start_low']|b['start_high']<<32
        if not verified_proof(proof,pid=b['pid'],ticks=ticks,session_id=session_id,package=PACKAGE,
                flags=manifest['flags'],closure=manifest['source_closure_sha256'],expected_host_returncode=1 if key=='host_loss' else 0):refuse()
        audits=read(directory/'native-unified-audits.json')
        if type(audits) is not list or len(audits)!=proof['native_durable_journal_records']:refuse()
        if key=='normal':
            for gate in (0,1):
                for desired in (False,True):
                    if not any(r['kind']==1 and r['audit']['phase']==1 and r['audit']['gate']==gate
                        and r['audit']['requested_enabled'] is desired for r in audits):refuse()
            if not any(r['kind']==2 and r['audit']['phase']==1 and r['audit']['observed_mask']&2 for r in audits):refuse()
        if key=='host_loss':
            if not any(r['kind']=='owned_publisher_and_helper_loss' for r in rows):refuse()
            if not all(any(r['kind']==1 and r['audit']['gate']==gate and r['audit']['phase']==4
                and r['audit']['trigger']==3 for r in audits) for gate in (0,1)):refuse()
        if key=='natural_stop' and not any(r['kind']=='native_terminal_candidate' for r in rows):refuse()
        pins=read(directory/'source-pins.json')
        if any(pins.get(name)!=sha for name,sha in manifest['input_pins'].items()):refuse()
        if any(digest(name)!=sha for name,sha in pins.items()):refuse()
        files.update(Path(name) for name in pins)
        files.update(directory/name for name in ('independent-release.json','commands.jsonl','native-unified-audits.json','source-pins.json','field-runner.py'))
        if key!='natural_stop':
            copies=read(directory/'source-copies.json')
            if {r['path']:r['sha256'] for r in copies}!=pins or len(copies)!=len(pins):refuse()
            for row in copies:
                if Path(row['copy']).name!=row['copy'] or digest(directory/'source'/row['copy'])!=row['sha256']:refuse()
                files.add(directory/'source'/row['copy'])
            files.add(directory/'source-copies.json')
    for name in ('build-capability.json','template-safety.json'):
        path=Path(value['visibility'])/name
        if read(path).get('package_sha256')!=PACKAGE:refuse()
        files.add(path)
    cap=read(Path(value['visibility'])/'build-capability.json')
    files.update(Path(p) for p in cap['evidence'])
    files.update(Path(p) for p in cap['source_sha256'])
    # All imported execution and presentation modules are software-qualified
    # together. Any new dependency changes membership and needs a fresh bundle.
    for directory in ('integration/host_runtime','strategy','visibility','production','native-ai','agent_runtime/src/tacticore_agent_runtime'):
        files.update((ROOT/directory).glob('*.py'))
    files.add(ROOT/'integration/macro_host.py')
    for directory in ('desktop-ui/src','desktop-ui/src-tauri/src'):
        files.update(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.ts','.tsx','.rs','.css'))
    files.update(ROOT/name for name in ('desktop-ui/src-tauri/target/debug/tacticore-desktop.exe',
        'desktop-ui/src-tauri/build.rs','desktop-ui/src-tauri/tauri.conf.json','desktop-ui/src-tauri/Cargo.toml',
        'desktop-ui/src-tauri/Cargo.lock','desktop-ui/package.json','desktop-ui/package-lock.json'))
    evidence=tuple(sorted((str(p.resolve()),digest(p)) for p in files))
    return UnifiedStrategicScopeV5(PACKAGE,pairs,regions,evidence),files

def load(path,session=None):
    value=read(path);scope,files=inputs(value)
    if value['pins']!={str(p.resolve()):digest(p) for p in files}:refuse()
    if session is not None and session['mod_sha256']!=PACKAGE:refuse()
    return value,scope

def create(path,**fields):
    value=dict(schema_version=13,kind=KIND,**{k:str(Path(v).resolve()) for k,v in fields.items()},pins={})
    scope,files=inputs(value);value['pins']={str(p.resolve()):digest(p) for p in files}
    with Path(path).open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2)
    return scope.public()
