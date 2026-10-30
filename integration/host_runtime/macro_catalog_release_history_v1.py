"""Historical V5 native cleanup only; never a catalog admission/upgrade.

First release still uses the frozen V5 current-file qualifier. This reader
requires its completed durable receipt and recomputes the full native proof
against pre-execution software bytes. No archived source is executed. Known
frozen Python algorithms receive explicit readers in private namespaces; no
module global is patched. Native runtime and qualification artifacts remain
current and hash checked; only workspace software may have been upgraded.
"""
from copy import deepcopy
from dataclasses import fields
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from types import FunctionType,SimpleNamespace

from .contracts import ContractError,SessionBinding
from . import macro_release_review_v5 as frozen
from . import macro_catalog_bundle_v12 as catalog
from . import macro_expansion_scope as native

ROOT=frozen.ROOT
V5_SHA='c9c01c57f536594e597d3a466fac25c31518119166a78e348b17d0dceacbe4fb'
JOURNAL_KIND='macro_catalog_v5_pre_execution_journal_location_v1'
SOFTWARE_ROOTS=('integration','strategy','native-ai','production','visibility','agent_runtime/src','desktop-ui/src','acceptance')
SOFTWARE_SUFFIXES=frozenset(('.py','.ts','.tsx','.rs','.cpp','.h'))

def executed_algorithm_paths():
    """Exact project/external Python used by historical native proof replay.

    These are executable algorithms, not ordinary Host/UI/strategy records.
    Includes native.runtime_build -> build.profile/verify_inputs and its
    compiled stream parser/import chain. No path is accepted from a caller.
    """
    names=('integration/host_runtime/contracts.py',
        'integration/host_runtime/resource_settlement_adapter.py',
        'integration/host_runtime/resource_reservations.py',
        'integration/host_runtime/macro_policy_runtime.py',
        'integration/host_runtime/macro_release_review_v5.py',
        'integration/host_runtime/macro_catalog_release_history_v1.py',
        'integration/host_runtime/macro_catalog_bundle_v12.py',
        'integration/host_runtime/macro_expansion_scope.py',
        'integration/host_runtime/raw_admission_publisher_v4.py',
        'native-ai/macro-policy-runtime-v2/client.py','native-ai/macro-policy-runtime-v2/build.py',
        'native-ai/macro_expansion_contract.py','native-ai/stage_macro_expansion.py',
        'native-ai/stage_macro_group_roles.py','native-ai/stage_macro_base_defense.py',
        'native-ai/stage_macro_regions.py','native-ai/stage_macro_policy.py',
        'native-ai/read_map_waypoints.py','native-ai/stage_macro_probe.py',
        'native-ai/stage_commanders.py','native-ai/validate_side_imports.py',
        'reference/Ra3-Copilot/unit-codes/tools/sage_hash.py')
    return tuple((ROOT/name).resolve() for name in names)+(Path('E:/RA3Modding/Analysis/Remix037/manifest.py').resolve(),)

def _require_creation_v1(start,ticks):
    """Fixed pure v1 FILETIME conversion; discovery/UI code is not executed."""
    try:
        parsed=datetime.fromisoformat(start)
        if parsed.tzinfo is None:raise ValueError()
        delta=parsed.astimezone(timezone.utc)-datetime(1601,1,1,tzinfo=timezone.utc)
        lower=((delta.days*86400+delta.seconds)*1_000_000+delta.microseconds)*10
        if type(ticks) is not int or not lower<=ticks<=lower+9:raise ValueError()
    except (ValueError,TypeError,OverflowError):fail()

def fail(code='macro_catalog_historical_release_v1_unverified'):raise ContractError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def is_software(path):
    path=Path(path).resolve()
    return path.suffix in SOFTWARE_SUFFIXES and any(path.is_relative_to(ROOT/name) for name in SOFTWARE_ROOTS)

def _clone(function,**dependencies):
    """Execute only installed known code, with explicit immutable dependencies."""
    original=getattr(function,'__wrapped__',function)
    clone=FunctionType(original.__code__,dict(original.__globals__,**dependencies),
        name=original.__name__,argdefs=original.__defaults__,closure=original.__closure__)
    clone.__kwdefaults__=original.__kwdefaults__
    return clone

def _archives(output):
    path=output/'sources.json';raw=path.read_bytes();value=json.loads(raw.decode('utf-8-sig'))
    rows=value.get('sources') if type(value) is dict else None
    if value.get('kind')!='pre_execution_macro_host_sources' or type(rows) is not list or len(rows)<6:fail()
    copies={};evidence={str(path):hashlib.sha256(raw).hexdigest()}
    for index,row in enumerate(rows):
        if (type(row) is not dict or set(row)!={'path','copy','sha256'} or type(row['path']) is not str
                or not Path(row['path']).is_absolute() or row['copy']!=str(index)+'-'+Path(row['path']).name):fail()
        original=Path(row['path']).resolve();copy=(output/'source'/row['copy']).resolve()
        if original in copies or copy.parent!=(output/'source').resolve() or sha(copy)!=row['sha256']:fail()
        copies[original]=(copy,row['sha256']);evidence[str(copy)]=row['sha256']
    if Path(rows[0]['path']).resolve()!=ROOT/'integration/macro_host.py':fail()
    outer_path=Path(rows[2]['path']).resolve();outer=load(copies[outer_path][0])
    if type(outer) is not dict or set(outer)!=catalog.FIELDS or type(outer.get('schema_version')) is not int or outer['schema_version']!=12:fail()
    # Run before executing contract/session, catalog helpers or native build
    # algorithms. Historical software archives never authorize new algorithms.
    if type(outer.get('pins')) is not dict:fail()
    for algorithm in executed_algorithm_paths():
        wanted=outer['pins'].get(str(algorithm))
        if algorithm not in copies or copies[algorithm][1]!=wanted or sha(algorithm)!=wanted:fail()
    base_path,_,_,_=catalog._header(outer)
    if type(outer.get('pins')) is not dict or not 1<=len(outer['pins'])<=8192 or base_path not in copies:fail()
    if sha(outer_path)!=copies[outer_path][1] or sha(base_path)!=copies[base_path][1]:fail()
    base=load(copies[base_path][0])
    if (type(base) is not dict or type(base.get('schema_version')) is not int or base['schema_version']!=11
            or base.get('kind')!='verified_macro_fixed_consumer_bootstrap' or type(base.get('pins')) is not dict
            or outer['pins'].get(str(base_path))!=copies[base_path][1]
            or any(outer['pins'].get(name)!=wanted for name,wanted in base['pins'].items())):fail()
    # Software is never supplied by an arbitrary archive path. Membership,
    # original path and byte digest must all match the original exact pins.
    for name,wanted in outer['pins'].items():
        original=Path(name).resolve()
        if str(original)!=name:fail()
        if is_software(original):
            if original not in copies or copies[original][1]!=wanted:fail()
        elif sha(original)!=wanted:fail()
        evidence[name]=wanted
    for path,wanted in ((Path(frozen.__file__).resolve(),V5_SHA),(Path(catalog.__file__).resolve(),frozen.CATALOG_SHA),
            (Path(native.__file__).resolve(),frozen.LEGACY_SHA),(frozen.PUBLISHER,frozen.PUBLISHER_SHA),(frozen.CLIENT,frozen.CLIENT_SHA),
            (Path(__file__).resolve(),sha(__file__))):
        if sha(path)!=wanted or path not in copies or copies[path][1]!=wanted or outer['pins'].get(str(path))!=wanted:fail()
    evidence[str(outer_path)]=copies[outer_path][1];evidence[str(base_path)]=copies[base_path][1]
    binding=SessionBinding.from_dict(load(copies[Path(rows[4]['path']).resolve()][0]))
    recorded=load(copies[Path(rows[1]['path']).resolve()][0])
    return copies,outer,binding,recorded,evidence,outer_path,base_path,SimpleNamespace(package_sha256=binding.mod_sha256)

def _durable(output,marker,release,receipt,copies,journal):
    if type(release) is not dict or release!=load(output/'macro-release.json'):fail()
    descriptor=output/'publication-v5-history-journal.json'
    if descriptor not in copies or sha(descriptor)!=copies[descriptor][1]:fail()
    location=load(copies[descriptor][0])
    if (type(location) is not dict or set(location)!={'kind','schema_version','ledger_path','run_id','binding_hash'}
            or location.get('kind')!=JOURNAL_KIND or type(location.get('schema_version')) is not int or location['schema_version']!=1
            or location['run_id']!=marker['run_id'] or location['binding_hash']!=marker['binding_hash']
            or type(location['ledger_path']) is not str or not Path(location['ledger_path']).is_absolute()
            or str(Path(location['ledger_path']).resolve())!=location['ledger_path']):fail()
    connection=None
    try:
        if journal is None:
            connection=sqlite3.connect(Path(location['ledger_path']).as_uri()+'?mode=ro',uri=True,timeout=5)
            database=connection
        else:
            database=journal._db
            actual=database.execute('PRAGMA database_list').fetchone()[2]
            if Path(actual).resolve()!=Path(location['ledger_path']):fail()
        if connection is not None:database.row_factory=sqlite3.Row
        run=database.execute('SELECT binding FROM runs WHERE run_id=?',(marker['run_id'],)).fetchone()
        rows=database.execute('SELECT * FROM commands WHERE run_id=?',(marker['run_id'],)).fetchall()
        stops=[row for row in rows if row['request_id']=='macro-stop' and row['operation']=='macro_policy_stop']
        starts=[row for row in rows if row['operation']=='host_start']
        if (run is None or SessionBinding.from_dict(json.loads(run['binding'])).binding_hash!=marker['binding_hash']
                or len(stops)!=1 or stops[0]['status']!='released'
                or len(starts)!=1 or starts[0]['status']!='completed'
                or any(row['status'] in ('reserved','dispatching','accepted','started','uncertain') for row in rows)):fail()
        started=json.loads(starts[0]['receipt'])
        if any(started.get(key)!=release.get(key) for key in ('host_pid','host_start_time')):fail()
        completed=json.loads(stops[0]['receipt'])
        if receipt is not None and completed!=receipt:fail()
        if (completed.get('native_release_verified') is not True or completed.get('binding_hash')!=marker['binding_hash']
                or completed.get('release_sha256')!=sha(output/'macro-release.json')
                or any(completed.get(key)!=release.get(key) for key in ('host_pid','host_start_time','final_state_sha256',*frozen.EXTENSION_FIELDS))):fail()
        selectors=database.execute('SELECT payload FROM events WHERE run_id=? AND event_type=?',(marker['run_id'],frozen.SELECTOR)).fetchall()
        if len(selectors)!=1:fail()
        event=json.loads(selectors[0]['payload'])
        if (event.get('contract_sha256')!=sha(output/'publication-v5-contract.json')
                or event.get('outer_bundle_sha256')!=marker['outer_bundle_sha256']
                or event.get('base_bundle_sha256')!=marker['base_bundle_sha256']
                or event.get('native_constructor_started') is not False):fail()
        return completed
    except sqlite3.Error:fail()
    finally:
        if connection is not None:connection.close()

@frozen.contract_errors
def historical_projection_v1(directory,*,output,release,receipt=None,journal=None,expected=None,expected_binding=None,expected_run_id=None):
    """Recompute native cleanup after a COMPLETED strict V5 release only.

    Catalog actions/eligibility are deliberately never returned or granted.
    Missing, failed or unknown durable completion cannot enter this grammar.
    """
    output=Path(output).resolve();contract=output/'publication-v5-contract.json'
    archived=_archives(output);copies=archived[0];marker=load(contract)
    durable=_durable(output,marker,release,receipt,copies,journal)
    def historical_sha(path):
        path=Path(path).resolve()
        return sha(copies[path][0]) if is_software(path) and path in copies else sha(path)
    validate=lambda path,**expected:_validate_historical_contract_v1(path,archived=archived,hash_reader=historical_sha,**expected)
    def pin(evidence,path,wanted=None):
        observed=historical_sha(path)
        if wanted is not None and observed!=wanted or str(Path(path).resolve()) in evidence and evidence[str(Path(path).resolve())]!=observed:fail()
        evidence[str(Path(path).resolve())]=observed
        return Path(path).resolve()
    raw_verifier=_clone(native.v2_trial,sha=historical_sha,pin=pin)
    assess=_clone(frozen._assess_release_v5,sha=historical_sha,validate_publication_contract_v5=validate,
        legacy=SimpleNamespace(v2_trial=raw_verifier,records=native.records))
    proof,result=assess(directory,contract_path=contract,expected=expected,expected_binding=expected_binding,expected_run_id=expected_run_id)
    # Re-read all archive bytes and the actual durable completion. A green
    # sidecar alone is never sufficient, including after a source upgrade.
    if _archives(output)!=archived:fail()
    if _durable(output,marker,release,receipt,copies,journal)!=durable:fail()
    return proof,result


def _validate_historical_contract_v1(contract_path,*,archived,hash_reader,expected=None,expected_binding=None,expected_run_id=None):
    # Static versioned copy of the frozen V5 pure contract grammar. Only
    # archive reader and pure FILETIME conversion differ; no archived code runs.
    sha=hash_reader;__file__=frozen.__file__
    FIELDS=frozen.FIELDS;KIND=frozen.KIND;SELECTOR=frozen.SELECTOR;SettlementSession=frozen.SettlementSession
    PUBLISHER=frozen.PUBLISHER;CLIENT=frozen.CLIENT
    PUBLISHER_SHA=frozen.PUBLISHER_SHA;CLIENT_SHA=frozen.CLIENT_SHA
    CATALOG_SHA=frozen.CATALOG_SHA;LEGACY_SHA=frozen.LEGACY_SHA
    _uuid=frozen._uuid;legacy=native
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
        _require_creation_v1(expected_binding.game_process_start,session.process_creation_filetime)
    copies,bundle,archived_binding,recorded_session,evidence,outer_path,base_path,scope=deepcopy(archived)
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
    _require_creation_v1(archived_binding.game_process_start,session.process_creation_filetime)
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
