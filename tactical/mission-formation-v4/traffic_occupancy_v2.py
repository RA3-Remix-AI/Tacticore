"""Read-only classification of owned mobile foot traffic, never passability.

Only exact Conscript/Flak actors with full current admission2 evidence become
soft traffic. Static, unknown, garrisoned, locked or otherwise unproved objects
remain hard obstacles. The leased pair's clearance is always a separate gate.
"""
import hashlib,importlib.util,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mfm4_traffic_admission2',HERE.parent/'mission_actor_admission_v2.py')
admission=importlib.util.module_from_spec(spec);spec.loader.exec_module(admission)
ALLOWED={'0x19ab11af','0x2c358c61'}
def point(value):return isinstance(value,(list,tuple)) and len(value)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in value)
def verified_mobile(row,owner=None):
    if row.get('traffic_class')!='verified_mobile_foot' or row.get('type_hash') not in ALLOWED:return False
    evidence=row.get('traffic_admission',{})
    if not isinstance(evidence,dict):return False
    ground=evidence.get('grounded_status',{})
    if not isinstance(ground,dict):return False
    try:owner_matches=owner is None or int(evidence.get('owner','0'),0)==(int(owner,0) if isinstance(owner,str) else owner)
    except (TypeError,ValueError):return False
    return bool(admission.verify_evidence(evidence)['verified'] and point(row.get('xyz')) and evidence.get('object_id')==row.get('object_id') and evidence.get('address')==row.get('address') and evidence.get('type_hash')==row.get('type_hash') and ground.get('xyz')==row['xyz'] and owner_matches)

def partition(owned,actor_ids,owner=None):
    hard=[];mobile=[]
    for row in owned:
        if row['object_id'] in actor_ids:continue
        (mobile if verified_mobile(row,owner) else hard).append(row)
    return hard,mobile

def verify_census(census,owner):
    """Pure requalification; class labels never substitute admission evidence."""
    try:
        start,end=census['frame_start'],census['frame_end'];rows=census['owned_positions']
        if census.get('protocol')!='verified_mobile_foot_traffic_v2' or census.get('owner')!=owner or census.get('reader_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or census.get('mutations') is not False or census.get('walkable_route_verified') is not False:return False
        if type(start) is not int or type(end) is not int or not 0<start<=end<=start+4 or not isinstance(rows,list) or not 1<=len(rows)<=256:return False
        ids=[]
        for row in rows:
            oid=row['object_id'];ids.append(oid)
            if type(oid) is not int or oid<=0 or not point(row['xyz']) or not isinstance(row['address'],str) or int(row['address'],0)<=0 or not isinstance(row['type_hash'],str) or not 0<int(row['type_hash'],0)<=0xffffffff:return False
            if row.get('traffic_class') not in ('hard_or_unknown','verified_mobile_foot'):return False
            if row['traffic_class']=='verified_mobile_foot' and (not verified_mobile(row,owner) or not start<=row['traffic_admission']['frame']<=end):return False
        return len(set(ids))==len(ids)
    except (ValueError,TypeError,KeyError):return False

def classify_owned(memory,owned,owner,logic):
    start=memory.u32(logic+0x50);rows=[];ids=set()
    if len(owned)>256:raise ValueError('traffic_own_census_capacity')
    for candidate in owned:
        row={k:candidate[k] for k in ('object_id','address','type_hash','xyz')}
        if type(row['object_id']) is not int or row['object_id']<=0 or row['object_id'] in ids or not point(row['xyz']):raise ValueError('traffic_own_census_identity')
        ids.add(row['object_id']);row.update(traffic_class='hard_or_unknown',traffic_reason='outside_verified_mobile_scope')
        if row['type_hash'] in ALLOWED:
            try:
                evidence=admission.actor_admission(memory,int(row['address'],0));ground=evidence.get('grounded_status',{})
                row.update(traffic_admission=evidence)
                if admission.verify_evidence(evidence)['verified'] and evidence.get('object_id')==row['object_id'] and evidence.get('address')==row['address'] and evidence.get('type_hash')==row['type_hash'] and int(evidence.get('owner','0'),0)==int(owner,0) and int(evidence.get('state_snapshot',{}).get('update','0'),0)==int(candidate['ai_address'],0):
                    row.update(xyz=ground['xyz'],traffic_class='verified_mobile_foot',traffic_reason='current_exact_ground_and_admission2')
            except (ValueError,RuntimeError,KeyError,TypeError):row['traffic_reason']='admission_unavailable_keep_hard'
        rows.append(row)
    end=memory.u32(logic+0x50)
    if not 0<start<=end<=start+4:raise ValueError('traffic_own_census_clock_skew')
    if any(not start<=r['traffic_admission']['frame']<=end for r in rows if r['traffic_class']=='verified_mobile_foot'):raise ValueError('traffic_admission_outside_census')
    return dict(protocol='verified_mobile_foot_traffic_v2',frame_start=start,frame_end=end,owner=owner,owned_positions=rows,reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mutations=False,walkable_route_verified=False)

def near(a,b):return math.dist(a[:2],b[:2])<20 and abs(a[2]-b[2])<10
def hard_occupied(position,owned,actor_ids):
    return any(r['object_id'] not in actor_ids and near(r['xyz'],position) and not verified_mobile(r) for r in owned)
def traffic_cost(position,owned,actor_ids):
    return sum(r['object_id'] not in actor_ids and near(r['xyz'],position) and verified_mobile(r) for r in owned)
