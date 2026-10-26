import unittest,uuid
from formations import FormationRegistry

def unit(ident,kind='0x19ab11af',hp=100):return dict(object_id=ident,type_hash=kind,hp=hp,xyz=[ident,0,0])

class FormationTests(unittest.TestCase):
    def setUp(self):self.registry=FormationRegistry(str(uuid.uuid4()));self.units=[unit(i) for i in range(1,7)]+[unit(7,'0x2c358c61')]
    def refresh(self,units=None,eligible=None):return self.registry.refresh(self.units if units is None else units,set(range(1,8)) if eligible is None else eligible,lambda point:'home_base')
    def test_formations_disjoint_and_no_native_ids_in_public(self):
        public=self.refresh();private=list(self.registry.private.values())
        self.assertEqual(len(public),2)
        self.assertFalse(set(private[0]['object_ids'])&set(private[1]['object_ids']))
        self.assertTrue(any(len(form['roles'])==2 for form in public))
        self.assertNotIn('object_ids',str(public));self.assertNotIn('xyz',str(public))
    def test_roster_version_changes_only_with_membership(self):
        first=self.refresh();second=self.refresh()
        self.assertEqual(first,second)
        replaced=[unit(99) if u['object_id']==1 else u for u in self.units]
        third=self.refresh(replaced,set(range(2,8))|{99})
        changed=next(x for x in third if x['formation_id']==first[0]['formation_id'])
        self.assertGreater(changed['version'],first[0]['version'])
    def test_leased_units_never_recruited_into_another_roster(self):
        public=self.refresh();fid=public[0]['formation_id'];held=set(self.registry.private[fid]['object_ids'])
        self.registry.reserve([fid]);self.refresh()
        for other,record in self.registry.private.items():
            if other!=fid:self.assertFalse(held&set(record['object_ids']))
        self.assertFalse(next(x for x in self.refresh() if x['formation_id']==fid)['available'])
    def test_dead_or_unverified_units_excluded(self):
        self.assertEqual(self.refresh([unit(1,hp=0),unit(2,'0x33026fa1')],{1,2}),[])
    def test_leased_units_still_described_when_native_readiness_excludes_script_team(self):
        first=self.refresh();main=first[0]['formation_id'];self.registry.reserve([main])
        available=set(range(1,8))-set(self.registry.private[main]['object_ids'])
        current=self.refresh(eligible=available)
        self.assertEqual(len(current),2)
        self.assertEqual(next(f for f in current if f['formation_id']==main)['roles'],first[0]['roles'])
    def test_controller_claims_exclude_live_eligible_units_and_invalidate_old_roster(self):
        original=self.refresh();fid=original[0]['formation_id']
        forms=self.registry.refresh(self.units,set(range(1,8)),lambda point:'home_base',claimed_ids={1,7})
        self.assertFalse({1,7}&{oid for f in self.registry.private.values() for oid in f['object_ids']})
        self.assertGreater(next(f for f in forms if f['formation_id']==fid)['version'],original[0]['version'])
        self.refresh()
        self.assertTrue({1,7}<={oid for f in self.registry.private.values() for oid in f['object_ids']})
    def test_external_controller_cannot_take_an_existing_inflight_formation(self):
        first=self.refresh();fid=first[0]['formation_id'];self.registry.reserve([fid])
        actor=self.registry.private[fid]['object_ids'][0]
        with self.assertRaisesRegex(ValueError,'already allocated'):
            self.registry.refresh(self.units,set(range(1,8)),lambda point:'home_base',claimed_ids={actor})
    def test_air_is_unavailable_without_purpose_evidence(self):
        self.assertEqual(self.refresh([unit(90,'0x40acad6d')],{90}),[])
    def test_air_scout_is_separate_and_never_joins_ground_force(self):
        self.registry=FormationRegistry(str(uuid.uuid4()),air_scout=True)
        forms=self.refresh(self.units+[unit(90,'0x40acad6d'),unit(91,'0x40acad6d')],set(range(1,8))|{90,91})
        scout=next(f for f in forms if f['roles']=={'air':1})
        self.assertEqual(self.registry.private[scout['formation_id']]['object_ids'],[90])
        self.assertTrue(all(90 not in value['object_ids'] and 91 not in value['object_ids'] for fid,value in self.registry.private.items() if fid!=scout['formation_id']))
        self.registry.reserve([scout['formation_id']])
        updated=self.refresh(self.units+[unit(91,'0x40acad6d')],set(range(1,8))|{91})
        self.assertNotIn(scout['formation_id'],[f['formation_id'] for f in updated])
        self.assertEqual(self.registry.private[scout['formation_id']]['object_ids'],[90])

if __name__=='__main__':unittest.main()
