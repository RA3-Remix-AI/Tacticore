"""Pure optional-telemetry decision, never an admission/publication authority.

The transport must preserve its actual caught builder error on this sample.
Missing data without that exact error is not evidence of a benign race.
Upstream process/EXE/profile/signature/view validation still runs unchanged.
"""
from dataclasses import dataclass
import math
import re

from .contracts import ContractError

KIND='strategic_optional_builder_queue_race_v1'
IDENTITY=('magic','version','pid','owner','ai','personality','personality_id','player_template','engine')
CONTROL=('stopped','production_active','construction_active','expansion_active',
         'reservation_unresolved','reconciliation_blocked','strategy_unknown')


def refuse(reason):raise ContractError('optional_builder_'+reason)


def integer(value,minimum=0,maximum=0xffffffff):
    return type(value) is int and minimum<=value<=maximum


def pointer(value):
    if type(value) is not str or re.fullmatch(r'0x[0-9a-f]{1,8}',value) is None:refuse('native_pointer')
    return int(value,16)


@dataclass(frozen=True)
class OptionalBuilderGap:
    kind:str
    observed_frames:tuple
    builder_status:str='unknown'
    queue_effect_verified:bool=False
    detailed_action_granted:bool=False
    dispatch_authority_granted:bool=False


def assess_optional_builder_gap_v1(sample,*,strategic_only,controller_state,journal_rows,
        transport_ledger,pending,native_state,native_identity,flags,flag_names,lawful_view):
    """Validate actual supplied facts; caller-owned inputs are not authenticated.

    Returns timing for native strategic observation + own census, never a fake
    builder sample. Exact source faults other than this one still refuse.
    """
    if strategic_only is not True:refuse('strategic_mode_required')
    if type(sample) is not dict or 'build_observation' in sample:refuse('not_a_builder_gap')
    if sample.get('build_observation_error')!='macro_builder_queue_changed':refuse('exact_queue_race_required')
    if 'read_error' in sample or sample.get('expansion_sample_errors'):refuse('other_sample_failure')
    if type(controller_state) is not dict or set(controller_state)!=set(CONTROL):refuse('controller_state')
    if any(type(value) is not bool or value for value in controller_state.values()):refuse('controller_active_or_unknown')
    if type(journal_rows) is not list or any(type(row) is not dict or row.get('status')!='completed' for row in journal_rows):refuse('durable_ledger_not_settled')
    if type(transport_ledger) is not dict or pending is not False or any(
            type(row) is not dict or row.get('status')!='acknowledged' for row in transport_ledger.values()):refuse('native_ledger_not_settled')
    if type(native_identity) is not dict or set(native_identity)!=set(IDENTITY)|{'process_creation_filetime'}:refuse('identity_fields')
    if any(not integer(native_identity[key],1) for key in IDENTITY) or not integer(native_identity['process_creation_filetime'],1,2**64-1):refuse('identity_values')
    if native_identity['magic']!=1297100850 or native_identity['version']!=2:refuse('protocol_identity')
    if type(native_state) is not dict or any(type(native_state.get(key)) is not int or native_state[key]!=native_identity[key] for key in IDENTITY):refuse('native_identity_changed')
    if not integer(native_state.get('start_high')) or not integer(native_state.get('start_low')) or (native_state['start_high']<<32)|native_state['start_low']!=native_identity['process_creation_filetime']:refuse('native_incarnation_changed')
    if not integer(native_state.get('request')) or native_state.get('ack')!=native_state['request'] or type(native_state.get('ack')) is not int:refuse('native_unknown_sequence')
    if any(type(native_state.get(key)) is not int or native_state[key]!=value for key,value in
            dict(phase=1,active=0,error=0,self_hook_installed=1,lease_held=1).items()):refuse('native_not_idle_owned')
    if not integer(native_state.get('last_frame'),1) or not integer(native_state.get('applied_mask'),0,(1<<20)-1):refuse('native_frames_or_mask')
    deadline=native_state.get('deadline_frame')
    if native_state['applied_mask']:
        if not integer(deadline,1) or not 0<deadline-native_state['last_frame']<=1350:refuse('native_deadline')
    elif type(deadline) is not int or deadline!=0 or type(native_state.get('cleanup_verified')) is not int or native_state['cleanup_verified']!=1:refuse('native_empty_gate')
    if type(flag_names) is not tuple or len(flag_names)!=20 or len(set(flag_names))!=20 or any(type(x) is not str or not x for x in flag_names):refuse('flag_manifest')
    if type(flags) is not dict or type(flags.get('flags')) is not list or len(flags['flags'])!=20:refuse('independent_flags')
    for index,(row,name) in enumerate(zip(flags['flags'],flag_names)):
        if type(row) is not dict or row.get('name')!=name or type(row.get('present')) is not bool:refuse('independent_flags')
        wanted=bool(native_state['applied_mask']&(1<<index))
        if wanted and (row['present'] is not True or row.get('value') is not True) or not wanted and row['present'] and row.get('value') is not False:refuse('flag_native_disagreement')
    # Only the qualified high-level transport bits may already be held.
    if native_state['applied_mask'] & ~sum(1<<n for n in (0,1,3,4,8,9,10,11,12)):refuse('detailed_native_gate_active')
    obs=sample.get('observation')
    if type(obs) is not dict or obs.get('source')!='native_macro_read_only' or type(obs.get('native_calls')) is not int or obs['native_calls']!=0 or type(obs.get('process_writes')) is not int or obs['process_writes']!=0:refuse('observation_source')
    census=obs.get('construction_feedback')
    if type(census) is not dict or census.get('enemy_details_read') is not False:refuse('census_scope')
    if type(lawful_view) is not dict or lawful_view.get('paused') is not False or type(lawful_view.get('game_time_seconds')) not in (float,int) or not math.isfinite(lawful_view['game_time_seconds']):refuse('lawful_clock')
    field=lawful_view.get('battlefield',{})
    if field.get('visibility_verified') is not True or type(field.get('viewer_player_id')) is not int or field['viewer_player_id']!=3:refuse('lawful_visibility')
    frames=(obs.get('frame'),census.get('frame'))
    if any(not integer(value,1) for value in frames) or abs(frames[0]-frames[1])>15 or any(abs(lawful_view['game_time_seconds']*15-value)>15 for value in (*frames,native_state['last_frame'])):refuse('observation_timing')
    own=obs.get('native')
    if type(own) is not dict or own.get('store_membership_verified') is not True or own.get('side_matches_player') is not True or own.get('mutations') is not False:refuse('own_native_scope')
    for actual,expected in (('player','owner'),('ai_player','ai'),('personality_wrapper','personality'),('instance_id','personality_id'),('player_template','player_template')):
        if pointer(own.get(actual))!=native_identity[expected]:refuse('own_native_identity')
    if type(own.get('player_index')) is not int or own['player_index']!=3:refuse('own_player')
    return OptionalBuilderGap(KIND,frames)
