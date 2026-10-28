import copy
import unittest
from derive_macro_package import compare


def fixture():
    row=dict(name='GameObject:Base',source='base.xml',type_id=1,instance_id=2,type_hash=3,instance_hash=4,
        refs=[(1,2)],flags=0,binary_offset=0,binary_size=4,imp_offset=0,imp_size=4,relo_offset=0,relo_size=4)
    base=dict(header=[1,9,2],manifest_refs=b'fixed',rows=[row],files={ext:b'base' for ext in ['bin','imp','relo']})
    current=copy.deepcopy(base);current['rows'].append(dict(row,name='AIStrategicStateDefinition:New',instance_id=5))
    return base,current


class DerivationTests(unittest.TestCase):
    def test_identical_original_and_ai_append(self):
        result=compare(*fixture());self.assertEqual(result['original_assets_preserved'],1)

    def test_ai_target_definition_append_preserves_all_original_visibility_assets(self):
        base,current=fixture();current['rows'][1]['name']='AITargetingHeuristic:PublicWaypoint'
        self.assertEqual(compare(base,current)['added_ai_assets'],['AITargetingHeuristic:PublicWaypoint'])

    def test_every_original_blob_is_required(self):
        for ext in ['bin','imp','relo']:
            base,current=fixture();current['files'][ext]=b'edit'
            with self.assertRaisesRegex(ValueError,'original_payload_changed'):compare(base,current)

    def test_metadata_and_dependency_changes_rejected(self):
        base,current=fixture();current['rows'][0]['refs']=[]
        with self.assertRaisesRegex(ValueError,'metadata_changed'):compare(base,current)
        base,current=fixture();current['manifest_refs']+=b'new'
        with self.assertRaisesRegex(ValueError,'dependencies_or_count'):compare(base,current)

    def test_added_gameobject_or_alias_rejected(self):
        for change in [dict(name='GameObject:New'),dict(instance_id=2)]:
            base,current=fixture();current['rows'][1].update(change)
            with self.assertRaisesRegex(ValueError,'unique_ai_only'):compare(base,current)

    def test_layout_and_original_only_rejected(self):
        base,current=fixture();current['header'][2]=3
        with self.assertRaisesRegex(ValueError,'layout'):compare(base,current)
        base,current=fixture();current['rows'].pop()
        with self.assertRaisesRegex(ValueError,'dependencies_or_count'):compare(base,current)


if __name__=='__main__':unittest.main()
