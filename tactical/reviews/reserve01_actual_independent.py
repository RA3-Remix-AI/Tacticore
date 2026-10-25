"""Offline review only; preserves frozen RSV1 report and qualifier."""
import hashlib, importlib.util, json, struct, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'acceptance/runs/20261026-024703-commander'
RAW = RUN/'paid-reserve01-reserve.json'
Q = ROOT/'tactical/reserve-v1/reserve_qualification.py'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('reserve01_frozen_q', Q)
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
r = json.loads(RAW.read_text(encoding='utf-8-sig'))
n = r['native']; ro = r['birth_source']['production_readonly']
source = Path(r['birth_source']['path'])
producer = json.loads(source.read_text(encoding='utf-8-sig'))
status = producer['production_stopped']
raw_header = bytes.fromhex(ro['header_hex']); h = list(struct.unpack('<64I', raw_header))
parts = {
    'magic': h[0] == 0x50434d44,
    'actual_version_is_frozen_producer_version_one': h[1] == 1,
    'frozen_q_erroneously_requires_version_two': h[1] == 2,
    'pid_thread': h[2:4] == [n['pid'], n['thread']],
    'owner_ai_personality_template_start': h[4:11] == [n[k] for k in ('owner','ai','personality','personality_id','player_template','start_low','start_high')],
    'session': str(uuid.UUID(bytes=raw_header[44:60])) == n['session_id'],
    'commander': str(uuid.UUID(bytes=raw_header[60:76])) == n['commander_id'],
    'phase_two': h[23] == 2,
    'no_active_no_error': h[25] == h[62] == 0,
    'restored_five_mask': h[61] == 31,
    'callback_thread': h[63] == n['thread'],
    'spent': h[59] == status['spent_committed'] == 85,
    'budget': h[19] == status['total_budget'] == 85,
    'receipt_index': 0 <= ro['receipt_index'] < h[60] <= 1024,
}
es = r['events']; start = next(e for e in es if e['kind'] == 40)
cleanup = next(e for e in es if e['kind'] == 50 and e['arg'] == 4)
hold = [e for e in es if e['kind'] == 3 and start['frame'] <= e['frame'] and e['seq'] < cleanup['seq']]
bad = next(e for e in hold if not q.holding_sample(e['sample'], n))
frames = [e['frame'] for e in hold]
missing = sorted(set(range(frames[0], frames[-1]+1))-set(frames))

def pe_read(data, va, size):
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    count, optsize = struct.unpack_from('<H', data, pe+6)[0], struct.unpack_from('<H', data, pe+20)[0]
    opt = pe+24; base = struct.unpack_from('<I', data, opt+28)[0]; rva = va-base
    for i in range(count):
        off = opt+optsize+40*i
        vs, address, rawsize, rawoff = struct.unpack_from('<4I', data, off+8)
        if address <= rva < address+max(vs,rawsize):
            return data[rawoff+rva-address:rawoff+rva-address+size]
    raise ValueError('PE address not mapped')

exe = Path('E:/RedRar3/Data/RA3_1.12.game'); data = exe.read_bytes()
getter = struct.unpack('<I', pe_read(data, 0xc553d0+8, 4))[0]
code = pe_read(data, getter, 6)
literal = struct.unpack_from('<I', code, 1)[0]
name = pe_read(data, literal, 80).split(b'\0')[0].decode('ascii')
result = {
    'protocol': 'reserve01_offline_independent_review_v1',
    'raw_path': str(RAW), 'raw_sha256': sha(RAW), 'qualifier_sha256': sha(Q),
    'producer_report_sha256': sha(source),
    'frozen_qualifier_result': q.qualify(r),
    'producer_header_subchecks': parts,
    'independent_producer_header_actual_version_one_verified': all(v for k,v in parts.items() if k != 'frozen_q_erroneously_requires_version_two'),
    'q_bug_location': 'reserve_qualification.py:292 expects production version 2, while frozen client.py:start writes version 1; no frozen file changed',
    'producer_source_sha256': sha(ROOT/'production/persistent/client.py'),
    'producer_shared_sha256': sha(ROOT/'production/persistent/shared.h'),
    'hold_before_cleanup': {
        'first_frame': frames[0], 'last_frame': frames[-1], 'count': len(frames),
        'max_gap': max(b-a for a,b in zip(frames,frames[1:])), 'missing_frame_ids': missing,
        'max_anchor_drift': max(q.distance(e['sample']['xyz'],start['sample']['xyz']) for e in hold),
        'first_invalid_sample': bad, 'cleanup_intent_seq': cleanup['seq'],
        'strict_ninety_frame_hold_verified': False,
        'all_observed_prefix_frames_present': not missing,
        'required_window_complete': False,
    },
    'static_state_name': {'executable_sha256': sha(exe), 'vtable': '0xc553d0', 'getter': hex(getter), 'getter_bytes': code.hex(), 'literal': hex(literal), 'name': name},
    'inference_limit': 'State entry alone proves neither displacement nor triggering actor or command. Later cleanup samples do not complete the interrupted hold window.',
    'tactical_source_granted': False, 'effect_verified': False, 'reserve_to_mission_handoff_verified': False,
    'raw_or_qualifier_mutations': False, 'sdk_calls_by_review': 0,
}
out = ROOT/'strategy/reviews/reserve01-actual-independent.json'
out.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
print(json.dumps({'review':str(out),'sha256':sha(out),'failed_checks':[k for k,v in result['frozen_qualifier_result']['checks'].items() if not v], 'producer_subchecks':parts,'hold':{k:v for k,v in result['hold_before_cleanup'].items() if k!='first_invalid_sample'}, 'bad_frame':bad['frame'],'bad_state':bad['sample']['state_id'],'static_state_name':result['static_state_name']}))
