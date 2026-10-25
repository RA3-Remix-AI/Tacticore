import copy
import struct
import uuid
import ctypes
from pathlib import Path
import unittest
import reserve_qualification as q


def fixture():
    n = dict(thing=0x1000, object_id=804, type_hash=0x19ab11af, owner=0x2000,
             template_ptr=0x3000, update=0x4000, stance_module=0x5000, script_team=0x6000)
    s = dict(frame=101, thing=n['thing'], id=n['object_id'], type_hash=n['type_hash'], owner=n['owner'],
             template_ptr=n['template_ptr'], update=n['update'], update_vtable=0xc48670,
             update_backref=n['thing'], stance_module=n['stance_module'], stance_vtable=0xc37f90,
             stance_backref=n['thing'], stance_data=0x5100, stance=2, sm=0x7000, sm_owner=n['thing'],
             sm_flags=65536, state=0x7100, state_id=94, state_vtable=0xc551a0, state_owner_sm=0x7000,
             path=0, source=1, team=n['script_team'], child_sm=0x7200, child_sm_vtable=0xc4fb60,
             child_state=0x7300, child_state_id=0, child_state_vtable=0xc515f0,
             child_state_owner_sm=0x7200, holder=0, status_words=[0]*7,
             height_flags=4, height=0., hp=100., xyz=[10., 20., 210.])
    rows = [dict(seq=f-100, frame=f, kind=3, sample=dict(copy.deepcopy(s), frame=f)) for f in range(101, 194)]
    return n, rows


def full_fixture():
    n, rows = fixture()
    s = copy.deepcopy(rows[0]['sample'])
    names={key+'_id':str(uuid.UUID(int=i+1)) for i,key in enumerate(('session','commander','command','task'))}
    n.update(magic=0x52535635, version=5, pid=1234, thread=77, callback_thread=77,
             start_low=12, start_high=34, **names, seq=1, token=123, original_team=0x6100,
             default_team=0x6200, original_stance=0, test_stance=2, observed_frame=99,
             threat_frame=99, threat_clear=1, expires_frame=400, issued_frame=100, returned_frame=196,
             stage=5, phase=3, error=0, active=0, overflow=0, restore_mask=255, disposed=0, scene_changed=0,
             initial_stop_verified=1, cleanup_stop_verified=1, hold_verified=1, hold_started=103,
             hold_finished=193, hold_first_frame=103, hold_last_frame=193, hold_samples=91,
             hold_max_gap=1, hold_missing_frames=0, hold_anchor=[10.,20.,210.],
             stance_restored=1, stance_changed=1, return_verified=1, restore_before_enum=2, restore_after_enum=0,
             pool_before_enum=0, pool_after_enum=0, detach_calls=1, return_calls=1, stance_calls=2)
    n.update(logic=0x9010,ai=0x9020,personality=0x9030,personality_id=0x9040,player_template=0x9050)
    s.update(frame=100, stance=0, team=n['original_team'], source=0, state_id=1,
             state_vtable=0xc55598, stance_enum_count=4, stance_enum_list=0x8100,
             stance_enum_entries=[0,0,1,0,2,0,3,0])
    n['initial_sample'] = copy.deepcopy(s)
    es, counters = [], dict(explicit_stops=0,private_explicit_stops=0,automatic_stop2=0,private_automatic_stop2=0)
    calls = 0
    def event(kind, tag=0, arg=0, source=0, self=0, result=0, caller=0):
        nonlocal calls
        if kind == 50:
            calls += 1
            if arg in (3,4,8): counters['explicit_stops'] += 1
        if kind == 30 and source == 2: counters['automatic_stop2'] += 1
        if kind == 33:
            if source == 2: counters['private_automatic_stop2'] += 1
            else: counters['private_explicit_stops'] += 1
        es.append(dict(seq=len(es)+1,kind=kind,tag=tag,arg=arg,source=source,self=self,result=result,
                       caller=caller,frame=s['frame'],tick=s['frame']*67,thread=77,stage=0,error=0,
                       sdk_calls=calls,sample=copy.deepcopy(s),move=dict(goal_pointer=0,goal_bits=[0]*3,path=0,limit_bits=0,intent_seq=0,facade_seq=0,generation=0,flags=0),**counters))
    def stop(tag, source):
        event(30,tag,source=source,self=n['update']+0x24)
        event(32,tag,source=source,self=n['update'],caller=0x787791)
        s.update(source=source,path=0,state_id=94 if s['stance']==2 else 16,
                 state_vtable=0xc551a0 if s['stance']==2 else 0xc55130)
        event(33,tag,source=source,self=n['update'],caller=0x787791)
        event(31,tag,source=source,self=n['update']+0x24)
    def setter(tag,value):
        event(50,tag,arg=2 if tag==2 else 5,result=value)
        event(20,tag,arg=value,self=n['stance_module'])
        s['stance']=value;stop(tag,2)
        event(21,tag,arg=value,self=n['stance_module'],result=1)
    def transfer(tag):
        event(50,tag,arg=tag)
        event(10,tag,arg=int(tag==6),self=n['owner'])
        event(14,tag,self=s['team']);event(15,tag,self=s['team'])
        s['team']=n['script_team'] if tag==1 else n['default_team']
        event(12,tag,self=s['team']);event(13,tag,self=s['team'])
        event(11,tag,arg=int(tag==6),self=n['owner'])
    s['frame']=98;event(0)
    n['admission_first_sample']=copy.deepcopy(s)
    for frame in (98,99,100):
        s['frame']=frame;event(3);event(73,arg=n['original_team'],self=n['thing'],result=frame-98);es[-1]['move']=dict(goal_pointer=0x544d5034,goal_bits=[n['original_team'],0xc000,n['owner']],path=n['original_team'],limit_bits=0xc000,intent_seq=n['owner'],facade_seq=frame,generation=n['original_team'] if frame>98 else 0,flags=frame-98);event(60,arg=frame-97)
    event(61,arg=3)
    n.update(admission_samples=3,admission_first_frame=98,admission_last_frame=100,admission_verified=1,admission_max_gap=1,observed_frame=97)
    import hashlib
    command=str(uuid.UUID(int=100));task=str(uuid.UUID(int=101))
    n.update(production_command=list(struct.unpack('<4I',uuid.UUID(command).bytes)),production_task=list(struct.unpack('<4I',uuid.UUID(task).bytes)),production_seq=7,production_queue_id=9,production_birth_frame=96,production_paid=85,production_receipt_sha256=[1]*8)
    transfer(1);event(1);setter(2,2)
    event(50,3,arg=3);stop(3,1)
    for f in range(101,104):s['frame']=f;event(3)
    n['rally']=dict(factory_address=0x9100,factory_id=1,factory_owner=n['owner'],factory_template=0x9300,factory_type_hash=0x80d4ea1e,factory_source_frame=99,
        factory_x_bits=struct.unpack('<I',struct.pack('<f',-90.))[0],factory_y_bits=struct.unpack('<I',struct.pack('<f',20.))[0],proposal_origin=s['xyz'][:],proposal_direction=[0.,1.],goal=[10.,220.,210.],proposal_frame=103,
        arrival_samples=0,last_arrival_frame=107,rally_issue_frame=103,rally_reached_frame=0,rally_stop_verified=1,rally_stop_frame=107,
        move_intents=1,move_facade_entries=1,move_private_entries=1,foreign_move_entries=0,move_scope_open=0,move_generation=1,move_intent_seq=0)
    event(69);es[-1]['move']=dict(goal_pointer=0x9100,goal_bits=[1,n['owner'],0x9300],path=0x80d4ea1e,limit_bits=103,intent_seq=n['rally']['factory_x_bits'],facade_seq=n['rally']['factory_y_bits'],generation=struct.unpack('<I',struct.pack('<f',1000.))[0],flags=0xc4db60)
    event(62);es[-1]['stage']=1
    event(50,7,arg=7);intent=es[-1]['seq'];n['rally']['move_intent_seq']=intent
    event(64,7,source=1,self=n['update']+0x24,caller=0x100100);facade=es[-1]['seq']
    event(66,7,source=1,self=n['update'],caller=0x6d3b7d)
    event(67,7,source=1,self=n['update'],caller=0x6d3b7d)
    event(65,7,source=1,self=n['update']+0x24,caller=0x100100)
    for e in es[-4:]:e['move']=dict(goal_pointer=0xa000,goal_bits=list(struct.unpack('<3I',struct.pack('<3f',*n['rally']['goal']))),path=0,limit_bits=0 if e['kind'] in (64,65) else 0x7f7fffff,intent_seq=intent,facade_seq=facade,generation=1,flags=3 if e['kind'] in (64,66) else 7)
    s.update(state_id=1,state_vtable=0xc55598,path=0x9000)
    for f,x in ((104,50.),(105,75.),(106,75.),(107,75.)):
        s['frame']=f;s['xyz']=[x,20.,210.]
        if f>=105:s.update(state_id=94,state_vtable=0xc551a0,path=0)
        event(3);es[-1]['stage']=6
        if f>=105:event(70,arg=f-104);es[-1]['stage']=6
    event(71,arg=3);es[-1]['stage']=6;event(50,8,arg=8);stop(8,1)
    for f in range(108,201):
        s['frame']=f;event(3)
        if f==110:
            es[-1]['stage']=7;event(68,arg=3);es[-1]['stage']=7;event(72,arg=3);es[-1]['stage']=7;event(40);es[-1]['stage']=2
    event(41);event(50,4,arg=4);stop(4,1)
    for f in range(201,204):s['frame']=f;event(3)
    n.update(returned_frame=203,hold_started=110,hold_finished=200,hold_first_frame=110,hold_last_frame=200,hold_anchor=[75.,20.,210.])
    event(42);event(44);setter(5,0);event(45);event(46);transfer(6);event(47);event(4)
    n.update(sdk_calls=calls,count=len(es),**counters)
    n['anchor']=dict(candidate_samples=3,last_candidate_frame=107,candidate_frame=107,commit_frame=110,initial_outside_inner_zone=0,boundary_crossed=1,proposal_reached=0,admission_age_first=2,admission_age_last=4,initial_factory_gap=100.,candidate_xyz=[75.,20.,210.],actual_anchor=[75.,20.,210.],last_candidate_xyz=[75.,20.,210.],proposal_distance=struct.unpack('<f',struct.pack('<f',(65**2+200**2)**.5))[0])
    t = dict(pid=n['pid'],seq=1,token=123,**names,
             native_binary_sha256='synthetic',timer=0,active=0,restore_mask=255,phase=3,error=0,mutations=False,
             timer_after=0,shared_pointer=0x8000,shared_pointer_after=0x8000,binding_verified=True,
             entries=[dict(address=hex(a),actual=v,expected=v,restored=True) for a,v in q.HOOKS.items()])
    terminal_header(t,n)
    pre={k:n[k] for k in ('pid','session_id','commander_id','start_low','start_high','owner','logic','ai','personality','personality_id','player_template','script_team','default_team')}
    pre['window_thread']=77
    pre['selected']=dict(address=n['thing'],object_id=n['object_id'],ai_address=n['update'],type_hash=n['type_hash'],team=n['original_team'],
                        admission=dict(object_id=n['object_id'],frame=97),stance=dict(module=n['stance_module'],backref=n['thing'],vtable=0xc37f90,getter=0x71d3f0,enum=0,
                        data=0x5100,definition_list=0x8100,definition_count=4,definitions=[dict(enum=i,modifier=0) for i in range(4)]))
    td=0xc000;tv=n['original_team'];values={n['logic']+0x50:n['observed_frame'],n['thing']+0xdc:n['object_id'],n['thing']+0x418:n['owner'],n['thing']+0x374:n['update'],n['thing']+0x414:tv,tv:0xa100,tv+4:td,td:0xa200,td+8:n['owner']};raw_team={hex(k):struct.pack('<I',v).hex() for k,v in values.items()}
    pre['selected']['team_binding']=dict(protocol='rsv5_same_frame_owned_team_v1',frame=n['observed_frame'],team=hex(tv),definition=hex(td),owner=hex(n['owner']),raw_before=raw_team,raw_after=copy.deepcopy(raw_team),mutations=False)
    pre['current_visibility']=dict(frame=99,minimum_observed_enemy_distance=None,visible_enemy_count=0,hard_limit=350,preferred_margin=450,unknown_enemies_remain_unknown=True)
    return dict(native=n,events=es,preflight=pre,
                request={k:n[k] for k in ('seq','token','command_id','task_id','expires_frame')},
                session_id=n['session_id'],native_binary_sha256='synthetic',terminal_readonly=t,status='finished',host_exit=0)


def terminal_header(t,n):
    b=bytearray(1176)
    for key,off in {'magic':0,'version':4,'pid':8,'token':88,'seq':92,'owner':100,'thing':120,'object_id':124,
                    'phase':176,'active':184,'error':192,'restore_mask':196,'returned_frame':212,
                    'sdk_calls':216,'detach_calls':220,'return_calls':224,'return_verified':228,'stance_restored':264}.items():struct.pack_into('<I',b,off,n[key])
    for i,key in enumerate(('session','commander','command','task')):b[24+16*i:40+16*i]=uuid.UUID(n[key+'_id']).bytes
    struct.pack_into('<4I',b,636,*n['production_command']);struct.pack_into('<4I',b,652,*n['production_task'])
    for key,off in {'production_seq':668,'production_queue_id':672,'production_birth_frame':676,'production_paid':680,'admission_samples':716,'admission_first_frame':720,'admission_last_frame':724,'admission_verified':728,'admission_max_gap':732}.items():struct.pack_into('<I',b,off,n[key])
    struct.pack_into('<8I',b,684,*n['production_receipt_sha256'])
    a=n['rally'];struct.pack_into('<8I8f14I',b,976,*[a[k] for k in ('factory_address','factory_id','factory_owner','factory_template','factory_type_hash','factory_source_frame','factory_x_bits','factory_y_bits')],*a['proposal_origin'],*a['proposal_direction'],*a['goal'],*[a[k] for k in ('proposal_frame','arrival_samples','last_arrival_frame','rally_issue_frame','rally_reached_frame','rally_stop_verified','rally_stop_frame','move_intents','move_facade_entries','move_private_entries','foreign_move_entries','move_scope_open','move_generation','move_intent_seq')])
    a=n['anchor'];struct.pack_into('<9I11f',b,1096,*[a[k] for k in ('candidate_samples','last_candidate_frame','candidate_frame','commit_frame','initial_outside_inner_zone','boundary_crossed','proposal_reached','admission_age_first','admission_age_last')],a['initial_factory_gap'],*a['candidate_xyz'],*a['actual_anchor'],*a['last_candidate_xyz'],a['proposal_distance'])
    t['header_before_hex']=t['header_after_hex']=bytes(b).hex()



def factory_source_fixture(r):
    n=r['native'];a=n['rally'];birth=r['birth_source']
    word=lambda x:struct.pack('<I',x).hex()
    before=dict(thing_vtable_hex=word(0xc4db60),object_id_hex=word(a['factory_id']),owner_hex=word(n['owner']),template_pointer_hex=word(a['factory_template']),
        type_hash_hex=word(0x80d4ea1e),xyz_hex=struct.pack('<3f',-90.,20.,210.).hex(),body_pointer_hex=word(0xb000),hp_hex=struct.pack('<f',1000.).hex(),frame_hex=word(99),owner_index_hex=word(3))
    return dict(protocol='rsv5_current_owned_factory_v1',session_id=n['session_id'],pid=n['pid'],source_report=birth['path'],source_report_sha256=birth['sha256'],source_receipt_sha256=birth['receipt_sha256'],
        reader_sha256=q.sha(q.HERE/'rally_source.py'),mutations=False,sdk_calls=0,proposal_terrain_verified=False,route_verified=False,sample_before=before,sample_after=copy.deepcopy(before),
        factory_id=a['factory_id'],factory_address=hex(a['factory_address']),factory_owner=hex(a['factory_owner']),factory_template=hex(a['factory_template']),factory_hash=hex(a['factory_type_hash']),factory_xyz=[-90.,20.,210.],factory_hp=1000.,source_frame=99,
        factory_x_bits=a['factory_x_bits'],factory_y_bits=a['factory_y_bits'],logic=hex(n['logic']),owned_membership=dict(frame_start=99,frame_end=99,all_owned_ids=[a['factory_id']],member=dict(object_id=a['factory_id'],address=hex(a['factory_address']),owner_address=hex(n['owner']),owner_index_candidate=3,type_hash='0x80d4ea1e')))

class PhysicalQualification(unittest.TestCase):
    def test_three_distinct_then_exact_ninety(self):
        n, es = fixture()
        stop = q.stop_three(es, [10.,20.,210.], n, 100)
        self.assertTrue(stop['verified'])
        self.assertEqual(stop['frames'], [101,102,103])
        audit = q.hold_window(es, 103, [10.,20.,210.], n)
        self.assertTrue(audit['verified'])
        self.assertTrue(audit['continuous_all_logic_frames_verified'])
        self.assertEqual(audit['count'], 90)
        self.assertFalse(any(q.no_grant().values()))

    def test_only_two_stop_frames(self):
        n, es = fixture()
        self.assertFalse(q.stop_three(es[:2], [10.,20.,210.], n, 100)['verified'])

    def test_same_frame_cannot_supply_three(self):
        n, es = fixture()
        es[1]['sample']['frame'] = es[0]['frame']
        self.assertFalse(q.stop_three(es, [10.,20.,210.], n, 100)['verified'])

    def test_automatic_stop_source_two_never_supplies_gate(self):
        n, es = fixture()
        for e in es: e['sample']['source'] = 2
        self.assertFalse(q.stop_three(es, [10.,20.,210.], n, 100)['verified'])

    def test_path_even_with_state94_fails(self):
        n, es = fixture()
        es[44]['sample']['path'] = 0x1234
        self.assertFalse(q.hold_window(es, 103, [10.,20.,210.], n)['verified'])

    def test_path_zero_but_adjacent_movement_fails(self):
        n, es = fixture()
        es[44]['sample']['xyz'][0] += 2
        self.assertFalse(q.hold_window(es, 103, [10.,20.,210.], n)['verified'])

    def test_slow_cumulative_anchor_drift_fails(self):
        n, es = fixture()
        for e in es: e['sample']['xyz'][0] += (e['frame']-103)*.2
        self.assertFalse(q.hold_window(es, 103, [10.,20.,210.], n)['verified'])

    def test_any_missing_logical_frame_fails_without_filling(self):
        n, es = fixture()
        es = [e for e in es if e['frame'] != 150]
        a = q.hold_window(es, 103, [10.,20.,210.], n)
        self.assertFalse(a['verified'])
        self.assertEqual(a['missing_frame_ids'], [150])
        self.assertEqual(a['max_frame_gap'], 2)

    def test_duplicate_does_not_replace_missing_frame(self):
        n, es = fixture()
        es[49] = copy.deepcopy(es[48])
        self.assertFalse(q.hold_window(es, 103, [10.,20.,210.], n)['verified'])

    def test_wrong_module_or_actor_identity_fails(self):
        for key in ['stance_backref', 'update_backref', 'id', 'owner']:
            n, es = fixture()
            es[44]['sample'][key] += 4
            self.assertFalse(q.hold_window(es, 103, [10.,20.,210.], n)['verified'])

    def test_state94_wrong_vtable_or_owner_fails(self):
        for key in ['state_vtable', 'state_owner_sm']:
            n, es = fixture()
            es[44]['sample'][key] += 4
            self.assertFalse(q.hold_window(es, 103, [10.,20.,210.], n)['verified'])

    def test_dead_actor_cannot_supply_hold(self):
        n, es = fixture()
        es[44]['sample']['hp'] = 0
        self.assertFalse(q.hold_window(es, 103, [10.,20.,210.], n)['verified'])


class PreAdmissionQualification(unittest.TestCase):
    def test_actual_three_frames_are_before_every_sdk(self):
        r=full_fixture();a=q.pre_admission_audit(r);self.assertTrue(a['verified'],a);self.assertEqual(a['frames'],[98,99,100])
    def test_gap_duplicate_missing_or_early_sdk_cannot_reset_admission(self):
        for case in ('gap','duplicate','missing','early_sdk'):
            r=full_fixture();rows=[e for e in r['events'] if e['kind']==60]
            if case=='gap':rows[1]['frame']+=1
            elif case=='duplicate':rows[1]['frame']=rows[0]['frame']
            elif case=='missing':r['events'].remove(rows[1])
            else:next(e for e in r['events'] if e['kind']==50)['seq']=rows[1]['seq']
            self.assertFalse(q.pre_admission_audit(r)['verified'],case)
    def test_each_frame_actual_health_module_and_admission_must_hold(self):
        for key,value in [('hp',99.),('stance',2),('stance_data',1),('path',1),('sm_flags',1),('holder',1),('owner',1),('state_id',77),('stance_enum_entries',[0]*8)]:
            r=full_fixture();row=next(e for e in r['events'] if e['kind']==60 and e['arg']==2);row['sample'][key]=value
            if key=='path':row['sample']['state_id']=16
            self.assertFalse(q.pre_admission_audit(r)['verified'],key)
    def test_header_claims_never_replace_three_original_rows(self):
        for key,value in [('admission_samples',4),('admission_max_gap',2),('admission_first_frame',97),('admission_last_frame',101)]:
            r=full_fixture();r['native'][key]=value;self.assertFalse(q.pre_admission_audit(r)['verified'],key)
        r=full_fixture();r['native']['admission_first_sample']['hp']=1.;self.assertFalse(q.pre_admission_audit(r)['verified'])
    def test_normal_position_change_before_borrow_is_not_idle_claim(self):
        r=full_fixture();rows=[e for e in r['events'] if e['kind']==60]
        for i,e in enumerate(rows):
            e['sample']['xyz'][0]+=i*3.
            for proof in r['events']:
                if proof['kind'] in (3,73) and proof['frame']==e['frame']:proof['sample']=copy.deepcopy(e['sample'])
        next(e for e in r['events'] if e['kind']==61)['sample']=copy.deepcopy(rows[-1]['sample'])
        r['native']['admission_first_sample']=copy.deepcopy(rows[0]['sample']);r['native']['initial_sample']=copy.deepcopy(rows[-1]['sample'])
        self.assertTrue(q.pre_admission_audit(r)['verified'])


class OriginalPaidProvenance(unittest.TestCase):
    def setUp(self):
        import tempfile,hashlib,json
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.root=root
        self.r=full_fixture();self.r['preflight']['window_thread']=77;n=self.r['native'];command_id=str(uuid.UUID(bytes=struct.pack('<4I',*n['production_command'])));task_id=str(uuid.UUID(bytes=struct.pack('<4I',*n['production_task'])))
        self.receipt=dict(command_id=command_id,task_id=task_id,seq=7,unit='conscript',status='completed',accepted=True,completed=True,paid_verified=True,created=True,completion_observed=True,queue_preserved=True,payment_error=0,live_samples=10,paid=85,cost=85,queue_id=9,completion_frame=96,object_id=804)
        self.command=dict(command_id=command_id,task_id=task_id,seq=7,unit='conscript',session_id=n['session_id'],commander_id=n['commander_id'],player_id=3,budget=1000,reserve=1000,expires_frame=400)
        self.seal=lambda obj:hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.session=dict(session_id=n['session_id'],pid=n['pid'],scenario=dict(commander_id=n['commander_id']),run_directory=str(root))
        self.session_path=root/'session.json';self.session_path.write_text(json.dumps(self.session));self.r['session_source']=dict(path=str(self.session_path),sha256=q.sha(self.session_path))
        entries=[dict(address=hex(a),expected=b,actual=b) for a,b in {0x7ba770:'81ec3c010000f605486bce0001535657',0x70f440:'83ec08558b6c241085ed568bf1',0x849220:'81ecb4000000568bf18b46148b4e04',0x73e390:'83ec208b4424248b54242c5355',0x789bf0:'51568bf180be3801000000'}.items()]
        self.source=dict(session_id=n['session_id'],pid=n['pid'],production_source_sha256=q.sha(q.HERE.parent.parent/'production/persistent/client.py'),production_stopped=dict(native_phase=2,native_error=0,restore_mask=31,active_callbacks=0,player_id=3,session_id=n['session_id'],commander_id=n['commander_id'],ledger=[self.receipt],spent_committed=85,total_budget=4000),production_native_identity=dict(pid=n['pid'],session_id=n['session_id'],commander_id=n['commander_id'],owner=hex(n['owner']),thread=n['thread']),after_entries=entries,paid_orders_verified=True,serial_handover_verified=True,commands=[dict(command=self.command,receipt=dict(accepted=True))])
        self.source_path=root/'producer.json';self.source_path.write_text(json.dumps(self.source))
        h=[0]*64;h[:11]=[0x50434d44,1]+[n[k] for k in ('pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high')]
        h[11:15]=struct.unpack('<4I',uuid.UUID(n['session_id']).bytes);h[15:19]=struct.unpack('<4I',uuid.UUID(n['commander_id']).bytes);h[19]=4000;h[23]=2;h[59]=85;h[60]=1;h[61]=31;h[63]=77
        cmd=[7]+list(struct.unpack('<4I',uuid.UUID(command_id).bytes))+list(struct.unpack('<4I',uuid.UUID(task_id).bytes))+list(struct.unpack('<4I',uuid.UUID(n['session_id']).bytes))+list(struct.unpack('<4I',uuid.UUID(n['commander_id']).bytes))+[n['type_hash'],1000,1000,400,2,1,0x9100,1,0x9200]
        fields='state error attempted frame queue_id node cost quoted_cost cash liability prior_count preserved paid debit_count payment_error created object object_id object_owner object_hash completed completion_frame live_samples object_hp_bits object_x_bits object_y_bits factory_x_bits factory_y_bits'.split()
        values=dict(state=2,error=0,attempted=1,frame=90,queue_id=9,node=0xa000,cost=85,quoted_cost=85,cash=5000,liability=0,prior_count=0,preserved=1,paid=85,debit_count=1,payment_error=0,created=1,object=n['thing'],object_id=804,object_owner=n['owner'],object_hash=n['type_hash'],completed=1,completion_frame=96,live_samples=10)
        raw=struct.pack('<56I',*([0,1]+cmd+[values.get(k,0) for k in fields]));prefix=struct.pack('<64I',*h)
        ro=dict(protocol='reserve_birth_stopped_production_readonly_v1',mutations=False,sdk_calls=0,pid=n['pid'],session_id=n['session_id'],header_hex=prefix.hex(),header_after_hex=prefix.hex(),receipt_hex=raw.hex(),receipt_after_hex=raw.hex(),receipt_index=0,header_size=256,receipt_size=224,entries=entries,reader_sha256=q.sha(q.HERE/'birth_source.py'),producer_sha256=q.sha(q.HERE.parent.parent/'production/persistent/client.py'),native_binary_sha256=q.sha(q.HERE.parent.parent/'production/persistent/bin-v2/ProductionPersistent.dll'),native_host_sha256=q.sha(q.HERE.parent.parent/'production/persistent/bin-v2/persistent_host.exe'))
        seal=self.seal(self.receipt);n['production_receipt_sha256']=list(struct.unpack('<8I',bytes.fromhex(seal)))
        self.r['birth_source']=dict(path=str(self.source_path),sha256=q.sha(self.source_path),receipt=copy.deepcopy(self.receipt),receipt_sha256=seal,command=copy.deepcopy(self.command),production_readonly=ro)
        terminal_header(self.r['terminal_readonly'],n)
        self.r['rally_source']=factory_source_fixture(self.r)
    def tearDown(self):self.temp.cleanup()
    def test_complete_original_paid_file_and_raw_mapping(self):
        a=q.production_provenance(self.r);self.assertTrue(a['verified'],a)
    def test_actual_production_version_one_not_binary_directory_suffix(self):
        self.assertTrue(q.production_provenance(self.r)['verified'])
        ro=self.r['birth_source']['production_readonly'];raw=bytearray.fromhex(ro['header_hex']);struct.pack_into('<I',raw,4,2)
        ro['header_hex']=ro['header_after_hex']=raw.hex()
        self.assertFalse(q.production_provenance(self.r)['verified'])
    def test_actual_factory_receipt_and_double_raw_sample_join(self):
        self.assertTrue(q.rally_source_audit(self.r)['verified'],q.rally_source_audit(self.r))
        for mode in ('receipt','raw_owner','raw_hash','position','membership','native_observation','unknown_terrain_claim'):
            r=copy.deepcopy(self.r)
            if mode=='receipt':
                raw=bytearray.fromhex(r['birth_source']['production_readonly']['receipt_hex']);struct.pack_into('<I',raw,100,0x9110);r['birth_source']['production_readonly']['receipt_hex']=raw.hex()
            elif mode in ('raw_owner','raw_hash'):
                key='owner_hex' if mode=='raw_owner' else 'type_hash_hex'
                for side in ('sample_before','sample_after'):r['rally_source'][side][key]='00000000'
            elif mode=='position':r['rally_source']['factory_xyz'][0]+=1
            elif mode=='membership':r['rally_source']['owned_membership']['all_owned_ids']=[]
            elif mode=='native_observation':next(e for e in r['events'] if e['kind']==69)['move']['goal_bits'][1]+=4
            else:r['rally_source']['proposal_terrain_verified']=True
            self.assertFalse(q.rally_source_audit(r)['verified'],mode)
    def test_no_header_nonzero_or_cached_verified_can_replace_original_source(self):
        self.r['birth_source'].pop('production_readonly');self.r['birth_source']['verified']=True;self.assertFalse(q.production_provenance(self.r)['verified'])
    def test_original_receipt_or_actor_or_hash_or_future_birth_mismatch(self):
        for key,value in [('production_paid',84),('object_id',805),('production_birth_frame',98),('production_seq',8),('production_receipt_sha256',[1]*8)]:
            r=copy.deepcopy(self.r);r['native'][key]=value;self.assertFalse(q.production_provenance(r)['verified'],key)
    def test_raw_payment_created_and_owner_independently_checked(self):
        for offset in (0,112,120,160,168,184,188,192):
            r=copy.deepcopy(self.r);b=bytearray.fromhex(r['birth_source']['production_readonly']['receipt_hex']);struct.pack_into('<I',b,offset,0xffffffff)
            r['birth_source']['production_readonly']['receipt_hex']=r['birth_source']['production_readonly']['receipt_after_hex']=b.hex();self.assertFalse(q.production_provenance(r)['verified'],offset)
    def test_unstable_mapping_or_foreign_session_or_wrong_start_or_unrestored_bytes(self):
        for change in ('unstable','session','start','entry'):
            r=copy.deepcopy(self.r);ro=r['birth_source']['production_readonly']
            if change=='unstable':ro['header_after_hex']='00'*256
            elif change=='entry':ro['entries'][0]['actual']='00'
            else:
                b=bytearray.fromhex(ro['header_hex']);b[44 if change=='session' else 36]^=1;ro['header_hex']=ro['header_after_hex']=b.hex()
            self.assertFalse(q.production_provenance(r)['verified'],change)
    def test_full_synthetic_primitive_actual_compiled_source_not_field_grant(self):
        import lease
        self.r.update(lease.source_record(),executable_sha256=q.EXE);self.r['terminal_readonly']['native_binary_sha256']=self.r['native_binary_sha256']
        a=q.qualify(self.r);self.assertEqual(a['status'],'reserve_hold_primitive_verified',a);self.assertFalse(a['completion_claim']);self.assertFalse(a['tactical_source_granted']);self.assertFalse(a['reserve_to_mission_handoff_verified']);self.assertFalse(a['reserve_active_after_return']);self.assertEqual(a['reserve_lease_id'],self.r['native']['task_id'])


class FreshBirthAdmissionQualification(unittest.TestCase):
    def test_every_pre_sdk_frame_has_current_age_and_factory_distance(self):
        r=full_fixture();self.assertTrue(q.fresh_birth_admission_audit(r)['verified'])
        for mode in ('late_age','outside_factory','already_sdk'):
            r=full_fixture();rows=[e for e in r['events'] if e['kind']==60]
            if mode=='late_age':rows[-1]['frame']=r['native']['production_birth_frame']+301
            elif mode=='outside_factory':rows[1]['sample']['xyz'][0]=111.
            else:rows[1]['sdk_calls']=1
            self.assertFalse(q.fresh_birth_admission_audit(r)['verified'],mode)
    def test_previous_reserve2_actor_is_not_relabelled_a_fresh_factory_actor(self):
        import json
        p=q.HERE.parent.parent/'acceptance/runs/20261026-032102-commander/paid-reserve2-direct02.json'
        r=json.loads(p.read_text(encoding='utf-8-sig'));a=q.fresh_birth_admission_audit(r)
        self.assertFalse(a['verified']);self.assertFalse(a['checks']['each_observed_completion_age_bounded'])
        self.assertFalse(a['checks']['each_actual_factory_gap_bounded'])
        self.assertGreater(a['initial_factory_gap'],443.)
        self.assertFalse(q.no_grant()['tactical_source_granted'])


class TeamCohortQualification(unittest.TestCase):
    def test_fresh_guard_uses_proven_admitted_team_not_python_descriptor(self):
        r=full_fixture();n=r['native'];admitted=0x6300
        n['admission_first_sample']['team']=n['initial_sample']['team']=admitted
        borrow=next(e['seq'] for e in r['events'] if e['kind']==50 and e['arg']==1)
        for e in r['events']:
            if e['seq']<borrow or e['kind']==10 and e['tag']==1:e['sample']['team']=admitted
            if e['kind']==73:
                e['arg']=admitted;e['move']['goal_bits'][0]=admitted;e['move']['path']=admitted
                if e['move']['generation']:e['move']['generation']=admitted
            if e['kind'] in (14,15) and e['tag']==1:e['self']=e['sample']['team']=admitted
        self.assertNotEqual(n['original_team'],admitted)
        self.assertTrue(q.pre_admission_audit(r)['verified'])
        self.assertTrue(q.qualify(r)['checks']['fresh_original_admission'])
        transfer=next(e for e in r['events'] if e['kind']==10 and e['tag']==1);transfer['sample']['team']+=4
        self.assertFalse(q.qualify(r)['checks']['fresh_original_admission'])

    def race_fixture(self):
        r=full_fixture();sample=copy.deepcopy(next(e for e in r['events'] if e['kind']==3));sample['frame']=sample['sample']['frame']=97
        race=copy.deepcopy(sample);race.update(kind=74,arg=2,self=r['native']['thing'],result=0)
        race['move']=dict(goal_pointer=0x544d5034,goal_bits=[r['native']['original_team'],0xc000,r['native']['owner']],path=0x6300,limit_bits=0xc100,intent_seq=r['native']['owner'],facade_seq=97,generation=0,flags=0)
        r['events'][0]['frame']=r['events'][0]['sample']['frame']=97
        r['events'][1:1]=[sample,race]
        for i,e in enumerate(r['events']):e['seq']=i+1
        return r
    def trace(self):
        import native_layout as layout
        def plain(v):
            if isinstance(v,ctypes.Structure):return {k:plain(getattr(v,k)) for k,_ in v._fields_}
            if isinstance(v,ctypes.Array):return [plain(x) for x in v]
            return v
        p=layout.Probe.from_buffer_copy((q.HERE/'native-team-reset-positive.bin').read_bytes())
        return dict(native=plain(layout.Header.from_buffer_copy(bytes(p)[:layout.Probe.events.offset])),events=[plain(p.events[i]) for i in range(p.count)])
    def test_actual_two_old_samples_reset_then_three_real_new_team_samples(self):
        r=self.trace();a=q.pre_admission_audit(r);self.assertTrue(a['verified'],a)
        self.assertEqual(len(a['frames']),3);self.assertEqual(len(a['all_accepted_frames']),5)
        self.assertEqual([x['reason'] for x in a['cohort_resets']],[1])
        self.assertNotEqual(r['native']['initial_sample']['team'],r['native']['original_team'])
        self.assertLess(a['immutable_baseline_frame'],a['frames'][0])
        self.assertTrue(q.fresh_birth_admission_audit(r)['verified'])
    def test_same_frame_owned_team_race_discards_sample_without_extending_deadline(self):
        r=self.race_fixture();a=q.pre_admission_audit(r);self.assertTrue(a['verified'],a)
        self.assertEqual(a['frames'],[98,99,100]);self.assertEqual(a['all_observed_frames'],[97,98,99,100])
        self.assertEqual(a['cohort_resets'],[dict(frame=97,reason=2,discarded=0,old_team=0)])
        self.assertTrue(q.fresh_birth_admission_audit(r)['verified'])
        r['native']['observed_frame']=98
        self.assertFalse(q.pre_admission_audit(r)['verified'])
    def test_gap_after_discarded_race_is_not_hidden_by_a_new_cohort(self):
        r=self.race_fixture();next(e for e in r['events'] if e['kind']==3)['frame']=95
        self.assertFalse(q.pre_admission_audit(r)['verified'])
    def test_preborrow_passive_move_cannot_poison_or_supply_owned_move_credit(self):
        r=full_fixture();n=r['native'];original=[e for e in r['events'] if e['kind'] in (64,66,67,65)];passive=[]
        sample=copy.deepcopy(next(e for e in r['events'] if e['kind']==3)['sample'])
        for i,e in enumerate(original):
            x=copy.deepcopy(e);x.update(seq=-i-1,frame=98,tag=0,stage=0,sdk_calls=0,sample=copy.deepcopy(sample),explicit_stops=0,private_explicit_stops=0,automatic_stop2=0,private_automatic_stop2=0)
            x['move'].update(generation=0,intent_seq=0,facade_seq=0,flags=1);passive.append(x)
        r['events'][1:1]=passive;mapping={e['seq']:i+1 for i,e in enumerate(r['events'])}
        for e in r['events']:
            old=e['seq'];e['seq']=mapping[old]
            if e['kind'] in (64,65,66,67):
                if old>0:
                    e['move']['intent_seq']=mapping[e['move']['intent_seq']];e['move']['facade_seq']=mapping[e['move']['facade_seq']]
                elif e['kind']==64:e['move']['facade_seq']=e['seq']
        n['rally']['move_intent_seq']=mapping[n['rally']['move_intent_seq']]
        self.assertTrue(q.sdk_audit(r['events'],n)['verified'])
        self.assertTrue(q.move_audit(r)['verified'],q.move_audit(r))
        self.assertFalse(q.sdk_audit(r['events'],n)['pre_borrow_passive_sdk_credit'])
        borrow=next(e['seq'] for e in r['events'] if e['kind']==50 and e['arg']==1)
        r['events']=[e for e in r['events'] if not(e['kind']==66 and e['seq']>borrow)]
        self.assertFalse(q.move_audit(r)['verified'])
    def test_missing_owner_chain_wrong_owner_or_forged_reset_cannot_rebaseline(self):
        for mode in ('missing_proof','owner','missing_reset','wrong_reset_reason','prefix_rewrite'):
            r=self.trace()
            if mode=='missing_proof':r['events']=[e for e in r['events'] if e['kind']!=73]
            elif mode=='owner':next(e for e in r['events'] if e['kind']==73)['move']['intent_seq']=0
            elif mode=='missing_reset':r['events']=[e for e in r['events'] if e['kind']!=74]
            elif mode=='wrong_reset_reason':next(e for e in r['events'] if e['kind']==74)['arg']=2
            else:r['native']['admission_first_sample']=copy.deepcopy(next(e for e in r['events'] if e['kind']==60)['sample'])
            self.assertFalse(q.pre_admission_audit(r)['verified'],mode)
    def test_nonteam_health_baseline_survives_team_reset(self):
        r=self.trace();frame=r['native']['admission_first_frame']
        for e in r['events']:
            if e['frame']>=frame:e['sample']['hp']=90.
        r['native']['admission_first_sample']['hp']=r['native']['initial_sample']['hp']=90.
        a=q.pre_admission_audit(r);self.assertFalse(a['verified']);self.assertFalse(a['checks']['immutable_actor_module_health'])
    def test_actual_transfer_must_still_come_from_third_admitted_team(self):
        r=self.trace();next(e for e in r['events'] if e['kind']==10 and e['tag']==1)['sample']['team']+=4
        a=q.pre_admission_audit(r);self.assertFalse(a['verified']);self.assertFalse(a['checks']['actual_borrow_source_is_final_admitted_team'])
    def test_preflight_team_raw_double_read_not_stale_descriptor(self):
        r=full_fixture();self.assertTrue(q.preflight_team_audit(r)['verified'])
        for mode in ('stale_descriptor','owner','unstable','old_frame'):
            r=full_fixture();b=r['preflight']['selected']['team_binding']
            if mode=='stale_descriptor':r['preflight']['selected']['team']+=4
            elif mode=='owner':
                key=hex(int(b['definition'],0)+8);b['raw_before'][key]=b['raw_after'][key]='00000000'
            elif mode=='unstable':b['raw_after']={}
            else:b['frame']-=1
            self.assertFalse(q.preflight_team_audit(r)['verified'],mode)


class RallyQualification(unittest.TestCase):
    def test_original_synchronous_chain_and_physical_rally(self):
        r=full_fixture()
        self.assertTrue(q.move_audit(r)['verified'],q.move_audit(r))
        a=q.rally_audit(r);self.assertTrue(a['verified'],a)
        self.assertEqual(a['candidate_frames'],[105,106,107])
        self.assertGreaterEqual(a['physical_rally_progress'],60)
        self.assertFalse(a['proposal_is_ground_observation'])
        self.assertFalse(a['proposal_reached'])
        self.assertGreater(r['native']['anchor']['proposal_distance'],15)
    def test_candidate_displacement_and_outward_factory_threshold_are_independent(self):
        for mode in ('under_sixty','under_factory_120','back_toward_factory'):
            r=full_fixture()
            if mode=='under_sixty':
                for e in r['events']:
                    if e['kind'] in (3,70,71) and 105<=e['frame']<=107:e['sample']['xyz'][0]=69.
            elif mode=='under_factory_120':
                for e in r['events']:
                    if e['kind'] in (3,70,71) and 105<=e['frame']<=107:e['sample']['xyz']=[-90.,100.,210.]
            else:r['native']['initial_sample']['xyz']=[100.,20.,210.]
            self.assertFalse(q.rally_audit(r)['verified'],mode)
    def test_no_candidate_counter_or_current_pose_substitutes_original_events(self):
        for mode in ('no_seventy','missing_freeze','fake_candidate','duplicate_freeze'):
            r=full_fixture()
            if mode=='no_seventy':r['events']=[e for e in r['events'] if e['kind']!=70]
            elif mode=='missing_freeze':r['events']=[e for e in r['events'] if e['kind']!=71]
            elif mode=='fake_candidate':r['native']['anchor']['candidate_xyz'][0]+=1
            else:r['events'].append(copy.deepcopy(next(e for e in r['events'] if e['kind']==71)))
            self.assertFalse(q.rally_audit(r)['verified'],mode)
    def test_committed_anchor_is_actual_stop8_third_sample_not_proposal_or_mutable_pose(self):
        for mode in ('proposal','fake_commit','missing_commit','wrong_commit_frame'):
            r=full_fixture();a=r['native']['anchor']
            if mode=='proposal':a['actual_anchor']=r['native']['rally']['goal'][:]
            elif mode=='fake_commit':next(e for e in r['events'] if e['kind']==72)['sample']['xyz'][0]+=.5
            elif mode=='missing_commit':r['events']=[e for e in r['events'] if e['kind']!=72]
            else:a['commit_frame']+=1
            self.assertFalse(q.rally_audit(r)['verified'],mode)
    def test_proposal_reached_and_boundary_outputs_must_be_truthful(self):
        for key,value in [('proposal_reached',1),('initial_outside_inner_zone',1),('boundary_crossed',0),('proposal_distance',0.)]:
            r=full_fixture();r['native']['anchor'][key]=value
            self.assertFalse(q.rally_audit(r)['verified'],key)
    def test_state26_in_navigation_is_failure_even_without_motion(self):
        r=full_fixture();e=next(e for e in r['events'] if e['kind']==3 and e['frame']==104)
        e['sample'].update(state_id=26,state_vtable=0xc553d0,path=0)
        self.assertFalse(q.rally_audit(r)['verified'])
        self.assertFalse(q.qualify(r)['checks']['observed_active_state26_never_waived'])
    def test_raw_private_argument_thread_scope_and_generation_counterexamples(self):
        for key,value in [('source',0),('thread',78),('self',0x4004),('caller',1)]:
            r=full_fixture();next(e for e in r['events'] if e['kind']==66)[key]=value
            self.assertFalse(q.move_audit(r)['verified'],key)
        for key,value in [('path',1),('limit_bits',0),('intent_seq',1),('facade_seq',1),('generation',2),('flags',1),('goal_pointer',0),('goal_bits',[0]*3)]:
            r=full_fixture();next(e for e in r['events'] if e['kind']==66)['move'][key]=value
            self.assertFalse(q.move_audit(r)['verified'],key)
    def test_missing_deferred_duplicate_or_nested_delivery_has_no_credit(self):
        for mode in ('missing_private','duplicate_private','nested_facade','foreign_counter'):
            r=full_fixture();rows=r['events']
            if mode=='missing_private':r['events']=[e for e in rows if e['kind'] not in (66,67)]
            elif mode=='foreign_counter':r['native']['rally']['foreign_move_entries']=1
            else:rows.insert(1,copy.deepcopy(next(e for e in rows if e['kind']==(66 if mode=='duplicate_private' else 64))))
            self.assertFalse(q.move_audit(r)['verified'],mode)
    def test_frozen_left_side_origin_and_short_factory_vector(self):
        for mode in ('opposite','short','wrong_origin','nonfinite','one_hundred_one'):
            r=full_fixture();a=r['native']['rally']
            if mode=='opposite':a['proposal_direction']=[0.,-1.];a['goal'][1]=-80.
            elif mode=='short':a['factory_x_bits']=struct.unpack('<I',struct.pack('<f',9.))[0]
            elif mode=='wrong_origin':a['proposal_origin'][0]+=1
            elif mode=='nonfinite':r['native']['initial_sample']['xyz'][0]=float('nan')
            else:a['goal'][1]+=1
            self.assertFalse(q.rally_audit(r)['verified'],mode)
    def test_candidate_requires_three_real_consecutive_positive_frames(self):
        for mode in ('two','gap','source','ground','late'):
            r=full_fixture();rows=[e for e in r['events'] if e['kind']==3 and 105<=e['frame']<=107]
            if mode=='two':r['events'].remove(rows[0])
            elif mode=='gap':rows[0]['frame']-=1;rows[0]['sample']['frame']-=1
            elif mode=='source':rows[1]['sample']['source']=0
            elif mode=='ground':rows[1]['sample']['height_flags']=0
            else:r['native']['rally']['rally_issue_frame']=0
            self.assertFalse(q.rally_audit(r)['verified'],mode)
    def test_rally_stop_cannot_use_automatic_stop_or_skip_goal_excursion(self):
        for mode in ('source2','outside_goal','late'):
            r=full_fixture();rows=[e for e in r['events'] if e['kind']==3 and 108<=e['frame']<=110]
            if mode=='source2':rows[1]['sample']['source']=2
            elif mode=='outside_goal':rows[0]['sample']['xyz'][1]=136.
            else:next(e for e in r['events'] if e['kind']==50 and e['arg']==8)['frame']=40
            self.assertFalse(q.rally_audit(r)['verified'],mode)
    def test_hold_state26_no_displacement_is_still_failure(self):
        r=full_fixture();e=next(e for e in r['events'] if e['kind']==3 and e['frame']==150)
        e['sample'].update(state_id=26,state_vtable=0xc553d0)
        self.assertFalse(q.qualify(r)['hold_verified'])
    def test_committed_anchor_is_not_reanchored_during_hold(self):
        r=full_fixture();r['native']['anchor']['actual_anchor'][0]+=16
        self.assertFalse(q.hold_window(r['events'],110,[75.,20.,210.],r['native'])['verified'])


class FullRawQualification(unittest.TestCase):
    def make(self):
        r=full_fixture();r['preflight']['window_thread']=77;return r

    def test_full_raw_chains_and_release_without_source_grant(self):
        a=q.qualify(self.make())
        self.assertTrue(a['sdk_audit']['verified'])
        self.assertTrue(a['hold_verified'])
        self.assertTrue(a['physical_cleanup_stop_verified'])
        self.assertTrue(a['control_release_verified'])
        self.assertEqual([k for k,v in a['checks'].items() if not v],['compiled_source_revision','original_paid_birth_provenance','original_owned_factory_source'])
        self.assertEqual(a['status'],'not_passed')
        self.assertFalse(a['tactical_source_granted'])

    def test_missing_private_stop_cannot_use_header_count(self):
        r=self.make();r['events']=[e for e in r['events'] if not (e['kind']==33 and e['tag']==3)]
        self.assertFalse(q.sdk_audit(r['events'],r['native'])['verified'])
        self.assertFalse(q.qualify(r)['hold_verified'])

    def test_source_two_cannot_impersonate_explicit_stop(self):
        r=self.make()
        for e in r['events']:
            if e['tag']==3 and e['kind'] in (30,31,32,33):e['source']=2
        self.assertFalse(q.qualify(r)['checks']['eight_original_sdk_chains'])

    def test_ninth_call_rejected(self):
        r=self.make();r['events'].append(dict(copy.deepcopy(r['events'][-1]),kind=50,arg=3,tag=3))
        self.assertFalse(q.sdk_audit(r['events'],r['native'])['verified'])

    def test_pool_return_cannot_precede_original_enum(self):
        r=self.make()
        next(e for e in r['events'] if e['kind']==46)['sample']['stance']=2
        a=q.qualify(r)
        self.assertFalse(a['original_stance_restored'])
        self.assertFalse(a['checks']['original_stance_before_live_pool_return'])
        self.assertTrue(a['live_pool_return_verified'])

    def test_cleanup_timeout_is_release_only(self):
        r=self.make();n=r['native'];n.update(error=43,phase=4,cleanup_stop_verified=0)
        next(e for e in r['events'] if e['kind']==42)['kind']=43
        r['terminal_readonly'].update(error=43,phase=4)
        terminal_header(r['terminal_readonly'],n)
        a=q.qualify(r)
        self.assertFalse(a['physical_cleanup_stop_verified'])
        self.assertTrue(a['control_release_verified'])
        self.assertEqual(a['status'],'not_passed')

    def test_actual_bytes_not_restore_mask_alone(self):
        r=self.make();r['terminal_readonly']['entries'][0]['actual']='00'
        self.assertFalse(q.qualify(r)['restoration_verified'])

    def test_original_80_percent_hp_admission(self):
        r=self.make();r['native']['initial_sample']['hp']=79.99
        self.assertFalse(q.qualify(r)['checks']['fresh_original_admission'])

    def test_deferred_stop_must_not_renew_original_sixty_deadline(self):
        r=self.make()
        # An artificial late private callback must not reset the intent deadline.
        intent=next(e for e in r['events'] if e['kind']==50 and e['arg']==3)
        intent['frame']=40
        self.assertFalse(q.qualify(r)['checks']['actual_initial_stop_three'])

    def test_actual_cpp_trace_without_invented_original_events(self):
        if not (q.HERE/'native_layout.py').exists():self.skipTest('Wrapper actual layout pending')
        import native_layout as layout
        for filename in ('native-positive.bin','native-anchor-positive.bin','native-team-reset-positive.bin'):
            with self.subTest(trace=filename):
                p=layout.Probe.from_buffer_copy((q.HERE/filename).read_bytes())
                def plain(value):
                    if isinstance(value,ctypes.Structure):return {key:plain(getattr(value,key)) for key,_ in value._fields_}
                    if isinstance(value,ctypes.Array):return [plain(v) for v in value]
                    return value
                n=plain(layout.Header.from_buffer_copy(bytes(p)[:layout.Probe.events.offset]))
                es=[plain(p.events[i]) for i in range(p.count)]
                self.assertTrue(q.sdk_audit(es,n)['verified'])
                self.assertTrue(q.pre_admission_audit(dict(native=n,events=es))['verified'])
                self.assertTrue(q.fresh_birth_admission_audit(dict(native=n,events=es))['verified'],q.fresh_birth_admission_audit(dict(native=n,events=es)))
                initial=next(e for e in es if e['kind']==40)
                firstgate=next(e for e in es if e['kind']==62)
                stop=next(e for e in es if e['kind']==33 and e['tag']==3)
                gate=q.stop_three([e for e in es if stop['seq']<e['seq']<firstgate['seq']],stop['sample']['xyz'],n,stop['frame'])
                self.assertTrue(gate['verified'])
                audit=q.hold_window(es,initial['frame'],initial['sample']['xyz'],n)
                self.assertTrue(audit['verified'])
                self.assertEqual(audit['count'],90)
                self.assertEqual(n['sdk_calls'],8)
                self.assertFalse(q.qualify(dict(native=n,events=es))['tactical_source_granted'])
                # The real software hook caller is inside the harness, not the game adapter.
                # Preserve those bytes: this trace cannot certify the SDK caller source.
                move=q.move_audit(dict(native=n,events=es))
                self.assertFalse(move['verified'])
                self.assertEqual([k for k,v in move['checks'].items() if not v],['same_actual_actor_frame_thread_and_scope'])
                self.assertNotEqual(next(e for e in es if e['kind']==66)['caller'],0x6d3b7d)
                self.assertTrue(q.rally_audit(dict(native=n,events=es))['verified'],q.rally_audit(dict(native=n,events=es)))
        
                if filename=='native-anchor-positive.bin':
                    self.assertEqual(n['anchor']['proposal_reached'],0)
                    self.assertFalse(any(e['kind']==63 for e in es))
                    self.assertTrue(any(e['kind']==72 for e in es))

    def test_actual_source_bundle_exact_namespaces(self):
        if not (q.HERE/'lease.py').exists():self.skipTest('Wrapper Source joint pending')
        import lease
        record=lease.source_record();record['executable_sha256']=q.EXE
        self.assertTrue(q.source_pins(record))
        broken=copy.deepcopy(record);broken['external_sources']['lease.py']='0'*64
        self.assertFalse(q.source_pins(broken))
        self.assertEqual(len(q.external_source_paths()),13)
        self.assertIn('preflight.py',[p.name for p in q.source_paths()])

    def test_failed_setter_no_invented_restore_call(self):
        r=self.make();n=r['native'];n.update(stance_changed=0,restore_before_enum=0)
        r['events']=[e for e in r['events'] if e['tag']!=5]
        next(e for e in r['events'] if e['kind']==44)['sample']['stance']=0
        terminal_header(r['terminal_readonly'],n)
        a=q.qualify(r)
        self.assertTrue(a['original_stance_restored'])
        self.assertTrue(a['live_pool_return_verified'])
        self.assertEqual(a['status'],'not_passed')

    def test_terminal_header_identity_not_aggregate_boolean(self):
        r=self.make();t=r['terminal_readonly'];b=bytearray.fromhex(t['header_before_hex'])
        b[24]^=1;t['header_before_hex']=t['header_after_hex']=bytes(b).hex()
        self.assertFalse(q.qualify(r)['restoration_verified'])


if __name__ == '__main__':
    unittest.main()
