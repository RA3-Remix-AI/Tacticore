"""STN1 counterexamples, independently authored raw words; no field authority."""
import copy,unittest
import stance_ownership as m
TYPES=[0x19ab11af,0x2c358c61]

def decorate(e,enum=2,action=0,sets=1,restores=0,capture=110,automatic=0,restored=0,request=0,result=0):
 role=e['role'];thing=[0x2000,0x5000][role];update=[0x4000,0x6000][role];module=0x90000+role*0x1000;data=module+0x100;defs=module+0x200;sm=update+0x100;state=update+0x200
 e.setdefault('sm',sm);e.setdefault('state',state);e.setdefault('state_id',94);e.setdefault('source',1);e.setdefault('path',0);e.setdefault('holder',0);e.setdefault('sm_flags',0)
 w=[0]*68;w[:13]=[m.MAGIC,1,action,role,e['frame'],e['frame'],thing,e.get('unit_id',42+role),TYPES[role],e.get('owner',0x3000),update,0xc48670,thing];w[13:19]=[module,m.MODULE_VTABLE,thing,data,defs,2];w[19:27]=[0,0x9111,2,0x9222,0,0,0,0];w[27:38]=[enum,0,e['sm'],thing,e['state'],e['state_id'],m.HOLD_VTABLE if e['state_id']==94 else 0xc55130,e['sm'],e['sm_flags'],e['path'],e['source']];w[44:46]=[sets,restores]
 if e['kind'] in (130,131):w[46:50]=[module,request,result,0x123456];e['caller']=w[49] if e['kind']==130 else 0
 w[50:56]=[automatic,automatic,module,data,defs,2];w[56:64]=w[19:27];w[64:68]=[capture,1,0,restored];e.update(stack_word_count=68,stack_words=w+[0]*60,stack_count=0);return e

def header(w,automatic=0):
 return dict(module=w[13],vtable=w[14],backref=w[15],data=w[16],definition_list=w[17],definition_count=w[18],definition_entries=w[19:27],original_enum=0,capture_frame=w[64],set_calls=1,set_return=1,set_before=0,set_after=2,restore_calls=1,restore_return=1,restore_before=2,restore_after=0,restored=1,automatic_stop2=automatic,private_automatic_stop2=automatic,foreign_calls=0)

def fixture(callback=True):
 r=dict(preflight=dict(owner='0x3000',selected=dict(address='0x2000',object_id=42,type_hash=hex(TYPES[0]),ai_address='0x4000'),support=dict(address='0x5000',object_id=43,type_hash=hex(TYPES[1]),ai_address='0x6000')),initial_admission=dict(stances=[]),native=dict(stances=[]),events=[])
 def add(kind,role,frame,enum,**v):
  e=dict(seq=len(r['events'])+1,kind=kind,role=role,frame=frame,unit_id=42+role,owner=0x3000,tag=0,arg=0);e.update(v);decorate(e,enum,**e.pop('proof',{}));r['events'].append(e);return e
 for role in (0,1):
  c=add(132,role,110,0,proof=dict(action=5,sets=0));w=m.words(c);h=header(w,1 if callback else 0);r['native']['stances'].append(h);r['initial_admission']['stances'].append({k:v for k,v in h.items() if k in ('module','vtable','backref','data','definition_list','definition_count','original_enum')}|dict(definition_entries=w[19:23],mutations=False));add(1,role,110,0,tag=1,proof=dict(sets=0))
  add(130,role,110,0,tag=7,arg=2,proof=dict(action=1,request=2));add(131,role,110,2,tag=7,arg=1,proof=dict(action=2,request=2,result=1))
  for frame in (111,112,113):add(3,role,frame,2)
  add(130,role,120,2,tag=8,arg=0,proof=dict(action=3,restores=1))
  if callback:
   for kind in (30,32,33,31):add(kind,role,120,0,tag=8,arg=2,caller=0x787791,proof=dict(restores=1,automatic=1))
  add(131,role,120,0,tag=8,arg=1,proof=dict(action=4,restores=1,result=1,automatic=1 if callback else 0));add(15,role,120,0,tag=3,arg=1,proof=dict(restores=1,automatic=1 if callback else 0,restored=1));add(5,role,120,0,tag=3,proof=dict(restores=1,automatic=1 if callback else 0,restored=1))
 return r

class Stance(unittest.TestCase):
 def test_actual_compiled_stance_raw_without_field_or_transfer_claim(self):
  import importlib.util
  from pathlib import Path
  p=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('actual12_stance_decoder',p/'lease.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
  native=w.Tactical.from_buffer_copy((p/'stance-native-positive-v2.bin').read_bytes());r=dict(request={'task_id':'actual_cpp_only'});w.capture(r,native)
  self.assertEqual(len(r['events']),12)
  for role in (0,1):
   rows=[e for e in r['events'] if e['role']==role];self.assertTrue(all(m.definition(m.words(e)) and m.sample(e) for e in rows));self.assertEqual([e['kind'] for e in rows],[132,130,131,3,130,131]);self.assertEqual([m.words(e)[27] for e in rows],[0,0,2,2,2,0]);self.assertEqual(m.words(rows[3])[27],2);self.assertEqual(m.words(rows[3])[32:34],[94,0xc551a0]);self.assertTrue(m.sample(rows[3],hold=True));h=r['native']['stances'][role];self.assertEqual([h[k] for k in ('set_calls','set_return','set_before','set_after','restore_calls','restore_return','restore_before','restore_after','restored')],[1,1,0,2,1,1,2,0,1])
  self.assertFalse(m.audit(r)['verified']) # No actual borrow/Return or preflight in this software trace.
 def test_setter_tag_cannot_hide_unknown_dispatch_with_zero_counters(self):
  r=fixture();e=next(e for e in r['events'] if e['kind']==30);w=[0]*80;w[0]=0x44473131;w[22]=1;w[28:30]=[42,2];e.update(kind=124,stack_word_count=80,stack_words=w+[0]*48);self.assertFalse(m.audit(r)['verified'])
 def test_setter_tag_cannot_authorize_move_or_attack(self):
  for kind in (10,12,16,18,50):
   r=fixture();e=next(e for e in r['events'] if e['kind']==30);e['kind']=kind;self.assertFalse(m.audit(r)['verified'],kind)

 def test_raw_lifecycle_and_callback_counts(self):
  for callback in (False,True):
   a=m.audit(fixture(callback));self.assertTrue(a['verified'],a);self.assertFalse(a['source_authority_granted'])
 def test_counter_cannot_substitute_actual_module_state(self):
  for index,value in [(0,0),(13,123),(14,0),(15,3),(16,0),(18,0),(19,1),(27,0),(28,2),(32,16),(33,0xc55130),(34,0),(36,1),(37,2),(52,123),(65,0),(66,1)]:
   r=fixture();e=next(e for e in r['events'] if e['kind']==3);e['stack_words'][index]=value;self.assertFalse(m.audit(r)['verified'],index)
 def test_hold_needs_real_94_not_guard16(self):
  e=next(e for e in fixture()['events'] if e['kind']==3);self.assertTrue(m.sample(e,hold=True));e['state_id']=16;e['stack_words'][32:34]=[16,0xc55130];self.assertFalse(m.sample(e,hold=True))
 def test_restore_must_precede_original_return(self):
  r=fixture();rows=[e for e in r['events'] if e['role']==0];before=next(e for e in rows if e['kind']==130 and e['tag']==8);before['seq']=1000;self.assertFalse(m.audit(r)['verified'])
 def test_foreign_setter_and_failed_readback_rejected(self):
  for change in ('foreign','readback','return','callback','header','missing','admission'):
   r=fixture();e=next(e for e in r['events'] if e['kind']==131)
   if change=='foreign':e['tag']=0
   elif change=='readback':e['stack_words'][27]=0
   elif change=='return':e['arg']=0
   elif change=='callback':next(e for e in r['events'] if e['kind']==33)['arg']=1
   elif change=='header':r['native']['stances'][0]['restore_after']=2
   elif change=='missing':next(e for e in r['events'] if e['kind']==3).pop('stack_words')
   else:r['initial_admission']['stances'][0]['module']=123
   self.assertFalse(m.audit(r)['verified'],change)
if __name__=='__main__':unittest.main()
