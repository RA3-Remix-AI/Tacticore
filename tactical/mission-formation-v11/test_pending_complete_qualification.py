"""Complete protocol keeps damage, follow, physical homes and returns as gates."""
import copy,unittest
from test_complete_qualification import full_fixture,q
from test_pending_lineage import fixture as ticket_fixture

def delayed_fixture():
 r=full_fixture();ev=r['events'];facade=next(e for e in ev if e['kind']==50);role=facade['role'];u=q.actor(r,role);marker=max((e for e in ev if e['seq']<facade['seq'] and e.get('role')==role and e['kind'] in (81,85,92,95)),key=lambda e:e['seq']);own=[e for e in ev if facade['seq']<=e['seq']<=facade['seq']+3];end=own[-1];assert [e['kind'] for e in own]==[50,10,11,51]
 templates=ticket_fixture()['events'];new=[];counter=0
 for source in templates:
  if source['kind'] in (81,50,51):continue
  counter+=1;e=copy.deepcopy(facade);e.update(seq=-counter,kind=source['kind'],tag=source['tag'],frame=facade['frame']+(source['frame']>100),tick=(facade['frame']+(source['frame']>100))*60,caller=source['caller'],argument_path=source['argument_path'],argument_limit=source['argument_limit']);p=copy.deepcopy(source.get('lineage',{}))
  if p:
   p.update(role=role,mission_stage=facade['mission_stage'],issued_frame=facade['frame'],goal_kind=marker['kind'],goal_event_seq=marker['seq'],own_facade_seq=facade['seq'],slot=int(u['ai_address'],0)+0x310,goal=copy.deepcopy(facade['command_xyz']))
   for name in ('command','unpacked'):
    if p[name][1]==1:p[name][2:5]=[__import__('struct').unpack('<I',__import__('struct').pack('<f',v))[0] for v in p['goal']]
   for name in ('stored_after','observed_slot'):
    if p[name][1]==1:p[name][2:5]=[__import__('struct').unpack('<I',__import__('struct').pack('<f',v))[0] for v in p['goal']]
   if source['kind'] in (110,120,119,115,117):p['observed_this']=int(u['ai_address'],0)+0x24
   elif source['kind'] in (111,112,113,114):p['observed_this']=p['slot']
   elif source['kind']==116:p['observed_this']=int(u['ai_address'],0)
   if source['kind'] in (113,114,116):p['observed_thing']=int(u['address'],0)
   e['lineage']=p
  new.append(e)
 private=next(e for e in new if e['kind']==10)
 for e in new:
  if e['kind'] in (116,117):e['lineage']['private_seq']=private['seq']
 begin=[e for e in new if e['kind'] in (110,120,111,112)];finish=[e for e in new if e['kind']==119];later=[e for e in new if e['frame']>facade['frame']]
 i=ev.index(facade);ev[i:i+4]=[facade]+begin+[end]+finish;at=next(i for i,e in enumerate(ev) if e['frame']>facade['frame']);ev[at:at]=later
 seqmap={e['seq']:i+1 for i,e in enumerate(ev)}
 for e in ev:
  e['seq']=seqmap[e['seq']]
  if e.get('breadcrumb',{}).get('published_seq'):e['breadcrumb']['published_seq']=seqmap[e['breadcrumb']['published_seq']]
  if e.get('lineage'):
   for key in ('goal_event_seq','own_facade_seq','private_seq'):
    if e['lineage'][key]:e['lineage'][key]=seqmap[e['lineage'][key]]
 for rows in r['native']['crumbs']:
  for c in rows:c['published_seq']=seqmap[c['published_seq']]
 return r

class CompletePending(unittest.TestCase):
 def test_complete_deferred_delivery_preserves_every_physical_gate(self):
  r=delayed_fixture();a=q.qualify(r);self.assertEqual(a['status'],'formation_mission_effect_retreat_verified',a);self.assertTrue(a['pending_lineage']['verified']);self.assertTrue(a['pending_lineage']['observed']);self.assertFalse(a['pending_lineage']['field_verified']);self.assertTrue(q.lease_audit(r)['verified'])
 def test_accepted_native_flag_without_raw_chain_cannot_complete(self):
  for kind in (111,112,113,114,115,116,117):
   r=delayed_fixture();r['events']=[e for e in r['events'] if e['kind']!=kind];self.assertEqual(q.qualify(r)['status'],'not_passed',kind)
 def test_lineage_does_not_replace_damage_homes_or_normal_pool_return(self):
  for kind in (20,24,22,91,66,5):
   r=delayed_fixture();r['events']=[e for e in r['events'] if e['kind']!=kind];self.assertEqual(q.qualify(r)['status'],'not_passed',kind)

if __name__=='__main__':unittest.main()
