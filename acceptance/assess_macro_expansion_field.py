"""Independent offline review of fixed expansion research; ACK is not effect."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'buildpower': '0xcf8d9f20', 'buildrefinery': '0xc45aaeab'}
MAP_ID = 'map_mp_2_black1b'
ORIGIN_REGION = 'region_8_3'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines() if line]


def flag_state(value, flags, mask=0):
    rows = value.get('flags', []) if type(value) is dict else []
    return (type(rows) is list and len(rows) == 20 and all(type(r) is dict and 'value' in r for r in rows)
        and [r.get('name') for r in rows] == flags
        and all((r.get('present') is True and r.get('value') is True) if mask & (1 << i)
            else r.get('present') is False and r.get('value') is None or r.get('present') is True and r.get('value') is False
            for i, r in enumerate(rows)))


def explicit_clear_chain(release, transport_events, flags, session, intent_id, intent_seq, intent_frame):
    """The clear receipt and both transport records must prove one command."""
    if type(release) is not dict or type(release.get('receipt')) is not dict: return False
    receipt=release['receipt']; ident=receipt.get('command_id'); seq=receipt.get('seq'); native=receipt.get('native')
    try:
        if type(ident) is not str or str(uuid.UUID(ident))!=ident: return False
    except (ValueError,AttributeError): return False
    if (ident==intent_id or type(intent_seq) is not int or type(seq) is not int or not 0<intent_seq<seq<=2048
            or seq!=intent_seq+1 or type(release.get('original_seq')) is not int or release['original_seq']!=intent_seq or type(native) is not dict
            or receipt.get('native_gate_acknowledged') is not True): return False
    prepared=[r for r in transport_events if r.get('kind')=='command_prepared' and r.get('command_id')==ident]
    acknowledged=[r for r in transport_events if r.get('kind')=='command_acknowledged' and r.get('command_id')==ident]
    if len(prepared)!=1 or len(acknowledged)!=1: return False
    pending,ack=prepared[0],acknowledged[0]
    if (transport_events.index(pending)>=transport_events.index(ack)
            or any((r.get('session_id'),r.get('pid'))!=(session.get('session_id'),session.get('pid')) for r in (pending,ack))):
        return False
    if (any(type(pending.get(k)) is not int for k in ('seq','kind_code','mask','duration_frames'))
            or (pending['seq'],pending['kind_code'],pending['mask'],pending['duration_frames'])!=(seq,1,0,1)
            or type(ack.get('seq')) is not int or ack['seq']!=seq or ack.get('native_gate_acknowledged') is not True
            or ack.get('native')!=native or ack.get('independent_flags')!=receipt.get('independent_flags')): return False
    required=dict(request=seq,ack=seq,applied_mask=0,phase=1,error=0,active=0,cleanup_verified=1,deadline_frame=0,
        self_hook_installed=1,lease_held=1)
    if any(type(native.get(k)) is not int or native[k]!=v for k,v in required.items()): return False
    if type(intent_frame) is not int or type(native.get('last_frame')) is not int or native['last_frame']<intent_frame: return False
    return flag_state(receipt.get('independent_flags'),flags) and flag_state(ack.get('independent_flags'),flags)


def sample_frames(sample):
    if type(sample) is not dict or sample.get('errors'): return None
    try:
        frames = [sample['match']['simulation_frame']]+[sample[k]['frame']
            for k in ('macro', 'builder', 'readiness', 'dependency', 'lifecycle')]
        frames.append(sample['macro']['construction_feedback']['frame'])
        frames.append(sample['scenario']['frame'])
        if (sample.get('observation_domain') != 'coherent_construction'
                or sample['macro'].get('source') != 'native_macro_construction_domain_read_only'
                or sample['macro'].get('observation_domain') != 'construction'
                or sample['macro'].get('strategic_runtime_sample_included') is not False): return None
        before, after, census_frame = sample['macro']['frame'], sample['macro']['frame_after'], sample['macro']['construction_feedback']['frame']
        if (not all(type(v) is int for v in (before, after, census_frame))
                or not before <= census_frame <= after or after-before > 2): return None
        began, ended, timings = sample['started_monotonic_ns'], sample['ended_monotonic_ns'], sample['component_timings']
        if type(began) is not int or type(ended) is not int or ended < began: return None
        for name in ('match', 'macro', 'builder', 'readiness', 'dependency', 'lifecycle', 'flags', 'scenario'):
            row = timings[name]; start, finish = row['started_monotonic_ns'], row['ended_monotonic_ns']
            if (type(start) is not int or type(finish) is not int or not began <= start <= finish <= ended
                    or row.get('duration_ns') != finish-start or row.get('read_error') is not None): return None
        if not all(type(v) is int and v > 0 for v in frames) or max(frames)-min(frames) > 15: return None
        if (sample['builder'].get('source') != 'native_macro_builder_read_only'
                or sample['builder'].get('native_calls') != 0 or sample['builder'].get('process_writes') != 0
                or sample['macro']['construction_feedback'].get('enemy_details_read') is not False
                or sample['dependency'].get('enemy_details_read') is not False): return None
        return frames
    except (KeyError, TypeError): return None


def scenario_matches(sample):
    """Recompute TemplePrime/origin from map bytes and own census, independently."""
    try:
        facts = sample['scenario']; census = sample['macro']['construction_feedback']; match = sample['match']
        if (facts.get('source') != 'native_gamelogic_map_and_own_census'
                or facts.get('public_map_fact') is not True or facts.get('own_perspective') is not True
                or facts.get('enemy_positions_read') is not False or census.get('enemy_details_read') is not False): return False
        logic = int(facts['expected_game_logic'], 0)
        if (not 0x10000 <= logic <= 0xffffffff-0x100
                or any(int(value, 0) != logic for value in (facts['game_logic_before'], facts['game_logic_after'],
                    match['game_logic'], sample['dependency']['session_identity']['game']))
                or facts['logic_vtable_before'] != '0xbeb630' or facts['logic_vtable_after'] != '0xbeb630'): return False
        pointer = int(facts['map_pointer_before'], 0)
        if not 0x10000 <= pointer <= 0xffffffff-260 or int(facts['map_pointer_after'], 0) != pointer: return False
        raw, after = bytes.fromhex(facts['map_buffer_hex']), bytes.fromhex(facts['map_buffer_after_hex'])
        if len(raw) != 260 or raw != after or b'\0' not in raw: return False
        path = PureWindowsPath(raw.split(b'\0', 1)[0].decode('ascii'))
        if path.suffix.lower() != '.map' or path.stem.lower() != MAP_ID or path.parent.name.lower() != MAP_ID: return False
        times = (match['simulation_frame'], census['frame'], facts['frame_at_map_read'], facts['frame'])
        if (not all(type(v) is int and v > 0 for v in times)
                or not times[0] <= times[1] <= times[2] <= times[3] or times[3]-times[0] > 15
                or facts.get('own_census_frame') != census['frame']): return False
        yards = [r for r in census['own_objects'] if r.get('type_hash') == '0xc16ff13f'
            and type(r.get('hp')) in (int, float) and math.isfinite(r['hp']) and r['hp'] > 0]
        if len(yards) != 1: return False
        xyz = yards[0].get('xyz')
        if (type(xyz) not in (list, tuple) or len(xyz) != 3
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in xyz)): return False
        origin = 'region_'+str(int(xyz[0]//512))+'_'+str(int(xyz[1]//512))
        # Parsed metadata must agree too, but its booleans never replace bytes.
        return (origin == ORIGIN_REGION and facts.get('origin_region') == origin
            and facts.get('map_id') == MAP_ID and facts.get('status') == 'matched'
            and facts.get('scope_verified') is True)
    except (KeyError, TypeError, ValueError, UnicodeError, OverflowError): return False


def native_queues(sample, target, allowed_producers=None):
    objects = {r['thing_id']: r['type_hash'] for r in sample['macro']['construction_feedback']['own_objects']}
    producers = set(); queues = {}
    for row in sample['builder']['builders']:
        factory = row['factory']; ident = factory['thing_id']
        if (factory.get('type_hash') != '0xc16ff13f' or objects.get(ident) != '0xc16ff13f'
                or row.get('observation_available') is not True or factory.get('hp', 0) <= 0): continue
        producers.add(ident)
        if allowed_producers is not None and ident not in allowed_producers: continue
        for node in row['queue_candidate']['nodes']:
            if node.get('kind_raw') != 1 or node.get('template_hash') != target: continue
            number = node.get('production_id_raw'); cost = node.get('native_cost_plus_30'); paid = node.get('paid_accumulator_plus_68')
            if (type(number) is not int or number <= 0 or type(cost) is not int or cost <= 0
                    or type(paid) is not int or not 0 <= paid <= cost): raise ValueError('assessment_native_queue_fields')
            key = (ident, number)
            if key in queues and queues[key] != (cost, paid): raise ValueError('assessment_duplicate_native_queue')
            queues[key] = (cost, paid)
    return producers, queues, objects


def assess_data(preflight, events, transport_events, final, result, *, source_integrity, transport_preflight=None):
    config = preflight['config']; manifest = preflight['manifest']; flags = manifest.get('flags', [])
    action = config.get('action'); target = TARGETS.get(action); session = preflight.get('session', {})
    samples = [e for e in events if e.get('kind') == 'sample']
    valid = [e for e in samples if sample_frames(e.get('sample')) is not None]
    discarded = [dict(phase=e.get('phase'), monotonic_ns=e.get('monotonic_ns'),
        errors=e.get('sample', {}).get('errors', {})) for e in samples if e not in valid]
    prepared = [e for e in events if e.get('kind') == 'intent_prepared']
    acknowledgements = [e for e in events if e.get('kind') == 'intent_acknowledged']
    checks = dict(source_archives_intact=source_integrity,
        fixed_research_scope=(target is not None and preflight.get('model_calls') == 0 and config.get('model_calls') == 0
            and preflight.get('unit_orders') == 0 and preflight.get('enemy_details_read') is False
            and preflight.get('additional_count') == 1 and preflight.get('target_type_hash') == target
            and config.get('policy') in ([action], [action, 'budgeteconomy'])
            and manifest.get('protocol_version') == 2 and len(flags) == 20 and len(set(flags)) == 20),
        exact_session_identity=(type(session.get('pid')) is int and session['pid'] > 0
            and type(session.get('process_creation_filetime')) is int and session['process_creation_filetime'] > 0),
        lifecycle_within_sixty_seconds=(type(config.get('seconds')) in (float, int) and 1 <= config['seconds'] <= 60
            and type(result.get('live_lifecycle_began_monotonic_ns')) is int
            and type(result.get('live_lifecycle_ended_monotonic_ns')) is int
            and 0 <= result['live_lifecycle_ended_monotonic_ns']-result['live_lifecycle_began_monotonic_ns'] <= config['seconds']*1e9),
        sources_unchanged_at_end=result.get('source_archives_unchanged') is True and result.get('source_originals_unchanged') is True,
        memory_closed=result.get('memory_closed') is True)
    native_identities = [e['sample']['macro'].get('native', {}) for e in valid]
    checks['audited_p3_identity_consistent'] = (bool(native_identities) and all(
        n.get('player_index') == 3 and n.get('instance_id') == '0x799613e0'
        and n.get('store_membership_verified') is True and n.get('side_matches_player') is True
        and n == native_identities[0] for n in native_identities))
    checks['transport_events_bound_to_session'] = all(e.get('session_id') == session.get('session_id')
        and e.get('pid') == session.get('pid') for e in transport_events)
    checks['package_bound_to_session'] = (type(session.get('mod_sha256')) is str
        and len(session['mod_sha256']) == 64 and manifest.get('package_sha256') == session['mod_sha256'])
    checks['templeprime_and_own_origin_scope_confirmed'] = bool(valid) and all(scenario_matches(e['sample']) for e in valid)
    checks['declared_scenario_scope_fixed'] = preflight.get('scenario_scope') == dict(map_id=MAP_ID,
        required_origin_region=ORIGIN_REGION, region_cell_size=512,
        public_map_and_own_origin_required=True, enemy_positions_read=False)
    checks['construction_domain_and_original_frames_preserved'] = bool(valid) and preflight.get('sampling_scope') == dict(
        domain='coherent_construction', maximum_component_frame_span=15,
        dynamic_data_cached=False, full_macro_preflight_is_diagnostic_only=True)
    no_transport = not any(e.get('kind') in ('attach_prepared', 'attach_acknowledged') for e in transport_events)
    if no_transport and not prepared:
        checks['clean_no_dispatch'] = bool(valid) and flag_state(valid[-1]['sample'].get('flags'), flags)
        return dict(kind='macro_expansion_field_assessment', schema_version=1, protocol_version=2, action=action, checks=checks,
            disposition='not_qualified_no_intent', fixed_consumer_effect_supported=False,
            failed_samples=discarded, samples=len(samples), native_effects={},
            scenario_scope=dict(map_id=MAP_ID, required_origin_region=ORIGIN_REGION),
            product_capability_granted=False, field_qualification_granted=False, model_calls=0)
    cleanup = (type(final) is dict and final.get('session_id') == session.get('session_id')
        and final.get('pid') == session.get('pid') and final.get('process_creation_filetime') == session.get('process_creation_filetime')
        and final.get('mod_sha256') == session.get('mod_sha256')
        and final.get('cleanup_verified') is True and final.get('unknown_command_ids') == []
        and final.get('host_returncode') == 0 and flag_state(final.get('independent_flags'), flags)
        and all(final.get('native', {}).get(k) == v for k, v in dict(phase=2, error=0, active=0,
            applied_mask=0, cleanup_verified=1, self_hook_installed=0, lease_held=0).items()))
    checks['independent_twenty_flags_lease_hook_unknown_cleanup'] = cleanup
    checks['transport_preflight_exact_identity_and_quiescence'] = (type(transport_preflight) is dict
        and transport_preflight.get('session_sha256') == preflight.get('session_sha256')
        and type(preflight.get('session_sha256')) is str and len(preflight['session_sha256']) == 64
        and transport_preflight.get('process_creation_filetime') == session.get('process_creation_filetime')
        and transport_preflight.get('native') == (native_identities[0] if native_identities else None)
        and flag_state(transport_preflight.get('initial_flags'), flags))
    checks['one_fixed_intent'] = len(prepared) == len(acknowledgements) == 1
    effects = dict(positive_state_frames=[], matching_new_queue_observations=[], new_object_observations=[],
        completion_events=[], rejected_completion_claims=[], power_observations=[], prerequisite_observations=[], enqueue_admission_observations=[],
        outside_active_window_samples=[], exact_queue_to_object_link_verified=False, payment_verified=False,
        exclusive_fixed_intent_attribution_verified=False, unit_exit_verified=False)
    window_info = {}; conditional_unknown = False
    if checks['one_fixed_intent']:
        intent = prepared[0]; ack = acknowledgements[0]['receipt']; window = intent.get('window', {})
        command_id = intent.get('command_id'); seq = ack.get('seq')
        native_commands = [e for e in transport_events if e.get('kind') == 'command_acknowledged' and e.get('command_id') == command_id]
        commands_prepared = [e for e in transport_events if e.get('kind') == 'command_prepared' and e.get('command_id') == command_id]
        masks = {r['action']: 1 << flags.index(r['flag']) for r in manifest.get('consumers', []) if r.get('flag') in flags}
        mask = sum(masks.get(a, 0) for a in config['policy'])
        native = ack.get('native', {}); duration = window.get('native_duration_frames', 0)
        deadline = native.get('deadline_frame', 0); actual_start = deadline-duration
        checks['intent_receipt_bound_to_native_seq'] = (len(native_commands) == len(commands_prepared) == 1
            and native_commands[0].get('seq') == seq and native_commands[0].get('native') == native
            and commands_prepared[0].get('seq') == seq and commands_prepared[0].get('mask') == mask
            and commands_prepared[0].get('duration_frames') == duration
            and native.get('request') == native.get('ack') == seq and native.get('applied_mask') == mask
            and native.get('error') == 0 and native.get('phase') == 1
            and type(duration) is int and 1 <= duration <= 600
            and 0 < native.get('start_frame', 0) <= actual_start <= native.get('last_frame', -1) < deadline
            and flag_state(ack.get('independent_flags'), flags, mask))
        # start_frame in Shared is attach start; command application is the
        # actual native deadline minus its prepared duration, not attach time.
        clear_events = [e for e in events if e.get('kind') == 'intent_cleared' and e.get('original_seq') == seq]
        release = clear_events[0] if len(clear_events) == 1 else None
        clear_receipt = release.get('receipt') if release else None
        clear_native = clear_receipt.get('native') if type(clear_receipt) is dict else None
        if type(clear_native) is not dict: clear_native={}
        clear_frame = clear_native.get('last_frame')
        if type(clear_frame) is not int: clear_frame=None
        checks['explicit_clear_bound'] = explicit_clear_chain(release,transport_events,flags,session,
            command_id,seq,native.get('last_frame'))
        conditional_unknown = window.get('unknown_native_precondition_probe') is True
        window_start, window_end = window.get('starts_monotonic_ns', 0), window.get('expires_monotonic_ns', 0)
        checks['research_window_bound'] = (window.get('kind') == 'fixed_intent_research_window' and window.get('model_calls') == 0
            and type(window_start) is int and type(window_end) is int and 0 < window_end-window_start <= (5 if conditional_unknown else 30)*1e9
            and (not conditional_unknown or action == 'buildrefinery' and config.get('allow_unknown_native_precondition') is True)
            and checks['explicit_clear_bound'] and events.index(intent)<events.index(acknowledgements[0])<events.index(release)
            and type(release.get('monotonic_ns')) is int
            and window_start <= release['monotonic_ns'] <= (window_start+5_000_000_000 if conditional_unknown else window_end+5_000_000_000))
        baselines = [e for e in valid if e.get('phase') == 'baseline_attached'
            and e['monotonic_ns'] <= intent['monotonic_ns'] and events.index(e) < events.index(intent)]
        baseline = baselines[-1]['sample'] if baselines else None
        checks['fresh_empty_baseline'] = baseline is not None
        if baseline:
            producers, baseline_queues, baseline_objects = native_queues(baseline, target)
            checks['fresh_empty_baseline'] = (len(producers) == 1 and not baseline_queues
                and max(sample_frames(baseline)) <= actual_start and actual_start-max(sample_frames(baseline)) <= 30
                and flag_state(baseline.get('flags'), flags))
            flag = next((r['flag'] for r in manifest['consumers'] if r['action'] == action), None)
            baseline_ids = {i for i, kind in baseline_objects.items() if kind == target}
            checks['precondition_replayed'] = _baseline_precondition(baseline, action, conditional_unknown)
            completion_edges = _completion_edges(valid)
            for event in valid:
                sample = event['sample']; fs = sample_frames(sample)
                wall_start, wall_end = sample.get('started_monotonic_ns', 0), sample.get('ended_monotonic_ns', 0)
                state = sample.get('native', {})
                in_window = (event.get('phase') == 'active' and event.get('seq') == seq
                    and window_start <= wall_start <= wall_end <= window_end
                    and checks['explicit_clear_bound'] and checks['research_window_bound'] and wall_end <= release['monotonic_ns']
                    and all(actual_start <= f < deadline and f <= clear_frame for f in fs)
                    and sample['match'].get('pause_type_candidate') == sample['match'].get('pause_flag_candidate') == 0
                    and scenario_matches(sample)
                    and state.get('request') == state.get('ack') == seq and state.get('applied_mask') == mask
                    and state.get('phase') == 1 and state.get('error') == 0
                    and state.get('lease_held') == state.get('self_hook_installed') == 1
                    and flag_state(sample.get('flags'), flags, mask))
                effects['power_observations'].append(dict(frame=sample['readiness']['frame'], phase=event.get('phase'), **sample['readiness']['power']))
                for row in sample['dependency'].get('actions', []):
                    if row.get('action') != action: continue
                    effects['prerequisite_observations'].append(dict(frame=sample['dependency']['frame'],
                        prerequisite_met=row.get('prerequisite_met'), required_objects_met=row.get('native_required_objects_met'),
                        phase=event.get('phase'), within_active_window=in_window))
                    effects['enqueue_admission_observations'].append(dict(frame=sample['dependency']['frame'],
                        candidates=row.get('enqueue_admission_candidates', []), phase=event.get('phase'), within_active_window=in_window))
                _, queues, objects = native_queues(sample, target, producers)
                for ident, kind in objects.items():
                    if kind == target and ident not in baseline_ids:
                        effects['new_object_observations'].append(dict(thing_id=ident, frame=sample['macro']['construction_feedback']['frame'],
                            phase=event.get('phase'), within_active_window=in_window))
                for row in sample['lifecycle'].get('objects', []):
                    if (row.get('native_completion_transition_observed') is True
                            and (sample['dependency']['frame'], row.get('thing_id')) not in completion_edges):
                        effects['rejected_completion_claims'].append(dict(thing_id=row.get('thing_id'), frame=sample['lifecycle']['frame']))
                for frame, ident in completion_edges:
                    if frame == sample['dependency']['frame'] and objects.get(ident) == target:
                        effects['completion_events'].append(dict(thing_id=ident, frame=frame,
                            phase=event.get('phase'), within_active_window=in_window))
                if not in_window:
                    if event.get('phase') == 'active': effects['outside_active_window_samples'].append(dict(frames=fs, monotonic_ns=event['monotonic_ns']))
                    continue
                for key, (cost, paid) in queues.items():
                    if key not in baseline_queues:
                        effects['matching_new_queue_observations'].append(dict(producer_thing_id=key[0], production_id=key[1],
                            frame=sample['builder']['frame'], native_cost_raw=cost, paid_accumulator_raw=paid))
                if any(r.get('flag') == flag and r.get('dirty') is False and type(r.get('state_score')) in (int, float)
                        and math.isfinite(r['state_score']) and r['state_score'] > 0
                        and any(e.get('build_type_hash_raw') == target for e in r.get('entries', []))
                        for r in sample['builder'].get('macro_entries', [])):
                    effects['positive_state_frames'].append(sample['builder']['frame'])
        window_info = dict(native_seq=seq, attach_start_frame=native.get('start_frame'),
            command_applied_frame_from_deadline_and_duration=actual_start, native_deadline_frame=deadline,
            independent_clear_frame=clear_frame, fixed_intent_window=window)
    checks['positive_native_score_inside_window'] = bool(effects['positive_state_frames'])
    checks['matching_native_queue_inside_window'] = bool(effects['matching_new_queue_observations'])
    checks['completion_claims_match_raw_transition'] = not effects['rejected_completion_claims']
    checks['no_unknown_or_fault'] = (not any(e.get('kind') in ('clear_unknown', 'close_unknown', 'trial_fault', 'initialization_failed') for e in events)
        and not any(e.get('kind') in ('command_unknown', 'independent_readback_unknown') for e in transport_events))
    supported = all(checks.values())
    return dict(kind='macro_expansion_field_assessment', action=action, session_id=session.get('session_id'),
        schema_version=1, protocol_version=2, checks=checks, disposition='research_consumer_effect_supported' if supported else 'not_qualified',
        fixed_consumer_effect_supported=supported, native_window=window_info, native_effects=effects,
        samples=len(samples), valid_samples=len(valid), failed_samples=discarded,
        unknown_open_node_research_probe=conditional_unknown,
        scenario_scope=dict(map_id=MAP_ID, required_origin_region=ORIGIN_REGION),
        open_node_independent_readback_verified=False, product_capability_granted=False,
        field_qualification_granted=False, model_calls=0, formal_goal_complete=False)


def _baseline_precondition(sample, action, unknown_probe):
    if not scenario_matches(sample): return False
    if sample['match'].get('pause_type_candidate') != 0 or sample['match'].get('pause_flag_candidate') != 0: return False
    rows = [r for r in sample['dependency'].get('actions', []) if r.get('action') == action]
    if len(rows) != 1 or rows[0].get('prerequisite_met') is not True or rows[0].get('sdk_required_objects_match') is not True: return False
    if not any(r.get('native_enqueue_admission_met') is True for r in rows[0].get('enqueue_admission_candidates', [])): return False
    if action == 'buildrefinery': return unknown_probe
    power = sample['readiness'].get('power', {})
    return (type(power.get('native_supply')) is int and type(power.get('native_demand')) is int
        and power['native_demand'] > power['native_supply'] and power.get('native_energy_sufficient') is False)


def _completion_edges(valid):
    """Reconstruct edges from archived raw dependency states, not tracker claims."""
    previous = {}; last = None; session = None; edges = set()
    for event in valid:
        dep = event['sample']['dependency']; frame = dep['frame']; identity = dep.get('session_identity')
        if identity != session or last is None or not 0 < frame-last <= 30: previous = {}
        current = {}
        for row in dep.get('own_lifecycles', []):
            status = row.get('object_status', {}); unpack = row.get('unpack', {})
            key = tuple(row.get(k) for k in ('thing_id', 'thing_address', 'template_address', 'type_hash'))
            if any(v is None for v in key): continue
            active = unpack.get('native_unpack_in_progress'); notified = row.get('native_unpack_completion_notified')
            negative = any(status.get(k) for k in ('under_construction', 'pending_construction', 'unpacking', 'reconstructing'))
            before = previous.get(key)
            usable = (row.get('currently_registered') is True and row.get('named_template_supported') is True
                and row.get('hp', 0) > 0 and not any(status.get(k) for k in ('destroyed', 'sold', 'not_in_world')))
            if (usable and not negative and active is False and notified is True and before
                    and before['active'] is True and before['notified'] is False and before['negative']
                    and before['duration'] > 0 and before['started'] > 0
                    and before['duration'] == unpack.get('native_unpack_duration_frames')
                    and before['started'] == unpack.get('native_unpack_started_frame')):
                edges.add((frame, row['thing_id']))
            current[key] = dict(active=active, notified=notified, negative=negative,
                duration=unpack.get('native_unpack_duration_frames', 0), started=unpack.get('native_unpack_started_frame', 0))
        previous = current; last = frame; session = identity
    return edges


def assess(run):
    preflight = load(run/'driver-preflight.json'); events = records(run/'expansion-trial.jsonl')
    final_path = run/'transport/final-state.json'; stream_path = run/'transport/policy-probe.jsonl'
    final = load(final_path) if final_path.exists() else None
    stream = records(stream_path) if stream_path.exists() else []
    transport_preflight = load(run/'transport/preflight.json') if (run/'transport/preflight.json').exists() else None
    source_integrity = verify_archives(run, preflight)
    return assess_data(preflight, events, stream, final, load(run/'driver-result.json'),
        source_integrity=source_integrity, transport_preflight=transport_preflight)


def verify_archives(run, preflight):
    """Verify copied raw sources and their build/package bindings, offline only."""
    try:
        rows = preflight.get('sources', [])
        if not rows: return False
        by_path = {}
        for row in rows:
            source = Path(row['path']).resolve(); copy = (run/row['copy']).resolve()
            if not copy.is_relative_to(run.resolve()) or source in by_path or not copy.is_file() or sha(copy) != row['sha256']:
                return False
            by_path[source] = (copy, row['sha256'])
        required = {
            ROOT/'native-ai/macro_readiness_observation.py': 'd9abb6c26e218f5a719a22bed1279a8b468ae0611ebbc506ad0f2678b5704989',
            ROOT/'native-ai/readiness_dependency_contract.py': '7b80c594283631fa3cf31f616f63c4a38da32c1e8f29ee32e95fde988a3dee4b',
        }
        manifest = preflight['manifest']
        if (set(manifest['sources']) != {'client.py', 'build.py', 'native.cpp', 'host.cpp', 'shared.h'}
                or manifest.get('kind') != 'native_macro_policy_transport_v2_candidate'
                or manifest.get('protocol_version') != 2 or manifest.get('capability_granted') is not False): return False
        for name, digest in manifest['sources'].items(): required[ROOT/'native-ai/macro-policy-runtime-v2'/name] = digest
        report_path = Path(manifest['package_report']).resolve()
        required[report_path] = manifest['package_report_sha256']
        report = load(by_path[report_path][0])
        if (report.get('variant') != 'expanded_macro_policy_v2' or report.get('transport_protocol_version') != 2
                or report.get('big_sha256') != manifest['package_sha256']
                or report.get('contract_source_sha256') != manifest['profile_contract_sha256']
                or report.get('compiled_expansion_audit_sha256') != manifest['compiled_expansion_audit_sha256']): return False
        required[ROOT/'native-ai/stage_macro_expansion.py'] = report['source_sha256']
        required[ROOT/'native-ai/macro_expansion_contract.py'] = report['contract_source_sha256']
        required[report_path.parent/'TFMacroProbe.big'] = manifest['package_sha256']
        required[report_path.parent/'compiled-expansion-audit.json'] = report['compiled_expansion_audit_sha256']
        if any(path.resolve() not in by_path or by_path[path.resolve()][1] != digest for path, digest in required.items()): return False
        build_path = Path(preflight['build_path']).resolve()
        if by_path[build_path/'build-manifest.json'][1] != preflight['build_manifest_sha256']: return False
        if load(by_path[build_path/'build-manifest.json'][0]) != manifest: return False
        if load(by_path[Path(preflight['session_path']).resolve()][0]) != preflight['session']: return False
        if set(manifest['artifacts']) != {manifest['library'], 'macro_policy_host.exe'}: return False
        if any(by_path[build_path/name][1] != digest for name, digest in manifest['artifacts'].items()): return False
        return True
    except (KeyError, TypeError, ValueError, OSError): return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve()
    if output.exists() or not output.is_relative_to((ROOT/'reports').resolve()): raise ValueError('fresh_local_expansion_assessment_required')
    value = assess(args.run.resolve()); output.mkdir(parents=True)
    shutil.copy2(__file__, output/'assessor.py'); value['assessor_sha256'] = sha(Path(__file__))
    with (output/'assessment.json').open('x', encoding='utf8') as stream: json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(output=str(output), disposition=value['disposition'],
        research_effect_supported=value['fixed_consumer_effect_supported'], capability_granted=False)))


if __name__ == '__main__': main()
