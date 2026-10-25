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
    n.update(magic=0x52535631, version=1, pid=1234, thread=77, callback_thread=77,
             start_low=12, start_high=34, **names, seq=1, token=123, original_team=0x6100,
             default_team=0x6200, original_stance=0, test_stance=2, observed_frame=99,
             threat_frame=99, threat_clear=1, expires_frame=400, issued_frame=100, returned_frame=196,
             stage=5, phase=3, error=0, active=0, overflow=0, restore_mask=63, disposed=0, scene_changed=0,
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
            if arg in (3,4): counters['explicit_stops'] += 1
        if kind == 30 and source == 2: counters['automatic_stop2'] += 1
        if kind == 33:
            if source == 2: counters['private_automatic_stop2'] += 1
            else: counters['private_explicit_stops'] += 1
        es.append(dict(seq=len(es)+1,kind=kind,tag=tag,arg=arg,source=source,self=self,result=result,
                       caller=caller,frame=s['frame'],tick=s['frame']*67,thread=77,stage=0,error=0,
                       sdk_calls=calls,sample=copy.deepcopy(s),**counters))
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
        s['frame']=frame;event(3);event(60,arg=frame-97)
    event(61,arg=3)
    n.update(admission_samples=3,admission_first_frame=98,admission_last_frame=100,admission_verified=1,admission_max_gap=1,observed_frame=97)
    import hashlib
    command=str(uuid.UUID(int=100));task=str(uuid.UUID(int=101))
    n.update(production_command=list(struct.unpack('<4I',uuid.UUID(command).bytes)),production_task=list(struct.unpack('<4I',uuid.UUID(task).bytes)),production_seq=7,production_queue_id=9,production_birth_frame=96,production_paid=85,production_receipt_sha256=[1]*8)
    transfer(1);event(1);setter(2,2)
    event(50,3,arg=3);stop(3,1)
    for f in range(101,194):
        s['frame']=f;event(3)
        if f==103:event(40)
    event(41);event(50,4,arg=4);stop(4,1)
    for f in range(194,197):s['frame']=f;event(3)
    event(42);event(44);setter(5,0);event(45);event(46);transfer(6);event(47);event(4)
    n.update(sdk_calls=calls,count=len(es),**counters)
    t = dict(pid=n['pid'],seq=1,token=123,**names,
             native_binary_sha256='synthetic',timer=0,active=0,restore_mask=63,phase=3,error=0,mutations=False,
             timer_after=0,shared_pointer=0x8000,shared_pointer_after=0x8000,binding_verified=True,
             entries=[dict(address=hex(a),actual=v,expected=v,restored=True) for a,v in q.HOOKS.items()])
    terminal_header(t,n)
    pre={k:n[k] for k in ('pid','session_id','commander_id','start_low','start_high','owner','logic','ai','personality','personality_id','player_template','script_team','default_team')}
    pre['selected']=dict(address=n['thing'],object_id=n['object_id'],ai_address=n['update'],type_hash=n['type_hash'],team=n['original_team'],
                        admission=dict(object_id=n['object_id'],frame=97),stance=dict(module=n['stance_module'],backref=n['thing'],vtable=0xc37f90,getter=0x71d3f0,enum=0,
                        data=0x5100,definition_list=0x8100,definition_count=4,definitions=[dict(enum=i,modifier=0) for i in range(4)]))
    pre['current_visibility']=dict(frame=99,minimum_observed_enemy_distance=None,visible_enemy_count=0,hard_limit=350,preferred_margin=450,unknown_enemies_remain_unknown=True)
    return dict(native=n,events=es,preflight=pre,
                request={k:n[k] for k in ('seq','token','command_id','task_id','expires_frame')},
                session_id=n['session_id'],native_binary_sha256='synthetic',terminal_readonly=t,status='finished',host_exit=0)


def terminal_header(t,n):
    b=bytearray(976)
    for key,off in {'magic':0,'version':4,'pid':8,'token':88,'seq':92,'owner':100,'thing':120,'object_id':124,
                    'phase':176,'active':184,'error':192,'restore_mask':196,'returned_frame':212,
                    'sdk_calls':216,'detach_calls':220,'return_calls':224,'return_verified':228,'stance_restored':264}.items():struct.pack_into('<I',b,off,n[key])
    for i,key in enumerate(('session','commander','command','task')):b[24+16*i:40+16*i]=uuid.UUID(n[key+'_id']).bytes
    struct.pack_into('<4I',b,636,*n['production_command']);struct.pack_into('<4I',b,652,*n['production_task'])
    for key,off in {'production_seq':668,'production_queue_id':672,'production_birth_frame':676,'production_paid':680,'admission_samples':716,'admission_first_frame':720,'admission_last_frame':724,'admission_verified':728,'admission_max_gap':732}.items():struct.pack_into('<I',b,off,n[key])
    struct.pack_into('<8I',b,684,*n['production_receipt_sha256'])
    t['header_before_hex']=t['header_after_hex']=bytes(b).hex()


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
        for i,e in enumerate(rows):e['sample']['xyz'][0]+=i*3.
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
        h=[0]*64;h[:11]=[0x50434d44,2]+[n[k] for k in ('pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high')]
        h[11:15]=struct.unpack('<4I',uuid.UUID(n['session_id']).bytes);h[15:19]=struct.unpack('<4I',uuid.UUID(n['commander_id']).bytes);h[19]=4000;h[23]=2;h[59]=85;h[60]=1;h[61]=31;h[63]=77
        cmd=[7]+list(struct.unpack('<4I',uuid.UUID(command_id).bytes))+list(struct.unpack('<4I',uuid.UUID(task_id).bytes))+list(struct.unpack('<4I',uuid.UUID(n['session_id']).bytes))+list(struct.unpack('<4I',uuid.UUID(n['commander_id']).bytes))+[n['type_hash'],1000,1000,400,2,1,0x9100,1,0x9200]
        fields='state error attempted frame queue_id node cost quoted_cost cash liability prior_count preserved paid debit_count payment_error created object object_id object_owner object_hash completed completion_frame live_samples object_hp_bits object_x_bits object_y_bits factory_x_bits factory_y_bits'.split()
        values=dict(state=2,error=0,attempted=1,frame=90,queue_id=9,node=0xa000,cost=85,quoted_cost=85,cash=5000,liability=0,prior_count=0,preserved=1,paid=85,debit_count=1,payment_error=0,created=1,object=n['thing'],object_id=804,object_owner=n['owner'],object_hash=n['type_hash'],completed=1,completion_frame=96,live_samples=10)
        raw=struct.pack('<56I',*([0,1]+cmd+[values.get(k,0) for k in fields]));prefix=struct.pack('<64I',*h)
        ro=dict(protocol='reserve_birth_stopped_production_readonly_v1',mutations=False,sdk_calls=0,pid=n['pid'],session_id=n['session_id'],header_hex=prefix.hex(),header_after_hex=prefix.hex(),receipt_hex=raw.hex(),receipt_after_hex=raw.hex(),receipt_index=0,header_size=256,receipt_size=224,entries=entries,reader_sha256=q.sha(q.HERE/'birth_source.py'),producer_sha256=q.sha(q.HERE.parent.parent/'production/persistent/client.py'),native_binary_sha256=q.sha(q.HERE.parent.parent/'production/persistent/bin-v2/ProductionPersistent.dll'),native_host_sha256=q.sha(q.HERE.parent.parent/'production/persistent/bin-v2/persistent_host.exe'))
        seal=self.seal(self.receipt);n['production_receipt_sha256']=list(struct.unpack('<8I',bytes.fromhex(seal)))
        self.r['birth_source']=dict(path=str(self.source_path),sha256=q.sha(self.source_path),receipt=copy.deepcopy(self.receipt),receipt_sha256=seal,command=copy.deepcopy(self.command),production_readonly=ro)
        terminal_header(self.r['terminal_readonly'],n)
    def tearDown(self):self.temp.cleanup()
    def test_complete_original_paid_file_and_raw_mapping(self):
        a=q.production_provenance(self.r);self.assertTrue(a['verified'],a)
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


class FullRawQualification(unittest.TestCase):
    def make(self):
        r=full_fixture();r['preflight']['window_thread']=77;return r

    def test_full_raw_chains_and_release_without_source_grant(self):
        a=q.qualify(self.make())
        self.assertTrue(a['sdk_audit']['verified'])
        self.assertTrue(a['hold_verified'])
        self.assertTrue(a['physical_cleanup_stop_verified'])
        self.assertTrue(a['control_release_verified'])
        self.assertEqual([k for k,v in a['checks'].items() if not v],['compiled_source_revision','original_paid_birth_provenance'])
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
        self.assertFalse(q.qualify(r)['checks']['six_original_sdk_chains'])

    def test_seventh_call_rejected(self):
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
        p=layout.Probe.from_buffer_copy((q.HERE/'native-positive.bin').read_bytes())
        def plain(value):
            if isinstance(value,ctypes.Structure):return {key:plain(getattr(value,key)) for key,_ in value._fields_}
            if isinstance(value,ctypes.Array):return [plain(v) for v in value]
            return value
        n=plain(layout.Header.from_buffer_copy(bytes(p)[:layout.Probe.events.offset]))
        es=[plain(p.events[i]) for i in range(p.count)]
        self.assertTrue(q.sdk_audit(es,n)['verified'])
        self.assertTrue(q.pre_admission_audit(dict(native=n,events=es))['verified'])
        initial=next(e for e in es if e['kind']==40)
        stop=next(e for e in es if e['kind']==33 and e['tag']==3)
        gate=q.stop_three([e for e in es if stop['seq']<e['seq']<initial['seq']],stop['sample']['xyz'],n,stop['frame'])
        self.assertTrue(gate['verified'])
        audit=q.hold_window(es,initial['frame'],initial['sample']['xyz'],n)
        self.assertTrue(audit['verified'])
        self.assertEqual(audit['count'],90)
        self.assertEqual(n['sdk_calls'],6)
        self.assertFalse(q.qualify(dict(native=n,events=es))['tactical_source_granted'])

    def test_actual_source_bundle_exact_namespaces(self):
        if not (q.HERE/'lease.py').exists():self.skipTest('Wrapper Source joint pending')
        import lease
        record=lease.source_record();record['executable_sha256']=q.EXE
        self.assertTrue(q.source_pins(record))
        broken=copy.deepcopy(record);broken['external_sources']['lease.py']='0'*64
        self.assertFalse(q.source_pins(broken))
        self.assertEqual(len(q.external_source_paths()),12)
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
