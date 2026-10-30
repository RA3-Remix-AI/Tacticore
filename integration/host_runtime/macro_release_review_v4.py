"""Explicit release grammar for source-bound unpublished V4 preparations.

Original transport journals are neither changed nor filtered for callers.
Only the pure old verifier's records reader receives the proven projection.
"""
from dataclasses import fields
import hashlib
import json
from pathlib import Path
from types import FunctionType
import uuid

from .contracts import ContractError,SessionBinding
from .resource_settlement_adapter import SettlementSession,digest
from . import macro_expansion_scope as legacy

ROOT=legacy.ROOT
KIND='guarded_admission_publication_contract_v4'
PUBLISHER=ROOT/'integration/host_runtime/raw_admission_publisher_v4.py'
PUBLISHER_SHA='5ea68144ca59e34f77443c40e9edba929694afd7ec6ec00a75333662b152d4c2'
CLIENT=ROOT/'native-ai/macro-policy-runtime-v2/client.py'
CLIENT_SHA='c67cbb37368a415e6fc1a56be0bef631fdeb1a993dde6f8ab3f7559685b666ae'
LEGACY_SHA='2c5bb72d463f9e1d1bdfd6391df2aae3aba021d78b506578d0735e28216542af'
FIELDS={'kind','schema_version','session','binding_hash','run_id','native_build_manifest_path','native_build_manifest_sha256',
    'publisher_source_path','publisher_source_sha256','client_source_path','client_source_sha256',
    'controller_factory_source_sha256','delivery_adapter_source_sha256','pre_execution_sources_sha256',
    'created_monotonic_ns','native_constructor_started'}

def fail(code='macro_release_v4_unverified'):raise ContractError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def _uuid(value):
    try:return type(value) is str and str(uuid.UUID(value))==value
    except (ValueError,TypeError,AttributeError):return False

def publication_v4_was_selected(output,*,journal=None,run_id=None):
    """A required selector cannot disappear into the legacy cleanup grammar.

    These signals only REQUIRE strict verification; they never prove release.
    The durable event also survives removal of the JSON marker/event copy.
    """
    output=Path(output)
    if (output/'publication-v4-contract.json').exists():return True
    path=output/'host-events.jsonl'
    if path.exists():
        raw=path.read_bytes()
        if len(raw)>256*1024*1024:fail('macro_release_v4_selector_history_bounds')
        events=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line]
        if any(type(row) is not dict for row in events):fail('macro_release_v4_selector_history_invalid')
        if any(row.get('kind')=='macro_admission_publication_contract_frozen' for row in events):return True
    database=getattr(journal,'_db',None)
    if database is not None:
        try:
            return database.execute('SELECT 1 FROM events WHERE run_id=? AND event_type=? LIMIT 1',
                (run_id,'macro_admission_publication_contract_frozen')).fetchone() is not None
        except Exception:fail('macro_release_v4_selector_history_unavailable')
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
    bundle=load(copies[Path(rows[2]['path']).resolve()][0])
    if (type(bundle) is not dict or bundle.get('schema_version') not in (10,11) or type(bundle.get('schema_version')) is not int
            or bundle.get('kind')!=('verified_macro_expansion_bootstrap' if bundle['schema_version']==10 else 'verified_macro_fixed_consumer_bootstrap')
            or type(bundle.get('pins')) is not dict):fail()
    if Path(rows[4]['path']).name!='binding.json':fail()
    binding=SessionBinding.from_dict(load(copies[Path(rows[4]['path']).resolve()][0]))
    recorded_session=load(copies[Path(rows[1]['path']).resolve()][0])
    return copies,bundle,binding,recorded_session,evidence

def validate_publication_contract_v4(contract_path,*,expected=None,expected_binding=None,expected_run_id=None):
    contract_path=Path(contract_path).resolve();host=contract_path.parent
    if (contract_path.name!='publication-v4-contract.json' or not host.is_relative_to(ROOT/'acceptance/runs')
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
    copies,bundle,archived_binding,recorded_session,evidence=_frozen_sources(host)
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
        ROOT/'integration/macro_host.py':copies[ROOT/'integration/macro_host.py'][1]}
    if (Path(marker['publisher_source_path']).resolve()!=PUBLISHER or Path(marker['client_source_path']).resolve()!=CLIENT
            or sources[PUBLISHER]!=PUBLISHER_SHA or sources[CLIENT]!=CLIENT_SHA
            or sha(PUBLISHER)!=PUBLISHER_SHA or sha(CLIENT)!=CLIENT_SHA or sha(Path(legacy.__file__))!=LEGACY_SHA):fail()
    for original,wanted in sources.items():
        if original not in copies or copies[original][1]!=wanted or bundle['pins'].get(str(original))!=wanted:fail()
    manifest_path=Path(marker['native_build_manifest_path']).resolve()
    if (manifest_path!=Path(bundle['build']).resolve()/'build-manifest.json'
            or sha(manifest_path)!=marker['native_build_manifest_sha256']
            or bundle['pins'].get(str(manifest_path))!=marker['native_build_manifest_sha256']):fail()
    manifest=load(manifest_path)
    if type(manifest) is not dict:fail()
    if expected is not None and manifest!=expected:fail()
    if manifest.get('protocol_version')!=2 or manifest.get('package_sha256')!=session.package_sha256:fail()
    event_path=host/'host-events.jsonl';event_raw=event_path.read_bytes()
    events=[json.loads(line) for line in event_raw.decode('utf-8-sig').splitlines() if line]
    if any(type(row) is not dict for row in events):fail()
    selected=[(i,row) for i,row in enumerate(events) if row.get('kind')=='macro_admission_publication_contract_frozen']
    constructors=[i for i,row in enumerate(events) if row.get('kind')=='macro_native_transport_constructor_begin']
    if len(selected)!=1 or len(constructors)!=1 or selected[0][0]>=constructors[0]:fail()
    event=selected[0][1];marker_sha=hashlib.sha256(raw).hexdigest()
    if (event.get('contract_sha256')!=marker_sha or event.get('publisher_source_sha256')!=PUBLISHER_SHA
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

def _assess_release_v4(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    marker,session,manifest,evidence=validate_publication_contract_v4(contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)
    directory=Path(directory).resolve();policy=(directory/'policy-probe.jsonl').resolve()
    if directory!=ROOT/'reports'/('macro-desktop-'+marker['run_id']):fail()
    input_bytes={directory/name:(directory/name).read_bytes() for name in ('preflight.json','final-state.json')}
    raw=policy.read_bytes()
    if len(raw)>256*1024*1024 or not raw.endswith(b'\n'):fail()
    rows=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines()]
    from .raw_admission_publisher_v4 import project_unpublished_records_v4
    projected,excluded=project_unpublished_records_v4(rows,session)
    # Reuse the exact old verifier with one explicit file-reader dependency.
    # It still hashes policy-probe.jsonl ORIGINAL bytes into its evidence.
    def records(path):return projected if Path(path).resolve()==policy else legacy.records(path)
    namespace=dict(legacy.v2_trial.__globals__,records=records)
    verifier=FunctionType(legacy.v2_trial.__code__,namespace,name='projected_v4_release_verifier',
        argdefs=legacy.v2_trial.__defaults__,closure=legacy.v2_trial.__closure__)
    verifier.__kwdefaults__=legacy.v2_trial.__kwdefaults__
    pre,final,actual,verified_rows,pins=verifier(directory,expected=manifest)
    if (pre!=json.loads(input_bytes[directory/'preflight.json'].decode('utf-8-sig'))
            or final!=json.loads(input_bytes[directory/'final-state.json'].decode('utf-8-sig'))):fail('macro_release_v4_source_changed')
    if verified_rows!=projected or not session.matches_native(final.get('native')):fail()
    if (final.get('session_id')!=session.session_id or final.get('pid')!=session.pid
            or final.get('process_creation_filetime')!=session.process_creation_filetime):fail()
    pre_native=pre.get('native',{})
    if any(pre_native.get(k)!=wanted for k,wanted in dict(player=session.game_identity[1],ai_player=session.ai_player,
            personality_wrapper=session.personality_wrapper,player_template=session.player_template).items()):fail()
    proof=dict(kind='macro_publication_v4_release_projection',schema_version=1,
        contract_sha256=evidence[str(Path(contract_path).resolve())],raw_records_sha256=hashlib.sha256(raw).hexdigest(),
        pre_attach_host_event_prefix_sha256=_pre_attach_event_prefix_sha(Path(contract_path).resolve().parent),
        original_record_count=len(rows),physical_record_count=len(projected),unpublished_pairs=excluded,
        excluded_pairs_sha256=digest(excluded),native_release_verified=True,
        admission_buffer_settlement_asserted=False,payment_or_refund_asserted=False)
    # Sidecar is written only by Host/explicit review publisher. Read-only
    # validation and timeline receive the same recomputed pure proof below.
    for path,wanted in {**evidence,**pins}.items():
        if sha(path)!=wanted:fail('macro_release_v4_source_changed')
    if raw!=policy.read_bytes():fail('macro_release_v4_source_changed')
    if any(path.read_bytes()!=original for path,original in input_bytes.items()):fail('macro_release_v4_source_changed')
    evidence.update(pins);evidence[str(Path(__file__).resolve())]=sha(__file__)
    proof['reviewer_source_sha256']=sha(__file__)
    event_path=str(Path(contract_path).resolve().parent/'host-events.jsonl')
    proof['evidence']=[dict(path=path,sha256=wanted) for path,wanted in sorted(evidence.items()) if path!=event_path]
    return proof,(pre,final,actual,rows,evidence)

def v4_release_trial(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    """Return old tuple shape with COMPLETE original records and SHA evidence."""
    return _assess_release_v4(directory,contract_path=contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)[1]

def projection_proof_v4(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    return _assess_release_v4(directory,contract_path=contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)

def write_release_review_v4(directory,*,contract_path,expected=None,expected_binding=None,expected_run_id=None):
    """Host-only append: preserve full proof beside its pre-attach selector."""
    proof,result=projection_proof_v4(directory,contract_path=contract_path,expected=expected,
        expected_binding=expected_binding,expected_run_id=expected_run_id)
    path=Path(contract_path).resolve().with_name('publication-v4-release-review.json')
    with path.open('x',encoding='utf8') as stream:json.dump(proof,stream,indent=2);stream.write('\n')
    return path,sha(path),result
