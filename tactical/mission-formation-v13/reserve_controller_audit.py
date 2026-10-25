"""MF13 original paid-slot/controller evidence. Import performs no game access.

The outer lease, each producer command and the later mission commit keep their
own identities. Diagnostic snapshots never confer current actor/Move credit.
"""
import ctypes as c
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import uuid

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('mf13_controller_actual_layout', HERE/'native_layout.py')
L = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(L)
TYPES = (0x19ab11af, 0x2c358c61)
COSTS = (85, 220)
RS_KINDS = set(range(141, 159)) | {163}
IMMUTABLE = ('thing','id','type_hash','owner','template_ptr','update','update_vtable',
             'update_backref','stance_module','stance_vtable','stance_backref','stance_data',
             'stance_enum_list','stance_enum_count','stance_enum_entries','hp')
DYNAMIC_RECEIPT = {'updates','version','live_samples','object_hp_bits','object_x_bits',
                   'object_y_bits','factory_x_bits','factory_y_bits'}


def word(x): return type(x) is int and 0 <= x <= 0xffffffff
def f32(x): return struct.unpack('<f',struct.pack('<I',x))[0]
def rounded_float(x): return struct.unpack('<f',struct.pack('<f',x))[0]
def floats(ws): return [f32(x) for x in ws]
def point(x): return isinstance(x,(list,tuple)) and len(x)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in x)
def distance(a,b): return math.dist(a[:2],b[:2]) if point(a) and point(b) else math.inf
def near(a,b,t=.02): return point(a) and point(b) and all(abs(x-y)<=t for x,y in zip(a,b))
def ident(ws): return str(uuid.UUID(bytes=struct.pack('<4I',*ws)))
def nonzero(ws): return isinstance(ws,list) and len(ws)==4 and all(word(x) for x in ws) and any(ws)


def plain(obj):
    if isinstance(obj,c.Array): return [plain(x) for x in obj]
    if isinstance(obj,c.Structure): return {name:plain(getattr(obj,name)) for name,*_ in obj._fields_}
    return obj


def decode(cls, words):
    raw=struct.pack('<%dI'%len(words),*words)
    if len(raw)!=c.sizeof(cls): raise ValueError('typed_size')
    return plain(cls.from_buffer_copy(raw))


def stack(e):
    w=e['stack_words']
    if not isinstance(w,list) or len(w)!=128 or e.get('stack_word_count')!=128 or not all(word(x) for x in w):
        raise ValueError('original_stack128')
    return w


def reserve_record(e):
    w=stack(e);r=e['role'];k=e['kind']
    if k not in RS_KINDS or w[:4]!=[0x52533133,1,r,k] or r not in (0,1) or w[4]!=e['frame'] or w[6]!=e['arg'] or w[126:]!=[0,0]:
        raise ValueError('RS13_binding')
    s=decode(L.ReserveSample13,w[8:68])
    if s['frame']!=w[4]: raise ValueError('fixed_sample_frame')
    return dict(event=e,words=w,sample=s,team=w[68:78],factory=w[78:88],previous_xyz=floats(w[88:91]),
                previous_frame=w[91],baseline_hp=f32(w[92]),start=w[93],reserve_deadline=w[94],deadline=w[95],
                observed_path=w[96],receipt_frame=w[97],completion_frame=w[98],borrow_frame=w[99],ready_frame=w[100],
                first_role=w[101],brake_count=w[102],stop_frame=w[103],reference_role=w[104],reference_frame=w[105],
                policy=w[106],reference_thing=w[107],radial=floats(w[108:111]),first_anchor=floats(w[111:114]),
                proposal=floats(w[114:117]),brake=floats(w[117:120]),anchor=floats(w[120:123]),
                held_mask=w[123],ready_mask=w[124],reset_count=w[125])


def surface(s, actor, owner):
    try:
        bits=s['status_words'];excluded=(0,7,8,51,61,161,207,211)
        count=s['stance_enum_count'];entries=s['stance_enum_entries'];enums=entries[:2*count:2]
        return (all(s[k]==actor[k] for k in ('thing','id','type_hash','template_ptr','update','stance_module','stance_data','stance_enum_list','stance_enum_count','stance_enum_entries'))
                and s['owner']==owner and s['thing']!=0 and s['type_hash'] in TYPES
                and s['update_vtable']==0xc48670 and s['update_backref']==s['thing']
                and s['stance_vtable']==0xc37f90 and s['stance_backref']==s['thing'] and s['stance_data']!=0
                and s['stance_enum_list']!=0 and 1<=count<=4 and len(entries)==8 and len(set(enums))==count and {0,2}<=set(enums)<=set(range(4)) and entries[2*count:]==[0]*(8-2*count)
                and s['sm']!=0 and s['state']!=0 and s['sm_owner']==s['thing'] and s['state_owner_sm']==s['sm']
                and len(bits)==7 and all(word(x) for x in bits) and not any(bits[i//32]&(1<<(i%32)) for i in excluded)
                and s['holder']==0 and s['height_flags']&4!=0 and math.isfinite(s['height']) and abs(s['height'])<=.5
                and math.isfinite(s['hp']) and s['hp']>0 and point(s['xyz']))
    except (KeyError,TypeError,IndexError): return False


def holding(s, actor, owner, script):
    return bool(surface(s,actor,owner) and s['team']==script and s['stance']==2 and s['state_id']==94
                and s['state_vtable']==0xc551a0 and s['path']==0 and s['source']==1 and not s['sm_flags']&0xffff)


def input_audit(r):
    n=r['native'];i=n['controller_input'];pre=r['preflight'];slots=i['slots']
    binding={'producer_pid':'pid','producer_thread':'thread','producer_owner':'owner','producer_ai':'ai',
             'producer_start_low':'start_low','producer_start_high':'start_high','producer_personality':'personality',
             'producer_personality_id':'personality_id','producer_player_template':'player_template'}
    checks={
        'actual_namespace':(n['magic'],n['version'])==(0x4d463133,13),
        'immutable_outer_uuid':nonzero(i['controller']) and nonzero(i['lease']) and ident(i['controller'])==n['command_id'] and ident(i['lease'])==n['task_id'],
        'exact_policy':all(i[k]==v for k,v in {'schema':1,'reserve_duration_frames':300,'lease_duration_frames':4500,'reserve_floor':1000,'total_paid_max':305,'slot_count':2,'allocation_scope':1,'force_numerator':1,'force_denominator':1}.items()),
        'process_and_producer_binding':all(i[k]==n[v] for k,v in binding.items()) and ident(i['producer_session'])==n['session_id']==r['session_id'] and ident(i['producer_commander'])==n['commander_id'] and n['thread']==pre['window_thread'],
        'formation_binding':nonzero(i['formation']) and i['formation_version']>0,
        'bounded_startup':0<i['startup_wall_ms']<=60000 and pre['frame']<i['startup_deadline_frame']<=pre['frame']+900,
        'exact_two_paid_slots':len(slots)==2,
    }
    for role,s in enumerate(slots):
        checks['exact_two_paid_slots'] &= (s['role']==role and s['unit_hash']==TYPES[role] and s['expected_cost']==COSTS[role]
            and nonzero(s['command']) and nonzero(s['task']) and s['seq']>0 and all(s[k]>0 and s[k]%4==0 for k in ('factory','factory_template','iface'))
            and s['factory_id']>0 and s['factory_hash']==0x80d4ea1e)
    checks['distinct_bound_commands']=slots[0]['command']!=slots[1]['command'] and slots[0]['task']!=slots[1]['task'] and slots[0]['seq']!=slots[1]['seq']
    return dict(verified=all(v is True for v in checks.values()),checks=checks)


def producer_audit(r,roles=(0,1)):
    n=r['native'];i=n['controller_input'];rows=[e for e in r['events'] if e['kind']==140];checks=dict(original_rpc1_pairs=bool(rows),exact_binding=True,paid_original_receipts=True,immutable_payment_projection=True,header_output_join=True)
    prior={};last_generation=0;observations=[]
    if len(rows)%2: checks['original_rpc1_pairs']=False
    for a,b in zip(rows[::2],rows[1::2]):
        x,y=stack(a),stack(b);role=a['role'];valid=role in (0,1) and a['arg']==1 and b['arg']==2 and a['seq']<b['seq'] and a['frame']==b['frame'] and b['role']==role
        valid &= x[:7]==y[:7]==[0x52504331,1,role,a['frame'],x[4],a['frame'],a['frame']] and x[7]==y[7]==last_generation+1 and x[72:]==y[72:]
        checks['original_rpc1_pairs'] &= bool(valid);last_generation=x[7]
        if role not in (0,1): continue
        h=decode(L.ProductionHeader13,x[8:72]);h2=decode(L.ProductionHeader13,y[8:72]);p=decode(L.ProductionReceipt13,x[72:]);s=i['slots'][role];cmd=p['command']
        for header,e in ((h,a),(h2,b)):
            valid=(header['magic']==0x50434d44 and header['version']==1 and header['phase']==1 and header['error']==header['stop_requested']==0
                and 0<=header['active']<=100000 and 0<header['count']<=1024 and x[4]<header['count'] and 50<=header['reserve_floor']<=10000 and header['spent']<=header['total_budget'] and 305<=header['total_budget']<=20000
                and ((e['tick']-header['heartbeat'])&0xffffffff)<=2000 and header['callback_thread']==i['producer_thread']
                and all(header[k]==i['producer_'+k] for k in ('pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high','session','commander')))
            checks['exact_binding'] &= bool(valid)
        checks['original_rpc1_pairs'] &= h['count']==h2['count']
        wanted={'seq':s['seq'],'id':s['command'],'task':s['task'],'session':i['producer_session'],'commander':i['producer_commander'],'hash':s['unit_hash'],'factory':s['factory'],'factory_id':s['factory_id'],'iface':s['iface']}
        payment=(all(cmd[k]==v for k,v in wanted.items()) and cmd['reserve']>=max(1000,h['reserve_floor'],h2['reserve_floor']) and COSTS[role]<=cmd['budget']<=1000 and cmd['reserve']<=100000 and 0<=cmd['queue_limit']<=2 and p['prior_count']<=cmd['queue_limit'] and p['liability']<=20000 and (p['prior_count']>0 or p['liability']==0) and p['paid']+p['liability']+cmd['reserve']<=p['cash']
            and p['updates']==0 and p['version']>0 and p['state']==2 and p['error']==p['payment_error']==0 and p['debit_count']==1
            and all(p[k]==1 for k in ('attempted','preserved','created','completed')) and all(p[k]>0 for k in ('queue_id','node','object','object_id','completion_frame','live_samples'))
            and p['object_owner']==n['owner'] and p['object_hash']==TYPES[role] and p['paid']==p['cost']==p['quoted_cost']==COSTS[role]
            and 0<p['frame']<=p['completion_frame']<=a['frame'] and cmd['expires']>=p['frame'])
        checks['paid_original_receipts'] &= bool(payment)
        projection={k:v for k,v in p.items() if k not in DYNAMIC_RECEIPT}
        if role in prior: checks['immutable_payment_projection'] &= projection==prior[role][0] and p['version']>=prior[role][1]['version'] and p['live_samples']>=prior[role][1]['live_samples']
        prior[role]=(projection,p)
        observations.append(dict(role=role,frame=a['frame'],generation=x[7],receipt_index=x[4],receipt=p,seq=a['seq']))
    for role in roles:
        slot=n['slots'][role];rr=[o for o in observations if o['role']==role]
        checks['header_output_join'] &= bool(rr) and slot['receipt']==rr[-1]['receipt'] and slot['receipt_version']==rr[-1]['receipt']['version'] and slot['receipt_index']==rr[-1]['receipt_index'] and slot['receipt_observed_frame']==slot['completion_observed_frame']==rr[0]['frame']
    checks['header_output_join'] &= last_generation==n['controller']['producer_snapshots']
    return dict(verified=all(v is True for v in checks.values()),checks=checks,observations=observations,scope='historical_paid_provenance_not_current_actor_admission')


def producer_arm_audit(r):
    """Recompute producer identity and active E9 destinations from original RPM."""
    n=r['native'];i=n['controller_input'];a=r['producer_readonly_at_arm'];loaded=a['loaded'];checks={}
    binding=('pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high')
    headers=[]
    for key,tickkey in (('header_before_hex','tick_before'),('header_after_hex','tick_after')):
        raw=bytes.fromhex(a[key])
        if len(raw)!=256:raise ValueError('producer_arm_header_size')
        h=plain(L.ProductionHeader13.from_buffer_copy(raw));headers.append(h)
        checks[key]=(h['magic']==0x50434d44 and h['version']==1 and h['phase']==1 and h['error']==h['stop_requested']==0 and h['callback_thread']==i['producer_thread']
            and 0<=h['count']<=1024 and 0<=h['active']<=100000 and 50<=h['reserve_floor']<=10000 and 0<=h['spent']<=h['total_budget'] and 305<=h['total_budget']<=20000
            and ((a[tickkey]-h['heartbeat'])&0xffffffff)<=2000 and all(h[k]==i['producer_'+k] for k in binding+('session','commander')))
    checks['original_reader_and_readonly_scope']=(a['protocol']=='mf13_running_producer_readonly_at_arm_v1' and a['pid']==n['pid'] and a['mutations'] is False and a['sdk_calls']==0 and a['game_memory_writes'] is False and a['reader_sha256']==hashlib.sha256((HERE/'producer_binding.py').read_bytes()).hexdigest() and a['running_helper_sha256']==hashlib.sha256((HERE.parent/'running_birth_source_v1.py').read_bytes()).hexdigest())
    checks['raw_header_continuity']=headers[0]['count']<=headers[1]['count'] and headers[0]['spent']<=headers[1]['spent'] and ((a['tick_after']-a['tick_before'])&0xffffffff)<0x80000000
    expected={k:i['producer_'+k] for k in binding}
    first=i['slots'][0]
    expected.update(command_id=ident(first['command']),task_id=ident(first['task']),seq=first['seq'],unit='conscript',cost=85,factory=first['factory'],factory_id=first['factory_id'],iface=first['iface'],object=0,object_id=0)
    checks['exact_arm_command_and_process']=a['expected']==expected
    runtime=a['runtime'];wanted=dict(owner_vtable=0xc5bce0,player_index=3,player_template=i['producer_player_template'],ai=i['producer_ai'],ai_vtable=0xc60f60,ai_owner=i['producer_owner'],ai_owner_second=i['producer_owner'],personality=i['producer_personality'],personality_id=i['producer_personality_id'])
    checks['actual_player_runtime']=all(runtime[k]==v for k,v in wanted.items()) and runtime['logic']==n['logic'] and type(runtime['frame']) is int and runtime['frame']>0
    path=HERE.parent.parent/'production/persistent/bin-v2/ProductionPersistent.dll';binary=path.read_bytes();nt=struct.unpack_from('<I',binary,0x3c)[0]
    checks['actual_loaded_pe32_identity']=(Path(loaded['module_path']).resolve()==path.resolve() and loaded['module_sha256']==hashlib.sha256(binary).hexdigest() and binary[:2]==b'MZ' and 0x40<=nt<=0x1000 and nt==loaded['pe_offset'] and binary[nt:nt+4]==b'PE\0\0' and binary[nt+24:nt+26]==b'\x0b\x01' and struct.unpack_from('<I',binary,nt+24+56)[0]==loaded['image_size'])
    num=lambda x:int(x,0) if isinstance(x,str) else x
    base=num(loaded['module_base']);size=loaded['image_size'];checks['actual_loaded_pe32_identity'] &= 0x10000<=base and base%0x1000==0 and 0x1000<=size<=0x10000000 and base+size<=2**32
    source=(HERE.parent.parent/'production/persistent/executor.cpp').read_text();block=source.split('static Hook hooks[]={',1)[1].split(';',1)[0]
    originals={int(addr,0):(bytes.fromhex(raw.replace('\\x','')),int(length)) for addr,raw,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block)}
    entries=loaded['entries'];seen=set();checks['all_five_actual_installed_entries']=len(entries)==len(originals)==5
    for row in entries:
        address=num(row['address']);raw=bytes.fromhex(row['actual']);original,length=originals[address]
        target=(address+5+struct.unpack('<i',raw[1:5])[0])&0xffffffff
        checks['all_five_actual_installed_entries'] &= address not in seen and row['expected']==original.hex() and row['length']==len(raw)==length and raw[0]==0xe9 and raw[5:]==original[5:] and target==num(row['jump_target']) and base<=target<base+size
        seen.add(address)
    return dict(verified=all(v is True for v in checks.values()),checks=checks,actor_admission_credit=False,source='original_producer_rpm_before_controller_arm')


def cohort_audit(r, records, roles=(0,1)):
    n=r['native'];checks=dict(actual_positive_samples=True,immutable_first_baseline=True,actual_team_chain_and_cohort=True,exact_final_three=True,borrow_after_accept=True)
    result=[]
    for role in roles:
        slot=n['slots'][role];actor=slot['admission_last'];baseline=None;team=count=0;run=[];last=0;accepted=[];reset_count=0;reset_proof=None
        rr=[z for z in records if z['event']['role']==role and z['event']['kind'] in (141,142,143,144)]
        for z in rr:
            e=z['event'];s=z['sample'];k=e['kind'];t=z['team'];frame=s['frame']
            positive=(surface(s,actor,n['owner']) and s['hp']>=(.8*(100 if role==0 else 120)) and s['stance']==0 and not s['sm_flags']&0xffff
                and (s['state_id']==1 or s['state_id']==16 and not s['path'] or s['state_id']==10 and s['state_vtable']==0xc548c0))
            if k==141 and e['arg']==0:
                checks['actual_positive_samples'] &= baseline is None
                continue
            checks['actual_positive_samples'] &= bool(positive and 0<=frame-slot['completion_observed_frame']<=300 and 0<=frame-slot['receipt']['completion_frame']<=300)
            f=z['factory'];factory=[f32(f[6]),f32(f[7]),0.]
            checks['actual_positive_samples'] &= bool(f[:5]==[r['native']['controller_input']['slots'][role]['factory'],r['native']['controller_input']['slots'][role]['factory_id'],n['owner'],r['native']['controller_input']['slots'][role]['factory_template'],0x80d4ea1e] and f[5]==frame and f32(f[8])>0 and f[9]==0xc4db60 and distance(s['xyz'],factory)<=200)
            if baseline is None: baseline=s
            checks['immutable_first_baseline'] &= all(s[key]==baseline[key] for key in IMMUTABLE) and z['baseline_hp']==baseline['hp']
            prior=[team,count] if not (k==141 and reset_proof and reset_proof[0]==frame) else reset_proof[1]
            valid=(t[0]==0x544d5034 and t[7]==frame and t[8:]==prior and all(x>=0x10000 and x%4==0 for x in (t[1],t[2],t[4],t[5])) and t[1]!=n['script_team'] and t[4]!=n['script_team'] and t[3]==t[6]==n['owner'])
            stable=t[1]==t[4]==s['team'] and t[2]==t[5]
            if last and frame not in (last,last+1): valid=False
            if k==142:
                valid &= (e['arg']==1 and stable and count>0 and team!=s['team'] or e['arg']==2 and not stable)
                reset_proof=(frame,[team,count]);last=frame
                team=count=0;run=[];reset_count+=1
            elif k==141:
                valid &= stable and (not count or team==s['team']) and e['arg']==count+1
                if not count: team=s['team']
                count+=1;run.append(z);last=frame
                valid &= z['words'][7]==count
            elif k==144:
                valid &= stable and count==3 and len(run)==3 and e['arg']==3 and run[-1]['sample']==s
                accepted.append(z)
            else: valid=False
            checks['actual_team_chain_and_cohort'] &= bool(valid)
        frames=[z['sample']['frame'] for z in run]
        final=(len(accepted)==1 and frames==list(range(frames[0],frames[0]+3)) if frames else False)
        final &= bool(count==3 and slot['cohort_count']==3 and slot['cohort_first_frame']==frames[0] and slot['cohort_last_frame']==frames[-1] and slot['admission_first']==run[0]['sample'] and slot['admission_last']==run[-1]['sample'] and slot['admitted_team']==team and slot['cohort_reset_count']==reset_count) if final else False
        if final:
            actual_factory=[f32(run[-1]['factory'][6]),f32(run[-1]['factory'][7]),0.]
            final &= abs(slot['initial_factory_gap']-distance(run[-1]['sample']['xyz'],actual_factory))<=.02
        checks['exact_final_three'] &= final
        borrow=[e for e in r['events'] if e['role']==role and e['kind']==1 and e['tag']==1]
        checks['borrow_after_accept'] &= bool(final and len(borrow)==1 and accepted[0]['event']['seq']<borrow[0]['seq'] and borrow[0]['frame']==slot['borrow_frame']==frames[-1] and borrow[0]['team']==n['script_team'])
        result.append(dict(role=role,frames=frames,admitted_team=team,reset_count=reset_count,baseline_frame=baseline['frame'] if baseline else None))
    return dict(verified=all(v is True for v in checks.values()),checks=checks,roles=result)


def clock_audit(r, records, require_pair=True):
    n=r['native'];out=n['controller'];events=r['events'];freeze=[z for z in records if z['event']['kind']==145];borrows=[e for e in events if e['kind']==1 and e['tag']==1];checks={}
    checks['single_actual_first_borrow_clock']=len(freeze)==1 and (len(borrows)==2 if require_pair else 1<=len(borrows)<=2) and len({e['role'] for e in borrows})==len(borrows)
    if not checks['single_actual_first_borrow_clock']: return dict(verified=False,checks=checks)
    z=freeze[0];start=z['sample']['frame'];first=min(borrows,key=lambda e:e['seq'])
    checks['single_actual_first_borrow_clock'] &= z['event']['seq']<first['seq'] and first['frame']==start and first['role']==z['first_role']
    checks['fixed_original_deadlines']=out['clock_frozen']==1 and out['reserve_start_frame']==out['lease_issued_frame']==n['issued_frame']==start and out['reserve_deadline_frame']==start+300 and out['hard_deadline_frame']==n['mission_deadline_frame']==start+4500
    checks['no_reset_renewal']=all((a['start'],a['reserve_deadline'],a['deadline'])==((0,0,0) if a['event']['seq']<z['event']['seq'] else (start,start+300,start+4500)) for a in records)
    checks['bounded_borrow_and_commit']=all(start<=e['frame']<start+300 for e in borrows) and (not out['mission_commit_frame'] or start<=out['mission_commit_frame']<start+300)
    return dict(verified=all(v is True for v in checks.values()),checks=checks,start=start,reserve_deadline=start+300,hard_deadline=start+4500,first_borrow_seq=first['seq'],first_borrow_role=first['role'])


def ready_audit(r, records):
    """Recompute fixed brake/anchor and all observed ready frames, never90 fill."""
    n=r['native'];checks=dict(single_proposal_and_brake=True,original_first_and_second_proposal=True,frozen_observed_path=True,actual_three_brake_samples=True,strict_actual_anchor=True,second_role_actual_pair_geometry=True,complete_ready_holding=True,same_frame_pair=True);roles=[]
    for role in (0,1):
        slot=n['slots'][role];actor=slot['admission_last'];rr=[z for z in records if z['event']['role']==role];by=lambda k:[z for z in rr if z['event']['kind']==k]
        proposals=by(146);trigger=by(149);commits=by(150);ready=by(151);paths=by(147)
        checks['single_proposal_and_brake'] &= len(proposals)==len(trigger)==len(commits)==len(ready)==1
        if not (len(proposals)==len(trigger)==len(commits)==len(ready)==1): continue
        p,t,a,rd=proposals[0],trigger[0],commits[0],ready[0];f=[f32(p['factory'][6]),f32(p['factory'][7]),0.]
        basis=p['radial'];expected=[p['sample']['xyz'][0]-200*basis[1],p['sample']['xyz'][1]+200*basis[0],p['sample']['xyz'][2]] if p['policy']==1 else [p['first_anchor'][0]-80*basis[1],p['first_anchor'][1]+80*basis[0],p['first_anchor'][2]]
        checks['single_proposal_and_brake'] &= (near(p['proposal'],expected) and abs(math.hypot(*basis[:2])-1)<1e-4 and near(slot['proposal'],p['proposal']) and p['event']['seq']<t['event']['seq']<a['event']['seq']<=rd['event']['seq'])
        checks['single_proposal_and_brake'] &= near(slot['initial_xyz'],p['sample']['xyz']) and slot['move_issued_frame']==p['sample']['frame'] and slot['brake_frame']==t['sample']['frame'] and slot['brake_count']==3 and near(slot['brake_xyz'],t['sample']['xyz'])
        first=p['first_role'];reference=p['sample']['xyz'];valid=first in (0,1)
        if role==first:
            valid &= p['policy']==1 and p['reference_role']==role and p['reference_frame']==p['sample']['frame'] and p['reference_thing']==slot['thing']
        elif first in (0,1):
            sources=[z for z in records if z['event']['role']==first and z['event']['kind']==150 and z['event']['seq']<p['event']['seq']]
            valid &= len(sources)==1 and p['policy']==2
            if sources:
                reference=sources[0]['anchor'];valid &= near(p['first_anchor'],reference) and p['reference_role']==first and p['reference_frame']==sources[0]['sample']['frame'] and p['reference_thing']==n['slots'][first]['thing']
        length=distance(reference,f)
        radial=[(reference[0]-f[0])/length,(reference[1]-f[1])/length,0.] if length>=5 and math.isfinite(length) else [math.inf]*3
        valid &= near(p['radial'],radial,.0001) and all(slot[k]==p[v] for k,v in (('proposal_reference_role','reference_role'),('proposal_reference_frame','reference_frame'),('proposal_reference_thing','reference_thing'),('proposal_policy','policy'))) and near(slot['factory_radial_basis'],p['radial']) and near(slot['first_role_actual_anchor'],p['first_anchor'])
        checks['original_first_and_second_proposal'] &= bool(valid)
        frozen=0
        checks['frozen_observed_path'] &= len(paths)<=1
        if paths:
            q=paths[0];s=q['sample'];frozen=q['event']['arg'];checks['frozen_observed_path'] &= bool(frozen and frozen%4==0 and s['path']==frozen and s['state_id']==1 and s['state_vtable']==0xc55598 and s['source']==1 and q['observed_path']==slot['observed_path']==frozen and slot['observed_path_frame']==s['frame'])
        else: checks['frozen_observed_path'] &= slot['observed_path']==0
        for z in [z for z in by(163) if p['event']['seq']<z['event']['seq']<t['event']['seq']]:
            s=z['sample']
            checks['frozen_observed_path'] &= bool(s['path']%4==0 and (not s['path'] or frozen and s['path']==frozen) and s['state_id']!=26)
        brake=[z for z in by(148) if z['event']['seq']<=t['event']['seq']][-3:];frames=[z['sample']['frame'] for z in brake]
        good=len(brake)==3 and frames==list(range(frames[0],frames[0]+3)) and [z['event']['arg'] for z in brake]==[1,2,3] and near(t['brake'],t['sample']['xyz']) and t['sample']==brake[-1]['sample'] and t['sample']['frame']-p['sample']['frame']<=90
        for j,z in enumerate(brake):
            s=z['sample'];current_factory=[f32(z['factory'][6]),f32(z['factory'][7]),0.];mode=(s['state_id']==1 and s['state_vtable']==0xc55598 and frozen and s['path']==frozen or s['state_id']==94 and s['state_vtable']==0xc551a0 and not s['path'])
            good &= bool(surface(s,actor,n['owner']) and s['team']==n['script_team'] and s['stance']==2 and s['source']==1 and not s['sm_flags']&0xffff and mode and distance(s['xyz'],p['sample']['xyz'])>=60 and distance(s['xyz'],current_factory)>=max(120,slot['initial_factory_gap']) and (j==0 or distance(s['xyz'],brake[j-1]['sample']['xyz'])<=5))
        checks['actual_three_brake_samples'] &= bool(good)
        s=a['sample'];af=[f32(a['factory'][6]),f32(a['factory'][7]),0.];checks['strict_actual_anchor'] &= bool(holding(s,actor,n['owner'],n['script_team']) and near(s['xyz'],a['anchor']) and near(slot['anchor'],a['anchor']) and a['sample']==rd['sample'] and slot['anchor_frame']==slot['ready_frame']==s['frame'] and 0<s['frame']-a['stop_frame']<=60 and distance(s['xyz'],t['brake'])<=15 and distance(s['xyz'],p['sample']['xyz'])>=60 and distance(s['xyz'],af)>=max(120,slot['initial_factory_gap']))
        if role!=first and first in (0,1):
            for z in brake+[a]:
                other=[x['sample'] for x in records if x['event']['kind']==163 and x['event']['role']==first and x['sample']['frame']==z['sample']['frame']]
                checks['second_role_actual_pair_geometry'] &= bool(len(other)==1 and holding(other[0],n['slots'][first]['admission_last'],n['owner'],n['script_team']) and distance(other[0]['xyz'],n['slots'][first]['anchor'])<=15 and 25<=distance(z['sample']['xyz'],other[0]['xyz'])<=180)
        holds=by(155);hframes=[a['sample']['frame']]+[z['sample']['frame'] for z in holds];prior=a['sample']['xyz'];maximum=0.
        for z in holds:
            s=z['sample'];checks['complete_ready_holding'] &= bool(z['event']['arg']==1 and holding(s,actor,n['owner'],n['script_team']) and distance(s['xyz'],prior)<=1 and distance(s['xyz'],a['anchor'])<=15);prior=s['xyz'];maximum=max(maximum,distance(s['xyz'],a['anchor']))
        checks['complete_ready_holding'] &= (hframes==list(range(hframes[0],hframes[-1]+1)) and slot['hold_first_frame']==hframes[0] and slot['hold_last_frame']==hframes[-1] and slot['hold_samples']==len(hframes) and slot['hold_failed']==0 and hframes[-1]>=n['controller']['mission_commit_frame'])
        checks['complete_ready_holding'] &= slot['hold_max_gap']==(1 if holds else 0) and abs(slot['max_hold_drift']-maximum)<=.05
        roles.append(dict(role=role,anchor=a['anchor'],anchor_frame=a['sample']['frame'],hold_frames=hframes,observed_path=frozen,brake_frames=frames))
    pair=[z for z in records if z['event']['kind']==152];checks['same_frame_pair'] &= len(pair)==1 and len(roles)==2
    if len(pair)==1 and len(roles)==2:
        frame=pair[0]['sample']['frame'];poses=[]
        for role in (0,1):
            matches=[z['sample'] for z in records if z['event']['role']==role and z['event']['kind'] in (150,155) and z['sample']['frame']==frame]
            checks['same_frame_pair'] &= len(matches)==1
            if matches: poses.append(matches[0]['xyz'])
        checks['same_frame_pair'] &= len(poses)==2 and 25<=distance(*poses)<=180 and n['controller']['pair_ready_frame']==frame and pair[0]['held_mask']==pair[0]['ready_mask']==3
    return dict(verified=all(v is True for v in checks.values()),checks=checks,roles=roles,mandatory_ninety_frames_per_role=False)


def commit_audit(r, records):
    """Whole original body is write-once. Digest syntax is not a physical proof."""
    n=r['native'];i=n['controller_input'];ctl=n['controller'];m=n['mission_commit'];b=m['body'];rows=[z for z in records if z['event']['kind'] in (153,154)];checks={}
    checks['one_accepted_write_once_commit']=m['generation']==2 and m['status']==1 and m['reason']==0 and len(rows)==1 and rows[0]['event']['kind']==153
    frame=rows[0]['sample']['frame'] if len(rows)==1 else 0
    checks['separate_exact_parent_child_and_lease']=all(b[k]==i[k] for k in ('controller','lease','formation','formation_version')) and all(nonzero(b[k]) for k in ('parent_command','parent_task','command','task')) and b['command']!=b['parent_command'] and b['task']!=b['parent_task'] and b['seq']>0
    checks['exact_pair_and_public_scope']=b['front_id']==n['slots'][0]['id'] and b['support_id']==n['slots'][1]['id'] and b['front_id']!=b['support_id'] and all(b[k]==v for k,v in {'module':1,'purpose':1,'allocation_scope':1,'force_numerator':1,'force_denominator':1}.items())
    checks['no_clock_renewal']=all(b[k]==ctl[k] for k in ('reserve_start_frame','reserve_deadline_frame','hard_deadline_frame')) and ctl['reserve_start_frame']<=frame<ctl['reserve_deadline_frame'] and frame==ctl['mission_commit_frame']==ctl['approach_frame']==m['ack_frame']
    checks['current_target_and_proof']=all(b[k]>0 for k in ('target_unit','target_id','target_hash','target_owner','target_template','button','button_schema','command_set')) and b['target_owner']!=n['owner'] and 0<=frame-b['target_observed_frame']<=60 and b['threat_clear']==1 and 0<=frame-b['threat_frame']<=60 and point(b['visible_target']) and any(b['visibility_proof_sha256']) and 30<=b['combat_frames']<=300
    starts=[e for e in r['events'] if e['kind']==76 and e['frame']==frame];checks['same_lease_dispatch_no_reborrow']=len(starts)==2 and {e['role'] for e in starts}=={0,1} and all(rows and rows[0]['event']['seq']<e['seq'] for e in starts) and all(e['frame']<=frame for e in r['events'] if e['kind']==1 and e['tag']==1)
    # The canonical seal is an explicit report object; never manufacture a q12 request.
    request=r.get('mission_request');checks['original_body_seal']=False
    if isinstance(request,dict):
        raw=bytes.fromhex(request['commit_body_hex']);prefix=bytes.fromhex(request['commit_prefix_hex'])
        decoded=plain(L.MissionCommitBody13.from_buffer_copy(raw))
        digest=hashlib.sha256(prefix).digest()
        checks['original_body_seal']=(len(raw)==284 and len(prefix)==L.MissionCommitBody13.digest_sha256.offset==252
            and raw[:252]==prefix and decoded==b and list(struct.unpack('<8I',digest))==b['digest_sha256'] and request['digest_sha256']==digest.hex())
        checks['separate_exact_parent_child_and_lease'] &= (ident(b['parent_command'])==request['parent_command_id'] and ident(b['parent_task'])==request['parent_task_id']
            and ident(b['command'])==request['child_command_id']==str(uuid.uuid5(uuid.UUID(request['parent_command_id']),'formation'))
            and ident(b['task'])==request['child_task_id']==str(uuid.uuid5(uuid.UUID(request['parent_task_id']),'formation')))
    return dict(verified=all(v is True for v in checks.values()),checks=checks,commit_frame=frame,lease_issued_frame=ctl['lease_issued_frame'],body=b)


def target_proof_audit(r,records):
    n=r['native'];request=r['mission_request'];b=n['mission_commit']['body'];target=r['private_target'];checks={}
    source=Path(request['visibility_proof_path']).read_bytes();safety=Path(request['safety_path']).read_bytes()
    proof=json.loads(source.decode('utf-8-sig'));catalog=json.loads(safety.decode('utf-8-sig'))
    digest=hashlib.sha256(source).digest()
    checks['original_visibility_file_and_digest']=(hashlib.sha256(source).hexdigest()==request['visibility_proof_sha256'] and list(struct.unpack('<8I',digest))==b['visibility_proof_sha256'])
    checks['session_and_original_visibility_protocol']=(proof.get('schema_version')==2 and proof.get('object_visibility_method')=='native_footprint_reconstruction' and proof.get('session_id')==r['session_id'] and proof.get('target_player_id')==3 and proof.get('package_sha256')==r['package_sha256']==catalog.get('package_sha256') and all(proof.get(k) is True for k in ('footprint_live_verified','terrain_view_live_verified','object_view_live_verified','conservative_stealth_exclusion_reviewed','no_observer_fallback')))
    checks['original_safety_file']=hashlib.sha256(safety).hexdigest()==request['safety_sha256']=='1d14e41e10224fb2a8215a2321a7fbbbeae8434b8c006a80fd314f4a11e7719e'
    key=lambda x:int(x,0) if isinstance(x,str) else x
    checks['original_private_target_and_native_mirror']=(all(b[k]==key(target[v])==n[k] for k,v in (('target_unit','address'),('target_id','object_id'),('target_hash','type_hash'),('target_owner','owner'),('target_template','template'))) and target['observed_frame']==b['target_observed_frame'] and target['owner_player_id']!=3 and target['owner_player_id'] in range(20))
    expected_contact='contact_'+hashlib.sha256((r['session_id']+':'+str(target['owner_player_id'])+':'+str(target['object_id'])).encode()).hexdigest()[:20]
    entry=catalog['templates'].get(target['type_hash'],{})
    checks['public_contact_and_ground_scope']=request['contact_id']==expected_contact and entry.get('role')==request['target_role'] and entry.get('role') in ('infantry','armor','structure','economy') and (entry['role']!='economy' or target['type_hash']=='0xc45aaeab')
    accepted=[z['event'] for z in records if z['event']['kind']==153]
    checks['current_native_fov_at_actual_accept']=len(accepted)==1 and accepted[0]['target_visible']==1 and accepted[0]['target_id']==b['target_id'] and point(accepted[0]['visible_target_xyz'])
    return dict(verified=all(v is True for v in checks.values()),checks=checks,capability_or_memory_alone_is_current_target_authority=False)


def parent_request_audit(r):
    """Original public request lineage, distinct from actual model HTTP provenance."""
    n=r['native'];mr=r['mission_request'];body=n['mission_commit']['body'];public=mr['public_command'];formation=mr['formation']
    raw=Path(mr['public_command_path']).read_bytes();source=json.loads(raw.decode('utf-8-sig'))
    native_id=str(uuid.uuid5(uuid.UUID(ident(body['controller'])),'paid_pair'));fid='formation_'+uuid.UUID(native_id).hex[:16]
    versions=public['formation_versions'];valid_versions=versions==[[fid,1]] or versions=={fid:1}
    roles=public['required_roles'];force=public['force_fraction'];checks={}
    checks['original_public_file']=hashlib.sha256(raw).hexdigest()==mr['public_command_sha256'] and source==public
    checks['registered_public_formation']=(ident(body['formation'])==native_id==mr['native_formation_uuid'] and body['formation_version']==1 and set(formation)=={'formation_id','version','roles','region_id','available'} and formation['formation_id']==fid and type(formation['version']) is int and formation['version']==1 and formation['roles']=={'infantry':1,'anti_air':1} and all(type(x) is int for x in formation['roles'].values()) and type(formation['region_id']) is str and bool(formation['region_id']) and formation['available'] is True)
    checks['exact_combined_arms_public_request']=(public['module']=='combined_arms' and public['purpose']=='coordinate_force' and public['formation_ids']==[fid] and valid_versions and isinstance(roles,list) and len(roles)==2 and set(roles)=={'infantry','anti_air'} and type(force) in (int,float) and force==1 and public['target_contact_id']==mr['contact_id'])
    checks['parent_process_session_and_sequence']=(public['session_id']==r['session_id']==n['session_id'] and public['player_id']==3 and public['commander_id']==n['commander_id'] and public['seq']==body['seq'] and type(public['seq']) is int and str(uuid.UUID(public['command_id']))==str(uuid.UUID(mr['parent_command_id']))==ident(body['parent_command']) and str(uuid.UUID(public['task_id']))==str(uuid.UUID(mr['parent_task_id']))==ident(body['parent_task']))
    checks['original_parent_deadline_is_existing_lease_hard']=(type(public['expires_frame']) is int and public['expires_frame']==body['hard_deadline_frame']==n['controller']['hard_deadline_frame'] and n['controller']['mission_commit_frame']<public['expires_frame'])
    return dict(verified=all(v is True for v in checks.values()),checks=checks,model_http_origin_verified=False,physical_completion_claim=False,scope='original_parent_envelope_and_child_binding_only')


def stop_audit(r,records):
    n=r['native'];checks=dict(fixed_actual_frame_coverage=True,three_initial_and_brake_stops=True,explicit_normal_stop_source=True);roles=[]
    for role in (0,1):
        slot=n['slots'][role];actor=slot['admission_last'];rows=[z for z in records if z['event']['role']==role];samples=[z for z in rows if z['event']['kind']==163]
        frames=[z['sample']['frame'] for z in samples]
        # Every borrowed reserve frame up to model dispatch is present exactly once.
        expected=list(range(slot['borrow_frame']+1,n['controller']['mission_commit_frame']+1))
        actual=[f for f in frames if slot['borrow_frame']<f<=n['controller']['mission_commit_frame']]
        checks['fixed_actual_frame_coverage'] &= actual==expected
        proposals=[z for z in rows if z['event']['kind']==146];anchors=[z for z in rows if z['event']['kind']==150]
        gates=[]
        for gate in proposals+anchors:
            frame=gate['sample']['frame'];issue=gate['stop_frame']
            if gate['event']['kind']==146:
                # The other role may already be stopped while waiting for the
                # first anchor. Its original60f gate is not reset at proposal.
                window=[z for z in samples if issue<z['sample']['frame']<=frame];run=[]
                for j in range(2,len(window)):
                    trial=window[j-2:j+1]
                    if trial[-1]['sample']['frame']-issue>60:break
                    if [z['sample']['frame'] for z in trial]==list(range(trial[0]['sample']['frame'],trial[0]['sample']['frame']+3)) and all(holding(z['sample'],actor,n['owner'],n['script_team']) and distance(z['sample']['xyz'],z['previous_xyz'])<=1 for z in trial):
                        run=trial;break
                if run:
                    checks['three_initial_and_brake_stops'] &= all(holding(z['sample'],actor,n['owner'],n['script_team']) and distance(z['sample']['xyz'],z['previous_xyz'])<=1 for z in window if z['sample']['frame']>run[-1]['sample']['frame'])
            else:run=[z for z in samples if frame-2<=z['sample']['frame']<=frame]
            valid=len(run)==3 and [z['sample']['frame'] for z in run]==list(range(run[0]['sample']['frame'],run[0]['sample']['frame']+3)) and issue<run[0]['sample']['frame'] and run[-1]['sample']['frame']-issue<=60
            for j,z in enumerate(run):
                valid &= holding(z['sample'],actor,n['owner'],n['script_team']) and distance(z['sample']['xyz'],z['previous_xyz'])<=1
                if j: valid &= distance(z['sample']['xyz'],run[j-1]['sample']['xyz'])<=1
            if gate['event']['kind']==150: valid &= all(distance(z['sample']['xyz'],gate['brake'])<=15 for z in run)
            checks['three_initial_and_brake_stops'] &= bool(valid);gates.append(dict(frame=frame,issue=issue,frames=[z['sample']['frame'] for z in run]))
            facade=[e for e in r['events'] if e['role']==role and e['kind']==30 and e['tag']==4 and e['arg']==1 and e['frame']==issue]
            private=[e for e in r['events'] if e['role']==role and e['kind']==32 and e['tag']==4 and e['arg']==1 and e['frame']==issue]
            done=[e for e in r['events'] if e['role']==role and e['kind']==33 and e['tag']==4 and e['arg']==1 and e['frame']==issue]
            checks['explicit_normal_stop_source'] &= (len(facade)==len(private)==len(done)==1 and facade[0]['seq']<private[0]['seq']<done[0]['seq']<gate['event']['seq'] and private[0]['caller']==done[0]['caller']==0x787791)
        checks['three_initial_and_brake_stops'] &= len(proposals)==len(anchors)==1
        roles.append(dict(role=role,sample_frames=actual,gates=gates))
    return dict(verified=all(v is True for v in checks.values()),checks=checks,roles=roles)


def origin_stream(words):
    """Parse only the Native read-order stream; hidden actors have no XYZ row."""
    if not isinstance(words,list) or not 28<=len(words)<=65536 or not all(word(x) for x in words): raise ValueError('origin_words')
    at=0
    def take(count=1):
        nonlocal at
        if at+count>len(words): raise ValueError('origin_truncated')
        result=words[at:at+count];at+=count
        return result[0] if count==1 else result
    h=take(20)
    if h[0]!=0x4f533133 or h[2] not in (0,1) or not point(floats(h[6:9])): raise ValueError('origin_header')
    frame,role,thing,oid,owner=h[1:6];own=floats(h[6:9]);head=h[9];manager,mvt,impl,cells,width,height=h[10:16];origin=floats(h[16:18]);scale=f32(h[18]);fallback=h[19]
    if not (manager and mvt==0xc6aefc and impl and cells and 0<width<=4096 and 0<height<=4096 and width*height<=4000000 and all(math.isfinite(x) for x in origin) and math.isfinite(scale) and 0<scale<=10): raise ValueError('origin_grid')
    seen=set();expected=head;visible=[];nodecount=0;own_found=False
    def cell_positive(address,count,flag):
        return address>=cells and (address-cells)%0x34==0 and (address-cells)//0x34<width*height and flag==0 and count>0 and (count!=0xffff or fallback==1)
    while words[at]!=0x504f5354:
        if take()!=0x4e4f4445: raise ValueError('origin_node_tag')
        t,vt,uid,ownr,nxt,mask,ovt,index,result=take(9);nodecount+=1
        if t!=expected or not t or t%4 or t in seen or vt!=0xc4db60 or not uid or nxt==t or nodecount>2048: raise ValueError('origin_live_chain')
        seen.add(t);enemy=False
        if t==thing:
            if (uid,ownr)!=(oid,owner): raise ValueError('origin_current_own_identity')
            own_found=True
        if ownr and ownr!=owner:
            if ovt!=0xc5bce0 or index>=20: raise ValueError('origin_owner')
            rel,buckets,count,sentinel,link=take(5)
            if not rel or not sentinel:
                if link:raise ValueError('origin_null_relation_chain')
            else:
                if not buckets or not 1<=count<=4096:raise ValueError('origin_relation_table')
                chain=set()
                while link:
                    node,key,value,nextlink=take(4)
                    if node!=link or node%4 or node in chain or len(chain)>=100 or nextlink==node: raise ValueError('origin_relation_chain')
                    chain.add(node)
                    if key==index:
                        if value>2:raise ValueError('origin_unknown_relation')
                        enemy=value==0;break
                    link=nextlink
                # A complete no-key traversal is the original neutral fallback.
            if take()!=0x454e4452: raise ValueError('origin_relation_unproven')
        authorized=False;record=0
        if enemy:
            record,recordimpl,first,num,pending,masked=take(6)
            if record and recordimpl!=impl or num>4096 or num and not first:raise ValueError('origin_record_unknown')
            eligible=not mask&((1<<11)|(1<<12)) and record!=0 and recordimpl==impl and pending==masked==0 and first!=0 and 0<num<=4096
            if eligible:
                total=take();actual=0;footprint=[]
                for i in range(num):
                    idx,address,count,flag=take(4)
                    footprint.append((address,count,flag))
                    if idx!=i: raise ValueError('origin_footprint_index')
                    if address:
                        actual+=1
                        if not (address>=cells and (address-cells)%0x34==0 and (address-cells)//0x34<width*height): raise ValueError('origin_cell_range')
                        eligible &= cell_positive(address,count,flag)
                    elif (count,flag)!=(0,1): raise ValueError('origin_null_cell')
                if total!=actual: raise ValueError('origin_footprint_count')
                eligible &= total>0
                again=take(7)
                if again!=[0x464f4f54,record,impl,first,num,pending,masked]: raise ValueError('origin_footprint_identity_race')
                for previous in footprint:
                    if tuple(take(3))!=previous: raise ValueError('origin_footprint_cell_race')
            if eligible:
                center,count,flag=take(3);post=take(7);position=floats(take(3));gap=f32(take())
                if not point(position): raise ValueError('origin_xyz')
                gx=int(rounded_float(rounded_float(position[0]-origin[0])*scale));gy=int(rounded_float(rounded_float(position[1]-origin[1])*scale))
                if not (0<=gx<width and 0<=gy<height) or center!=cells+(gy*width+gx)*0x34 or not cell_positive(center,count,flag): raise ValueError('origin_center')
                if post!=[vt,uid,ownr,nxt,mask,record,impl] or abs(gap-distance(own,position))>.05: raise ValueError('origin_authorized_join')
                authorized=True;visible.append(dict(thing=t,id=uid,owner=ownr,xyz=position,gap=gap))
        if result!=(2 if authorized else 1 if enemy else 0) or take()!=0x454e444e: raise ValueError('origin_result_not_raw_recomputed')
        expected=nxt
    post=take(13)
    if post!=[0x504f5354,*h[10:20],head,frame]:raise ValueError('origin_grid_or_head_race')
    if take()!=0x454e4453: raise ValueError('origin_end')
    nodes,auth,minimum,clear,valid,after,head_after=take(7)
    computed_min=min((x['gap'] for x in visible),default=f32(0x7f7fffff));computed_clear=all(x['gap']>350 for x in visible)
    if at!=len(words) or expected or not own_found or nodes!=nodecount or auth!=len(visible) or abs(f32(minimum)-computed_min)>.05 or clear!=int(computed_clear) or valid!=1 or after!=frame or head_after!=head:
        raise ValueError('origin_complete_same_frame')
    return dict(frame=frame,role=role,thing=thing,id=oid,owner=owner,xyz=own,visible_enemies=visible,clear=computed_clear,live_node_count=nodes)


def origin_audit(r,records):
    rows=[e for e in r['events'] if e['kind'] in (160,161,162)];scans=[];pending=None;words=[];checks=dict(complete_original_chunk_stream=bool(rows),every_admitted_sample_current_clear=True)
    for e in rows:
        w=stack(e);magic,version,generation,role,frame,offset,count,result=w[:8]
        if magic!=0x4f533133 or version!=1 or role!=e['role'] or frame!=e['frame'] or generation!=e['arg'] or result not in (0,1,2): raise ValueError('origin_chunk_binding')
        if e['kind']==160:
            if pending is not None or count or offset or any(w[8:]): raise ValueError('origin_duplicate_begin')
            pending=(generation,role,frame,result);words=[]
        elif e['kind']==161:
            if pending!=(generation,role,frame,result) or offset!=len(words) or not 1<=count<=120 or any(w[8+count:]) or len(words)+count>65536: raise ValueError('origin_chunk_order')
            words.extend(w[8:8+count])
        else:
            if pending!=(generation,role,frame,result) or count or offset!=len(words) or any(w[8:]): raise ValueError('origin_end_binding')
            if result:
                parsed=origin_stream(words)
                if (parsed['frame'],parsed['role'])!=(frame,role) or result!=(1 if parsed['clear'] else 2): raise ValueError('origin_scan_claim')
                scans.append(dict(parsed,generation=generation,end_seq=e['seq']))
            pending=None
    checks['complete_original_chunk_stream'] &= pending is None
    for z in records:
        if z['event']['kind']!=141 or z['event']['arg']<=0: continue
        s=z['sample'];matching=[x for x in scans if x['role']==z['event']['role'] and x['frame']==s['frame'] and x['end_seq']<z['event']['seq']]
        checks['every_admitted_sample_current_clear'] &= bool(len(matching)==1 and matching[0]['clear'] and matching[0]['thing']==s['thing'] and matching[0]['id']==s['id'] and matching[0]['owner']==s['owner'] and near(matching[0]['xyz'],s['xyz']))
    return dict(verified=all(v is True for v in checks.values()),checks=checks,scans=scans,hidden_position_reads_accepted=False)


def proof_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def borrow_boundary(r,role):
    """Actual normal Transfer(false) and Remove chain; no header-only claim."""
    n=r['native'];es=[e for e in r['events'] if e.get('role')==role];slot=n['slots'][role];manager=n['ai']+0x104
    rows=lambda k,tag:[e for e in es if e['kind']==k and e['tag']==tag]
    gates=rows(144,0);before=rows(14,1);after=rows(15,1);remove=rows(18,1);removed=rows(19,1);borrow=rows(1,1);capture=rows(132,0)
    valid=len(gates)==len(before)==len(after)==len(remove)==len(removed)==len(borrow)==len(capture)==1
    if not valid:return dict(verified=False,checks={'one_original_normal_borrow':False})
    chain=[gates[0],capture[0],before[0],remove[0],removed[0],after[0],borrow[0]]
    valid &= all(a['seq']<b['seq'] for a,b in zip(chain,chain[1:])) and len({e['frame'] for e in chain})==1 and chain[-1]['frame']==slot['borrow_frame']
    valid &= before[0]['arg']==after[0]['arg']==0 and before[0]['team']==slot['admitted_team'] and after[0]['team']==borrow[0]['team']==n['script_team']
    valid &= remove[0]['arg']==removed[0]['arg']==manager and remove[0]['caller']==0x838877 and all(e['unit_id']==slot['id'] and e['owner']==n['owner'] and e['thread']==n['thread'] for e in chain)
    valid &= math.isfinite(borrow[0]['own_hp']) and borrow[0]['own_hp']>0 and (n if role==0 else n['support'])['detach_calls']==1
    w=capture[0]['stack_words'];s=slot['admission_last'];h=n['stances'][role]
    valid &= (capture[0]['stack_word_count']==68 and len(w)>=68 and w[:4]==[0x53544e31,1,5,role] and w[4]==w[5]==slot['borrow_frame'] and w[6]==s['thing'] and w[7]==s['id'] and w[9]==s['owner'] and w[10]==s['update'] and w[13:19]==[s['stance_module'],s['stance_vtable'],s['stance_backref'],s['stance_data'],s['stance_enum_list'],s['stance_enum_count']] and w[19:27]==s['stance_enum_entries'] and w[27]==w[28]==0 and w[64]==slot['borrow_frame'] and h['capture_frame']==slot['borrow_frame'] and h['original_enum']==0 and h['module']==s['stance_module'])
    return dict(verified=bool(valid),checks={'one_original_normal_borrow':bool(valid)},borrow_seq=borrow[0]['seq'],events=chain)


def borrow_audit(r):
    roles=[dict(role=role,**borrow_boundary(r,role)) for role in (0,1)]
    return dict(verified=all(x['verified'] for x in roles),roles=roles)


def precommit_audit(r):
    es=r['events'];accepts=[e for e in es if e['kind']==153];end=accepts[0]['seq'] if len(accepts)==1 else len(es)+1
    checks=dict(actual_borrow_boundaries=True,no_controlled_attack_before_model=True,no_target_mirror_before_accept=True)
    for role in (0,1):
        starts=[e for e in es if e['kind']==14 and e['tag']==1 and e['role']==role]
        checks['actual_borrow_boundaries'] &= len(starts)==1
        if starts:checks['no_controlled_attack_before_model'] &= not any(e['role']==role and starts[0]['seq']<=e['seq']<end and e['kind'] in (12,13,34,35) for e in es)
    checks['no_target_mirror_before_accept']=all(e.get('target_id')==0 and e.get('target_visible')==0 for e in es if e['seq']<end)
    return dict(verified=all(v is True for v in checks.values()),checks=checks,precommit_attack_authority=False)


def live_facts(r):
    """Incremental original facts for the parent registry, no process access.

    Call only after wrapper Source verification. A verified claim records a past
    real borrow, and must be retained until independent terminal release. Missing
    or half-published evidence is waiting, never implicit release or replacement.
    """
    output=dict(verified=False,source_pins_required=True,clock={'verified':False},claims=[],ready=dict(verified=False,pair_ready_frame=0,observed_frame=0,roles=[],actual_gap=None,proof_sha256=None),tactical_source_granted=False,completion_claim=False,claim_scope='original_borrow_history_until_independent_release')
    try:
        n=r['native'];es=r['events'];records=[reserve_record(e) for e in es if e['kind'] in RS_KINDS]
        published=bool(es) and all(type(e['seq']) is int and e['seq']==index+1 for index,e in enumerate(es)) and all(a['frame']<=b['frame'] for a,b in zip(es,es[1:]))
        envelope=(r['controller_input']==n['controller_input'] and all(r['request'][k]==n[k] for k in ('command_id','task_id','seq','token')))
        base=published and envelope and input_audit(r)['verified'] and producer_arm_audit(r)['verified']
        clock=clock_audit(r,records,require_pair=False);output['clock']={k:v for k,v in clock.items() if k!='checks'}
        output['clock']['verified'] &= bool(base)
        if not base or not clock['verified']:return output
        origin=origin_audit(r,records)
        if not origin['verified']:return output
        for role in (0,1):
            try:
                producer=producer_audit(r,roles=(role,));cohort=cohort_audit(r,records,roles=(role,));borrow=borrow_boundary(r,role)
                verified=producer['verified'] and cohort['verified'] and borrow['verified']
                if not verified:continue
                slot=n['slots'][role];observations=[x for x in producer['observations'] if x['role']==role]
                source_events=[e for e in es if e['role']==role and e['kind'] in (140,141,142,143,144,132,14,18,19,15,1) and e['seq']<=borrow['borrow_seq']]
                digest=proof_sha(dict(protocol='mf13_original_borrow_fact_v1',controller_input=r['controller_input'],events=source_events,lease_start=clock['start']))
                output['claims'].append(dict(role=role,verified=True,object_id=slot['id'],thing=slot['thing'],type_hash=TYPES[role],update=slot['update'],admitted_team=slot['admitted_team'],borrow_frame=slot['borrow_frame'],borrow_seq=borrow['borrow_seq'],cohort_frames=cohort['roles'][0]['frames'],paid_cost=COSTS[role],receipt_generation=observations[-1]['generation'],proof_sha256=digest))
            except (KeyError,TypeError,ValueError,IndexError,OverflowError,struct.error,OSError):continue
        output['verified']=bool(output['claims'])
        if len(output['claims'])!=2 or len({x['object_id'] for x in output['claims']})!=2:return output
        ready=ready_audit(r,records)
        active=n['phase']==1 and n['controller']['stage']==2 and n['mission_commit']['generation']==0 and n['mission_commit']['status']==0
        latest=[];roles=[]
        for role in (0,1):
            rows=[z for z in records if z['event']['role']==role and z['event']['kind'] in (151,155)]
            if not rows:return output
            last=rows[-1];s=last['sample'];latest.append(last)
            role_digest=proof_sha(dict(protocol='mf13_latest_actual_ready_hold_v1',event=last['event']))
            roles.append(dict(role=role,anchor=n['slots'][role]['anchor'],anchor_frame=n['slots'][role]['anchor_frame'],latest_hold_frame=s['frame'],proof_sha256=role_digest))
        frame=latest[0]['sample']['frame'];gap=distance(latest[0]['sample']['xyz'],latest[1]['sample']['xyz'])
        valid=bool(active and ready['verified'] and frame==latest[1]['sample']['frame'] and 25<=gap<=180 and all(n['slots'][role]['hold_last_frame']==frame for role in (0,1)))
        output['ready']=dict(verified=valid,pair_ready_frame=n['controller']['pair_ready_frame'],observed_frame=frame,roles=roles,actual_gap=gap,proof_sha256=proof_sha(dict(protocol='mf13_same_frame_pair_ready_v1',events=[x['event'] for x in latest],pair_ready_frame=n['controller']['pair_ready_frame'])))
        return output
    except (KeyError,TypeError,ValueError,IndexError,OverflowError,struct.error,OSError):return output


def audit(r):
    try:
        records=[reserve_record(e) for e in r['events'] if e['kind'] in RS_KINDS]
        sections={}
        for name,fn,args in [('input',input_audit,(r,)),('producer_arm',producer_arm_audit,(r,)),('producer',producer_audit,(r,)),('cohort',cohort_audit,(r,records)),('borrow',borrow_audit,(r,)),('clock',clock_audit,(r,records)),('ready',ready_audit,(r,records)),('commit',commit_audit,(r,records)),('precommit',precommit_audit,(r,)),('stops',stop_audit,(r,records)),('origin',origin_audit,(r,records)),('target_proof',target_proof_audit,(r,records)),('parent_request',parent_request_audit,(r,))]:
            try:sections[name]=fn(*args)
            except (KeyError,TypeError,ValueError,IndexError,OverflowError,struct.error,OSError):
                sections[name]=dict(verified=False,checks={'well_formed_original_'+name:False})
        checks={k:v['verified'] for k,v in sections.items()}
        return dict(verified=all(v is True for v in checks.values()),checks=checks,**sections,field_verified=False,tactical_source_granted=False,completion_claim=False)
    except (KeyError,TypeError,ValueError,IndexError,OverflowError,struct.error,OSError):
        return dict(verified=False,checks={'well_formed_original_controller_evidence':False},field_verified=False,tactical_source_granted=False,completion_claim=False)
