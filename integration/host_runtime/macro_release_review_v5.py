"""Explicit schema12 release grammar; no current product routing is widened.

Original transport journals are neither changed nor filtered for callers.
Only the pure old verifier's records reader receives the proven projection.
"""
from dataclasses import fields
import hashlib
import json
from pathlib import Path
from types import FunctionType
from functools import wraps
import uuid

from .contracts import ContractError,SessionBinding
from .resource_settlement_adapter import SettlementSession,digest
from . import macro_expansion_scope as legacy
from . import macro_catalog_bundle_v12 as catalog
from .macro_consumer_catalog_scope_v2 import ConsumerCatalogScopeV2

ROOT=legacy.ROOT
KIND='guarded_catalog_admission_publication_contract_v5'
SELECTOR='macro_catalog_admission_publication_contract_v5_frozen'
EXTENSION_FIELDS=frozenset(('native_release_contract','publication_v5_contract_sha256',
    'publication_v5_release_review_sha256','publication_v5_outer_bundle_sha256','publication_v5_base_bundle_sha256'))
PUBLISHER=ROOT/'integration/host_runtime/raw_admission_publisher_v4.py'
PUBLISHER_SHA='5ea68144ca59e34f77443c40e9edba929694afd7ec6ec00a75333662b152d4c2'
CLIENT=ROOT/'native-ai/macro-policy-runtime-v2/client.py'
CLIENT_SHA='c67cbb37368a415e6fc1a56be0bef631fdeb1a993dde6f8ab3f7559685b666ae'
LEGACY_SHA='2c5bb72d463f9e1d1bdfd6391df2aae3aba021d78b506578d0735e28216542af'
CATALOG_SHA='970af8933350b76bc86749de669727fd3810c456c086d9edff738c97f298aaac'
FIELDS={'kind','schema_version','session','binding_hash','run_id','native_build_manifest_path','native_build_manifest_sha256',
    'publisher_source_path','publisher_source_sha256','client_source_path','client_source_sha256',
    'controller_factory_source_sha256','delivery_adapter_source_sha256','pre_execution_sources_sha256',
    'created_monotonic_ns','native_constructor_started','outer_bundle_path','outer_bundle_sha256',
    'base_bundle_path','base_bundle_sha256','catalog_loader_source_sha256','reviewer_source_sha256'}

def fail(code='macro_release_v5_unverified'):raise ContractError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def contract_errors(function):
    @wraps(function)
    def guarded(*args,**kwargs):
        try:return function(*args,**kwargs)
        except ContractError:raise
        except (OSError,ValueError,KeyError,TypeError,AttributeError,UnicodeError,RecursionError):fail()
    return guarded
def _uuid(value):
    try:return type(value) is str and str(uuid.UUID(value))==value
    except (ValueError,TypeError,AttributeError):return False

@contract_errors
def publication_v5_was_selected(output,*,journal=None,run_id=None):
    """A required selector cannot disappear into the legacy cleanup grammar.

    These signals only REQUIRE strict verification; they never prove release.
    The durable event also survives removal of the JSON marker/event copy.
    """
    output=Path(output)
    if (output/'publication-v5-contract.json').exists():return True
    # The immutable pre-execution outer bundle is another non-authorizing
    # selector. Removing marker, event and receipt extensions cannot downgrade
    # a schema12 run to the current schema10/11 cleanup grammar.
    source_path=output/'sources.json'
    if source_path.exists():
        source=load(source_path)
        if type(source) is not dict or type(source.get('sources')) is not list or len(source['sources'])<3:fail()
        row=source['sources'][2]
        if (type(row) is not dict or type(row.get('copy')) is not str
                or row['copy']!='2-'+Path(row.get('path','')).name):fail()
        copy=(output/'source'/row['copy']).resolve()
        if copy.parent!=(output/'source').resolve() or sha(copy)!=row.get('sha256'):fail()
        outer=load(copy)
        if type(outer) is not dict:fail()
        if outer.get('schema_version')==12 or outer.get('kind')==catalog.KIND:return True
    path=output/'host-events.jsonl'
    if path.exists():
        raw=path.read_bytes()
        if len(raw)>256*1024*1024:fail('macro_release_v5_selector_history_bounds')
        events=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line]
        if any(type(row) is not dict for row in events):fail('macro_release_v5_selector_history_invalid')
        if any(row.get('kind')==SELECTOR for row in events):return True
    database=getattr(journal,'_db',None)
    if database is not None:
        try:
            return database.execute('SELECT 1 FROM events WHERE run_id=? AND event_type=? LIMIT 1',
                (run_id,SELECTOR)).fetchone() is not None
        except Exception:fail('macro_release_v5_selector_history_unavailable')
    return False

def _frozen_sources(host):
    path=host/'sources.json';raw=path.read_bytes();value=json.loads(raw.decode('utf-8-sig'))
    if type(value) is not dict:fail()
    rows=value.get('sources')
    if value.get('kind')!='pre_execution_macro_host_sources' or type(rows) is not list or len(rows)<5:fail()
    copies={};evidence={str(path):hashlib.sha256(raw).hexdigest()}
    for index,row in enumerate(rows):
        if (type(row) is not dict or set(row)!={'path','copy','sha256'} or type(row['path']) is not str
                or not Path(row['path']).is_absolute() or type(row['copy']) is not str
                or row['copy']!=str(index)+'-'+Path(row['path']).name):fail()
        original=Path(row['path']).resolve();copy=(host/'source'/row['copy']).resolve()
        if original in copies or copy.parent!=(host/'source').resolve() or sha(copy)!=row['sha256']:fail()
        copies[original]=(copy,row['sha256']);evidence[str(copy)]=row['sha256']
    if Path(rows[0]['path']).resolve()!=ROOT/'integration/macro_host.py':fail()
    outer_path=Path(rows[2]['path']).resolve();bundle=load(copies[outer_path][0])
    if (type(bundle) is not dict or type(bundle.get('schema_version')) is not int or bundle['schema_version']!=12
            or bundle.get('kind')!=catalog.KIND or type(bundle.get('pins')) is not dict):fail()
    # Real original bytes and both pre-execution archive entries are required.
    # Full exact-pin and per-action qualification replay follows below.
    if sha(outer_path)!=copies[outer_path][1]:fail('macro_release_v5_outer_changed')
    base_path=catalog._local(bundle.get('base_bundle'))
    if base_path not in copies or sha(base_path)!=copies[base_path][1]:fail('macro_release_v5_base_archive_required')
    base=load(copies[base_path][0])
    if (type(base) is not dict or type(base.get('schema_version')) is not int or base['schema_version']!=11
            or base.get('kind')!='verified_macro_fixed_consumer_bootstrap'
            or bundle['pins'].get(str(base_path))!=copies[base_path][1]):fail('macro_release_v5_base_binding')
    if sha(Path(catalog.__file__))!=CATALOG_SHA:fail('macro_release_v5_catalog_source_changed')
    # Intentionally call the complete uncached proof on every release review.
    # A prior green assessment or cached scope cannot replace raw qualification.
    verified,scope=catalog._uncached(outer_path)
    if verified!=bundle or type(scope) is not ConsumerCatalogScopeV2 or scope.consumer_catalog_revision!=2:
        fail('macro_release_v5_catalog_qualification')
    for name,wanted in bundle['pins'].items():
        if sha(name)!=wanted:fail('macro_release_v5_catalog_evidence_changed')
        evidence[name]=wanted
    evidence[str(outer_path)]=copies[outer_path][1]
    evidence[str(base_path)]=copies[base_path][1]
    if Path(rows[4]['path']).name!='binding.json':fail()
    binding=SessionBinding.from_dict(load(copies[Path(rows[4]['path']).resolve()][0]))
    recorded_session=load(copies[Path(rows[1]['path']).resolve()][0])
    return copies,bundle,binding,recorded_session,evidence,outer_path,base_path,scope

@contract_errors
def validate_publication_contract_v5(contract_path,*,expected=None,expected_binding=None,expected_run_id=None):
    contract_path=Path(contract_path).resolve();host=contract_path.parent
    if (contract_path.name!='publication-v5-contract.json' or not host.is_relative_to(ROOT/'acceptance/runs')
            or not contract_path.is_file()):fail()
    raw=contract_path.read_bytes();marker=json.loads(raw.decode('utf-8-sig'))
    if (type(marker) is not dict or set(marker)!=FIELDS or marker.get('kind')!=KIND
            or type(marker.get('schema_version')) is not int or marker['schema_version']!=1
            or marker.get('native_constructor_started') is not False or not _uuid(marker.get('run_id'))
            or type(marker.get('created_monotonic_ns')) is not int or marker['created_monotonic_ns']<=0
            or type(marker.get('session')) is not dict
            or set(marker['session'])!={field.name for field in fields(SettlementSession)}):fail()
    data=dict(marker['session']);data['game_identity']=tuple(data['game_identity']);session=SettlementSession(**data);session.validate()
    if expected_run_id is not None and marker['run_id']!=expected_run_id:fail()
    if expected_binding is not None:
        if (type(expected_binding) is not SessionBinding or marker['binding_hash']!=expected_binding.binding_hash
                or session.session_id!=expected_binding.session_id or session.pid!=expected_binding.game_process_id
                or session.package_sha256!=expected_binding.mod_sha256 or session.executable_sha256!=expected_binding.game_sha256
                or expected_binding.player_id!=3):fail()
        from .session_discovery_native import require_creation
        require_creation(expected_binding.game_process_start,session.process_creation_filetime)
    copies,bundle,archived_binding,recorded_session,evidence,outer_path,base_path,scope=_frozen_sources(host)
    if (marker['outer_bundle_path']!=str(outer_path) or marker['base_bundle_path']!=str(base_path)
            or marker['outer_bundle_sha256']!=copies[outer_path][1] or marker['base_bundle_sha256']!=copies[base_path][1]
            or marker['catalog_loader_source_sha256']!=CATALOG_SHA
            or marker['reviewer_source_sha256']!=sha(__file__)
            or scope.package_sha256!=session.package_sha256):fail('macro_release_v5_bundle_binding')
    if (type(recorded_session) is not dict or marker['binding_hash']!=archived_binding.binding_hash
            or session.session_id!=archived_binding.session_id or session.pid!=archived_binding.game_process_id
            or session.executable_sha256!=archived_binding.game_sha256 or session.package_sha256!=archived_binding.mod_sha256
            or archived_binding.player_id!=3 or recorded_session.get('session_id')!=session.session_id
            or recorded_session.get('pid')!=session.pid
            or recorded_session.get('process_creation_filetime')!=session.process_creation_filetime
            or recorded_session.get('mod_sha256')!=session.package_sha256):fail()
    from .session_discovery_native import require_creation
    require_creation(archived_binding.game_process_start,session.process_creation_filetime)
    if expected_binding is not None and archived_binding!=expected_binding:fail()
    if marker['pre_execution_sources_sha256']!=evidence[str(host/'sources.json')]:fail()
    sources={PUBLISHER:marker['publisher_source_sha256'],CLIENT:marker['client_source_sha256'],
        ROOT/'integration/host_runtime/macro_expansion_factory_v4.py':marker['controller_factory_source_sha256'],
        ROOT/'integration/host_runtime/macro_admission_delivery_v4.py':marker['delivery_adapter_source_sha256'],
        Path(__file__).resolve():sha(__file__),
        Path(catalog.__file__).resolve():CATALOG_SHA,
        **{(catalog.ROOT/name).resolve():wanted for name,wanted in catalog.ALGORITHM_PINS.items()
           if name in ('integration/host_runtime/macro_consumer_catalog_review_v2.py',
                       'integration/host_runtime/macro_consumer_catalog_scope_v2.py')},
        ROOT/'integration/macro_host.py':copies[ROOT/'integration/macro_host.py'][1]}
    if (Path(marker['publisher_source_path']).resolve()!=PUBLISHER or Path(marker['client_source_path']).resolve()!=CLIENT
            or sources[PUBLISHER]!=PUBLISHER_SHA or sources[CLIENT]!=CLIENT_SHA
            or sha(PUBLISHER)!=PUBLISHER_SHA or sha(CLIENT)!=CLIENT_SHA or sha(Path(legacy.__file__))!=LEGACY_SHA):fail()
    for original,wanted in sources.items():
        # v5 did not exist in the frozen v12 exact-pin derivation. Its own
        # source has an explicit marker+archive binding instead of adding an
        # arbitrary unsupported pin to that older immutable closure.
        if original not in copies or copies[original][1]!=wanted:fail()
        if original!=Path(__file__).resolve() and bundle['pins'].get(str(original))!=wanted:fail()
    manifest_path=Path(marker['native_build_manifest_path']).resolve()
    if (manifest_path!=Path(bundle['build']).resolve()/'build-manifest.json'
            or sha(manifest_path)!=marker['native_build_manifest_sha256']
            or bundle['pins'].get(str(manifest_path))!=marker['native_build_manifest_sha256']):fail()
    manifest=load(manifest_path)
    if type(manifest) is not dict:fail()
    if expected is not None and manifest!=expected:fail()
    if (type(manifest.get('protocol_version')) is not int or manifest['protocol_version']!=2
            or type(manifest.get('epoch')) is not int or manifest['epoch']!=4
            or manifest.get('same_process_reattach_supported') is not False
            or manifest.get('package_sha256')!=session.package_sha256):fail()
    event_path=host/'host-events.jsonl';event_raw=event_path.read_bytes()
    events=[json.loads(line) for line in event_raw.decode('utf-8-sig').splitlines() if line]
    if any(type(row) is not dict for row in events):fail()
    selected=[(i,row) for i,row in enumerate(events) if row.get('kind')==SELECTOR]
    constructors=[i for i,row in enumerate(events) if row.get('kind')=='macro_native_transport_constructor_begin']
    if len(selected)!=1 or len(constructors)!=1 or selected[0][0]>=constructors[0]:fail()
    event=selected[0][1];marker_sha=hashlib.sha256(raw).hexdigest()
    if (event.get('contract_sha256')!=marker_sha or event.get('publisher_source_sha256')!=PUBLISHER_SHA
            or event.get('outer_bundle_sha256')!=marker['outer_bundle_sha256']
            or event.get('base_bundle_sha256')!=marker['base_bundle_sha256']
            or event.get('native_constructor_started') is not False or event.get('session_id')!=session.session_id
            or events[constructors[0]].get('session_id')!=session.session_id):fail()
    evidence.update({str(contract_path):marker_sha,str(event_path):hashlib.sha256(event_raw).hexdigest(),str(manifest_path):sha(manifest_path),
        str(PUBLISHER):PUBLISHER_SHA,str(CLIENT):CLIENT_SHA,str(Path(legacy.__file__).resolve()):LEGACY_SHA,
        str(Path(__file__).resolve()):sources[Path(__file__).resolve()]})
    return marker,session,manifest,evidence

def _pre_attach_event_prefix_sha(host):
    raw=(host/'host-events.jsonl').read_bytes();lines=raw.splitlines(keepends=True)
    values=[json.loads(line) for line in lines]
    if any(type(row) is not dict for row in values):fail()
    constructors=[i for i,row in enumerate(values) if row.get('kind')=='macro_native_transport_constructor_begin']
    if len(constructors)!=1:fail()
    return hashlib.sha256(b''.join(lines[:constructors[0]+1])).hexdigest()

def _assess_release_v5(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    marker,session,manifest,evidence=validate_publication_contract_v5(contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)
    directory=Path(directory).resolve();policy=(directory/'policy-probe.jsonl').resolve()
    if directory!=ROOT/'reports'/('macro-desktop-'+marker['run_id']):fail()
    input_bytes={directory/name:(directory/name).read_bytes() for name in ('preflight.json','final-state.json')}
    raw=policy.read_bytes()
    if len(raw)>256*1024*1024 or not raw.endswith(b'\n'):fail()
    rows=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines()]
    if any(type(row) is not dict for row in rows):fail()
    from .raw_admission_publisher_v4 import project_unpublished_records_v4
    projected,excluded=project_unpublished_records_v4(rows,session)
    if any(row.get('native_gate_acknowledged') is not True
           or type(row.get('native',{}).get('active')) is not int or row['native']['active']!=0
           for row in projected if row.get('kind')=='command_acknowledged'):fail('macro_release_v5_callback_not_quiescent')
    # Reuse the exact old verifier with one explicit file-reader dependency.
    # It still hashes policy-probe.jsonl ORIGINAL bytes into its evidence.
    def records(path):return projected if Path(path).resolve()==policy else legacy.records(path)
    namespace=dict(legacy.v2_trial.__globals__,records=records)
    verifier=FunctionType(legacy.v2_trial.__code__,namespace,name='projected_v5_release_verifier',
        argdefs=legacy.v2_trial.__defaults__,closure=legacy.v2_trial.__closure__)
    verifier.__kwdefaults__=legacy.v2_trial.__kwdefaults__
    pre,final,actual,verified_rows,pins=verifier(directory,expected=manifest)
    if (pre!=json.loads(input_bytes[directory/'preflight.json'].decode('utf-8-sig'))
            or final!=json.loads(input_bytes[directory/'final-state.json'].decode('utf-8-sig'))):fail('macro_release_v5_source_changed')
    if verified_rows!=projected or not session.matches_native(final.get('native')):fail()
    if (final.get('session_id')!=session.session_id or final.get('pid')!=session.pid
            or final.get('process_creation_filetime')!=session.process_creation_filetime):fail()
    pre_native=pre.get('native',{})
    if any(pre_native.get(k)!=wanted for k,wanted in dict(player=session.game_identity[1],ai_player=session.ai_player,
            personality_wrapper=session.personality_wrapper,player_template=session.player_template).items()):fail()
    proof=dict(kind='macro_publication_v5_release_projection',schema_version=1,
        contract_sha256=evidence[str(Path(contract_path).resolve())],raw_records_sha256=hashlib.sha256(raw).hexdigest(),
        outer_bundle_path=marker['outer_bundle_path'],outer_bundle_sha256=marker['outer_bundle_sha256'],
        base_bundle_path=marker['base_bundle_path'],base_bundle_sha256=marker['base_bundle_sha256'],
        pre_attach_host_event_prefix_sha256=_pre_attach_event_prefix_sha(Path(contract_path).resolve().parent),
        original_record_count=len(rows),physical_record_count=len(projected),unpublished_pairs=excluded,
        excluded_pairs_sha256=digest(excluded),native_release_verified=True,
        admission_buffer_settlement_asserted=False,payment_or_refund_asserted=False)
    # Sidecar is written only by Host/explicit review publisher. Read-only
    # validation and timeline receive the same recomputed pure proof below.
    for path,wanted in {**evidence,**pins}.items():
        if sha(path)!=wanted:fail('macro_release_v5_source_changed')
    if raw!=policy.read_bytes():fail('macro_release_v5_source_changed')
    if any(path.read_bytes()!=original for path,original in input_bytes.items()):fail('macro_release_v5_source_changed')
    evidence.update(pins);evidence[str(Path(__file__).resolve())]=sha(__file__)
    proof['reviewer_source_sha256']=sha(__file__)
    event_path=str(Path(contract_path).resolve().parent/'host-events.jsonl')
    proof['evidence']=[dict(path=path,sha256=wanted) for path,wanted in sorted(evidence.items()) if path!=event_path]
    return proof,(pre,final,actual,rows,evidence)

@contract_errors
def v5_release_trial(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    """Return old tuple shape with COMPLETE original records and SHA evidence."""
    return _assess_release_v5(directory,contract_path=contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)[1]

@contract_errors
def projection_proof_v5(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    return _assess_release_v5(directory,contract_path=contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)

def write_release_review_v5(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    """Host-only append: preserve full proof beside its pre-attach selector."""
    proof,result=projection_proof_v5(directory,contract_path=contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)
    path=Path(contract_path).resolve().with_name('publication-v5-release-review.json')
    with path.open('x',encoding='utf8') as stream:json.dump(proof,stream,indent=2);stream.write('\n')
    return path,sha(path),result


@contract_errors
def validate_release_extension_v5(directory,*,contract_path,release,receipt,expected=None,expected_binding=None,expected_run_id=None):
    """Future explicit route must match BOTH receipts and recomputed sidecar.

    This helper grants only native cleanup. Caller still validates its normal
    durable journal, host incarnation, binding and unresolved command checks.
    No exception may be interpreted as permission to try an older grammar.
    """
    proof,result=projection_proof_v5(directory,contract_path=contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)
    path=Path(contract_path).resolve().with_name('publication-v5-release-review.json')
    raw=path.read_bytes()
    if json.loads(raw.decode('utf-8-sig'))!=proof:fail('macro_release_v5_sidecar_mismatch')
    extension=dict(native_release_contract=KIND,publication_v5_contract_sha256=proof['contract_sha256'],
        publication_v5_release_review_sha256=hashlib.sha256(raw).hexdigest(),publication_v5_outer_bundle_sha256=proof['outer_bundle_sha256'],
        publication_v5_base_bundle_sha256=proof['base_bundle_sha256'])
    for value in (release,receipt):
        if (type(value) is not dict or value.get('native_release_verified') is not True
                or any(value.get(key)!=wanted for key,wanted in extension.items())):fail('macro_release_v5_extension_required')
    if path.read_bytes()!=raw:fail('macro_release_v5_sidecar_changed')
    return extension,result
