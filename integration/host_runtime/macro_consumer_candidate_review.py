"""Offline candidate review only. No scope construction or capability grant.

The separate fixed-consumer primed contract is not the original field contract.
The explicit schema11 loader may consume its queue fact; the report itself
never grants a capability or proves a product/model execution loop.
"""
from dataclasses import dataclass,asdict
import hashlib
import json
from pathlib import Path
import sys
import uuid

from .contracts import ContractError
from .macro_expansion_scope import ROOT,TARGETS,same_runtime,v2_trial

CONTRACT='fixed_consumer_primed_v1'
ACTIONS=('buildbarracks','buildfactory','buildbattlelab','producesickle','producebullfrog')
CHECKS=frozenset(('source_archives_intact','fixed_consumer_scope','zero_model_and_unit_orders','session_package_bound',
    'lifecycle_within_sixty_seconds','sources_unchanged_at_end','memory_closed','scenario_and_frames_verified',
    'p3_identity_consistent','native_process_incarnation_bound','transport_session_bound','no_unknown_or_fault',
    'initial_transport_quiescent','prime_ack_bound','prime_window_bound','two_distinct_prime_budget_frames',
    'initial_legal_idle_baseline','fresh_legal_post_prime_baseline','work_ack_bound','work_window_bound','explicit_clear_bound',
    'work_budget_reobserved','positive_native_score_inside_work','matching_new_queue_inside_work',
    'clear_after_first_queue_without_extra_sample','exact_four_command_ledger','close_ack_bound','independent_clean_close'))
SAMPLING_SCOPE=dict(domain='coherent_construction',maximum_component_frame_span=15,dynamic_data_cached=False)


def reject():raise ContractError('macro_consumer_candidate_not_qualified')


@dataclass(frozen=True)
class ConsumerCandidateReview:
    action:str
    queue_acceptance_supported:bool
    first_observed_queue_batch_count:int
    contract:str=CONTRACT
    schema_version:int=1
    kind:str='macro_consumer_candidate_review'
    review_scope:str='offline_candidate_evidence_only'
    product_capability_granted:bool=False
    field_qualification_granted:bool=False
    model_loop_verified:bool=False
    completion_verified:bool=False
    operational_verified:bool=False
    technology_unlock_verified:bool=False
    payment_verified:bool=False
    exclusive_attribution_verified:bool=False
    hard_native_queue_cap:bool=False

    def public(self):return asdict(self)


def review_data(pre,events,final,result,assessment,expected_manifest):
    """Additional version-specific guards after the trusted raw assessor replays.

    A positive return is a candidate fact and never an execution permission.
    The filesystem entry point below also requires v2 transport/source replay.
    """
    try:
        config=pre['config'];action=config['action'];session=pre['session'];checks=assessment['checks']
        sid=session['session_id']
        if (type(sid) is not str or str(uuid.UUID(sid))!=sid
                or pre.get('kind')!='fixed_consumer_primed_field_preflight'
                or type(pre.get('schema_version')) is not int or pre['schema_version']!=1
                or type(pre.get('protocol_version')) is not int or pre['protocol_version']!=2
                or pre.get('product_capability_granted') is not False or action not in ACTIONS
                or config.get('target_type_hash')!=TARGETS[action][0] or config.get('producer_type_hash')!=TARGETS[action][1]
                or pre.get('sampling_scope')!=SAMPLING_SCOPE or not same_runtime(pre['manifest'],expected_manifest)
                or session.get('mod_sha256')!=expected_manifest['package_sha256']
                or assessment.get('kind')!='fixed_consumer_primed_field_assessment'
                or type(assessment.get('schema_version')) is not int or assessment['schema_version']!=1
                or assessment.get('action')!=action or type(checks) is not dict or set(checks)!=CHECKS
                or any(value is not True for value in checks.values())
                or assessment.get('fixed_consumer_effect_supported') is not True
                or assessment.get('disposition')!='research_consumer_queue_supported'
                or any(assessment.get(key) is not False for key in ('product_capability_granted','field_qualification_granted',
                    'formal_runtime_qualification','formal_goal_complete'))
                or type(assessment.get('model_calls')) is not int or assessment['model_calls']!=0):reject()
        begin,end=result['live_lifecycle_began_monotonic_ns'],result['live_lifecycle_ended_monotonic_ns']
        if type(begin) is not int or type(end) is not int or not 0<=begin<=end or end-begin>60_000_000_000:reject()
        last=begin;samples=0
        for event in events:
            at=event.get('monotonic_ns')
            if type(at) is not int or not last<=at<=end:reject()
            last=at
            if event.get('kind')=='sample':
                sample=event['sample'];first,finish=sample['started_monotonic_ns'],sample['ended_monotonic_ns']
                if type(first) is not int or type(finish) is not int or not begin<=first<=finish<=at:reject()
                samples+=1
        if not samples or any(final.get(k)!=session.get(k) for k in ('session_id','pid','process_creation_filetime','mod_sha256')):reject()
        effects=assessment['native_effects'];queues=effects['matching_new_queue_observations'];count=effects['first_observed_queue_batch_count']
        if (type(count) is not int or count<=0 or type(queues) is not list or len(queues)!=count
                or any(effects.get(key) is not False for key in ('completion_verified','payment_verified','hard_native_queue_cap','exclusive_attribution_verified'))):reject()
        return ConsumerCandidateReview(action,True,count)
    except (KeyError,ValueError,TypeError,AttributeError):reject()


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def review_candidate(folder,*,expected_manifest):
    """Read only the declared archive and original inputs; never execute them."""
    # File-launched macro_host starts with only integration on sys.path.
    # Derive this trusted root from our installed source, never an artifact path.
    root=str(ROOT)
    if root not in sys.path:sys.path.insert(0,root)
    from acceptance import assess_macro_consumer_primed_field as assessor
    if Path(assessor.__file__).resolve()!=(ROOT/'acceptance/assess_macro_consumer_primed_field.py').resolve():reject()
    folder=Path(folder).resolve()
    names=('driver-preflight.json','driver-result.json','consumer-trial.jsonl',
        'transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl')
    paths=[folder/name for name in names];before={path:_sha(path) for path in paths}
    pre=json.loads(paths[0].read_text(encoding='utf-8-sig'))
    result=json.loads(paths[1].read_text(encoding='utf-8-sig'))
    events=[json.loads(line) for line in paths[2].read_text(encoding='utf8').splitlines() if line]
    assessment=assessor.assess(folder)
    _,final,manifest,_,transport_evidence=v2_trial(folder/'transport',expected=expected_manifest)
    if not same_runtime(pre['manifest'],manifest):reject()
    sources=pre.get('sources',[]);seen=set();evidence=dict(transport_evidence)
    for row in sources:
        original=Path(row['path']).resolve();archive=(folder/row['copy']).resolve()
        if (original in seen or not archive.is_relative_to(folder) or not archive.is_file()
                or _sha(archive)!=row['sha256'] or _sha(original)!=row['sha256']):reject()
        seen.add(original);evidence[str(archive)]=row['sha256'];evidence[str(original)]=row['sha256']
    if (not sources or _sha(Path(pre['session_path']).resolve())!=pre.get('session_sha256')
            or _sha(Path(pre['build_path']).resolve()/'build-manifest.json')!=pre.get('build_manifest_sha256')):reject()
    review=review_data(pre,events,final,result,assessment,expected_manifest)
    if any(_sha(path)!=digest for path,digest in before.items()):reject()
    evidence.update({str(path):digest for path,digest in before.items()})
    evidence[str(Path(__file__).resolve())]=_sha(Path(__file__).resolve())
    return review,evidence
