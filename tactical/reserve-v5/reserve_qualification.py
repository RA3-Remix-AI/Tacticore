"""Independent Reserve5 raw verifier. No game access or tactical capability grant."""
import hashlib
import json
import math
import struct
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
TYPES = {0x19ab11af: 100., 0x2c358c61: 120.}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def integer(x):
    return type(x) is int and 0 <= x <= 0xffffffff


def number(x):
    return int(x, 0) if isinstance(x, str) else x


def point(x):
    return isinstance(x, list) and len(x) == 3 and all(type(v) in (int, float) and math.isfinite(v) for v in x)


def distance(a, b):
    return math.dist(a[:2], b[:2]) if point(a) and point(b) else math.inf


def sample_identity(s, n):
    """Recompute original actor, module and actual native surface bindings."""
    try:
        pairs = {'thing': 'thing', 'id': 'object_id', 'type_hash': 'type_hash', 'owner': 'owner',
                 'template_ptr': 'template_ptr', 'update': 'update', 'stance_module': 'stance_module'}
        bound = all(integer(s[k]) and s[k] == n[v] for k, v in pairs.items())
        initial=n.get('initial_sample',{})
        bound &= all(s.get(key)==initial.get(key) for key in ('stance_data','stance_enum_list','stance_enum_count','stance_enum_entries')) if initial else True
        words = s['status_words']
        typed = isinstance(words, list) and len(words) == 7 and all(integer(w) for w in words)
        bit = lambda i: bool(words[i // 32] & (1 << (i % 32)))
        surface = typed and not any(bit(i) for i in (0, 7, 8, 51, 61, 161, 207, 211))
        return bool(bound and s['thing'] and s['owner'] and s['template_ptr'] and s['update']
                    and s['update_vtable'] == 0xc48670 and s['update_backref'] == n['thing']
                    and s['stance_vtable'] == 0xc37f90 and s['stance_backref'] == n['thing']
                    and s['stance_data'] and s['sm'] and s['state'] and s['sm_owner'] == n['thing']
                    and s['state_owner_sm'] == s['sm'] and integer(s['sm_flags'])
                    and s['holder'] == 0 and surface and s['height_flags'] & 4
                    and math.isfinite(s['height']) and abs(s['height']) <= .5
                    and s['type_hash'] in TYPES and math.isfinite(s['hp'])
                    and s['hp'] > 0 and point(s['xyz']) and integer(s['frame']))
    except (KeyError, ValueError, TypeError, IndexError):
        return False


def holding_sample(s, n):
    if not sample_identity(s, n):
        return False
    try:
        return bool(s['stance'] == 2 and s['state_id'] == 94 and s['state_vtable'] == 0xc551a0
                    and s['path'] == 0 and s['source'] == 1 and not s['sm_flags'] & 0xffff
                    and s['team'] == n['script_team'])
    except (KeyError, ValueError, TypeError, struct.error):
        return False


def stop_three(rows, origin, n, issue_frame, goal=None):
    """Only actual subsequent distinct samples contribute to the physical gate."""
    prior, run, frames, first = origin, 0, [], None
    for event in rows:
        s = event['sample']
        if event['kind'] != 3 or s['frame'] <= issue_frame:
            continue
        if frames and s['frame'] <= frames[-1]:
            return {'verified': False, 'frames': frames, 'gate': None}
        frames.append(s['frame'])
        stable = holding_sample(s, n) and distance(s['xyz'], prior) <= 1 and (goal is None or distance(s['xyz'],goal)<=15)
        run = run + 1 if stable else 0
        if stable and run == 1:
            first = s['xyz']
        prior = s['xyz']
        if run >= 3:
            return {'verified': s['frame'] - issue_frame <= 60, 'frames': frames[-3:],
                    'gate': event, 'first_stable_xyz': first}
        if s['frame'] - issue_frame > 60:
            break
    return {'verified': False, 'frames': frames, 'gate': None}


def hold_window(rows, start, anchor, n):
    """Strictly observed ninety logical frames; missing frames are never filled."""
    samples = [e for e in rows if e['kind'] == 3 and start < e['frame'] <= start + 90]
    frames = [e['frame'] for e in samples]
    missing = sorted(set(range(start + 1, start + 91)) - set(frames))
    gaps = [b - a for a, b in zip([start] + frames, frames)]
    prior, maximum, all_physical = anchor, 0., True
    for e in samples:
        s = e['sample']
        drift = distance(s['xyz'], anchor)
        all_physical &= holding_sample(s, n) and distance(s['xyz'], prior) <= 1 and drift <= 15
        if 'anchor' in n:
            all_physical &= distance(s['xyz'], n['anchor']['actual_anchor']) <= 15
        maximum = max(maximum, drift)
        prior = s['xyz']
    factory_gaps=[]
    if 'anchor' in n:
        f=[struct.unpack('<f',struct.pack('<I',n['rally'][k]))[0] for k in ('factory_x_bits','factory_y_bits')]+[0.]
        factory_gaps=[distance(anchor,f)]+[distance(e['sample']['xyz'],f) for e in samples]
    coverage = len(frames) == 90 and not missing and all(g == 1 for g in gaps)
    return {'verified': bool(coverage and all_physical), 'first_frame': frames[0] if frames else None,
            'last_frame': frames[-1] if frames else None, 'count': len(frames),
            'max_frame_gap': max(gaps, default=0), 'missing_frame_ids': missing,
            'continuous_all_logic_frames_verified': bool(coverage), 'physical_samples_verified': bool(all_physical),
            'max_anchor_drift': maximum, 'fixed_start': start, 'fixed_end': start + 90,
            'minimum_observed_factory_gap': min(factory_gaps) if factory_gaps else None,
            'factory_radius_during_hold_is_a_hard_gate': False}


def no_grant():
    return {'tactical_source_granted': False, 'effect_verified': False, 'completion_claim': False}


def source_paths():
    return [HERE / x for x in ('reserve_qualification.py', 'native_layout.py', 'lease.py', 'preflight.py', 'birth_source.py', 'rally_source.py', 'inert-layout.json')] + sorted(HERE.glob('*.cpp.inc'))


def external_source_paths():
    bridge = HERE.parent.parent
    return [bridge / x for x in (
        'tactical/ordered-combo/lease.py', 'tactical/mission_actor_admission_v2.py',
        'tactical/grounded_status_v2.py', 'tactical/grounded_status.py', 'tactical/mobility_guard.py',
        'visibility/capability.py', 'visibility/collector.py', 'visibility/projection.py',
        'production/persistent/client.py','production/persistent/shared.h',
        'production/persistent/bin-v2/ProductionPersistent.dll','production/persistent/bin-v2/persistent_host.exe',
        'integration/own_candidates.py')]


def source_pins(r):
    try:
        files = {'native_binary_sha256': HERE / 'bin/TacticalReserve5.dll',
                 'native_host_sha256': HERE / 'bin/tactical_host.exe',
                 'native_source_sha256': HERE / 'lease.cpp', 'native_shared_sha256': HERE / 'shared.h',
                 'wrapper_sha256': HERE / 'lease.py'}
        revision = json.loads((HERE / 'revision.json').read_text())
        compiled = {k: sha(p) for k, p in files.items() if k != 'wrapper_sha256'}
        compiled['native_includes_sha256'] = {p.name: sha(p) for p in sorted(HERE.glob('*.cpp.inc'))}
        inert = json.loads((HERE / 'inert-layout.json').read_text())
        abi = dict(sample=240,event=352,tactical=361624,events=1176,period_ms=20,fallback_ms=100,loss_ms=1000)
        return (set(compiled['native_includes_sha256']) == {'logic.cpp.inc', 'scheduler.cpp.inc', 'host_pulse.cpp.inc', 'rally.cpp.inc'}
                and all(r.get(k) == sha(p) for k, p in files.items())
                and all(r.get(k) == v == revision.get(k) for k, v in compiled.items())
                and r.get('native_revision_sha256') == sha(HERE / 'revision.json')
                and r.get('native_layout_sha256') == sha(HERE / 'native_layout.py')
                and r.get('supplemental_sources') == {p.name: sha(p) for p in source_paths()}
                and r.get('external_sources') == {p.relative_to(HERE.parent.parent).as_posix(): sha(p) for p in external_source_paths()}
                and revision['host_source_sha256'] == sha(HERE / 'host.cpp')
                and revision['build_script_sha256'] == sha(HERE / 'build.ps1')
                and revision['inert_layout_sha256'] == sha(HERE / 'inert-layout.json')
                and inert['dll_sha256'] == compiled['native_binary_sha256']
                and revision['layout'] == r.get('actual_host_abi') == abi
                and revision['hook_count']==8 and revision['restore_mask']==255
                and r.get('executable_sha256') == EXE)
    except (OSError, ValueError, TypeError):
        return False


HOOKS = {0x838820: '8b818c00000085c0744f568bb190000000',
         0x8d8880: '83ec24568b74242c8b4604', 0x8cd630: '83ec3453578b7c24408b4704',
         0x54b0a0: '83ec5c8b442460566a01508bf1', 0x721ad0: '83ec08558be98b45088b4804',
         0x7640f0: '83ec14538bd98b4308',
         0x571d90: '83ec5c8b442464566a01508bf1',
         0x76d9d0: '568bf1578b7e088bcf'}


def terminal_audit(r):
    try:
        n, t = r['native'], r['terminal_readonly']
        keys = ('pid', 'seq', 'token', 'session_id', 'commander_id', 'command_id', 'task_id')
        binding = all(t[k] == n[k] for k in keys) and t['native_binary_sha256'] == r['native_binary_sha256']
        entries = t['entries']
        actual = {number(e['address']): e for e in entries}
        pristine = len(entries) == 8 and set(actual) == set(HOOKS) and all(
            e['actual'].lower() == e['expected'].lower() == HOOKS[a]
            for a, e in actual.items())
        raw = bytes.fromhex(t['header_before_hex'])
        stable = len(raw)==1176 and t['header_before_hex']==t['header_after_hex']
        value = lambda offset: struct.unpack_from('<I',raw,offset)[0]
        header = (stable and value(0)==0x52535635 and value(4)==5 and value(8)==n['pid']
                  and value(88)==n['token'] and value(92)==n['seq']
                  and all(str(uuid.UUID(bytes=raw[24+16*i:40+16*i]))==n[key+'_id']
                          for i,key in enumerate(('session','commander','command','task'))))
        for key,offset in {'production_seq':668,'production_queue_id':672,'production_birth_frame':676,'production_paid':680,'admission_samples':716,'admission_first_frame':720,'admission_last_frame':724,'admission_verified':728,'admission_max_gap':732,'owner':100,'thing':120,'object_id':124,'phase':176,'active':184,'error':192,
                           'restore_mask':196,'returned_frame':212,'sdk_calls':216,'detach_calls':220,'return_calls':224,'return_verified':228,'stance_restored':264}.items():
            header &= value(offset)==n[key]
        header &= list(struct.unpack_from('<4I',raw,636))==n['production_command'] and list(struct.unpack_from('<4I',raw,652))==n['production_task'] and list(struct.unpack_from('<8I',raw,684))==n['production_receipt_sha256']
        rally = n['rally']
        packed = struct.pack('<8I8f14I', *[rally[k] for k in (
            'factory_address','factory_id','factory_owner','factory_template','factory_type_hash','factory_source_frame','factory_x_bits','factory_y_bits')],
            *rally['proposal_origin'], *rally['proposal_direction'], *rally['goal'],
            *[rally[k] for k in ('proposal_frame','arrival_samples','last_arrival_frame','rally_issue_frame','rally_reached_frame','rally_stop_verified','rally_stop_frame','move_intents','move_facade_entries','move_private_entries','foreign_move_entries','move_scope_open','move_generation','move_intent_seq')])
        header &= raw[976:1096] == packed
        anchor=n['anchor']
        header &= raw[1096:1176] == struct.pack('<9I11f', *[anchor[k] for k in (
            'candidate_samples','last_candidate_frame','candidate_frame','commit_frame','initial_outside_inner_zone','boundary_crossed','proposal_reached','admission_age_first','admission_age_last')],
            anchor['initial_factory_gap'],*anchor['candidate_xyz'],*anchor['actual_anchor'],*anchor['last_candidate_xyz'],anchor['proposal_distance'])
        return bool(binding and pristine and t['timer'] == t['active'] == n['active'] == 0
                    and t['restore_mask'] == n['restore_mask'] == 255 and t.get('mutations') is False
                    and t['phase'] == n['phase'] in (3, 4) and t['error'] == n['error'] and header
                    and t['timer_after']==0 and t['shared_pointer']==t['shared_pointer_after']>0
                    and t['binding_verified'] is True)
    except (KeyError, ValueError, TypeError, struct.error):
        return False


def sdk_audit(events, n):
    """Original pre/post inputs, nested source2 callbacks and conserved counters."""
    checks = {}
    intents = [e for e in events if e['kind'] == 50]
    checks['eight_original_intents_once'] = [e['arg'] for e in intents] == [1, 2, 3, 7, 8, 4, 5, 6]
    scopes, calls = [], 0
    counters = dict(explicit_stops=0, private_explicit_stops=0, automatic_stop2=0, private_automatic_stop2=0)
    borrow_seq=next((e['seq'] for e in intents if e['arg']==1),0)
    passive=[]
    valid, current = True, None
    for e in events:
        k, tag, src = e['kind'], e['tag'], e['source']
        if borrow_seq and e['seq']<borrow_seq and k in (12,13,14,15,30,31,32,33,64,65,66,67):
            valid &= tag==0 and e['sdk_calls']==0 and all(e[key]==0 for key in counters)
            passive.append(e);continue
        if k == 50:
            current = e['arg']; calls += 1
            valid &= current in (1,2,3,4,5,6,7,8) and tag == current
            if current in (3,4,8): counters['explicit_stops'] += 1
        if k == 30 and src == 2 and tag in (2,5): counters['automatic_stop2'] += 1
        if k == 33 and src == 2 and tag in (2,5): counters['private_automatic_stop2'] += 1
        if k == 33 and src == 1 and tag in (3,4,8) and e['caller'] == 0x787791:
            counters['private_explicit_stops'] += 1
        valid &= e['sdk_calls'] == calls and all(e[key] == value for key, value in counters.items())
        if k in (10,20,30,32,12,14):
            scopes.append(e)
            expected_self = n['owner'] if k == 10 else n['stance_module'] if k == 20 else n['update'] + 0x24 if k == 30 else n['update'] if k == 32 else None
            valid &= expected_self is None or e['self'] == expected_self
            if k == 10: valid &= tag in (1,6) and tag == current and e['arg'] == (tag == 6)
            if k == 20: valid &= tag in (2,5) and tag == current and e['arg'] == (2 if tag == 2 else n['original_stance'])
            if k in (30,32):
                valid &= (tag in (2,5) and tag == current and src == 2 or tag in (3,4,8) and tag == current and src == 1)
                if k == 32: valid &= e['caller'] == 0x787791
            if k in (12,14): valid &= tag in (1,6) and tag == current
        elif k in (11,21,31,33,13,15):
            if not scopes: valid = False; continue
            before = scopes.pop()
            valid &= k == before['kind'] + 1 and tag == before['tag'] and src == before['source'] and e['self'] == before['self'] and e['arg'] == before['arg']
            if k == 11: valid &= e['sample']['team'] == (n['script_team'] if tag == 1 else n['default_team'])
            if k == 21: valid &= e['result'] == 1 and e['sample']['stance'] == e['arg']
    checks['typed_nested_original_calls'] = bool(valid and not scopes)
    checks['exact_explicit_call_totals'] = (calls == n['sdk_calls'] == 8 and n['detach_calls'] == n['return_calls'] == 1
        and n['stance_calls'] == 2 and n['explicit_stops'] == n['private_explicit_stops'] == 3
        and all(n[key] == value for key, value in counters.items())
        and counters['automatic_stop2'] == counters['private_automatic_stop2'])
    checks['one_explicit_stop_chain_per_intent'] = all(
        [e['kind'] for e in events if e['tag'] == tag and e['kind'] in (30,31,32,33)] == [30,32,33,31] for tag in (3,4,8))
    checks['one_setter_and_transfer_each'] = all(
        sum(e['kind'] == kind and e['tag'] == tag for e in events) == 1
        for kind, tags in ((10,(1,6)),(11,(1,6)),(20,(2,5)),(21,(2,5))) for tag in tags)
    return dict(verified=all(checks.values()), checks=checks,pre_borrow_passive_event_count=len(passive),pre_borrow_passive_sdk_credit=False)


def team_proof_words(e):
    m=e['move'];words=[m['goal_pointer'],*m['goal_bits'],m['path'],m['limit_bits'],m['intent_seq'],m['facade_seq'],m['generation'],m['flags']]
    if len(words)!=10 or not all(integer(v) for v in words):raise ValueError('team_proof_shape')
    names='magic actor_team_before definition_before owner_before actor_team_after definition_after owner_after sample_frame previous_cohort_team previous_cohort_count'.split()
    proof=dict(zip(names,words))
    if 'team_proof' in e and e['team_proof']!=proof:raise ValueError('decoded_team_proof_changed')
    if 'team_proof_raw_hex' in e and bytes.fromhex(e['team_proof_raw_hex'])!=struct.pack('<10I',*words):raise ValueError('raw_team_proof_changed')
    return proof


def pre_admission_audit(r):
    """Replay every team cohort, including discarded runs and within-frame races."""
    checks=dict(exact_three_and_gate=False,every_actual_frame_eligible=True,immutable_actor_module_health=True,
                all_observed_have_team_evidence=True,raw_team_owner_chains_and_resets=True,original_raw_header_join=False,all_sdk_after_third_frame=False)
    try:
        n,es=r['native'],r['events'];intents=[e for e in es if e['kind']==50];borrow=next((e for e in intents if e['arg']==1),None)
        limit=borrow['seq'] if borrow else max((e['seq'] for e in es),default=0)+1
        samples=[e for e in es if e['kind']==3 and e['seq']<limit]
        fields=('thing','id','type_hash','owner','template_ptr','update','update_vtable','update_backref','stance_module','stance_vtable','stance_backref','stance_data','stance','stance_enum_list','stance_enum_count','stance_enum_entries','hp')
        count=team=last_observed=0;baseline=None;run=[];gate=None;accepted=[];resets=[]
        for index,body in enumerate(samples):
            end=samples[index+1]['seq'] if index+1<len(samples) else limit
            steps=[e for e in es if body['seq']<e['seq']<end and e['kind'] in (60,61,73,74,75)]
            proof_events=[e for e in steps if e['kind'] in (73,74,75)]
            checks['all_observed_have_team_evidence'] &= bool(proof_events)
            if not proof_events:continue
            a=proof_events[0]['sample'];frame=body['frame'];enums=a['stance_enum_entries'][:2*a['stance_enum_count']:2]
            checks['every_actual_frame_eligible'] &= (body['sdk_calls']==0 and a['frame']==frame and sample_identity(a,n) and a['stance']==0 and a['team']>0 and not a['team']%4 and a['team']!=n['script_team']
                and a['hp']>=TYPES[a['type_hash']]*.8 and not a['sm_flags']&0xffff and a['source'] in (0,1,2,3)
                and (a['state_id']==1 or a['state_id']==16 and a['path']==0 or a['state_id']==10 and a['state_vtable']==0xc548c0)
                and 1<=a['stance_enum_count']<=4 and len(set(enums))==len(enums) and {0,2}<=set(enums)<=set(range(4))
                and 0<=frame-n['observed_frame']<=30)
            if last_observed and frame!=last_observed+1:checks['raw_team_owner_chains_and_resets']=False
            last_observed=frame
            if baseline is None:baseline=a
            checks['immutable_actor_module_health'] &= all(a[k]==baseline[k] and body['sample'][k]==baseline[k] for k in fields)
            pending=None;skipped=False
            for e in steps:
                common=(e['frame']==frame and e['sample']==a and e['sdk_calls']==0 and e['stage']==0 and e['tag']==0 and e['thread']==n['thread'])
                checks['raw_team_owner_chains_and_resets'] &= common
                k=e['kind']
                if k in (73,74,75):
                    proof=team_proof_words(e)
                    positive=(proof['magic']==0x544d5034 and proof['sample_frame']==frame and e['self']==n['thing'] and e['source']==0
                        and proof['previous_cohort_team']==team and proof['previous_cohort_count']==count
                        and all(proof[x]>0 and not proof[x]%4 for x in ('actor_team_before','actor_team_after','definition_before','definition_after'))
                        and proof['actor_team_before']!=n['script_team'] and proof['actor_team_after']!=n['script_team']
                        and proof['owner_before']==proof['owner_after']==n['owner'])
                    stable=proof['actor_team_before']==proof['actor_team_after']==a['team'] and proof['definition_before']==proof['definition_after']
                    checks['raw_team_owner_chains_and_resets'] &= positive and e['result']==count
                    if k==75:checks['raw_team_owner_chains_and_resets']=False;continue
                    if k==74:
                        correct=(e['arg']==1 and stable and count>0 and team!=a['team'] or e['arg']==2 and not stable)
                        checks['raw_team_owner_chains_and_resets'] &= correct
                        resets.append(dict(frame=frame,reason=e['arg'],discarded=count,old_team=team))
                        count=team=0;run=[];pending=None;skipped=e['arg']==2
                    else:
                        checks['raw_team_owner_chains_and_resets'] &= stable and not skipped and pending is None and (not count or team==a['team'])
                        if not count:team=a['team']
                        pending=e
                elif k==60:
                    checks['raw_team_owner_chains_and_resets'] &= pending is not None and not skipped and e['arg']==count+1
                    count+=1;run.append(e);accepted.append(e);pending=None
                else:
                    checks['exact_three_and_gate'] = count==3 and len(run)==3 and gate is None and not skipped and pending is None and e['arg']==3 and e['sample']==run[-1]['sample']
                    gate=e
            if pending is not None:checks['raw_team_owner_chains_and_resets']=False
        frames=[e['frame'] for e in run]
        if gate and len(run)==3:
            checks['exact_three_and_gate'] &= frames==list(range(frames[0],frames[0]+3)) and [e['arg'] for e in run]==[1,2,3] and all(e['seq']<gate['seq'] for e in run) and gate['frame']==frames[-1]
            checks['original_raw_header_join']=(n['admission_samples']==3 and n['admission_verified']==1 and n['admission_first_frame']==frames[0] and n['admission_last_frame']==n['issued_frame']==frames[-1] and n['admission_max_gap']==1
                and n['admission_first_sample']==run[0]['sample'] and n['initial_sample']==run[-1]['sample'] and n['initial_sample']['team']==team)
            transfers=[e for e in es if e['kind']==10 and e['tag']==1]
            checks['actual_borrow_source_is_final_admitted_team']=len(transfers)==1 and transfers[0]['sample']['team']==team and transfers[0]['seq']>gate['seq']
            checks['all_sdk_after_third_frame']=bool(intents) and all(e['seq']>gate['seq'] for e in intents) and all(e['sdk_calls']==0 for e in es if e['seq']<=gate['seq'])
        return dict(verified=all(v is True for v in checks.values()),checks=checks,frames=frames,gate_seq=gate['seq'] if gate else None,admitted_team=hex(team) if team else None,
            all_observed_frames=[e['frame'] for e in samples],all_accepted_frames=[e['frame'] for e in accepted],cohort_resets=resets,immutable_baseline_frame=baseline['frame'] if baseline else None)
    except (KeyError,TypeError,ValueError,IndexError,StopIteration):return dict(verified=False,checks=dict(checks,well_formed_pre_admission=False),frames=[])


def production_provenance(r):
    """Independent original ledger and actual stopped producer bytes; no live access."""
    checks={}
    try:
        n=r['native'];birth=r['birth_source'];session_source=r['session_source']
        session_path=Path(session_source['path']).resolve();session=json.loads(session_path.read_text(encoding='utf-8-sig'));run=Path(session['run_directory']).resolve()
        checks['current_session_source']=sha(session_path)==session_source['sha256'] and session['session_id']==r['session_id']==n['session_id'] and session['pid']==n['pid'] and session['scenario']['commander_id']==n['commander_id']
        path=Path(birth['path']).resolve();source=json.loads(path.read_text(encoding='utf-8-sig'));checks['original_producer_file']=path.is_relative_to(run) and sha(path)==birth['sha256'] and source['session_id']==n['session_id'] and source['pid']==n['pid'] and source['production_source_sha256']==sha(HERE.parent.parent/'production/persistent/client.py')
        status=source['production_stopped'];identity=source['production_native_identity'];receipt=birth['receipt'];command=birth['command'];ro=birth['production_readonly']
        seal=hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        checks['unchanged_complete_original_receipt']=seal==birth['receipt_sha256'] and source['paid_orders_verified'] is True and source['serial_handover_verified'] is True and all(status.get(k)==v and type(status.get(k)) is type(v) for k,v in dict(native_phase=2,native_error=0,restore_mask=31,active_callbacks=0,player_id=3).items()) and status['session_id']==n['session_id'] and status['commander_id']==n['commander_id'] and all(identity[k]==v for k,v in dict(pid=n['pid'],session_id=n['session_id'],commander_id=n['commander_id'],owner=hex(n['owner']),thread=n['thread']).items())
        original=[x for x in status['ledger'] if x.get('command_id')==command['command_id']]
        commands=[x for x in source['commands'] if x['command'].get('command_id')==command['command_id']]
        checks['original_ledger_command_join']=len(original)==len(commands)==1 and original[0]==receipt and commands[0]['command']==command and commands[0]['receipt']['accepted'] is True and all(receipt[k]==command[k] for k in ('command_id','task_id','seq','unit')) and command['session_id']==n['session_id'] and command['commander_id']==n['commander_id'] and command['player_id']==3
        unit='conscript' if n['type_hash']==0x19ab11af else 'flak' if n['type_hash']==0x2c358c61 else None;cost=85 if unit=='conscript' else 220
        checks['paid_birth_actor_binding']=unit is not None and receipt['unit']==unit and receipt['object_id']==n['object_id'] and receipt['paid']==receipt['cost']==n['production_paid']==cost and all(receipt[k] is True for k in ('accepted','completed','paid_verified','created','completion_observed','queue_preserved')) and receipt['payment_error']==0 and integer(receipt['live_samples']) and receipt['live_samples']>0 and receipt['status']=='completed' and 0<receipt['queue_id']==n['production_queue_id'] and 0<receipt['completion_frame']==n['production_birth_frame']<=n['observed_frame'] and 0<receipt['seq']==n['production_seq']
        checks['immutable_native_provenance_words']=n['production_command']==list(struct.unpack('<4I',uuid.UUID(command['command_id']).bytes)) and n['production_task']==list(struct.unpack('<4I',uuid.UUID(command['task_id']).bytes)) and n['production_receipt_sha256']==list(struct.unpack('<8I',bytes.fromhex(seal))) and command['command_id']!=n['command_id'] and command['task_id']!=n['task_id']
        entries={0x7ba770:'81ec3c010000f605486bce0001535657',0x70f440:'83ec08558b6c241085ed568bf1',0x849220:'81ecb4000000568bf18b46148b4e04',0x73e390:'83ec208b4424248b54242c5355',0x789bf0:'51568bf180be3801000000'}
        good_entries=lambda rows:len(rows)==5 and len({number(x['address']) for x in rows})==5 and all(x['expected']==x['actual']==entries.get(number(x['address'])) for x in rows)
        checks['original_producer_and_sidecar_five_bytes']=good_entries(source['after_entries']) and good_entries(ro['entries'])
        prefix=bytes.fromhex(ro['header_hex']);raw=bytes.fromhex(ro['receipt_hex'])
        checks['original_stable_native_bytes']=len(prefix)==ro['header_size']==256 and len(raw)==ro['receipt_size']==224 and ro['header_hex']==ro['header_after_hex'] and ro['receipt_hex']==ro['receipt_after_hex'] and ro['mutations'] is False and ro['sdk_calls']==0 and ro['protocol']=='reserve_birth_stopped_production_readonly_v1' and ro['pid']==n['pid'] and ro['session_id']==n['session_id'] and ro['reader_sha256']==sha(HERE/'birth_source.py') and ro['producer_sha256']==sha(HERE.parent.parent/'production/persistent/client.py') and ro['native_binary_sha256']==sha(HERE.parent.parent/'production/persistent/bin-v2/ProductionPersistent.dll') and ro['native_host_sha256']==sha(HERE.parent.parent/'production/persistent/bin-v2/persistent_host.exe')
        h=list(struct.unpack('<64I',prefix));a=list(struct.unpack('<56I',raw));cmd=a[2:28];v=dict(zip('state error attempted frame queue_id node cost quoted_cost cash liability prior_count preserved paid debit_count payment_error created object object_id object_owner object_hash completed completion_frame live_samples object_hp_bits object_x_bits object_y_bits factory_x_bits factory_y_bits'.split(),a[28:]))
        checks['raw_native_process_owner_thread']=h[:4]==[0x50434d44,1,n['pid'],n['thread']] and h[4:11]==[n[k] for k in ('owner','ai','personality','personality_id','player_template','start_low','start_high')] and str(uuid.UUID(bytes=prefix[44:60]))==n['session_id'] and str(uuid.UUID(bytes=prefix[60:76]))==n['commander_id'] and h[23]==2 and h[25]==h[62]==0 and h[61]==31 and h[63]==n['thread'] and h[59]==status['spent_committed'] and h[19]==status['total_budget'] and 0<=ro['receipt_index']<h[60]<=1024
        checks['raw_native_exact_command']=cmd[0]==command['seq'] and str(uuid.UUID(bytes=raw[12:28]))==command['command_id'] and str(uuid.UUID(bytes=raw[28:44]))==command['task_id'] and str(uuid.UUID(bytes=raw[44:60]))==n['session_id'] and str(uuid.UUID(bytes=raw[60:76]))==n['commander_id'] and cmd[17]==n['type_hash'] and cmd[18:21]==[command['budget'],command['reserve'],command['expires_frame']]
        checks['raw_native_paid_created_complete']=a[0]==0 and v['state']==2 and v['error']==v['payment_error']==0 and v['attempted']==1 and v['preserved']==1 and v['debit_count']>0 and v['created']==1 and v['completed']==1 and v['object']>0 and v['object_owner']==n['owner'] and v['object_hash']==n['type_hash'] and all(v[k]==receipt[k] for k in ('queue_id','object_id','paid','cost','completion_frame','live_samples')) and v['paid']==v['cost']==cost
        return dict(verified=all(v is True for v in checks.values()),checks=checks,producer_report_sha256=birth['sha256'],receipt_sha256=seal,production_command_id=command['command_id'],production_task_id=command['task_id'],production_queue_id=receipt['queue_id'],birth_frame=receipt['completion_frame'],holding_is_mission_effect=False)
    except (KeyError,ValueError,TypeError,IndexError,OSError,struct.error):return dict(verified=False,checks=dict(checks,well_formed_original_production_provenance=False),holding_is_mission_effect=False)


def rally_audit(r):
    """Frozen observed candidate, explicit Stop8, then a committed actual anchor."""
    checks = {}
    try:
        n, es = r['native'], r['events']; a=n['rally']; anchor=n['anchor']
        only=lambda k:next(e for e in es if e['kind']==k) if sum(e['kind']==k for e in es)==1 else None
        proposal,candidate,stopped,committed,hold=map(only,(62,71,68,72,40))
        intents={e['arg']:e for e in es if e['kind']==50}
        required=(proposal,candidate,stopped,committed,hold,intents.get(7),intents.get(8))
        checks['unique_proposal_candidate_stop_commit_hold']=all(required)
        if not all(required):return dict(verified=False,checks=checks)
        origin,direction,goal=a['proposal_origin'],a['proposal_direction'],a['goal']
        f=[struct.unpack('<f',struct.pack('<I',a[k]))[0] for k in ('factory_x_bits','factory_y_bits')]+[0.]
        b=n['initial_sample']['xyz'];p=proposal['sample']['xyz'];initial_gap=distance(b,f)
        length=math.hypot(b[0]-f[0],b[1]-f[1])
        finite=point(b) and point(p) and point(goal) and point(origin) and len(direction)==2 and all(math.isfinite(v) for v in f+direction)
        checks['original_factory_and_stopped_geometry']=bool(finite and length>=5 and origin==p and a['proposal_frame']==proposal['frame'])
        expected=[-(b[1]-f[1])/length,(b[0]-f[0])/length] if finite and length>=5 else [math.inf,math.inf]
        checks['fixed_left_two_hundred_metre_proposal']=bool(checks['original_factory_and_stopped_geometry'] and all(abs(x-y)<=.00002 for x,y in zip(direction,expected))
            and all(abs(goal[i]-(p[i]+200*expected[i]))<=.002 for i in range(2)) and goal[2]==p[2])
        checks['initial_stop_then_one_move_then_candidate']=proposal['seq']<intents[7]['seq']<candidate['seq']<intents[8]['seq']<stopped['seq']<committed['seq']<hold['seq'] and a['rally_issue_frame']==intents[7]['frame']==proposal['frame'] and proposal['stage']==1 and candidate['stage']==6
        def navigable(s):
            return sample_identity(s,n) and s['stance']==2 and s['source']==1 and not s['sm_flags']&0xffff and s['team']==n['script_team'] and s['state_id']!=26
        samples=[e for e in es if e['kind']==3 and intents[7]['seq']<e['seq']<candidate['seq'] and e['frame']>intents[7]['frame']]
        run=[];gate=None;expected_markers=[]
        for e in samples:
            eligible=holding_sample(e['sample'],n) and distance(e['sample']['xyz'],p)>=60 and distance(e['sample']['xyz'],f)>=max(120,initial_gap)
            if not eligible:run=[];continue
            if run and (e['frame']!=run[-1]['frame']+1 or distance(e['sample']['xyz'],run[-1]['sample']['xyz'])>1):run=[]
            run.append(e);expected_markers.append((e,len(run)))
            if len(run)==3:gate=e;break
        markers=[e for e in es if e['kind']==70]
        checks['actual_candidate_three_no_counter_substitution']=bool(gate and len(markers)==len(expected_markers) and all(
            e['frame']==sample['frame'] and e['sample']==sample['sample'] and sample['seq']<e['seq']<candidate['seq'] and e['arg']==count and e['stage']==6
            for e,(sample,count) in zip(markers,expected_markers)))
        checks['first_candidate_frozen_within_original_ninety']=bool(gate and gate['frame']==candidate['frame']==anchor['candidate_frame']==anchor['last_candidate_frame']
            and anchor['candidate_samples']==3 and gate['frame']-intents[7]['frame']<=90 and candidate['frame']==intents[8]['frame']
            and anchor['candidate_xyz']==candidate['sample']['xyz']==gate['sample']['xyz'] and anchor['last_candidate_xyz']==anchor['candidate_xyz'] and candidate['arg']==3)
        checks['navigation_all_actual_positive_and_no_state26']=bool(samples) and all(navigable(e['sample']) for e in samples) and all(b['frame']>a['frame'] for a,b in zip(samples,samples[1:]))
        private=next((e for e in es if e['kind']==33 and e['tag']==8 and e['source']==1),None)
        stops=[e for e in es if e['kind']==3 and private and private['seq']<e['seq']<stopped['seq']]
        audit=stop_three(stops,intents[8]['sample']['xyz'],n,intents[8]['frame'],anchor['candidate_xyz'])
        checks['stop8_three_then_actual_commit_opens_hold']=bool(audit['verified'] and audit['gate']['frame']==stopped['frame']==committed['frame']==hold['frame']==anchor['commit_frame']==n['hold_started']
            and a['rally_stop_frame']==intents[8]['frame'] and a['rally_stop_verified']==1 and stopped['stage']==7 and committed['stage']==7 and hold['stage']==2
            and stopped['arg']==committed['arg']==3
            and committed['sample']['xyz']==anchor['actual_anchor']==hold['sample']['xyz']==n['hold_anchor'] and distance(anchor['actual_anchor'],anchor['candidate_xyz'])<=15
            and distance(anchor['actual_anchor'],p)>=60 and distance(anchor['actual_anchor'],f)>=max(120,initial_gap))
        checks['truthful_initial_and_boundary_facts']=bool(abs(anchor['initial_factory_gap']-initial_gap)<=.001 and anchor['initial_outside_inner_zone']==int(initial_gap>=120)
            and anchor['boundary_crossed']==int(initial_gap<120 and distance(anchor['actual_anchor'],f)>=120))
        near_count=0;near_last=0;reached_frame=0
        for e in samples:
            close=distance(e['sample']['xyz'],goal)<=15
            near_count=(near_count+1 if near_count and e['frame']==near_last+1 else 1) if close else 0
            near_last=e['frame']
            if near_count>=3 and not reached_frame:reached_frame=e['frame']
        diagnostic=[e for e in es if e['kind']==63]
        checks['proposal_diagnostic_never_substitutes_actual_anchor']=bool(anchor['proposal_reached']==int(bool(reached_frame)) and a['rally_reached_frame']==reached_frame
            and a['arrival_samples']==near_count and a['last_arrival_frame']==near_last and len(diagnostic)==int(bool(reached_frame))
            and all(e['frame']==reached_frame and e['stage']==6 and e['arg']==3 for e in diagnostic)
            and abs(anchor['proposal_distance']-distance(anchor['actual_anchor'],goal))<=.002)
        return dict(verified=all(v is True for v in checks.values()),checks=checks,proposal_frame=proposal['frame'],candidate_frames=[e['frame'] for e in run[-3:]],rally_stop=audit,
            candidate_anchor=anchor['candidate_xyz'],actual_anchor=anchor['actual_anchor'],proposal_is_ground_observation=False,
            proposal_reached=bool(anchor['proposal_reached']),physical_rally_progress=distance(p,anchor['actual_anchor']),initial_outside_inner_zone=bool(anchor['initial_outside_inner_zone']),boundary_crossed=bool(anchor['boundary_crossed']))
    except (KeyError,TypeError,ValueError,IndexError,StopIteration,ZeroDivisionError,struct.error):
        return dict(verified=False,checks=dict(checks,well_formed_rally=False))


def rally_source_audit(r):
    """Independent owned-factory raw bytes and the immutable original receipt."""
    checks = {}
    try:
        n, source, birth = r['native'], r['rally_source'], r['birth_source']; a=n['rally']
        checks['source_identity_and_seals'] = (source['protocol']=='rsv5_current_owned_factory_v1' and source['session_id']==n['session_id'] and source['pid']==n['pid']
            and source['source_report']==birth['path'] and source['source_report_sha256']==birth['sha256'] and source['source_receipt_sha256']==birth['receipt_sha256']
            and source['reader_sha256']==sha(HERE/'rally_source.py') and source['mutations'] is False and source['sdk_calls']==0
            and source['proposal_terrain_verified'] is False and source['route_verified'] is False)
        before, after=source['sample_before'],source['sample_after']
        checks['actual_double_sample_unchanged'] = before==after
        word=lambda key:struct.unpack('<I',bytes.fromhex(before[key]))[0]
        xyz=list(struct.unpack('<3f',bytes.fromhex(before['xyz_hex'])));hp=struct.unpack('<f',bytes.fromhex(before['hp_hex']))[0]
        factory, factory_id=struct.unpack_from('<II',bytes.fromhex(birth['production_readonly']['receipt_hex']),100)
        checks['raw_original_factory_and_own_live_identity'] = (word('thing_vtable_hex')==0xc4db60 and word('object_id_hex')==factory_id==source['factory_id']==a['factory_id']
            and factory==number(source['factory_address'])==a['factory_address'] and word('owner_hex')==number(source['factory_owner'])==a['factory_owner']==n['owner']
            and word('template_pointer_hex')==number(source['factory_template'])==a['factory_template'] and word('template_pointer_hex')>0
            and word('type_hash_hex')==number(source['factory_hash'])==a['factory_type_hash']==0x80d4ea1e and word('owner_index_hex')==3
            and word('body_pointer_hex')>0 and math.isfinite(hp) and hp==source['factory_hp'] and hp>0)
        checks['real_factory_position_and_input_words'] = point(xyz) and xyz==source['factory_xyz'] and word('frame_hex')==source['source_frame']==a['factory_source_frame']
        checks['real_factory_position_and_input_words'] &= [a['factory_x_bits'],a['factory_y_bits']]==[source['factory_x_bits'],source['factory_y_bits']]==list(struct.unpack('<2I',bytes.fromhex(before['xyz_hex'])[:8]))
        member=source['owned_membership']; row=member['member']; ids=member['all_owned_ids']
        checks['current_owned_membership_same_frame'] = (number(source['logic'])==n['logic'] and member['frame_start']==member['frame_end']==source['source_frame']
            and n['observed_frame']<=source['source_frame']<=n['issued_frame'] and len(ids)==len(set(ids)) and ids.count(factory_id)==1
            and row['object_id']==factory_id and number(row['address'])==factory and number(row['owner_address'])==n['owner']
            and row['owner_index_candidate']==3 and number(row['type_hash'])==0x80d4ea1e)
        observed=[e for e in r['events'] if e['kind']==69];proposals=[e for e in r['events'] if e['kind']==62]
        checks['actual_native_factory_before_proposal'] = False
        if len(observed)==len(proposals)==1:
            e,proposal=observed[0],proposals[0];m=e['move']
            words=[m['goal_pointer'],*m['goal_bits'],m['path'],m['limit_bits'],m['intent_seq'],m['facade_seq'],m['generation'],m['flags']]
            hp_now=struct.unpack('<f',struct.pack('<I',words[8]))[0]
            checks['actual_native_factory_before_proposal']=(e['seq']<proposal['seq'] and e['frame']==proposal['frame']==words[5]
                and words[:5]==[factory,factory_id,n['owner'],a['factory_template'],0x80d4ea1e]
                and words[6:8]==[a['factory_x_bits'],a['factory_y_bits']] and math.isfinite(hp_now) and hp_now>0 and words[9]==0xc4db60)
        return dict(verified=all(v is True for v in checks.values()),checks=checks,factory_address=hex(factory),factory_id=factory_id,source_frame=source['source_frame'],proposal_terrain_verified=False,route_verified=False)
    except (KeyError,TypeError,ValueError,IndexError,OSError,struct.error):
        return dict(verified=False,checks=dict(checks,well_formed_factory_source=False))


def move_audit(r):
    """Only one real synchronous facade/private interval earns Move provenance."""
    checks = {}
    try:
        n, es = r['native'], r['events']; a=n['rally']
        intents=[e for e in es if e['kind']==50 and e['arg']==7]
        borrowed=next((e['seq'] for e in es if e['kind']==50 and e['arg']==1),0)
        passive=[e for e in es if e['kind'] in (64,65,66,67) and e['seq']<borrowed]
        rows=[e for e in es if e['kind'] in (64,65,66,67) and e['seq']>=borrowed]
        checks['one_intent_and_four_original_steps'] = len(intents)==1 and [e['kind'] for e in rows]==[64,66,67,65]
        checks['pre_borrow_observations_never_move_credit'] = all(e['tag']==0 and e['sdk_calls']==0 and all(e[k]==0 for k in ('explicit_stops','private_explicit_stops','automatic_stop2','private_automatic_stop2')) for e in passive)
        if not checks['one_intent_and_four_original_steps']:return dict(verified=False,checks=checks)
        intent=intents[0];before,private,post,after=rows
        bits=list(struct.unpack('<3I',struct.pack('<3f',*a['goal'])))
        checks['same_actual_actor_frame_thread_and_scope'] = (intent['seq']<before['seq']<private['seq']<post['seq']<after['seq']
            and all(e['frame']==intent['frame']==a['rally_issue_frame'] and e['thread']==n['thread'] and e['tag']==7 and e['source']==1
                    and sample_identity(e['sample'],n) and e['sample']['team']==n['script_team'] and e['sample']['stance']==2 for e in rows)
            and before['self']==after['self']==n['update']+0x24 and private['self']==post['self']==n['update']
            and before['caller']==after['caller'] and before['caller']>0 and private['caller']==post['caller']==0x6d3b7d)
        checks['immutable_original_goal_generation_and_publication'] = all(e['move']['goal_bits']==bits and e['move']['intent_seq']==intent['seq']==a['move_intent_seq']
            and e['move']['facade_seq']==before['seq'] and e['move']['generation']==a['move_generation']==1
            and integer(e['move']['goal_pointer']) and e['move']['goal_pointer']>0 and not e['move']['goal_pointer']%4 for e in rows)
        checks['real_private_arguments_no_path_and_fltmax'] = (all(e['arg']==0 and e['move']['path']==0 and e['move']['limit_bits']==0x7f7fffff for e in (private,post))
            and private['move']['goal_pointer']==post['move']['goal_pointer'] and all(e['arg']==0 and e['move']['path']==e['move']['limit_bits']==0 for e in (before,after))
            and before['move']['goal_pointer']==after['move']['goal_pointer'])
        checks['observed_owned_scope_once_then_returned'] = [e['move']['flags'] for e in rows]==[3,3,7,7] and a['move_intents']==a['move_facade_entries']==a['move_private_entries']==1 and a['foreign_move_entries']==a['move_scope_open']==0
        return dict(verified=all(v is True for v in checks.values()),checks=checks,intent_seq=intent['seq'],facade_seq=before['seq'],private_seq=private['seq'],deferred_move_credit=False)
    except (KeyError,TypeError,ValueError,IndexError,struct.error):
        return dict(verified=False,checks=dict(checks,well_formed_original_move=False),deferred_move_credit=False)


def fresh_birth_admission_audit(r):
    """Every observed candidate, including discarded cohorts, keeps original limits."""
    try:
        n=r['native'];a=n['rally'];audit=pre_admission_audit(r)
        frames=audit['frames'];rows=[e for e in r['events'] if e['kind']==60 and e['frame'] in frames]
        borrow=next((e['seq'] for e in r['events'] if e['kind']==50 and e['arg']==1),0)
        observed={}
        for e in r['events']:
            if e['kind'] in (73,74,75) and (not borrow or e['seq']<borrow):observed.setdefault(e['frame'],e)
        observations=list(observed.values())
        factory=[struct.unpack('<f',struct.pack('<I',a[k]))[0] for k in ('factory_x_bits','factory_y_bits')]
        ages=[e['frame']-n['production_birth_frame'] for e in observations]
        gaps=[distance(e['sample']['xyz'],factory+[0.]) for e in observations]
        initial_gap=distance(n['initial_sample']['xyz'],factory+[0.])
        checks=dict(exact_pre_sdk_frames=len(rows)==3 and audit['verified'] and all(e['sdk_calls']==0 for e in observations),
            each_observed_completion_age_bounded=bool(ages) and all(0<=age<=300 for age in ages),
            each_actual_factory_gap_bounded=bool(gaps) and all(math.isfinite(gap) and gap<=200 for gap in gaps),
            initial_sample_and_issued_frame_join=bool(rows) and n['initial_sample']==rows[-1]['sample'] and n['issued_frame']==rows[-1]['frame'])
        if 'anchor' in n:
            a=n['anchor'];checks['original_native_age_and_initial_gap_outputs']=bool(rows) and a['admission_age_first']==rows[0]['frame']-n['production_birth_frame'] and a['admission_age_last']==rows[-1]['frame']-n['production_birth_frame'] and abs(a['initial_factory_gap']-initial_gap)<=.001
        return dict(verified=all(v is True for v in checks.values()),checks=checks,completion_observation_ages=ages,
                    actual_pre_sdk_factory_gaps=gaps,initial_factory_gap=initial_gap,initial_outside_inner_zone=initial_gap>=120,
                    exact_engine_constructor_birth_frame_verified=False)
    except (KeyError,TypeError,ValueError,IndexError,struct.error):
        return dict(verified=False,checks={'well_formed_fresh_birth_admission':False})


def preflight_team_audit(r):
    """The Python descriptor team is fresh raw evidence, separate from admitted team."""
    try:
        n=r['native'];actor=r['preflight']['selected'];b=actor['team_binding']
        team=number(b['team']);definition=number(b['definition']);raw=b['raw_before']
        expected={n['logic']+0x50:b['frame'],n['thing']+0xdc:n['object_id'],n['thing']+0x418:n['owner'],n['thing']+0x374:n['update'],n['thing']+0x414:team,team+4:definition,definition+8:n['owner']}
        keys={hex(a) for a in (*expected,team,definition)}
        checks=dict(same_actual_raw_sample=raw==b['raw_after'] and set(raw)==keys,
            raw_addresses_and_values=all(struct.unpack('<I',bytes.fromhex(raw[hex(address)]))[0]==value for address,value in expected.items()),
            original_input_team_source=team==number(actor['team'])==n['original_team'] and b['protocol']=='rsv5_same_frame_owned_team_v1' and b['mutations'] is False,
            current_owned_non_script=team>0 and definition>0 and not team%4 and not definition%4 and team!=n['script_team'] and number(b['owner'])==n['owner'],
            same_admission_frame=b['frame']==actor['admission']['frame']==n['observed_frame'])
        return dict(verified=all(v is True for v in checks.values()),checks=checks,descriptor_team=hex(team),descriptor_frame=b['frame'])
    except (KeyError,TypeError,ValueError,IndexError,struct.error):return dict(verified=False,checks={'well_formed_preflight_team':False})


def _qualify(r):
    n, es, rq, pre = r['native'], r['events'], r['request'], r['preflight']
    checks = {'compiled_source_revision': source_pins(r)}
    checks['identity_and_original_thread'] = (n['magic'] == 0x52535635 and n['version'] == 5
        and n['pid'] == pre['pid'] and n['thread'] == n['callback_thread'] == pre['window_thread']
        and all(n[k] == rq[k] for k in ('command_id','task_id','seq','token'))
        and n['session_id'] == pre['session_id'] == r['session_id'] and n['commander_id'] == pre['commander_id']
        and n['start_low'] == pre['start_low'] and n['start_high'] == pre['start_high'])
    selected = pre['selected']; stance = selected['stance']; admission = selected['admission']
    input_team=preflight_team_audit(r)
    checks['fresh_python_team_descriptor_binding']=input_team['verified']
    checks['original_readonly_actor_and_stance_join'] = (
        n['thing']==number(selected['address']) and n['object_id']==selected['object_id']
        and n['update']==number(selected['ai_address']) and n['type_hash']==number(selected['type_hash'])
        and all(n[k]==number(pre[k]) for k in ('owner','logic','ai','personality','personality_id','player_template','script_team','default_team'))
        and n['original_team']==number(selected['team']) and n['stance_module']==number(stance['module'])
        and number(stance['backref'])==n['thing'] and number(stance['vtable'])==0xc37f90
        and number(stance['getter'])==0x71d3f0 and stance['enum']==n['original_stance']==0
        and admission['object_id']==n['object_id'] and admission['frame']==n['observed_frame'])
    provenance = production_provenance(r)
    checks['original_paid_birth_provenance'] = provenance['verified']
    admission_audit = pre_admission_audit(r)
    checks['three_original_pre_sdk_admission_frames'] = admission_audit['verified']
    fresh = fresh_birth_admission_audit(r)
    checks['fresh_paid_factory_actor_before_all_sdk'] = fresh['verified']
    checks['published_bound_raw_samples'] = (bool(es) and len(es) <= 1024 and n['overflow'] == 0
        and n['count'] == len(es) and all(e['seq'] == i+1 and e['thread'] == n['thread']
            and e['kind'] in (0,1,3,4,10,11,12,13,14,15,20,21,30,31,32,33,40,41,42,43,44,45,46,47,50,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75)
            and e['frame'] == e['sample']['frame'] and sample_identity(e['sample'],n) for i,e in enumerate(es))
        and all(b['frame'] >= a['frame'] and 0 <= ((b['tick']-a['tick']) & 0xffffffff) < 0x80000000 for a,b in zip(es,es[1:])))
    s = n['initial_sample']; enums = s['stance_enum_entries']
    checks['fresh_original_admission'] = (sample_identity(s,n) and s['stance'] == n['original_stance'] == 0
        and s['hp'] >= TYPES[s['type_hash']] * .8
        and n['test_stance'] == 2 and s['team'] == n['admission_first_sample']['team'] != n['script_team'] and admission_audit['verified']
        and 1 <= s['stance_enum_count'] <= 4 and len(enums) == 8
        and {0,2} <= set(enums[0:2*s['stance_enum_count']:2]) and not s['sm_flags'] & 0xffff
        and len(set(enums[0:2*s['stance_enum_count']:2]))==s['stance_enum_count']
        and set(enums[0:2*s['stance_enum_count']:2])<=set(range(4))
        and number(stance['data'])==s['stance_data'] and number(stance['definition_list'])==s['stance_enum_list']
        and stance['definition_count']==s['stance_enum_count']
        and [v for d in stance['definitions'] for v in (d['enum'],number(d['modifier']))]==enums[:s['stance_enum_count']*2]
        and (s['state_id'] == 1 or s['state_id'] == 16 and s['path'] == 0 or s['state_id'] == 10 and s['state_vtable'] == 0xc548c0)
        and n['issued_frame'] == s['frame'] and 0 <= s['frame'] - n['observed_frame'] <= 30)
    checks['fixed_total_deadline'] = (rq['expires_frame'] == n['expires_frame'] and 210 <= n['expires_frame'] - n['issued_frame'] <= 300
        and n['issued_frame'] <= n['returned_frame'] <= n['expires_frame'] and es[-1]['tick']-es[0]['tick'] <= 30000)
    unique_samples = [e for e in es if e['kind'] == 3]
    checks['real_unique_frame_progress'] = all(b['frame'] > a['frame'] for a,b in zip(unique_samples,unique_samples[1:]))
    checks['observed_active_state26_never_waived'] = all(e['sample']['state_id']!=26 for e in unique_samples if e['sdk_calls'] and e['stage'] in (1,6,7,2))
    sdk = sdk_audit(es,n); checks['eight_original_sdk_chains'] = sdk['verified']
    one = lambda kind: next(e for e in es if e['kind'] == kind) if sum(e['kind'] == kind for e in es)==1 else None
    initial, hold_end, clean, timeout, before_restore, after_restore, before_pool, after_pool = map(one,(40,41,42,43,44,45,46,47))
    first_gate, rally_gate, candidate_gate, commit_gate = map(one,(62,68,71,72))
    stops = {tag: next((e for e in es if e['kind'] == 33 and e['tag'] == tag and e['source']==1),None) for tag in (3,4,8)}
    intents = {e['arg']:e for e in es if e['kind']==50}
    initial_audit = stop_three([e for e in unique_samples if stops[3] and stops[3]['seq'] < e['seq'] and e['frame']>stops[3]['frame'] and (not first_gate or e['seq'] < first_gate['seq'])], intents.get(3,{}).get('sample',{}).get('xyz',[]), n, intents.get(3,{}).get('frame',0))
    initial_ok = bool(first_gate and initial_audit['verified'] and initial_audit['gate']['frame'] == first_gate['frame'] and n['initial_stop_verified'] == 1)
    checks['actual_initial_stop_three'] = initial_ok
    window = hold_window(es, initial['frame'], initial['sample']['xyz'], n) if initial else {'verified':False,'continuous_all_logic_frames_verified':False}
    rally = rally_audit(r)
    checks['actual_rally_geometry_arrival_and_stop'] = rally['verified']
    factory = rally_source_audit(r)
    checks['original_owned_factory_source'] = factory['verified']
    move = move_audit(r)
    checks['one_synchronous_original_move_chain'] = move['verified']
    checks['fixed_ninety_real_frames'] = bool(initial_ok and rally['verified'] and window['verified'] and hold_end
        and hold_end['frame'] == initial['frame']+90 == n['hold_finished'] and n['hold_verified']==1
        and n['hold_first_frame']==initial['frame'] and n['hold_last_frame']==hold_end['frame']
        and n['hold_samples']==91 and n['hold_max_gap']==1 and n['hold_missing_frames']==0)
    cleanup_audit = stop_three([e for e in unique_samples if stops[4] and stops[4]['seq'] < e['seq'] and e['frame']>stops[4]['frame'] and (not clean or e['seq'] < clean['seq'])], intents.get(4,{}).get('sample',{}).get('xyz',[]), n, intents.get(4,{}).get('frame',0))
    cleanup_ok = bool(clean and not timeout and cleanup_audit['verified'] and cleanup_audit['gate']['frame']==clean['frame'] and n['cleanup_stop_verified']==1)
    checks['actual_cleanup_stop_three'] = cleanup_ok
    restore_pres = [e for e in es if e['kind']==20 and e['tag']==5]
    restore_posts = [e for e in es if e['kind']==21 and e['tag']==5]
    changed_restore = bool(n['stance_changed']==1 and before_restore and after_restore
        and len(restore_pres)==len(restore_posts)==1
        and before_restore['seq']<restore_pres[0]['seq']<restore_posts[0]['seq']<after_restore['seq']
        and restore_pres[0]['arg']==restore_posts[0]['arg']==n['original_stance']
        and restore_posts[0]['result']==1 and restore_posts[0]['sample']['stance']==n['original_stance'])
    unchanged_restore = bool(n['stance_changed']==0 and not restore_pres and not restore_posts
        and before_restore and before_restore['sample']['stance']==n['original_stance'])
    restore_ok = bool(before_restore and after_restore and before_pool and after_pool
        and before_restore['seq'] < after_restore['seq'] < before_pool['seq'] < after_pool['seq']
        and all(e['sample']['stance']==n['original_stance'] for e in (after_restore,before_pool,after_pool))
        and all(sample_identity(e['sample'],n) for e in (before_restore,after_restore,before_pool,after_pool))
        and n['restore_before_enum']==before_restore['sample']['stance']
        and n['restore_after_enum']==n['pool_before_enum']==n['pool_after_enum']==n['original_stance']==0
        and n['stance_restored']==1 and (changed_restore or unchanged_restore))
    returns = [e for e in es if e['kind']==11 and e['tag']==6]
    def live_actor(s):
        return (all(s.get(k)==n.get(v) for k,v in {'thing':'thing','id':'object_id','type_hash':'type_hash','owner':'owner','template_ptr':'template_ptr','update':'update'}.items())
                and s.get('update_vtable')==0xc48670 and s.get('update_backref')==n['thing']
                and type(s.get('hp')) in (float,int) and math.isfinite(s['hp']) and s['hp']>0)
    returned = bool(before_pool and after_pool and len(returns)==1
        and before_pool['seq'] < returns[0]['seq'] < after_pool['seq']
        and all(live_actor(e['sample']) for e in (before_pool,returns[0],after_pool))
        and returns[0]['sample']['team']==n['default_team'] and n['return_verified']==1
        and after_pool['sample']['team']==n['default_team'] and n['disposed']==n['scene_changed']==0)
    checks['original_stance_before_live_pool_return'] = bool(returned and restore_ok)
    ordered = [intents.get(i) for i in (1,2,3)] + [first_gate,intents.get(7),candidate_gate,intents.get(8),rally_gate,commit_gate,initial,hold_end,intents.get(4),clean,before_restore,intents.get(5),after_restore,before_pool,intents.get(6),after_pool,one(4)]
    checks['original_gate_order_no_extra_command_during_hold'] = bool(all(ordered)
        and all(a['seq']<b['seq'] for a,b in zip(ordered,ordered[1:]))
        and es[0]['kind']==0 and es[-1]['kind']==4 and clean['frame']-intents[4]['frame']<=60)
    pristine = terminal_audit(r); checks['actual_eight_original_bytes_and_timer_zero'] = pristine
    checks['successful_native_terminal'] = (r['status']=='finished' and r['host_exit']==0 and n['phase']==3 and n['error']==0 and n['stage']==5)
    no_lease = bool(pristine and checks['compiled_source_revision'] and n['detach_calls']==n['return_calls']==n['sdk_calls']==0 and all(e['sdk_calls']==0 for e in es) and not any(e['kind']==50 or e['kind']==10 and e['arg']==0 for e in es))
    passed = all(v is True for v in checks.values())
    return dict(status='reserve_hold_primitive_verified' if passed else 'not_passed', checks=checks,
                hold_verified=bool(checks['fixed_ninety_real_frames']), physical_cleanup_stop_verified=cleanup_ok,
                original_stance_restored=restore_ok, live_pool_return_verified=returned, restoration_verified=pristine,
                control_release_verified=bool(returned and pristine or no_lease), no_actor_lease_verified=no_lease, coverage=window, sdk_audit=sdk,
                initial_stop=initial_audit, cleanup_stop=cleanup_audit, pre_admission=admission_audit, fresh_birth_admission=fresh, preflight_team=input_team, production_provenance=provenance, rally=rally, rally_source=factory, move_audit=move, reserve_lease_id=n['task_id'], reserve_actor_id=n['object_id'], reserve_active_after_return=False, reserve_to_mission_handoff_verified=False, **no_grant())


def qualify(report):
    try:
        return _qualify(report)
    except (KeyError, ValueError, TypeError, IndexError, OverflowError, StopIteration):
        return dict(status='not_passed', checks={'well_formed_raw_evidence':False}, hold_verified=False,
                    physical_cleanup_stop_verified=False, original_stance_restored=False,
                    live_pool_return_verified=False, restoration_verified=False, control_release_verified=False, **no_grant())


def qualify_path(path):
    path = Path(path)
    result = qualify(json.loads(path.read_text(encoding='utf-8-sig')))
    result.update(source_report=str(path.resolve()), source_sha256=sha(path), qualifier_sha256=sha(__file__))
    return result

