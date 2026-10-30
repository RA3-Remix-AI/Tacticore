"""Protocol-2 grants require raw lifecycle and per-consumer field evidence.

An append-only compiled audit can preserve old consumer semantics, but neither
that audit nor a transport ACK qualifies any of the seven new work actions.
"""
from dataclasses import dataclass, fields, replace
import importlib.util
import json
from pathlib import Path

from .contracts import ContractError
from .macro_group_role_scope import GroupRoleScope
from .macro_policy_runtime import ROOT, PRESETS, ACCOUNTS, ratios_match, sha, load

SOURCES=('shared.h','native.cpp','host.cpp','build.py','client.py')
HERE=ROOT/'native-ai/macro-policy-runtime-v2'
EXTRA_ACTIONS=('buildpower','buildbarracks','buildfactory','buildrefinery',
               'buildbattlelab','producesickle','producebullfrog')
TARGETS={'buildpower':('0xcf8d9f20','0xc16ff13f','construction'),
    'buildbarracks':('0x80d4ea1e','0xc16ff13f','construction'),
    'buildfactory':('0xd50c222e','0xc16ff13f','construction'),
    'buildrefinery':('0xc45aaeab','0xc16ff13f','construction'),
    'buildbattlelab':('0xb7377639','0xc16ff13f','construction'),
    'producesickle':('0x60f0b4e9','0xd50c222e','production'),
    'producebullfrog':('0x522bcb61','0xd50c222e','production')}


def expansion_catalog_overrides(actions):
    from .macro_group_role_contract import group_role_catalog_overrides
    result=group_role_catalog_overrides()
    for action in actions:
        if action not in EXTRA_ACTIONS:raise ContractError('macro_expansion_catalog_action')
        result[action]=dict(domain=TARGETS[action][2],exclusive_with_other_construction_or_production=True,
            maximum_duration_seconds=40,additional_counts=[1] if TARGETS[action][2]=='production' else [],
            count_control_basis='new_native_queue_acceptances',requires_fresh_native_readiness_and_dependency=True,
            native_ai_selects_location_and_operates_units=True,completion_guaranteed=False,
            technology_unlock_guaranteed=False,arbitrary_quantity_granted=False,automatic_retry_allowed=False)
    return result


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def pin(evidence,path):
    path=Path(path).resolve();digest=sha(path);key=str(path)
    if key in evidence and evidence[key]!=digest:raise ContractError('macro_expansion_evidence_conflict')
    evidence[key]=digest
    return path


def records(path):
    try:
        result=[json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines() if line]
        if any(type(row) is not dict for row in result):raise ValueError()
        return result
    except (ValueError,UnicodeError,OSError):raise ContractError('macro_expansion_records_invalid') from None


def flag_state(value,expected,mask=0):
    rows=value.get('flags',[]) if type(value) is dict else []
    return (type(mask) is int and 0<=mask<(1<<20) and type(rows) is list
        and len(rows)==20 and all(type(row) is dict for row in rows)
        and [row.get('name') for row in rows]==list(expected)
        and all(row.get('present') is True and row.get('value') is True if mask&(1<<index)
            else row.get('present') is False or row.get('present') is True and row.get('value') is False
            for index,row in enumerate(rows)))


def cleared_flags(value,expected):return flag_state(value,expected)


def native_identity(state,reference):
    keys=('magic','version','pid','start_low','start_high','owner','ai','personality','personality_id','player_template')
    return (type(state) is dict and all(type(state.get(key)) is int and state[key]==reference.get(key) for key in keys))


def runtime_build(build):
    """Read-only replay of actual package bytes and generated v2 transport."""
    build=Path(build).resolve();manifest=load(build/'build-manifest.json')
    if (manifest.get('kind')!='native_macro_policy_transport_v2_candidate'
            or type(manifest.get('protocol_version')) is not int or manifest['protocol_version']!=2
            or manifest.get('field_verified') is not False or manifest.get('capability_granted') is not False
            or set(manifest.get('sources',{}))!=set(SOURCES)):
        raise ContractError('macro_expansion_protocol2_build_required')
    builder=module('_qualified_macro_v2_builder',HERE/'build.py')
    report_path=Path(manifest['package_report']).resolve();report=load(report_path)
    if sha(report_path)!=manifest.get('package_report_sha256'):raise ContractError('macro_expansion_package_report_changed')
    header,binding=builder.profile(report,manifest.get('epoch'))
    if (any(manifest.get(key)!=value for key,value in binding.items())
            or (build/'profile.h').read_text(encoding='ascii')!=header
            or sha(build/'profile.h')!=manifest.get('profile_header_sha256')
            or manifest.get('package_sha256')!=report['big_sha256']
            or manifest.get('compiled_expansion_audit_sha256')!=report['compiled_expansion_audit_sha256']):
        raise ContractError('macro_expansion_generated_build_mismatch')
    evidence={}
    for name,digest in manifest['sources'].items():
        if sha(HERE/name)!=digest:raise ContractError('macro_expansion_native_sources_changed')
        pin(evidence,HERE/name)
    if set(manifest.get('artifacts',{}))!={manifest['library'],'macro_policy_host.exe'}:
        raise ContractError('macro_expansion_artifact_set')
    for name,digest in manifest['artifacts'].items():
        if Path(name).name!=name or sha(build/name)!=digest:raise ContractError('macro_expansion_binary_changed')
        pin(evidence,build/name)
    audit_path=builder.verify_inputs(report,report_path);audit=load(audit_path)
    for name in ('build-manifest.json','profile.h'):pin(evidence,build/name)
    for path in (report_path,audit_path,report_path.parent/'TFMacroProbe.big',
                 ROOT/'native-ai/macro_expansion_contract.py',ROOT/'native-ai/stage_macro_expansion.py'):
        pin(evidence,path)
    for path,digest in audit['evidence'].items():
        if sha(Path(path))!=digest:raise ContractError('macro_expansion_compiled_evidence_changed')
        pin(evidence,path)
    return manifest,report,audit,evidence


def same_runtime(first,second):
    # Epoch changes only the private DLL/mapping namespace; all executable
    # semantics, limits, bits, consumers and source bytes must remain identical.
    names=('protocol_version','package_sha256','sources','flags','consumers','exclusive_masks',
        'profile_contract','maximum_requests','absolute_native_wall_ms','maximum_host_wall_seconds',
        'heartbeat_loss_ms','same_process_reattach_supported','compiled_expansion_audit_sha256')
    return type(first) is dict and type(second) is dict and all(first.get(name)==second.get(name) for name in names)


def v2_trial(directory,*,fault=False,expected=None):
    directory=Path(directory).resolve();pre=load(directory/'preflight.json');final=load(directory/'final-state.json')
    evidence={};copies={}
    for source in pre.get('sources',[]):
        path=(directory/'source'/source['copy']).resolve()
        name=Path(source['path']).name
        if (path.parent!=(directory/'source').resolve() or name in copies or sha(path)!=source['sha256']):
            raise ContractError('macro_expansion_frozen_source_changed')
        copies[name]=(path,Path(source['path']));pin(evidence,path)
    if any(name not in copies for name in (*SOURCES,'build-manifest.json','profile.h')):
        raise ContractError('macro_expansion_transport_source_set')
    manifest=load(copies['build-manifest.json'][0])
    current,_,_,current_pins=runtime_build(copies['build-manifest.json'][1].parent)
    if current!=manifest or expected is not None and not same_runtime(expected,manifest):
        raise ContractError('macro_expansion_transport_build_mismatch')
    for name in SOURCES:
        if sha(copies[name][0])!=manifest['sources'][name]:
            raise ContractError('macro_expansion_transport_source_mismatch')
    if sha(copies['profile.h'][0])!=manifest['profile_header_sha256']:
        raise ContractError('macro_expansion_transport_profile_mismatch')
    for relative in ('native-ai/macro_observation.py','native-ai/macro_area_defense_observation.py',
            'native-ai/verify_area_defense_observer.py','native-ai/macro_group_role_observation.py',
            'native-ai/verify_group_role_observer.py','native-ai/macro_build_observation.py',
            'native-ai/read_script_flags.py','visibility/native_read.py','production/observe_production.py',
            'production/session_package.py','native-ai/read_selected_personality.py','probe.py'):
        original=(ROOT/relative).resolve();entry=copies.get(original.name)
        if entry is None or entry[1].resolve()!=original or sha(entry[0])!=sha(original):
            raise ContractError('macro_expansion_transport_observer_changed')
        pin(evidence,original)
    sessions=[path for path,_ in copies.values() if path.suffix=='.json' and sha(path)==pre.get('session_sha256')]
    if len(sessions)!=1:raise ContractError('macro_expansion_transport_session_missing')
    session=load(sessions[0]);native=final.get('native',{})
    if (final.get('session_id')!=session.get('session_id') or final.get('pid')!=session.get('pid')
            or final.get('process_creation_filetime')!=session.get('process_creation_filetime')
            or pre.get('process_creation_filetime')!=session.get('process_creation_filetime')
            or final.get('mod_sha256')!=session.get('mod_sha256') or session.get('mod_sha256')!=manifest['package_sha256']
            or final.get('cleanup_verified') is not True or final.get('unknown_command_ids')!=[]
            or final.get('intentional_external_host_loss',False) is not fault):
        raise ContractError('macro_expansion_transport_identity_or_cleanup')
    required=dict(magic=0x4d503032,version=2,pid=session['pid'],phase=2,error=0,active=0,
                  applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0,personality_id=0x799613e0)
    if any(type(native.get(key)) is not int or native[key]!=value for key,value in required.items()):
        raise ContractError('macro_expansion_transport_native_cleanup')
    owner=pre.get('native',{})
    if (owner.get('player_index')!=3 or owner.get('instance_id')!='0x799613e0'
            or owner.get('store_membership_verified') is not True or owner.get('side_matches_player') is not True
            or not cleared_flags(pre.get('initial_flags'),manifest['flags'])):
        raise ContractError('macro_expansion_transport_initial_identity_or_flags')
    for key,source in (('owner','player'),('ai','ai_player'),('personality','personality_wrapper'),('player_template','player_template')):
        if native.get(key)!=int(owner.get(source,'0'),0):raise ContractError('macro_expansion_transport_owner_mismatch')
    creation=session['process_creation_filetime']
    if (type(creation) is not int or creation<=0 or native.get('start_low')!=creation&0xffffffff
            or native.get('start_high')!=creation>>32):
        raise ContractError('macro_expansion_transport_creation_mismatch')
    if (not cleared_flags(final.get('independent_flags'),manifest['flags'])
            or fault and (final.get('host_returncode') in (None,0) or native.get('watchdog_reason')!=1)
            or not fault and final.get('host_returncode')!=0):
        raise ContractError('macro_expansion_transport_twenty_flags_or_exit')
    rows=records(directory/'policy-probe.jsonl')
    if any(row.get('session_id')!=session['session_id'] or row.get('pid')!=session['pid'] for row in rows):
        raise ContractError('macro_expansion_transport_event_binding')
    if any(row.get('kind') in ('command_unknown','independent_readback_unknown') for row in rows):
        raise ContractError('macro_expansion_transport_unknown_command')
    prepared={};acks={}
    for row in rows:
        if row.get('kind')=='command_prepared':
            key=row.get('command_id')
            if key in prepared:raise ContractError('macro_expansion_transport_duplicate_command')
            prepared[key]=row
        if row.get('kind')=='command_acknowledged':
            key=row.get('command_id')
            if key in acks:raise ContractError('macro_expansion_transport_duplicate_ack')
            acks[key]=row
    if not prepared or set(prepared)!=set(acks):raise ContractError('macro_expansion_transport_incomplete_commands')
    for key,row in prepared.items():
        ack=acks[key];state=ack.get('native',{});seq=row.get('seq')
        if (type(seq) is not int or not 1<=seq<=2048 or seq!=ack.get('seq')
                or not native_identity(state,native)
                or state.get('request')!=seq or state.get('ack')!=seq or state.get('error')!=0
                or state.get('version')!=2 or state.get('pid')!=session['pid']
                or row.get('kind_code') not in (1,2)
                or row.get('kind_code')==1 and (seq>2047 or type(row.get('duration_frames')) is not int
                    or not 1<=row['duration_frames']<=4500)
                or state.get('applied_mask')!=(row.get('mask') if row.get('kind_code')==1 else 0)
                or not flag_state(ack.get('independent_flags'),manifest['flags'],state.get('applied_mask',0))):
            raise ContractError('macro_expansion_transport_ack_binding')
    seqs=sorted(row['seq'] for row in prepared.values())
    if seqs!=list(range(1,len(seqs)+1)) or native.get('ack')!=seqs[-1] or native.get('request')!=seqs[-1]:
        raise ContractError('macro_expansion_transport_sequence')
    for name in ('preflight.json','final-state.json','policy-probe.jsonl'):pin(evidence,directory/name)
    evidence.update(current_pins)
    return pre,final,manifest,rows,evidence


def verify_runtime_lifecycles(normal,host_loss,expiry,build):
    current,report,audit,evidence=runtime_build(build)
    values=[v2_trial(normal,expected=current),v2_trial(host_loss,fault=True,expected=current),
            v2_trial(expiry,expected=current)]
    flags={row['action']:row['flag'] for row in current['consumers']}
    for action,value in (('budgeteconomy',values[0]),('budgetarmy',values[1])):
        masks={row['command_id']:row for row in value[3] if row.get('kind')=='command_prepared'}
        acks=[row for row in value[3] if row.get('kind')=='command_acknowledged']
        bit=1<<current['flags'].index(flags[action]);windows=[]
        for index,ack in enumerate(acks):
            prepared=masks[ack['command_id']];state=ack['native']
            if prepared['kind_code']!=1 or not prepared['mask']&bit:continue
            end=min(state['deadline_frame'],acks[index+1]['native']['last_frame'] if index+1<len(acks) else state['deadline_frame'])
            windows.append((state['deadline_frame']-prepared['duration_frames'],end))
        frames={row['observation']['frame'] for row in value[3] if row.get('kind')=='macro_observation'
            and row.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag')==flags[action]
            and any(begin<=row['observation']['frame']<end for begin,end in windows)
            and ratios_match(row['observation']['budget_feedback'].get('account_shares'),PRESETS[action])}
        if len(frames)<2:raise ContractError('macro_expansion_budget_adoption_missing')
    fault=values[1]
    if not any(row.get('kind')=='native_host_loss_cleanup_verified'
        and native_identity(row.get('native'),fault[1]['native'])
        and all(row['native'].get(key)==value for key,value in dict(phase=2,error=0,active=0,applied_mask=0,
            cleanup_verified=1,self_hook_installed=0,lease_held=0,watchdog_reason=1).items())
        and cleared_flags(row.get('independent_flags'),current['flags'])
        and row.get('host_returncode') not in (None,0) for row in fault[3]):
        raise ContractError('macro_expansion_host_loss_missing')
    expiry_ack={row['native']['ack']:row for row in values[2][3] if row.get('kind')=='command_acknowledged'
        and row['native']['applied_mask']!=0}
    if not any(row.get('kind')=='native_policy_expiry_verified'
        and native_identity(row.get('native'),values[2][1]['native'])
        and all(row['native'].get(key)==value for key,value in dict(phase=1,error=0,active=0,applied_mask=0,
            deadline_frame=0,cleanup_verified=1,self_hook_installed=1,lease_held=1).items())
        and row['native'].get('ack') in expiry_ack and row['native'].get('request')==row['native']['ack']
        and row.get('expected_deadline_frame')==expiry_ack[row['native']['ack']]['native'].get('deadline_frame')
        and row['native'].get('last_frame',-1)>=row.get('expected_deadline_frame',2**64)
        and cleared_flags(row.get('independent_flags'),current['flags']) for row in values[2][3]):
        raise ContractError('macro_expansion_expiry_missing')
    release_frames=[row['native']['last_frame'] for row in values[0][3] if row.get('kind')=='command_acknowledged'
        and row['native']['phase']==1 and row['native']['applied_mask']==0]
    if not any(row.get('kind')=='macro_observation' and row.get('label')=='after_native_policy_reassessment'
        and row.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag') is None
        and any(row.get('observation',{}).get('frame',-1)>=frame for frame in release_frames)
        and ratios_match(row.get('observation',{}).get('budget_feedback',{}).get('account_shares'),dict(zip(ACCOUNTS,[0,0,.85,.05,0,.1])))
        for row in values[0][3]):raise ContractError('macro_expansion_native_delegation_missing')
    for value in values:evidence.update(value[4])
    return current,report,audit,evidence


@dataclass(frozen=True)
class ExpansionScope(GroupRoleScope):
    expansion_choices:tuple=()
    expansion_evidence:tuple=()
    fixed_consumer_qualifications:tuple=()
    native_transport_protocol:int=2
    native_transport_client:str='client.py'

    @property
    def production_counts(self):
        base=super().production_counts
        return dict(base,**{action:(1,) for action in self.expansion_choices if TARGETS[action][2]=='production'})

    @property
    def production_flags(self):
        base=super().production_flags
        return dict(base,**{action:self.expansion_flags[action] for action in self.expansion_choices if TARGETS[action][2]=='production'})

    @property
    def expansion_flags(self):
        return {action:flag for action,flag in self.expansion_evidence}

    @property
    def available_actions(self):
        return tuple(dict.fromkeys((*super().available_actions,*self.expansion_choices)))

    def model_catalog_overrides(self):
        return expansion_catalog_overrides(self.expansion_choices)

    def public(self):
        result=super().public()
        result.update(kind='verified_native_macro_expansion_scope',native_transport_protocol=2,
            native_transport_client='client.py',field_qualified_expansion_actions=list(self.expansion_choices),
            pending_expansion_actions=[action for action in EXTRA_ACTIONS if action not in self.expansion_choices],
            construction_choices=(['buildreactor'] if self.construction_flag else [])
                +[action for action in self.expansion_choices if TARGETS[action][2]=='construction'],
            model_loop_verified_for_expansion=False,construction_completed_guaranteed=False,
            technology_unlock_guaranteed=False,arbitrary_quantity_granted=False,
            completion_independently_verified=False,operational_independently_verified=False,
            technology_unlock_independently_verified=False,resource_reservation_verified=False,
            new_product_requests_require_trusted_cost_and_resource_reservation=True,
            budget_hard_cap_verified=False,
            expansion_qualification={action:('field_queue_acceptance_qualified' if action in self.expansion_choices
                else 'blocked_field_qualification_missing') for action in EXTRA_ACTIONS})
        if self.fixed_consumer_qualifications:
            result['fixed_consumer_qualification_contracts']={action:dict(schema_version=1,kind=contract,
                qualification='fixed_consumer_queue_acceptance_only') for action,contract in self.fixed_consumer_qualifications}
        return result


def verify_expansion_scope(legacy,*,build,normal,host_loss,expiry,field_directories):
    if not isinstance(legacy,GroupRoleScope):raise ContractError('macro_expansion_schema9_legacy_required')
    manifest,report,audit,evidence=verify_runtime_lifecycles(normal,host_loss,expiry,build)
    if (audit['baseline_package_sha256']!=legacy.package_sha256
            or list(legacy.budget.flags)!=manifest['flags'][:13]
            or report['legacy_consumer_definitions']!=manifest['consumers'][:13]):
        raise ContractError('macro_expansion_legacy_semantics_not_preserved')
    directories=list(field_directories)
    if len(directories)>7:raise ContractError('macro_expansion_field_qualification_set')
    assessor=module('_macro_expansion_field_qualification',ROOT/'acceptance/assess_macro_expansion_field.py')
    granted={};seen=set()
    for directory in directories:
        folder=Path(directory).resolve();pre=load(folder/'driver-preflight.json')
        action=pre.get('action');assessment=assessor.assess(folder)
        if (pre.get('kind')!='fixed_macro_expansion_field_preflight'
                or pre.get('schema_version')!=1 or type(pre.get('schema_version')) is not int
                or pre.get('protocol_version')!=2 or type(pre.get('protocol_version')) is not int
                or action not in EXTRA_ACTIONS or action in seen or assessment.get('action')!=action
                or assessment.get('kind')!='macro_expansion_field_assessment'
                or type(assessment.get('schema_version')) is not int or assessment['schema_version']!=1
                or type(assessment.get('protocol_version')) is not int or assessment['protocol_version']!=2
                or type(assessment.get('checks')) is not dict or not assessment['checks']
                or any(value is not True for value in assessment['checks'].values())
                or assessment.get('fixed_consumer_effect_supported') is not True
                or assessment.get('unknown_open_node_research_probe') is True
                or pre.get('config',{}).get('allow_unknown_native_precondition') is True
                or assessment.get('product_capability_granted') is not False
                or pre.get('additional_count')!=1 or type(pre.get('additional_count')) is not int
                or pre.get('target_type_hash')!=TARGETS[action][0]
                or pre.get('mod_sha256')!=manifest['package_sha256']
                or not same_runtime(pre.get('manifest',{}),manifest)):
            raise ContractError('macro_expansion_consumer_field_not_qualified')
        seen.add(action)
        _,_,_,_,trial_pins=v2_trial(folder/'transport',expected=manifest)
        for source in pre['sources']:
            path=(folder/source['copy']).resolve()
            if not path.is_relative_to(folder) or sha(path)!=source['sha256']:
                raise ContractError('macro_expansion_consumer_source_changed')
            pin(evidence,path)
        for name in ('driver-preflight.json','driver-result.json','expansion-trial.jsonl'):pin(evidence,folder/name)
        evidence.update(trial_pins)
        granted[action]=next(row['flag'] for row in manifest['consumers'] if row['action']==action)
    pin(evidence,ROOT/'acceptance/assess_macro_expansion_field.py')
    merged=dict(legacy.evidence)
    for path,digest in evidence.items():
        if path in merged and merged[path]!=digest:raise ContractError('macro_expansion_legacy_evidence_changed')
        merged[path]=digest
    budget=replace(legacy.budget,package_sha256=manifest['package_sha256'],native_sources=manifest['sources'],
                   flags=tuple(manifest['flags']),evidence=merged)
    return ExpansionScope(**{field.name:getattr(legacy,field.name) for field in fields(GroupRoleScope)
                             if field.name not in ('budget','evidence')},
        budget=budget,evidence=merged,expansion_choices=tuple(action for action in EXTRA_ACTIONS if action in granted),
        expansion_evidence=tuple((action,granted[action]) for action in EXTRA_ACTIONS if action in granted))


def extend_fixed_consumer_scope(scope,*,build,contracts):
    """Schema11 only: replay a distinct fixed-consumer contract after schema10 gates.

    Only the independently reviewed sickle contract is enabled in this release.
    A candidate queue fact grants neither a model loop nor a hard quantity cap.
    """
    from .macro_consumer_candidate_review import CONTRACT,ConsumerCandidateReview,review_candidate
    if not isinstance(scope,ExpansionScope):raise ContractError('macro_fixed_consumer_expansion_scope_required')
    if type(contracts) is not list or not 1<=len(contracts)<=1:
        raise ContractError('macro_fixed_consumer_contract_set')
    manifest,_,_,build_evidence=runtime_build(build)
    if (scope.package_sha256!=manifest['package_sha256'] or list(scope.budget.flags)!=manifest['flags']
            or scope.budget.native_sources!=manifest['sources']):
        raise ContractError('macro_fixed_consumer_runtime_mismatch')
    choices=set(scope.expansion_choices);granted=dict(scope.expansion_evidence);qualified=dict(scope.fixed_consumer_qualifications)
    evidence=dict(scope.evidence);new_evidence=dict(build_evidence);directories=set()
    for entry in contracts:
        if (type(entry) is not dict or set(entry)!={'schema_version','kind','action','directory'}
                or type(entry.get('schema_version')) is not int or entry['schema_version']!=1
                or entry.get('kind')!=CONTRACT or entry.get('action')!='producesickle'
                or type(entry.get('directory')) is not str):
            raise ContractError('macro_fixed_consumer_contract_schema')
        action=entry['action'];folder=Path(entry['directory'])
        if (not folder.is_absolute() or str(folder).startswith('\\\\') or not folder.is_dir()
                or folder.resolve() in directories or action in choices):
            raise ContractError('macro_fixed_consumer_duplicate_or_path')
        directories.add(folder.resolve())
        review,pins=review_candidate(folder,expected_manifest=manifest)
        if (type(review) is not ConsumerCandidateReview or review.action!=action or review.contract!=CONTRACT
                or review.queue_acceptance_supported is not True or type(review.first_observed_queue_batch_count) is not int
                or review.first_observed_queue_batch_count<1
                or any(getattr(review,key) is not False for key in ('product_capability_granted','field_qualification_granted',
                    'model_loop_verified','completion_verified','operational_verified','technology_unlock_verified',
                    'payment_verified','exclusive_attribution_verified','hard_native_queue_cap'))):
            raise ContractError('macro_fixed_consumer_candidate_not_qualified')
        matches=[row for row in manifest['consumers'] if row.get('action')==action]
        if len(matches)!=1:raise ContractError('macro_fixed_consumer_manifest_action')
        choices.add(action);granted[action]=matches[0]['flag'];qualified[action]=CONTRACT
        for path,digest in pins.items():
            if path in new_evidence and new_evidence[path]!=digest:raise ContractError('macro_fixed_consumer_evidence_changed')
            new_evidence[path]=digest
    for path,digest in new_evidence.items():
        if path in evidence and evidence[path]!=digest:raise ContractError('macro_fixed_consumer_evidence_changed')
        evidence[path]=digest
    return replace(scope,budget=replace(scope.budget,evidence=evidence),evidence=evidence,
        expansion_choices=tuple(action for action in EXTRA_ACTIONS if action in choices),
        expansion_evidence=tuple((action,granted[action]) for action in EXTRA_ACTIONS if action in granted),
        fixed_consumer_qualifications=tuple((action,qualified[action]) for action in EXTRA_ACTIONS if action in qualified))
