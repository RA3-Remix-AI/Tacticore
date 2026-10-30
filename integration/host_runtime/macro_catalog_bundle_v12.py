"""Explicit schema12 file wrapper; never widens the frozen schema11 loader.

This module proves only immutable capability evidence. It opens no game process,
does not register a bundle and grants no current readiness, finance or dispatch.
"""
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
import re

from .contracts import ContractError
from . import macro_bundle as legacy
from . import macro_consumer_catalog_review_v2 as catalog_review
from . import macro_consumer_catalog_scope_v2 as catalog_scope
from .macro_bundle_cache import VerifiedFileScopeCache,stable_file
from .macro_expansion_scope import ExpansionScope,EXTRA_ACTIONS

ROOT=Path(__file__).resolve().parents[2]
KIND='verified_macro_consumer_catalog_bootstrap_v12'
FIELDS=frozenset(('schema_version','kind','base_bundle','build','visibility','consumer_catalog_contracts','pins'))
ALGORITHM_PINS={
    'integration/host_runtime/macro_consumer_catalog_review_v2.py':'d44c9edd2bee55f40009287580f7c04074efd54167a567cd911146910ad9ba40',
    'integration/host_runtime/macro_consumer_catalog_scope_v2.py':'7f030f9e070304de35efb57bfebd64b5b8196d4771f25d3c0284a69b493e4aa6',
    **catalog_review.PINS}
_CACHE=VerifiedFileScopeCache(source_paths=(Path(__file__),Path(legacy.__file__),
    Path(catalog_review.__file__),Path(catalog_scope.__file__)))
_load_base_bundle=legacy.load_bundle
_extend_catalog=catalog_scope.extend_fixed_consumer_catalog_v2


def fail(code='not_qualified'):raise ContractError('macro_catalog_bundle_v12_'+code)
def _sha(path):return stable_file(path)[0].sha256


def _local(value,*,directory=False,reports=False):
    if type(value) is not str or not value or len(value)>32768 or '\0' in value:fail('canonical_local_path_required')
    path=Path(value)
    if not path.is_absolute() or str(path).startswith('\\\\'):fail('canonical_local_path_required')
    try:resolved=path.resolve(strict=True)
    except (OSError,ValueError):fail('canonical_local_path_required')
    if (str(resolved)!=value or str(resolved).startswith('\\\\')
            or (not resolved.is_dir() if directory else not resolved.is_file())
            or reports and not resolved.is_relative_to(ROOT/'reports')):fail('canonical_local_path_required')
    return resolved


def _contracts(value):
    if type(value) is not list or not 1<=len(value)<=len(catalog_review.ACTIONS):fail('contract_set')
    actions=set();directories=set();result=[]
    for entry in value:
        if (type(entry) is not dict or set(entry)!={'schema_version','kind','action','directory'}
                or type(entry.get('schema_version')) is not int or entry['schema_version']!=2
                or entry.get('kind')!=catalog_review.CONTRACT or entry.get('action') not in catalog_review.ACTIONS):fail('contract_schema')
        folder=_local(entry.get('directory'),directory=True,reports=True)
        if entry['action'] in actions or folder in directories:fail('duplicate_contract')
        actions.add(entry['action']);directories.add(folder);result.append(deepcopy(entry))
    return result


def _header(value):
    if (type(value) is not dict or set(value)!=FIELDS or type(value.get('schema_version')) is not int
            or value['schema_version']!=12 or value.get('kind')!=KIND):fail('schema')
    # Reject the entire descriptor set before replaying any supplied evidence.
    contracts=_contracts(value['consumer_catalog_contracts'])
    return _local(value['base_bundle']),_local(value['build'],directory=True),_local(value['visibility'],directory=True),contracts


def _algorithms():
    for name,wanted in ALGORITHM_PINS.items():
        if _sha(ROOT/name)!=wanted:fail('frozen_catalog_algorithm_changed')


def _scope_preserved(base,scope,actions,manifest):
    if type(scope) is not catalog_scope.ConsumerCatalogScopeV2 or scope.consumer_catalog_revision!=2:fail('typed_scope_required')
    expected=tuple(action for action in EXTRA_ACTIONS if action in set(base.expansion_choices)|set(actions))
    if scope.expansion_choices!=expected:fail('unrequested_action_grant')
    changed={'budget','evidence','expansion_choices','expansion_evidence','fixed_consumer_qualifications'}
    if any(getattr(scope,field.name)!=getattr(base,field.name) for field in fields(ExpansionScope) if field.name not in changed):fail('base_scope_changed')
    if any(getattr(scope.budget,field.name)!=getattr(base.budget,field.name) for field in fields(base.budget) if field.name!='evidence'):fail('base_budget_changed')
    flags=dict(base.expansion_evidence);qualified=dict(base.fixed_consumer_qualifications)
    for action in actions:
        matches=[row for row in manifest.get('consumers',[]) if type(row) is dict and row.get('action')==action]
        if len(matches)!=1 or type(matches[0].get('flag')) is not str:fail('manifest_action')
        flags[action]=matches[0]['flag'];qualified[action]=catalog_review.CONTRACT
    if (dict(scope.expansion_evidence)!=flags or dict(scope.fixed_consumer_qualifications)!=qualified
            or len(scope.expansion_evidence)!=len(flags) or len(scope.fixed_consumer_qualifications)!=len(qualified)):
        fail('action_contract_or_flag_changed')


def _put(expected,path,wanted=None):
    path=_local(str(Path(path).resolve(strict=True)))
    if wanted is not None and (type(wanted) is not str or re.fullmatch('[0-9a-f]{64}',wanted) is None):fail('evidence_digest')
    observed=_sha(path)
    if wanted is not None and observed!=wanted:fail('evidence_changed')
    key=str(path)
    if key in expected and expected[key]!=observed:fail('pin_conflict')
    expected[key]=observed


def catalog_inputs_v12(value):
    """Return the exact derived scope and complete expected pin closure."""
    base_path,build,visibility,contracts=_header(value);_algorithms()
    base_stamp,base_raw=stable_file(base_path,maximum=2*1024*1024,keep_bytes=True)
    base_header=json.loads(base_raw.decode('utf-8-sig'))
    if (type(base_header) is not dict or type(base_header.get('schema_version')) is not int
            or base_header['schema_version']!=11 or base_header.get('kind')!='verified_macro_fixed_consumer_bootstrap'):
        fail('same_version_schema11_base_required')
    base,base_scope=_load_base_bundle(base_path)
    if base!=base_header or type(base_scope) is not ExpansionScope:fail('verified_base_required')
    if build!=_local(base.get('build'),directory=True) or visibility!=_local(base.get('visibility'),directory=True):fail('base_runtime_or_visibility_changed')
    if (type(base.get('pins')) is not dict or not 1<=len(base['pins'])<=8192
            or type(base_scope.evidence) is not dict):fail('base_pins')
    actions=[entry['action'] for entry in contracts]
    if any(action in base_scope.expansion_choices for action in actions):fail('already_granted_action')
    scope=_extend_catalog(base_scope,build=build,contracts=contracts)
    manifest_path=build/'build-manifest.json'
    _,manifest_raw=stable_file(manifest_path,maximum=2*1024*1024,keep_bytes=True)
    manifest=json.loads(manifest_raw.decode('utf-8-sig'))
    if (type(manifest) is not dict or type(manifest.get('epoch')) is not int or manifest['epoch']!=4
            or type(manifest.get('protocol_version')) is not int or manifest['protocol_version']!=2
            or manifest.get('same_process_reattach_supported') is not False):fail('unchanged_epoch4_required')
    _scope_preserved(base_scope,scope,actions,manifest)
    expected={};_put(expected,base_path,base_stamp.sha256)
    # The old loader already established exact membership of all base pins.
    # Keep every one, including non-scope software and source archives.
    for name,wanted in base['pins'].items():_put(expected,_local(name),wanted)
    for name,wanted in scope.evidence.items():_put(expected,_local(name),wanted)
    for name,wanted in ALGORITHM_PINS.items():_put(expected,ROOT/name,wanted)
    for path in (Path(__file__),Path(legacy.__file__),ROOT/'integration/host_runtime/macro_bundle_cache.py',
            ROOT/'integration/host_runtime/contracts.py',manifest_path,
            visibility/'build-capability.json',visibility/'template-safety.json'):_put(expected,path)
    if len(expected)>8192:fail('pin_set_too_large')
    if stable_file(base_path,maximum=2*1024*1024)[0]!=base_stamp:fail('base_changed_during_review')
    _algorithms()
    return scope,{name:expected[name] for name in sorted(expected)}


def required_files_v12(value):
    """Pure proof replay, including base bytes, all evidence and new sources."""
    _,pins=catalog_inputs_v12(value)
    return [Path(name) for name in pins]


def _uncached(path):
    _,raw=stable_file(path,maximum=2*1024*1024,keep_bytes=True)
    value=json.loads(raw.decode('utf-8-sig'));scope,expected=catalog_inputs_v12(value)
    if type(value['pins']) is not dict or value['pins']!=expected:fail('exact_pins_required')
    return value,scope


def _session(scope,session):
    if session is not None and (type(session) is not dict or session.get('mod_sha256')!=scope.package_sha256):fail('session_package_mismatch')


def load_catalog_bundle_v12(path,session=None):
    """No live facts are cached; current session/package is checked every call."""
    try:
        value,scope=_CACHE.load(path,_uncached)
        _session(scope,session)
        return value,scope
    except ContractError:raise
    except (OSError,ValueError,KeyError,TypeError,UnicodeError,RecursionError):fail()


def create_catalog_bundle_v12(path,*,base_bundle,consumer_catalog_contracts,session=None):
    """Write one new file after exact reviews; never modifies the base or registry."""
    try:
        base_path=_local(str(Path(base_bundle).resolve(strict=True)))
        _,raw=stable_file(base_path,maximum=2*1024*1024,keep_bytes=True)
        header=json.loads(raw.decode('utf-8-sig'))
        value=dict(schema_version=12,kind=KIND,base_bundle=str(base_path),build=header.get('build'),visibility=header.get('visibility'),
            consumer_catalog_contracts=deepcopy(consumer_catalog_contracts),pins={})
        scope,value['pins']=catalog_inputs_v12(value);_session(scope,session)
        target=Path(path)
        if not target.is_absolute() or str(target).startswith('\\\\'):fail('canonical_local_path_required')
        with target.open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
        return load_catalog_bundle_v12(target,session)[1].public()
    except (ContractError,FileExistsError):raise
    except (OSError,ValueError,KeyError,TypeError,UnicodeError,RecursionError):fail()
