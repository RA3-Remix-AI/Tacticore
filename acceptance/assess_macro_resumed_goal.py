"""Explicit schema9 G0-G8 join; frozen historical domains are not new grants.

This is a local acceptance evaluator. It performs no game, provider, RPC or UI
actions. Missing regression/playback/restoration proof keeps completion false.
Independent installation, cross-machine portability and native replay fidelity
are not added completion gates and are never claimed here.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path,PurePosixPath
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import assess,records,load,sha
from assess_macro_desktop_group_roles import evaluate as replay_roles,ROLE_GOALS,ATTACK_FIRST_SHA
from export_macro_timeline import project as project_timeline
from integration.host_runtime.macro_bundle import load_bundle
from integration.host_runtime.macro_policy_runtime import trial

DOMAIN_CHECKS={
    'model_build_intent_native_queue_and_foundation_feedback',
    'economic_and_technology_allocation_native_adoption_and_feedback',
    'model_unit_type_and_quantity_native_queue_effect_and_feedback',
    'actual_user_stop_preserves_bounded_production',
    'scout_native_movement_lawful_contact_and_later_model_feedback',
    'two_regions_native_group_movement_and_later_model_feedback','same_owned_units_later_reassigned',
    'real_native_infrastructure_defense_and_later_model_feedback','unit_operations_remain_native'}
REGRESSION_SOURCES=('integration/macro_host.py','strategy/http_adapter.py','strategy/macro_policy.py',
    'strategy/engine.py','strategy/battle_agent.py',
    'integration/host_runtime/macro_live.py',
    'integration/host_runtime/macro_policy_runtime.py','integration/host_runtime/macro_regions.py',
    'integration/host_runtime/macro_group_role_contract.py','integration/host_runtime/macro_group_role_scope.py',
    'desktop-ui/src/NativeApp.tsx')
HOST_REQUIRED_SOURCES=REGRESSION_SOURCES[:-1]
TRUSTED_FROZEN_REPORTS={
    'G6':'093bee24c623cdedd09bdb81868827fd88c1a195eebc7c9b350738ca64f055d5',
    'G7':'a8c70ae607d1ac6fdca6431613a07d9f844c7f5489400308e9f9a27c1d5f7f4c',
    'G8':'61250aa7773587f3885252189f1cbc281a1b43bc61ca9db3e107072078438f70'}
STAGE_CHECKS={
    'G6':DOMAIN_CHECKS,
    'G7':{'bounded_natural_session_verified','started_from_opening','genuine_continued_rounds',
        'current_client_start_observed','current_profile_revision_consumed','prior_model_strategy_reaches_later_round',
        'native_effect_and_later_real_feedback','native_opponent_and_natural_outcome','no_host_fault',
        'stopped_without_new_commands','independent_native_release','playable_timeline_and_result',
        'screenshots_logs_config_and_replay_delivered','replay_limits_disclosed'},
    'G8':{'native_baseline_has_no_model_or_commands_and_native_loss','fixed_policy_has_native_effect_and_natural_outcome',
        'model_has_genuine_closed_loop_and_natural_outcome','styles_consumed_with_same_historical_observation',
        'valid_style_decisions_differ','directed_live_choices_have_separate_native_effect',
        'shadow_is_separate_from_live','causal_and_winrate_limits_preserved'}}
TIMELINE_TEMPLATE_SHA='2e4e6f53773db5031f9c9d7efce0b466af50bdbf1a35cbb2125ca6bc2d0499d7'
TIMELINE_EXPORTER_SHA='4c035e8673ddccccc1c1296e33fe5ced4b371863b991a307d717ec6bb7161617'
REPORT_SPECS={
    'G6':('user_macro_G6_bounded_domain_coverage','assess_macro_capability_coverage.py'),
    'G7':('user_macro_G7_complete_match_assessment','assess_macro_complete_match.py'),
    'G8':('user_macro_G8_descriptive_contribution_assessment','assess_macro_contribution.py'),
    'role':('desktop_model_original_native_group_roles_assessment','assess_macro_desktop_group_roles.py')}


@dataclass(frozen=True)
class Inputs:
    run:Path
    run_id:str
    role_assessments:tuple[Path,...]
    domain_assessment:Path
    complete_match_assessment:Path
    contribution_assessment:Path
    download:Path
    original_export:Path
    original_profile:Path
    restored_profile:Path
    restoration:Path
    delivery:Path
    current_executable:Path
    current_frontend:Path
    current_screenshot:Path
    timeline_reviews:tuple[Path,...]=()
    regression_evidence:Path|None=None


def safe_child(folder,name):
    if type(name) is not str:raise ValueError('artifact_name_required')
    normalized=name.replace('\\','/');part=PurePosixPath(normalized)
    if (part.is_absolute() or ':' in normalized or str(part)!=normalized
            or any(p in ('','.','..') for p in part.parts)):
        raise ValueError('artifact_relative_path_required')
    path=(folder/Path(*part.parts)).resolve()
    if not path.is_relative_to(folder.resolve()) or path.is_symlink():raise ValueError('artifact_path_escape')
    return path


def verify_files(folder,files,*,strict=False):
    if not isinstance(files,dict) or not files:raise ValueError('artifact_inventory_required')
    evidence={}
    for name,description in files.items():
        path=safe_child(folder,name);digest=description if type(description) is str else description.get('sha256')
        if sha(path)!=digest:raise ValueError('artifact_hash_changed')
        if isinstance(description,dict) and (type(description.get('bytes')) is not int or path.stat().st_size!=description['bytes']):
            raise ValueError('artifact_size_changed')
        evidence[str(path)]=digest
    if strict:
        if any(p.is_symlink() for p in folder.rglob('*')):raise ValueError('delivery_symlink_not_allowed')
        actual={str(p.resolve()) for p in folder.rglob('*') if p.is_file() and p.resolve()!=(folder/'manifest.json').resolve()}
        if actual!=set(evidence):raise ValueError('delivery_inventory_incomplete')
    return evidence


def timeline_matches_raw(run,run_id,data):
    host=run/'battle-host';native=ROOT/'reports'/('macro-desktop-'+run_id)
    _,final,_,raw,_=trial(native)
    events=records(host/'host-events.jsonl');snapshots=records(host/'macro-snapshots.jsonl')
    acks={r['command_id']:r for r in raw if r['kind']=='command_acknowledged'}
    expected=project_timeline(events,acks,snapshots)
    expected.append(dict(t=final['native']['last_frame']/15,type='stop',native_release_verified=final['cleanup_verified']))
    expected.sort(key=lambda row:row['t'])
    source_paths=[host/'host-events.jsonl',host/'macro-snapshots.jsonl',host/'sources.json',host/'profile.json',native/'policy-probe.jsonl']
    source_hashes={p.name:sha(p) for p in source_paths}
    sources={r['name']:r['sha256'] for r in data.get('sources',[])}
    # Role qualification playback need not add a natural outcome. A separately
    # qualified G7 timeline supplies that result, rather than inventing one.
    return (data.get('kind')=='recorded_macro_timeline' and data.get('schema_version')==1
        and data.get('events')==expected and all(sources.get(name)==digest for name,digest in source_hashes.items())
        and data.get('unit_animation_recorded') is False)


def render_timeline_html(data):
    template_path=ROOT/'acceptance/macro_timeline.html';exporter=ROOT/'acceptance/export_macro_timeline.py'
    if sha(template_path)!=TIMELINE_TEMPLATE_SHA or sha(exporter)!=TIMELINE_EXPORTER_SHA:
        raise ValueError('timeline_player_source_not_approved')
    template=template_path.read_text(encoding='utf8')
    if template.count('__MACRO_TIMELINE_DATA__')!=1:raise ValueError('timeline_player_template_invalid')
    encoded=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026')
    return template.replace('__MACRO_TIMELINE_DATA__',encoded)


def verify_report(path,stage=None,*,seen=None):
    """Rehash report, frozen assessor and all nested report/source inventories."""
    path=Path(path).resolve();seen=set() if seen is None else seen
    if path in seen:return load(path),{}
    seen.add(path)
    if (path.parent/'INVALIDATED.txt').exists():raise ValueError('invalidated_assessment')
    value=load(path);assessor=path.parent/'assessor.py'
    if sha(assessor)!=value.get('assessor_sha256'):raise ValueError('assessment_source_changed')
    if stage:
        kind,source=REPORT_SPECS[stage]
        if value.get('kind')!=kind or sha(ROOT/'acceptance'/source)!=value['assessor_sha256']:
            raise ValueError('unsupported_assessment_version')
        if stage in TRUSTED_FROZEN_REPORTS:
            checks=value.get('checks')
            if not isinstance(checks,dict) or set(checks)!=STAGE_CHECKS[stage] or any(type(v) is not bool for v in checks.values()):
                raise ValueError('assessment_check_schema')
            # The approved historical snapshots anchor all nested result
            # fields. A copied assessor hash plus a new self-authored ledger
            # is not evidence that the historical stage was ever evaluated.
            if sha(path)!=TRUSTED_FROZEN_REPORTS[stage]:raise ValueError('untrusted_frozen_stage_snapshot')
    supplied=value.get('evidence')
    if not isinstance(supplied,dict) or not supplied:
        # These two early domain formats predate source ledgers. Recompute
        # their exact run from raw observations, as the frozen G6 evaluator
        # does; never accept their old success flags as substitute evidence.
        legacy={'desktop_macro_construction_evidence_assessment':'construction',
            'desktop_macro_production_evidence_assessment':'production'}
        if stage is not None or value.get('kind') not in legacy:raise ValueError('assessment_source_ledger_missing')
        from assess_macro_capability_coverage import replay_legacy_domain
        from assess_macro_desktop_production import assess as production
        from assess_macro_desktop_construction import assess as construction
        fresh,proof=replay_legacy_domain(path,construction if legacy[value['kind']]=='construction' else production)
        for source,digest in proof.items():
            if sha(Path(source))!=digest:raise ValueError('legacy_domain_evidence_changed')
        _,frozen=frozen_sources(next(Path(p).parent for p in proof if Path(p).name=='host-events.jsonl'))
        proof.update(frozen);proof[str(assessor)]=sha(assessor);return fresh,proof
    evidence={str(path):sha(path),str(assessor):sha(assessor)}
    for source,digest in supplied.items():
        source=Path(source).resolve()
        if sha(source)!=digest:raise ValueError('assessment_evidence_changed')
        evidence[str(source)]=digest
        if source.name=='assessment.json':
            nested=load(source)
            if 'assessor_sha256' in nested:
                _,joined=verify_report(source,seen=seen);evidence.update(joined)
        elif source.name in ('manifest.json','browser-review.json'):
            inventory=load(source).get('files')
            if isinstance(inventory,dict):evidence.update(verify_files(source.parent,inventory))
        elif source.name=='sources.json' and source.parent.name=='battle-host':
            _,joined=frozen_sources(source.parent);evidence.update(joined)
    return value,evidence


def frozen_sources(host):
    ledger=load(host/'sources.json');rows=ledger.get('sources');mapping={};evidence={str((host/'sources.json').resolve()):sha(host/'sources.json')}
    if not isinstance(rows,list) or not rows:raise ValueError('frozen_source_ledger_missing')
    copies=set()
    for row in rows:
        original=str(Path(row['path']).resolve());copy=safe_child(host/'source',row['copy'])
        if copy.parent!=(host/'source').resolve() or original in mapping or copy in copies:
            raise ValueError('frozen_source_alias')
        if sha(copy)!=row['sha256']:raise ValueError('frozen_source_changed')
        mapping[original]=row['sha256'];copies.add(copy);evidence[str(copy)]=row['sha256']
    return mapping,evidence


def regression_checks(path,frozen):
    require_host_sources(frozen)
    if path is None:return False,{},'regression_evidence_not_supplied'
    value=load(path);evidence={str(path.resolve()):sha(path)}
    if value.get('schema_version')!=1 or value.get('kind')!='macro_regression_evidence':raise ValueError('regression_schema')
    sources=value.get('sources',{});logs=value.get('logs',{})
    required={str((ROOT/p).resolve()) for p in REGRESSION_SOURCES}
    if not required<=set(sources) or set(logs)!={'macro','host','strategy','ui'}:raise ValueError('regression_scope_missing')
    for source,digest in sources.items():
        source=Path(source).resolve()
        if sha(source)!=digest:raise ValueError('regression_source_changed')
        if str(source) in frozen and frozen[str(source)]!=digest:raise ValueError('regression_source_differs_from_run')
        evidence[str(source)]=digest
    for name,row in logs.items():
        log=Path(row['path']).resolve();text=log.read_text(encoding='utf-8-sig')
        if (sha(log)!=row.get('sha256') or type(row.get('tests')) is not int or row['tests']<=0
                or row.get('result')!='passed' or not isinstance(row.get('command'),list)
                or not row['command'] or any(type(a) is not str or not a for a in row['command'])):
            raise ValueError('regression_log_binding')
        if name=='ui':
            number=lambda label:re.search(r'(?m)^[ \t]*(?:ℹ|#)?[ \t]*'+label+r'[ \t]+(\d+)[ \t]*$',text)
            counts={k:number(k) for k in ('tests','pass','fail','cancelled')}
            passed=all(counts.values()) and all(int(counts[k].group(1))==n for k,n in
                [('tests',row['tests']),('pass',row['tests']),('fail',0),('cancelled',0)])
        else:
            found=re.search(r'Ran\s+(\d+)\s+tests?\s+in\s+',text)
            passed=found is not None and int(found.group(1))==row['tests'] and text.rstrip().endswith('OK') and 'FAILED (' not in text
        if not passed:raise ValueError('regression_log_not_passed')
        evidence[str(log)]=row['sha256']
    return True,evidence,None


def require_host_sources(frozen):
    required={str((ROOT/p).resolve()) for p in HOST_REQUIRED_SOURCES}
    if not required<=set(frozen):raise ValueError('required_host_frozen_sources_missing')


def require_role_source_match(role_frozen,current_frozen):
    require_host_sources(role_frozen)
    for name in HOST_REQUIRED_SOURCES:
        path=str((ROOT/name).resolve())
        if role_frozen[path]!=current_frozen[path]:raise ValueError('role_execution_source_differs_from_current_run')


def role_report_inputs(value):
    paths=[Path(p).resolve() for p in value['evidence']]
    hosts={p.parent for p in paths if p.name=='host-events.jsonl' and p.parent.name=='battle-host'}
    if len(hosts)!=1:raise ValueError('role_exact_run_missing')
    host=next(iter(hosts));run=host.parent
    if not run.is_relative_to((ROOT/'acceptance/runs').resolve()):raise ValueError('role_run_outside_acceptance')
    candidates=[]
    for path in paths:
        if path.suffix=='.json' and path.name not in ('assessment.json','manifest.json','sources.json'):
            doc=load(path)
            if isinstance(doc,dict) and doc.get('redacted') is True and doc.get('run_id')==value['run_id']:
                candidates.append(path)
    if len(set(candidates))<2 or len({sha(p) for p in candidates})!=1:raise ValueError('role_download_export_pair_missing')
    return run,candidates[0],candidates[1]


def profile_restored(original,restored,proof,run_id,session_id,original_path,restored_path):
    clean=lambda p:{k:v for k,v in p.get('draft',{}).items() if k!='revision'}
    stable=('profile_id','name','connection_id','model','personality','doctrine','preferences','custom_traits','library_hash')
    return (bool(original.get('draft')) and clean(original)==clean(restored)
        and all(original.get(k)==restored.get(k) for k in stable)
        and type(restored.get('revision')) is int and restored['revision']>original.get('revision',0)
        and proof.get('restore_required') is False and proof.get('restored_via_actual_ui') is True
        and proof.get('host_stopped_before_restore') is True
        and proof.get('original_revision')==original['revision'] and proof.get('restored_revision')==restored['revision']
        and proof.get('original_effective_hash')==original['effective']['effective_hash']
        and proof.get('restored_effective_hash')==restored['effective']['effective_hash']
        and proof.get('original_snapshot_sha256')==sha(original_path)
        and proof.get('restored_snapshot_sha256')==sha(restored_path)
        and proof.get('current_run_id')==run_id and proof.get('current_session_id')==session_id)


def evaluate(args):
    run=args.run.resolve();host=run/'battle-host';session=load(run/'session.json');status=load(host/'host-status.json')
    if not run.is_relative_to((ROOT/'acceptance/runs').resolve()):raise ValueError('current_acceptance_run_required')
    profile=load(host/'profile.json');executed=load(run/'executed-client.json');release=load(host/'macro-release.json')
    binding=release['binding']
    if (status.get('session_id')!=session['session_id'] or status.get('pid')!=session['pid']
            or release.get('run_id')!=args.run_id or status.get('runtime_macro',{}).get('run_id')!=args.run_id
            or binding.get('session_id')!=session['session_id'] or binding.get('game_process_id')!=session['pid']):
        raise ValueError('current_run_binding_mismatch')
    common=assess(run,args.run_id,args.download.resolve(),args.original_export.resolve())
    native=ROOT/'reports'/('macro-desktop-'+args.run_id)
    _,final,manifest,_,native_evidence=trial(native)
    bundle,scope=load_bundle(run/'macro-budget-bundle.json',session)
    if bundle['schema_version']!=9 or session['mod_sha256']!=ATTACK_FIRST_SHA or manifest['package_sha256']!=ATTACK_FIRST_SHA:
        raise ValueError('current_schema9_group_roles_required')
    public=scope.public();allowed=set(public['available_actions'])
    if not set(ROLE_GOALS)<=allowed:raise ValueError('current_role_scope_missing')
    frozen,evidence=frozen_sources(host);require_host_sources(frozen)
    if any(sha(Path(path))!=frozen[path] for path in (str((ROOT/p).resolve()) for p in HOST_REQUIRED_SOURCES)):
        raise ValueError('current_runtime_source_differs_from_frozen_run')
    evidence.update(common['evidence']);evidence.update(native_evidence)
    values={};provenance=[]
    for stage,path in [('G6',args.domain_assessment),('G7',args.complete_match_assessment),('G8',args.contribution_assessment)]:
        value,proof=verify_report(path,stage);values[stage]=value;evidence.update(proof)
        provenance.append(dict(stage=stage,path=str(path.resolve()),sha256=sha(path),kind=value['kind'],
            assessor_sha256=value['assessor_sha256'],reused_frozen_evidence=True,trusted_frozen_snapshot=True,session_id=value.get('session_id')))
    qualified=set();role_sessions={};role_reports=[];role_runs={}
    if not 1<=len(args.role_assessments)<=3 or len(set(p.resolve() for p in args.role_assessments))!=len(args.role_assessments):
        raise ValueError('one_to_three_distinct_role_reports_required')
    for path in args.role_assessments:
        value,proof=verify_report(path,'role');role_run,download,original=role_report_inputs(value)
        role_bundle=load(role_run/'macro-budget-bundle.json');role_session=load(role_run/'session.json')
        if value.get('session_id')!=role_session['session_id']:raise ValueError('role_report_session_mismatch')
        if role_bundle.get('schema_version')!=9 or role_session.get('mod_sha256')!=ATTACK_FIRST_SHA:
            raise ValueError('role_report_is_not_schema9')
        fresh=replay_roles(role_run,value['run_id'],download,original)
        keys=('session_id','run_id','shared_checks','role_results','bounded_role_lifecycles_verified','no_new_commands_after_stop_verified',
            'independently_qualified_model_deployment_roles','all_three_model_role_feedback_loops_verified')
        if any(value.get(k)!=fresh.get(k) for k in keys):raise ValueError('role_report_replay_mismatch')
        roles=set(fresh['independently_qualified_model_deployment_roles']);qualified|=roles
        role_runs[(value['session_id'],value['run_id'])]=role_run
        for role in roles:role_sessions.setdefault(role,set()).add((value['session_id'],value['run_id']))
        role_frozen,frozen_proof=frozen_sources(role_run/'battle-host');require_host_sources(role_frozen)
        require_role_source_match(role_frozen,frozen)
        evidence.update(frozen_proof);evidence.update(proof)
        role_reports.append(value)
        provenance.append(dict(stage='role',path=str(path.resolve()),sha256=sha(path),kind=value['kind'],
            assessor_sha256=value['assessor_sha256'],session_id=value['session_id'],run_id=value['run_id'],qualified_roles=sorted(roles),schema_version=9,
            research_continuation=role_session.get('research_continuation') is True,
            fresh_match=role_session.get('fresh_match'),continuation_of=role_session.get('continuation_of')))
    current_files={r['path'].replace('\\','/'):r['sha256'] for r in executed['frontend']}
    if len(current_files)!=len(executed['frontend']):raise ValueError('executed_frontend_alias')
    retained=verify_files(run/'executed-client-dist',current_files);current_frontend=verify_files(args.current_frontend.resolve(),current_files)
    actual_dist={str(p.resolve()) for p in args.current_frontend.rglob('*') if p.is_file()}
    if actual_dist!=set(current_frontend):raise ValueError('current_frontend_inventory_changed')
    evidence.update(retained);evidence.update(current_frontend)
    executable_matches=(Path(executed['executable']).resolve()==args.current_executable.resolve()
        and sha(args.current_executable)==executed['executable_sha256'])
    events=records(host/'host-events.jsonl');requests=[r for r in events if r['kind']=='model_macro_request_context']
    plans=[r['plan'] for r in events if r['kind']=='plan_applied'];responses=[r for r in events if r['kind']=='commander_model_response_returned']
    stops=[i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started']
    dispatch_kinds={'model_macro_native_acknowledged','model_macro_production_acknowledged','model_macro_construction_acknowledged',
        'model_macro_scout_acknowledged','model_macro_region_acknowledged'}
    quiet=bool(stops) and not any(r['kind']=='commander_model_call_started' or r['kind'].endswith('_prepared')
        or r['kind'] in dispatch_kinds for r in events[stops[0]+1:])
    clean=(release.get('native_release_verified') is True and release.get('final_state_sha256')==sha(native/'final-state.json')
        and final['cleanup_verified'] is True and final['unknown_command_ids']==[])
    regression,regression_proof,regression_missing=regression_checks(args.regression_evidence,frozen);evidence.update(regression_proof)
    restoration=profile_restored(load(args.original_profile),load(args.restored_profile),load(args.restoration),
        args.run_id,session['session_id'],args.original_profile,args.restored_profile)
    g6=values['G6'];g7=values['G7'];g8=values['G8']
    domains=(DOMAIN_CHECKS<=set(g6.get('checks',{})) and all(v is True for v in g6['checks'].values()))
    g7_ok=(g7.get('full_G7_verified') is True and set(g7.get('checks',{}))==STAGE_CHECKS['G7'] and all(v is True for v in g7['checks'].values())
        and g7.get('real_model_responses',0)>=3 and g7.get('native_macro_plan_dispatches',0)>=2 and g7.get('prior_strategy_memory_rounds',0)>=2)
    g8_ok=(g8.get('full_G8_verified') is True and set(g8.get('checks',{}))==STAGE_CHECKS['G8'] and all(v is True for v in g8['checks'].values())
        and g8.get('win_rate_improvement_verified') is False and g8.get('causal_live_style_behavior_difference_verified') is False)
    current_subset=('exact_pre_execution_sources_retained','current_profile_consumed','exact_public_request_context_retained',
        'real_provider_response','macro_unit_jobs_absent','native_cleanup_verified','user_stop_completed',
        'multiple_real_model_rounds','downloaded_export_matches')
    g5=(all(common['checks'].get(k) is True for k in current_subset) and executable_matches
        and (executed.get('opening_wait_armed_via_actual_ui') is True or executed.get('started_via_actual_ui') is True)
        and executed.get('profile_revision')==profile['revision']
        and len(responses)>=2 and status.get('state')=='stopped' and status.get('reason_code')=='user_stop' and quiet and clean)
    phase=dict(G0=bool(requests) and status.get('jobs')==[] and all(r['context'].get('control_mode')=='macro_native' for r in requests)
            and all(not p.get('tactical_tasks') and p.get('runtime_task') is None for p in plans) and clean,
        G1=domains and set(ROLE_GOALS)<=qualified and set(ROLE_GOALS)<=allowed,
        G2=regression and all(r['bounded_role_lifecycles_verified'] is True for r in role_reports),
        G3=len(responses)>=2 and bool(plans) and quiet and clean and not any(r['kind']=='host_fault' for r in events)
            and g7.get('prior_strategy_memory_rounds',0)>=2,
        G4=domains and set(ROLE_GOALS)<=qualified,G5=g5,G6=domains and set(ROLE_GOALS)<=qualified,G7=g7_ok,G8=g8_ok)
    delivery=args.delivery.resolve();delivery_manifest=load(delivery/'manifest.json')
    delivered=verify_files(delivery,delivery_manifest['files'],strict=True);evidence.update(delivered)
    digests=set(delivered.values())
    required_artifacts=[args.download,host/'profile.json',run/'executed-client.json',host/'macro-release.json',
        args.original_profile,args.restored_profile,args.restoration,args.current_screenshot,
        args.domain_assessment,args.complete_match_assessment,args.contribution_assessment,*args.role_assessments]
    if not args.current_screenshot.resolve().is_relative_to(run):raise ValueError('current_screenshot_from_other_run')
    signature=args.current_screenshot.read_bytes()[:12]
    screenshot=signature.startswith(b'\x89PNG\r\n\x1a\n') or signature.startswith(b'\xff\xd8\xff')
    artifact_complete=screenshot and all(sha(p) in digests for p in required_artifacts)
    # The frozen G7 delivery remains a legitimate source of the same-match
    # native replay, result screenshot, config, diagnostics and playable HTML.
    g7_manifests=[Path(p) for p in g7['evidence'] if Path(p).name=='manifest.json' and 'delivery' in Path(p).parts]
    historical_delivery=False
    for source in g7_manifests:
        old=load(source)
        wanted=('settlement.png','diagnostics.json','commander-config.json','natural.RA3Replay','macro-timeline.html')
        if all(name in old.get('files',{}) and old['files'][name]['sha256'] in digests for name in wanted):
            historical_delivery=True
    visible_roles=set();timeline_ok=bool(args.timeline_reviews)
    for path in args.timeline_reviews:
        review=load(path);proof=verify_files(path.parent,review['files']);data=load(path.parent/'macro-timeline.json')
        html=(path.parent/'macro-timeline.html').read_text(encoding='utf8')
        embedded=re.findall(r'<script id="timeline-data" type="application/json">(.*?)</script>',html,re.S)
        embedded_matches=(len(embedded)==1 and json.loads(embedded[0])==data and html==render_timeline_html(data)
            and review.get('template_sha256')==TIMELINE_TEMPLATE_SHA and review.get('exporter_sha256')==TIMELINE_EXPORTER_SHA)
        source_bound=any(r['session_id']==data.get('session_id') and r['run_id']==data.get('run_id') for r in role_reports)
        role_run=role_runs.get((data.get('session_id'),data.get('run_id')))
        source_bound=source_bound and role_run is not None and data.get('profile_revision')==load(role_run/'battle-host/profile.json')['revision']
        source_bound=source_bound and any(r.get('name')=='host-events.jsonl'
            and r.get('sha256')==sha(role_run/'battle-host/host-events.jsonl') for r in data.get('sources',[]))
        source_bound=source_bound and timeline_matches_raw(role_run,data['run_id'],data)
        checks=('play_verified','pause_verified','seek_verified','group_role_feedback_visible','stop_release_visible')
        good=source_bound and embedded_matches and all(review.get(k) is True for k in checks) and data.get('native_release_verified') is True
        good=good and data.get('game_replay_fidelity_verified') is False and sha(path) in digests
        good=good and all(digest in digests for name,digest in proof.items() if Path(name).name in ('macro-timeline.html','macro-timeline.json'))
        for role,runs in role_sessions.items():
            if good and (data.get('session_id'),data.get('run_id')) in runs and any(e.get('type')=='regional' and e.get('goal')==ROLE_GOALS[role] for e in data['events']):
                visible_roles.add(role)
        timeline_ok=timeline_ok and good;evidence.update(proof);evidence[str(path.resolve())]=sha(path)
    timeline_ok=timeline_ok and set(ROLE_GOALS)<=visible_roles
    readme=delivery/'README.txt';disclosed=(delivery_manifest.get('native_replay_fidelity_verified') is False
        and delivery_manifest.get('client_cross_machine_portability_verified') is False
        and delivery_manifest.get('credential_material_included') is False and delivery_manifest.get('unit_micro_control') is False
        and '不保证重现外部宏观指令' in readme.read_text(encoding='utf8'))
    final_checks=dict(all_G0_G8=all(phase.values()),current_schema9_client_verified=g5,
        all_role_chains_independently_replayed=set(ROLE_GOALS)<=qualified,
        final_delivery_bound_artifacts=artifact_complete and historical_delivery,
        standalone_playable_role_timelines=timeline_ok,temporary_style_restored=restoration,
        native_cleanup_verified=clean,no_new_commands_after_user_stop=quiet,replay_and_scope_limits_disclosed=disclosed)
    paths=[run/'session.json',run/'macro-budget-bundle.json',run/'executed-client.json',host/'profile.json',host/'macro-release.json',
        host/'host-events.jsonl',host/'host-status.json',args.original_profile,args.restored_profile,args.restoration,
        args.current_executable,args.current_screenshot,delivery/'manifest.json',readme]
    evidence.update({str(p.resolve()):sha(p) for p in paths})
    for name in ('macro_timeline.html','export_macro_timeline.py'):
        path=ROOT/'acceptance'/name;evidence[str(path.resolve())]=sha(path)
    return dict(kind='resumed_schema9_macro_G0_G8_local_goal_assessment',schema_version=1,objective='docs/commander-macro-goal-20261027.md',
        current_run_id=args.run_id,current_session_id=session['session_id'],current_game_pid=session['pid'],
        current_run_is_research_continuation=session.get('research_continuation') is True,current_run_fresh_match=session.get('fresh_match'),
        current_profile_revision=profile['revision'],restored_profile_revision=load(args.restored_profile).get('revision'),
        phase_checks=phase,final_checks=final_checks,formal_goal_complete=all(final_checks.values()),
        missing_independent_model_deployment_roles=sorted(set(ROLE_GOALS)-qualified),
        regression_evidence_missing_reason=regression_missing,source_assessments=provenance,
        reused_bounded_domain_coverage=g6.get('coverage',{}),current_qualified_scope=public,
        independently_qualified_model_deployment_roles=sorted(qualified),unit_operation_policy='native_ai',
        reused_complete_match_session_id=g7['session_id'],complete_match_model_side_outcome=g7.get('model_side_outcome'),
        local_scope='fixed RA3 1.12 / TemplePrime / P3 Soviet / bounded individually qualified native macro consumers',
        native_replay_fidelity_verified=False,client_cross_machine_portability_verified=False,
        portable_release_is_completion_gate=False,win_rate_improvement_verified=False,all_intents_successful=False,
        arbitrary_map_or_faction_coverage_verified=False,micro_control_enabled=False,evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    names=('run-directory','domain-assessment','complete-match-assessment','contribution-assessment','download','original-export',
        'original-profile','restored-profile','restoration','delivery','current-executable','current-frontend','current-screenshot','output')
    for name in names:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--role-assessment',type=Path,action='append',required=True)
    p.add_argument('--timeline-review',type=Path,action='append',default=[]);p.add_argument('--regression-evidence',type=Path)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to((ROOT/'reports').resolve()):raise ValueError('fresh_resumed_goal_output_required')
    args=Inputs(run=a.run_directory.resolve(),run_id=a.run_id,role_assessments=tuple(p.resolve() for p in a.role_assessment),
        timeline_reviews=tuple(p.resolve() for p in a.timeline_review),regression_evidence=a.regression_evidence,
        **{name:getattr(a,name).resolve() for name in ('domain_assessment','complete_match_assessment','contribution_assessment',
            'download','original_export','original_profile','restored_profile','restoration','delivery',
            'current_executable','current_frontend','current_screenshot')})
    value=evaluate(args);out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    value['evidence'][str((out/'assessor.py').resolve())]=value['assessor_sha256']
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k not in ('evidence','source_assessments')}))
    return 0 if value['formal_goal_complete'] else 2


if __name__=='__main__':raise SystemExit(main())
