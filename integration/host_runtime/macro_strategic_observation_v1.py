"""Strategic observation has no dependency on precise builder telemetry.

The binding is captured once after the verified transport constructor. Reads
remain bounded by the original lawful sampler, native identity and flag gates.
Nothing here grants an action or synthesizes queue/financial observations.
"""
from dataclasses import dataclass
import math

from .contracts import ContractError
from .macro_delegation_boundary_v1 import STRATEGIC_ACTIONS

KIND = 'native_strategy_without_builder_v1'
IDENTITY = ('magic', 'version', 'pid', 'start_low', 'start_high', 'owner', 'ai',
            'personality', 'personality_id', 'player_template', 'engine')


def refuse(reason):
    raise ContractError('macro_strategic_observation_' + reason)


def number(value, minimum=0, maximum=0xffffffff):
    return type(value) is int and minimum <= value <= maximum


@dataclass(frozen=True)
class StrategicTransportBindingV1:
    identity: tuple
    flags: tuple
    strategic_mask: int


def bind_strategic_transport_v1(transport, session):
    """Compare constructor facts with the actual session and own-player read."""
    state = transport.native_status()
    protocol = transport.manifest.get('protocol_version', 1)
    expected = dict(magic=0x4d503032 if protocol == 2 else 0x4d504f4c,
                    version=protocol, pid=session['pid'], owner=transport.owner,
                    start_low=session['process_creation_filetime'] & 0xffffffff,
                    start_high=session['process_creation_filetime'] >> 32,
                    engine=transport.memory.u32(0xcdd190))
    for field, key in (('ai', 'ai_player'), ('personality', 'personality_wrapper'),
                       ('personality_id', 'instance_id'), ('player_template', 'player_template')):
        expected[field] = int(transport.native[key], 0)
    flags = tuple(transport.manifest['flags'])
    if protocol not in (1, 2) or len(flags) != (20 if protocol == 2 else 13) or len(set(flags)) != len(flags):
        refuse('protocol')
    if transport.creation != session['process_creation_filetime'] or any(
            not number(state.get(k)) or state[k] != value for k, value in expected.items()):
        refuse('attach_identity')
    mask = 0
    for row in transport.manifest['consumers']:
        if row['action'] in STRATEGIC_ACTIONS:
            mask |= 1 << flags.index(row['flag'])
    return StrategicTransportBindingV1(tuple((k, expected[k]) for k in IDENTITY), flags, mask)


def validate_strategic_observation_v1(sample, view, native, flags, binding):
    if type(binding) is not StrategicTransportBindingV1:
        refuse('binding_missing')
    if type(sample) is not dict or 'read_error' in sample or 'observation' not in sample:
        refuse('native_sample_missing')
    if 'build_observation' in sample or 'build_observation_error' in sample:
        refuse('builder_was_requested')
    if any(not number(native.get(k)) or native[k] != value for k, value in binding.identity):
        refuse('identity_changed')
    if any(type(native.get(k)) is not int or native[k] != value for k, value in
           dict(phase=1, error=0, self_hook_installed=1, lease_held=1).items()):
        refuse('native_not_owned')
    if not number(native.get('request')) or type(native.get('ack')) is not int or native['request'] != native['ack']:
        refuse('delivery_unknown')
    if not number(native.get('applied_mask')) or native['applied_mask'] & ~binding.strategic_mask:
        refuse('precision_gate_active')
    rows = flags.get('flags') if type(flags) is dict else None
    if type(rows) is not list or len(rows) != len(binding.flags):
        refuse('flags_missing')
    for index, (row, name) in enumerate(zip(rows, binding.flags)):
        if (type(row) is not dict or row.get('name') != name or type(row.get('present')) is not bool
                or row['present'] and type(row.get('value')) is not bool):
            refuse('flags_invalid')
        actual = row['present'] and row['value']
        if actual != bool(native['applied_mask'] & (1 << index)):
            refuse('flags_disagree')
    observation = sample['observation']
    if (type(observation) is not dict or observation.get('source') != 'native_macro_read_only'
            or type(observation.get('native_calls')) is not int or observation['native_calls'] != 0
            or type(observation.get('process_writes')) is not int or observation['process_writes'] != 0):
        refuse('source')
    own = observation.get('native', {})
    identity = dict(binding.identity)
    if (own.get('store_membership_verified') is not True or own.get('side_matches_player') is not True
            or own.get('mutations') is not False or type(own.get('player_index')) is not int or own['player_index'] != 3):
        refuse('own_identity')
    for key, field in (('player', 'owner'), ('ai_player', 'ai'), ('personality_wrapper', 'personality'),
                       ('instance_id', 'personality_id'), ('player_template', 'player_template')):
        try:
            if type(own.get(key)) is not str or int(own[key], 0) != identity[field]:
                refuse('own_identity')
        except (ValueError, TypeError):
            refuse('own_identity')
    census = observation.get('construction_feedback', {})
    battlefield = view.get('battlefield', {})
    seconds = view.get('game_time_seconds')
    if (type(seconds) not in (int, float) or not math.isfinite(seconds)
            or battlefield.get('visibility_verified') is not True
            or type(battlefield.get('viewer_player_id')) is not int or battlefield['viewer_player_id'] != 3
            or census.get('enemy_details_read') is not False):
        refuse('lawful_view')
    frames = (observation.get('frame'), census.get('frame'))
    if any(not number(frame, 1) for frame in (*frames, native.get('last_frame'))):
        refuse('clock')
    if type(native.get('active')) is not int or native['active'] not in (0, 1):
        refuse('native_active_invalid')
    # A native callback or sequential sample can be transiently out of phase.
    # Defer this observation; never retry a command or retime its facts.
    if native['active'] or max(frames) - min(frames) > 15 or any(
            abs(seconds * 15 - frame) > 15 for frame in (*frames, native['last_frame'])):
        return None
    deadline = native.get('deadline_frame')
    if native['applied_mask']:
        if not number(deadline, 1) or not 0 < deadline - native['last_frame'] <= 4500:
            return None
    elif type(deadline) is not int or deadline != 0 or native.get('cleanup_verified') != 1:
        refuse('empty_gate_not_verified')
    return frames
