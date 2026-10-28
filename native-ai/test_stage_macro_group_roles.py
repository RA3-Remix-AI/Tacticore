import unittest
from pathlib import Path
import xml.etree.ElementTree as E
from stage_commanders import q
from stage_macro_base_defense import generate_area_defense
from stage_macro_group_roles import generate_group_roles,REPLACEMENTS


class GroupRoleCandidateTests(unittest.TestCase):
    def test_only_unqualified_build_states_and_personality_entries_change(self):
        raw=(Path(__file__).resolve().parents[1]/'reports/macro-temple-map-20261028-v1/Maps5.map.inner').read_bytes()
        c='57e668b4-4d89-43bd-bc92-0dd436f046ef'
        original,old=generate_area_defense(c,3,[],raw);xml,r=generate_group_roles(c,3,[],raw)
        a,b=E.fromstring(original),E.fromstring(xml)
        removed={x['state'].split(':',1)[1] for x in old['consumers'] if x['action'] in {v[0] for v in REPLACEMENTS}}
        def normal(node):
            node=E.fromstring(E.tostring(node))
            for x in node.iter():x.text=(x.text or '').strip() or None;x.tail=None
            return E.tostring(node)
        for node in a:
            if node.get('id') in removed or node.tag==q('AIPersonalityDefinition'):continue
            match=next(n for n in b if n.tag==node.tag and n.get('id')==node.get('id'))
            self.assertEqual(normal(node),normal(match))
        self.assertEqual(r['flags'],old['flags']);self.assertEqual(len(r['assets']),16)
        self.assertTrue(r['assets'][0]['name'].endswith('_Scout'))
        self.assertEqual(len({(x['type_id'],x['instance_id']) for x in r['assets']}),16)
        self.assertFalse(b.findall(q('AIMicroManagerData')))
        for role in r['group_role_candidates']:
            self.assertFalse(role['field_verified']);self.assertFalse(role['capability_granted'])
            node=next(n for n in b if n.get('id')==role['state'].split(':',1)[1]);tactic=node.find(q('Tactic'))
            self.assertFalse(tactic.findall('.//'+q('CreateUnits')))
            self.assertEqual(tactic.get('EndIfStateTurnsOff'),'true')
            if role['action'] in ('regroup','withdraw'):
                self.assertEqual(tactic.get('GatherWaypoint'),'Player_2_Start')
                self.assertEqual(tactic.find(q('TeamTemplate')).get('MicroManager'),'GrowingAttacksMicroManager_MEDIUM')
                if role['action']=='withdraw':
                    self.assertEqual(tactic.find(q('TeamTemplate')).get('Priority'),'COOP')
                    self.assertEqual(tactic.find(q('TeamTemplate')).get('AllowRecruitUnitsInCombat'),'true')
            else:self.assertEqual(tactic.get('Tactic'),'ReactiveDefense')


if __name__=='__main__':unittest.main()
