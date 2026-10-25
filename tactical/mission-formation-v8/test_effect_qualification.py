import copy,struct,unittest
from test_common_qualification import q,fixture

def effect_fixture():
 r=fixture();r['events']=[];n=r['native'];rq=r['request'];rq.update(target_object_id=77,button=dict(command_set_hash='0xb74cf71a',toggle=dict(entry='0xa000',schema='0xa100',asset_id='0x5977a798',asset_type='0x7d464170')));r['private_target']=dict(address=0xb000);r['preflight']['pid']=12
 n.update(attack_issued_frame=120,retreat_started=126,attack_calls=1,attack_facade_calls=1,attack_private_calls=1,damage_count=1,damage_total=5.,commit_own_calls=1,weapon_entry=0x123,weapon_template=0x456,weapon_slot=0x789,weapon_ammo=3,last_ammo=2,shot_samples=1,button=0xa000,button_schema=0xa100,prepare_gate_frame=114,toggle_calls=0,toggle_hook_calls=0,initial_weapon_asset=q.AK,prepare_reconstituted_stops=0)
 r['weapon_asset_binding']=dict(session_id=r['session_id'],pid=12,reported_entry='0x123',reported_template='0x456',asset_type='0x94d4d96e',asset_id='0x447ea26e',method='reported_template_plus4_to_schema_to_asset_header')
 def add(kind,role,frame,**v):
  e=dict(seq=len(r['events'])+1,kind=kind,role=role,frame=frame,tick=frame*60,thread=9,unit_id=42+role,owner=0x3000,x=20. if role else 100.,y=0.,z=210.,own_hp=100.,tag=0,arg=0,source=1,state_id=16,sm_flags=0,path=0,holder=0,lease_stage=0,mission_stage=2,target_visible=1,active_weapon_asset=q.AK,active_weapon_entry=0x123,damage_source=42,target_id=77,damage_before=0.,damage_after=0.,damage_reported=0.);e.update(v);r['events'].append(e);return e
 for role in (0,1):
  for k in (30,32,33,31):add(k,role,108,arg=1,caller=0x787791,tag=4)
 for f in (110,112,114):
  for role in (0,1):add(3,role,f)
 for role in (0,1):add(86,role,114)
 add(37,0,114);add(42,0,114)
 for k in (30,32,33,31):add(k,0,114,arg=1,caller=0x787791,lease_stage=4,tag=4)
 for f in (116,118,120):add(3,0,f,lease_stage=4)
 add(43,0,120,lease_stage=4)
 for k in (34,12,13,35):add(k,0,120,tag=2,lease_stage=1,arg=77,arg_source=1,arg_shots=0x7fffffff)
 add(24,0,124,lease_stage=1,caller=0x7d2946,damage_before=100.,damage_after=95.,damage_reported=5.)
 body=add(20,0,124,lease_stage=1,caller=0x78e313,damage_before=100.,damage_after=95.,damage_reported=5.)
 words=[0]*100;base=0x10000;pointer=base+40*4;words[:6]=[0x78e313,pointer,0xb000,0,0x7ad79e,pointer];packet=[0]*37;packet[0:3]=[0xbe9508,0xbe9318,42];packet[4:6]=[q.AK,q.AK];packet[7]=21;packet[35]=packet[36]=struct.unpack('<I',struct.pack('<f',5.))[0];words[40:77]=packet;body.update(stack_words=words,stack_word_count=100,stack_words_address=base)
 for role in (0,1):add(3,role,125,lease_stage=1)
 add(22,0,125,lease_stage=1,damage_before=3.,damage_after=2.)
 return r

class Effects(unittest.TestCase):
 def test_raw_packet_commit_ammo_and_actual_support(self):
  a=q.effect_audit(effect_fixture());self.assertTrue(a['verified'],a);self.assertEqual(a['source_damage_amount'],5.);self.assertFalse(a['lethal_verified'])
 def test_aggregate_damage_without_packet_is_not_effect(self):
  r=effect_fixture();next(e for e in r['events'] if e['kind']==20)['stack_words']=[];self.assertFalse(q.effect_audit(r)['verified'])
 def test_commit_identity_and_real_amount(self):
  for key,value in [('damage_source',43),('target_id',78),('caller',0),('damage_reported',6.),('tick',1)]:
   r=effect_fixture();next(e for e in r['events'] if e['kind']==24)[key]=value;self.assertFalse(q.effect_audit(r)['verified'],key)
 def test_firing_order_must_be_new_unique_source1_targeted(self):
  for key,value in [('arg_source',0),('arg_shots',1),('arg',78),('target_visible',0)]:
   r=effect_fixture();next(e for e in r['events'] if e['kind']==12)[key]=value;self.assertFalse(q.effect_audit(r)['verified'],key)
 def test_same_entry_and_partial_clip_chain_actual(self):
  for key,value in [('active_weapon_entry',0x234),('active_weapon_asset',0x41872ecc),('damage_before',1.)]:
   r=effect_fixture();next(e for e in r['events'] if e['kind']==22)[key]=value;self.assertFalse(q.effect_audit(r)['verified'],key)
  r=effect_fixture();r['native'].update(weapon_ammo=1,last_ammo=0);e=next(e for e in r['events'] if e['kind']==22);e.update(damage_before=1.,damage_after=0.);self.assertTrue(q.effect_audit(r)['verified'])
 def test_support_must_remain_actual_idle_at_frozen_point(self):
  for key,value in [('x',999.),('state_id',1),('path',1),('source',0)]:
   r=effect_fixture();next(e for e in r['events'] if e['kind']==3 and e['role']==1 and e['frame']==125)[key]=value;self.assertFalse(q.effect_audit(r)['verified'],key)
 def test_visible_nonlethal_scope_cannot_promote_lethal(self):
  r=effect_fixture()
  for e in r['events']:
   if e['kind'] in (20,24):e.update(damage_before=5.,damage_after=0.)
  self.assertFalse(q.effect_audit(r)['verified'])
 def test_hidden_hit_or_future_ammo_not_attributable(self):
  for kind,key,value in [(20,'target_visible',0),(22,'frame',140),(20,'damage_source',999)]:
   r=effect_fixture();next(e for e in r['events'] if e['kind']==kind)[key]=value;self.assertFalse(q.effect_audit(r)['verified'])
 def test_cannot_reuse_one_round_for_two_damage_packets(self):
  r=effect_fixture();hit=copy.deepcopy(next(e for e in r['events'] if e['kind']==20));hit['seq']=len(r['events'])+1;r['events'].append(hit);r['native'].update(damage_count=2,commit_own_calls=2,damage_total=10.);self.assertFalse(q.effect_audit(r)['verified'])
if __name__=='__main__':unittest.main()
