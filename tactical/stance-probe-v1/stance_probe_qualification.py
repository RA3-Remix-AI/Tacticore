"""Independent STP1 raw verifier. No game access or tactical capability grant."""
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


def stop_three(rows, origin, n, issue_frame):
    """Only actual subsequent distinct samples contribute to the physical gate."""
    prior, run, frames, first = origin, 0, [], None
    for event in rows:
        s = event['sample']
        if event['kind'] != 3 or s['frame'] <= issue_frame:
            continue
        if frames and s['frame'] <= frames[-1]:
            return {'verified': False, 'frames': frames, 'gate': None}
        frames.append(s['frame'])
        stable = holding_sample(s, n) and distance(s['xyz'], prior) <= 1
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
        maximum = max(maximum, drift)
        prior = s['xyz']
    coverage = len(frames) == 90 and not missing and all(g == 1 for g in gaps)
    return {'verified': bool(coverage and all_physical), 'first_frame': frames[0] if frames else None,
            'last_frame': frames[-1] if frames else None, 'count': len(frames),
            'max_frame_gap': max(gaps, default=0), 'missing_frame_ids': missing,
            'continuous_all_logic_frames_verified': bool(coverage), 'physical_samples_verified': bool(all_physical),
            'max_anchor_drift': maximum, 'fixed_start': start, 'fixed_end': start + 90}


def no_grant():
    return {'tactical_source_granted': False, 'effect_verified': False, 'completion_claim': False}


def source_paths():
    return [HERE / x for x in ('stance_probe_qualification.py', 'native_layout.py', 'lease.py', 'preflight.py', 'inert-layout.json')] + sorted(HERE.glob('*.cpp.inc'))


def external_source_paths():
    bridge = HERE.parent.parent
    return [bridge / x for x in (
        'tactical/ordered-combo/lease.py', 'tactical/mission_actor_admission_v2.py',
        'tactical/grounded_status_v2.py', 'tactical/grounded_status.py', 'tactical/mobility_guard.py',
        'visibility/capability.py', 'visibility/collector.py', 'visibility/projection.py')]


def source_pins(r):
    try:
        files = {'native_binary_sha256': HERE / 'bin/TacticalStanceProbe1.dll',
                 'native_host_sha256': HERE / 'bin/tactical_host.exe',
                 'native_source_sha256': HERE / 'lease.cpp', 'native_shared_sha256': HERE / 'shared.h',
                 'wrapper_sha256': HERE / 'lease.py'}
        revision = json.loads((HERE / 'revision.json').read_text())
        compiled = {k: sha(p) for k, p in files.items() if k != 'wrapper_sha256'}
        compiled['native_includes_sha256'] = {p.name: sha(p) for p in sorted(HERE.glob('*.cpp.inc'))}
        inert = json.loads((HERE / 'inert-layout.json').read_text())
        abi = dict(sample=240,event=312,tactical=320124,events=636,period_ms=20,fallback_ms=100,loss_ms=1000)
        return (set(compiled['native_includes_sha256']) == {'logic.cpp.inc', 'scheduler.cpp.inc', 'host_pulse.cpp.inc'}
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
                and revision['hook_count']==6 and revision['restore_mask']==63
                and r.get('executable_sha256') == EXE)
    except (OSError, ValueError, TypeError):
        return False


HOOKS = {0x838820: '8b818c00000085c0744f568bb190000000',
         0x8d8880: '83ec24568b74242c8b4604', 0x8cd630: '83ec3453578b7c24408b4704',
         0x54b0a0: '83ec5c8b442460566a01508bf1', 0x721ad0: '83ec08558be98b45088b4804',
         0x7640f0: '83ec14538bd98b4308'}


def terminal_audit(r):
    try:
        n, t = r['native'], r['terminal_readonly']
        keys = ('pid', 'seq', 'token', 'session_id', 'commander_id', 'command_id', 'task_id')
        binding = all(t[k] == n[k] for k in keys) and t['native_binary_sha256'] == r['native_binary_sha256']
        entries = t['entries']
        actual = {number(e['address']): e for e in entries}
        pristine = len(entries) == 6 and set(actual) == set(HOOKS) and all(
            e['actual'].lower() == e['expected'].lower() == HOOKS[a]
            for a, e in actual.items())
        raw = bytes.fromhex(t['header_before_hex'])
        stable = len(raw)==636 and t['header_before_hex']==t['header_after_hex']
        value = lambda offset: struct.unpack_from('<I',raw,offset)[0]
        header = (stable and value(0)==0x53545031 and value(4)==1 and value(8)==n['pid']
                  and value(88)==n['token'] and value(92)==n['seq']
                  and all(str(uuid.UUID(bytes=raw[24+16*i:40+16*i]))==n[key+'_id']
                          for i,key in enumerate(('session','commander','command','task'))))
        for key,offset in {'owner':100,'thing':120,'object_id':124,'phase':176,'active':184,'error':192,
                           'restore_mask':196,'returned_frame':212,'return_verified':228,'stance_restored':264}.items():
            header &= value(offset)==n[key]
        return bool(binding and pristine and t['timer'] == t['active'] == n['active'] == 0
                    and t['restore_mask'] == n['restore_mask'] == 63 and t.get('mutations') is False
                    and t['phase'] == n['phase'] in (3, 4) and t['error'] == n['error'] and header
                    and t['timer_after']==0 and t['shared_pointer']==t['shared_pointer_after']>0
                    and t['binding_verified'] is True)
    except (KeyError, ValueError, TypeError, struct.error):
        return False


def sdk_audit(events, n):
    """Original pre/post inputs, nested source2 callbacks and conserved counters."""
    checks = {}
    intents = [e for e in events if e['kind'] == 50]
    checks['six_original_intents_once'] = [e['arg'] for e in intents] == [1, 2, 3, 4, 5, 6]
    scopes, calls = [], 0
    counters = dict(explicit_stops=0, private_explicit_stops=0, automatic_stop2=0, private_automatic_stop2=0)
    valid, current = True, None
    for e in events:
        k, tag, src = e['kind'], e['tag'], e['source']
        if k == 50:
            current = e['arg']; calls += 1
            valid &= current in (1,2,3,4,5,6) and tag == current
            if current in (3,4): counters['explicit_stops'] += 1
        if k == 30 and src == 2 and tag in (2,5): counters['automatic_stop2'] += 1
        if k == 33 and src == 2 and tag in (2,5): counters['private_automatic_stop2'] += 1
        if k == 33 and src == 1 and tag in (3,4) and e['caller'] == 0x787791:
            counters['private_explicit_stops'] += 1
        valid &= e['sdk_calls'] == calls and all(e[key] == value for key, value in counters.items())
        if k in (10,20,30,32,12,14):
            scopes.append(e)
            expected_self = n['owner'] if k == 10 else n['stance_module'] if k == 20 else n['update'] + 0x24 if k == 30 else n['update'] if k == 32 else None
            valid &= expected_self is None or e['self'] == expected_self
            if k == 10: valid &= tag in (1,6) and tag == current and e['arg'] == (tag == 6)
            if k == 20: valid &= tag in (2,5) and tag == current and e['arg'] == (2 if tag == 2 else n['original_stance'])
            if k in (30,32):
                valid &= (tag in (2,5) and tag == current and src == 2 or tag in (3,4) and tag == current and src == 1)
                if k == 32: valid &= e['caller'] == 0x787791
            if k in (12,14): valid &= tag in (1,6) and tag == current
        elif k in (11,21,31,33,13,15):
            if not scopes: valid = False; continue
            before = scopes.pop()
            valid &= k == before['kind'] + 1 and tag == before['tag'] and src == before['source'] and e['self'] == before['self'] and e['arg'] == before['arg']
            if k == 11: valid &= e['sample']['team'] == (n['script_team'] if tag == 1 else n['default_team'])
            if k == 21: valid &= e['result'] == 1 and e['sample']['stance'] == e['arg']
    checks['typed_nested_original_calls'] = bool(valid and not scopes)
    checks['exact_explicit_call_totals'] = (calls == n['sdk_calls'] == 6 and n['detach_calls'] == n['return_calls'] == 1
        and n['stance_calls'] == 2 and n['explicit_stops'] == n['private_explicit_stops'] == 2
        and all(n[key] == value for key, value in counters.items())
        and counters['automatic_stop2'] == counters['private_automatic_stop2'])
    checks['one_explicit_stop_chain_per_intent'] = all(
        [e['kind'] for e in events if e['tag'] == tag and e['kind'] in (30,31,32,33)] == [30,32,33,31] for tag in (3,4))
    checks['one_setter_and_transfer_each'] = all(
        sum(e['kind'] == kind and e['tag'] == tag for e in events) == 1
        for kind, tags in ((10,(1,6)),(11,(1,6)),(20,(2,5)),(21,(2,5))) for tag in tags)
    return dict(verified=all(checks.values()), checks=checks)


def _qualify(r):
    n, es, rq, pre = r['native'], r['events'], r['request'], r['preflight']
    checks = {'compiled_source_revision': source_pins(r)}
    checks['identity_and_original_thread'] = (n['magic'] == 0x53545031 and n['version'] == 1
        and n['pid'] == pre['pid'] and n['thread'] == n['callback_thread'] == pre['window_thread']
        and all(n[k] == rq[k] for k in ('command_id','task_id','seq','token'))
        and n['session_id'] == pre['session_id'] == r['session_id'] and n['commander_id'] == pre['commander_id']
        and n['start_low'] == pre['start_low'] and n['start_high'] == pre['start_high'])
    selected = pre['selected']; stance = selected['stance']; admission = selected['admission']
    checks['original_readonly_actor_and_stance_join'] = (
        n['thing']==number(selected['address']) and n['object_id']==selected['object_id']
        and n['update']==number(selected['ai_address']) and n['type_hash']==number(selected['type_hash'])
        and all(n[k]==number(pre[k]) for k in ('owner','logic','ai','personality','personality_id','player_template','script_team','default_team'))
        and n['original_team']==number(selected['team']) and n['stance_module']==number(stance['module'])
        and number(stance['backref'])==n['thing'] and number(stance['vtable'])==0xc37f90
        and number(stance['getter'])==0x71d3f0 and stance['enum']==n['original_stance']==0
        and admission['object_id']==n['object_id'] and admission['frame']==n['observed_frame'])
    visibility = pre['current_visibility']; margin = visibility['minimum_observed_enemy_distance']
    checks['frozen_readonly_current_threat_gate'] = (visibility['frame']==n['threat_frame']
        and visibility['hard_limit']==350 and visibility['preferred_margin']==450
        and visibility['unknown_enemies_remain_unknown'] is True
        and type(visibility['visible_enemy_count']) is int and 0<=visibility['visible_enemy_count']<64
        and (visibility['visible_enemy_count']==0 and margin is None
             or visibility['visible_enemy_count']>0 and type(margin) in (int,float) and math.isfinite(margin) and margin>=350))
    checks['published_bound_raw_samples'] = (bool(es) and len(es) <= 1024 and n['overflow'] == 0
        and n['count'] == len(es) and all(e['seq'] == i+1 and e['thread'] == n['thread']
            and e['kind'] in (0,1,3,4,10,11,12,13,14,15,20,21,30,31,32,33,40,41,42,43,44,45,46,47,50)
            and e['frame'] == e['sample']['frame'] and sample_identity(e['sample'],n) for i,e in enumerate(es))
        and all(b['frame'] >= a['frame'] and 0 <= ((b['tick']-a['tick']) & 0xffffffff) < 0x80000000 for a,b in zip(es,es[1:])))
    s = n['initial_sample']; enums = s['stance_enum_entries']
    checks['fresh_original_admission'] = (sample_identity(s,n) and s['stance'] == n['original_stance'] == 0
        and s['hp'] >= TYPES[s['type_hash']] * .8
        and n['test_stance'] == 2 and s['team'] == n['original_team'] != n['script_team']
        and 1 <= s['stance_enum_count'] <= 4 and len(enums) == 8
        and {0,2} <= set(enums[0:2*s['stance_enum_count']:2]) and not s['sm_flags'] & 0xffff
        and len(set(enums[0:2*s['stance_enum_count']:2]))==s['stance_enum_count']
        and set(enums[0:2*s['stance_enum_count']:2])<=set(range(4))
        and number(stance['data'])==s['stance_data'] and number(stance['definition_list'])==s['stance_enum_list']
        and stance['definition_count']==s['stance_enum_count']
        and [v for d in stance['definitions'] for v in (d['enum'],number(d['modifier']))]==enums[:s['stance_enum_count']*2]
        and (s['state_id'] == 1 or s['state_id'] == 16 and s['path'] == 0 or s['state_id'] == 10 and s['state_vtable'] == 0xc548c0)
        and n['issued_frame'] == s['frame'] and 0 <= s['frame'] - n['observed_frame'] <= 60
        and 0 <= s['frame'] - n['threat_frame'] <= 60 and n['threat_clear'] == 1)
    checks['fixed_total_deadline'] = (rq['expires_frame'] == n['expires_frame'] and 210 <= n['expires_frame'] - n['issued_frame'] <= 300
        and n['issued_frame'] <= n['returned_frame'] <= n['expires_frame'] and es[-1]['tick']-es[0]['tick'] <= 30000)
    unique_samples = [e for e in es if e['kind'] == 3]
    checks['real_unique_frame_progress'] = all(b['frame'] > a['frame'] for a,b in zip(unique_samples,unique_samples[1:]))
    sdk = sdk_audit(es,n); checks['six_original_sdk_chains'] = sdk['verified']
    one = lambda kind: next(e for e in es if e['kind'] == kind) if sum(e['kind'] == kind for e in es)==1 else None
    initial, hold_end, clean, timeout, before_restore, after_restore, before_pool, after_pool = map(one,(40,41,42,43,44,45,46,47))
    stops = {tag: next((e for e in es if e['kind'] == 33 and e['tag'] == tag and e['source']==1),None) for tag in (3,4)}
    intents = {e['arg']:e for e in es if e['kind']==50}
    initial_audit = stop_three([e for e in unique_samples if stops[3] and stops[3]['seq'] < e['seq'] and e['frame']>stops[3]['frame'] and (not initial or e['seq'] < initial['seq'])], intents.get(3,{}).get('sample',{}).get('xyz',[]), n, intents.get(3,{}).get('frame',0))
    initial_ok = bool(initial and initial_audit['verified'] and initial_audit['gate']['frame'] == initial['frame']
        and n['initial_stop_verified'] == 1 and n['hold_started'] == initial['frame'] and n['hold_anchor'] == initial['sample']['xyz'])
    checks['actual_initial_stop_three'] = initial_ok
    window = hold_window(es, initial['frame'], initial['sample']['xyz'], n) if initial else {'verified':False,'continuous_all_logic_frames_verified':False}
    checks['fixed_ninety_real_frames'] = bool(initial_ok and window['verified'] and hold_end
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
    ordered = [intents.get(i) for i in (1,2,3)] + [initial,hold_end,intents.get(4),clean,before_restore,intents.get(5),after_restore,before_pool,intents.get(6),after_pool,one(4)]
    checks['original_gate_order_no_extra_command_during_hold'] = bool(all(ordered)
        and all(a['seq']<b['seq'] for a,b in zip(ordered,ordered[1:]))
        and es[0]['kind']==0 and es[-1]['kind']==4 and clean['frame']-intents[4]['frame']<=60)
    pristine = terminal_audit(r); checks['actual_six_original_bytes_and_timer_zero'] = pristine
    checks['successful_native_terminal'] = (r['status']=='finished' and r['host_exit']==0 and n['phase']==3 and n['error']==0 and n['stage']==5)
    passed = all(v is True for v in checks.values())
    return dict(status='stance_hold_primitive_verified' if passed else 'not_passed', checks=checks,
                hold_verified=bool(checks['fixed_ninety_real_frames']), physical_cleanup_stop_verified=cleanup_ok,
                original_stance_restored=restore_ok, live_pool_return_verified=returned, restoration_verified=pristine,
                control_release_verified=bool(returned and pristine), coverage=window, sdk_audit=sdk,
                initial_stop=initial_audit, cleanup_stop=cleanup_audit, **no_grant())


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

