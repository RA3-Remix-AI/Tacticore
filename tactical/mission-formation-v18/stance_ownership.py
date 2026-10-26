"""Independent STN1 normal stance ownership evidence. No engine access or authority."""
import importlib.util
from pathlib import Path
_actor_spec=importlib.util.spec_from_file_location('mf18_actual_slot_actor',Path(__file__).with_name('actor_binding.py'));_actors=importlib.util.module_from_spec(_actor_spec);_actor_spec.loader.exec_module(_actors)
MAGIC=0x53544e31
HOLD_STATE=94
HOLD_VTABLE=0xc551a0
MODULE_VTABLE=0xc37f90

def words(e):
 w=e.get('stack_words')
 return w[:68] if e.get('stack_word_count')==68 and isinstance(w,list) and 68<=len(w)<=128 and all(type(x) is int and 0<=x<=0xffffffff for x in w) and w[:2]==[MAGIC,1] else None

def definition(w):
 if not w or not 1<=w[18]<=4:return False
 entries=w[19:27];pairs=[entries[i:i+2] for i in range(0,2*w[18],2)];enums=[p[0] for p in pairs]
 return all(x<=3 for x in enums) and len(set(enums))==len(enums) and {0,2}<=set(enums) and entries[2*w[18]:]==[0]*(8-2*w[18]) and w[13]>0 and w[14]==MODULE_VTABLE and w[15]==w[6] and w[16]>0 and w[17]>0 and w[52:56]==[w[13],w[16],w[17],w[18]] and w[56:64]==entries and w[28]==0 and w[65]==1

def sample(e,hold=False):
 w=words(e)
 if not definition(w):return False
 bound=w[3]==e.get('role') and w[4]==w[5]==e.get('frame') and w[7]==e.get('unit_id') and w[9]==e.get('owner') and w[10]>0 and w[11]==0xc48670 and w[12]==w[6] and w[30]==w[6] and w[34]==w[29] and w[29]==e.get('sm') and w[31]==e.get('state') and w[32]==e.get('state_id') and w[35]==e.get('sm_flags') and w[36]==e.get('path') and w[37]==e.get('source')
 return bool(bound and (w[32]!=94 or w[33]==HOLD_VTABLE) and (not hold or w[27]==2 and w[32:34]==[HOLD_STATE,HOLD_VTABLE] and e.get('source')==1 and e.get('path')==e.get('holder')==0 and not e.get('sm_flags',0xffff)&0xffff))

def audit(report):
 try:return _audit(report)
 except (KeyError,TypeError,ValueError,IndexError):return dict(verified=False,checks={'well_formed_stance_evidence':False},roles=[],source_authority_granted=False)

def _audit(report):
 ev=report.get('events',[]);n=report.get('native',{});pre=report.get('preflight',{});out=[]
 checks=dict(actual_dual_capture=True,raw_actor_module_definitions=True,normal_set_and_restore=True,all_leased_samples_in_owned_stance=True,callback_stop2_separate=True,no_foreign_setter=True,header_event_conservation=True,setter_scope_only_source2_stop=True)
 for role in (0,1):
  rows=[e for e in ev if e.get('role')==role];actor=_actors.actor(report,role);num=lambda x:int(x,0) if isinstance(x,str) else x
  captures=[e for e in rows if e.get('kind')==132];borrow=[e for e in rows if e.get('kind')==1 and e.get('tag')==1];returns=[e for e in rows if e.get('kind')==15 and e.get('tag')==3]
  capture=captures[0] if len(captures)==1 else {};cw=words(capture);end=returns[0]['seq'] if len(returns)==1 else len(ev)+1
  checks['actual_dual_capture'] &= bool(cw and len(borrow)==1 and capture['seq']<borrow[0]['seq']<end and cw[2]==5 and cw[27]==cw[28]==0 and cw[64]==capture['frame'])
  proofs=[e for e in rows if e.get('seq',0)>=capture.get('seq',float('inf')) and words(e) is not None];required=[e for e in rows if capture and e['seq']>=capture['seq'] and e.get('kind') not in (20,21,24,25) and not 110<=e.get('kind',0)<=125 and not 140<=e.get('kind',0)<=167 and e.get('kind') not in (169,172,173)]
  checks['raw_actor_module_definitions'] &= bool(cw) and all(sample(e) and (lambda w:w[6]==num(actor.get('address')) and w[7]==actor.get('object_id') and w[8]==num(actor.get('type_hash')) and w[9]==num(pre.get('owner')) and w[10]==num(actor.get('ai_address')) and w[13:27]==cw[13:27] and w[28]==0 and w[52:65]==cw[52:65])(words(e)) for e in proofs) and all(words(e) is not None for e in required)
  setters=[e for e in rows if e.get('kind') in (130,131)];transactions=[]
  for before,after in zip(setters[::2],setters[1::2]):
   a=words(before);b=words(after);transactions.append((before,after,a,b))
  good=len(setters)==4 and len(transactions)==2 and all(a and b and before['kind']==130 and after['kind']==131 and before['seq']<after['seq'] and before['frame']==after['frame'] and before.get('tag')==after.get('tag')==tag and a[2]==step and b[2]==step+1 and a[46]==b[46]==cw[13] and a[47]==b[47]==desired and a[27]==old and b[27]==desired and a[48]==0 and b[48]==after.get('arg')==1 and before.get('arg')==desired and a[49]==b[49]==before.get('caller') and a[49]>0 and a[44:46]==b[44:46]==counts for (before,after,a,b),(tag,step,desired,old,counts) in zip(transactions,[(7,1,2,0,[1,0]),(8,3,0,2,[1,1])]))
  if good:good=borrow[0]['seq']<transactions[0][0]['seq']<transactions[0][1]['seq']<transactions[1][0]['seq']<transactions[1][1]['seq']<end
  checks['normal_set_and_restore'] &= bool(good) and all(words(e) and words(e)[27]==0 and words(e)[67]==1 for e in rows if e.get('kind') in (5,14,15,16,17) and e.get('tag')==3)
  ad=_actors.stance_admission(report,role)
  checks['actual_dual_capture'] &= bool(cw) and ad.get('mutations') is False and all(ad.get(k)==v for k,v in dict(module=cw[13],vtable=cw[14],backref=cw[15],data=cw[16],definition_list=cw[17],definition_count=cw[18],definition_entries=cw[19:19+2*cw[18]],original_enum=0).items())
  samples=[e for e in rows if e.get('kind')==3 and borrow and borrow[0]['seq']<e['seq']<end];checks['all_leased_samples_in_owned_stance'] &= bool(samples) and all(sample(e) and words(e)[27]==2 for e in samples)
  auto=[e for e in rows if e.get('kind') in (30,32,33,31) and e.get('tag') in (7,8)];facade=[e for e in auto if e['kind']==30];private=[e for e in auto if e['kind']==33]
  checks['callback_stop2_separate'] &= all(e.get('arg')==2 and any(before['seq']<e['seq']<after['seq'] and before.get('tag')==e.get('tag') for before,after,a,b in transactions) for e in auto) and len(auto)==4*len(facade)==4*len(private) and all([e['kind'] for e in auto if e.get('tag')==tag]==[30,32,33,31]*sum(e.get('tag')==tag for e in facade) for tag in (7,8))
  checks['setter_scope_only_source2_stop'] &= not any(e.get('tag') in (7,8) and e.get('kind') in (10,11,12,13,14,15,16,17,18,19,34,35,50,51) for e in rows) and all(e.get('frame')==before.get('frame') and e.get('arg')==2 and (e.get('kind') not in (32,33) or e.get('caller')==0x787791) for e in auto for before,after,a,b in transactions if before['seq']<e['seq']<after['seq'])
  dispatches=[e for e in rows if e.get('kind') in (124,125) and e.get('tag') in (7,8)]
  checks['setter_scope_only_source2_stop'] &= all(e.get('stack_word_count')==80 and isinstance(e.get('stack_words'),list) and len(e['stack_words'])>=80 and e['stack_words'][0]==0x44473131 and e['stack_words'][22]==1 and e['stack_words'][28:30]==[5,2] and any(before['seq']<e['seq']<after['seq'] and before.get('tag')==e.get('tag') for before,after,a,b in transactions) for e in dispatches)
  checks['no_foreign_setter'] &= not any(e.get('kind')==133 or e.get('kind') in (130,131) and e.get('tag') not in (7,8) or words(e) and words(e)[66]!=0 for e in rows)
  states=n.get('stances',[]);h=states[role] if isinstance(states,list) and len(states)==2 else {};expected=dict(module=cw[13],vtable=cw[14],backref=cw[15],data=cw[16],definition_list=cw[17],definition_count=cw[18],definition_entries=cw[19:27],original_enum=0,capture_frame=cw[64]) if cw else {}
  expected.update(set_calls=1,set_return=1,set_before=0,set_after=2,restore_calls=1,restore_return=1,restore_before=2,restore_after=0,restored=1,automatic_stop2=len(facade),private_automatic_stop2=len(private),foreign_calls=0)
  checks['header_event_conservation'] &= bool(cw) and all(h.get(k)==v for k,v in expected.items())
  out.append(dict(role=role,original_stance_restored=bool(good and h.get('restored')==h.get('restore_return')==1 and h.get('restore_after')==0 and all(words(e) and words(e)[27]==0 and words(e)[67]==1 for e in rows if e.get('kind') in (5,14,15,16,17) and e.get('tag')==3)),capture_seq=capture.get('seq'),setter_pairs=[[a['seq'],b['seq']] for a,b,_,_ in transactions],automatic_source2_stops=len(private),explicit_source1_stops=sum(e.get('kind')==33 and e.get('tag')==4 and e.get('arg')==1 for e in rows)))
 return dict(verified=all(v is True for v in checks.values()),checks=checks,roles=out,source_authority_granted=False)
