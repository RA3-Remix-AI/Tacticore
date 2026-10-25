"""Identity and serialization acceptance checks; no game or SDK mutations."""
import copy
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as E
from stage_commanders import (SDK, TYPE, emit_xml, make_registry, q,
                              sage_hash, safe_output, ROOT)


def binding():
    return dict(schema_version=1, game_sync_verified=False,
                instance_key=['session_id', 'player_id', 'commander_id'],
                commanders=[dict(id='12345678-1234-4234-8234-123456789abc', name='铁锤',
                                 connection_id='aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
                                 model_override='', effective_model='test-model', personality=0)])


class CommanderStagingTests(unittest.TestCase):
    def test_known_compiled_personality_hashes(self):
        for name, expected in [('4TFLLMAllied', 0x974c1e66),
                               ('4TFLLMJapan', 0xc3b03015),
                               ('4TFLLMSoviet', 0x8f4ead8a),
                               ('4TFLLMRandom', 0x4ebfb10f)]:
            self.assertEqual(sage_hash(name.lower()), expected)

    def test_rename_retains_all_native_ids_and_localization_keys(self):
        source = binding()
        before = make_registry(source, [])
        source['commanders'][0]['name'] = '重命名后的堡垒'
        source['commanders'][0]['id'] = source['commanders'][0]['id'].upper()
        after = make_registry(source, [])
        self.assertEqual(before['commanders'][0]['assets'], after['commanders'][0]['assets'])
        self.assertEqual(before['identity_revision'], after['identity_revision'])
        self.assertNotEqual(before['registry_revision'], after['registry_revision'])

    def test_chinese_xml_punctuation_preserved_as_localized_data(self):
        source = binding()
        source['commanders'][0]['name'] = '''铁锤 & <先锋> "一号" '指挥官' '''
        registry = make_registry(source, [])
        template = E.parse(SDK / 'SAGEXML/SkirmishAI/Personalities/RandomPersonalities.xml').getroot().find(q(TYPE))
        xml = emit_xml(registry, template)
        root = E.fromstring(xml)
        self.assertEqual(len(root.findall(q(TYPE))), 4)
        self.assertNotIn('<先锋>'.encode('utf-8'), xml)  # names never become XML syntax
        strings = {c['assets'][0]['localization_key']: c['name'] for c in registry['commanders']}
        roundtrip = json.loads(json.dumps(strings, ensure_ascii=False))
        self.assertEqual(next(iter(roundtrip.values())), source['commanders'][0]['name'])
        for asset in registry['commanders'][0]['assets']:
            self.assertEqual(root.find(q(TYPE) + "[@id='" + asset['asset_id'] + "']").get('PersonalityUIName'), next(iter(strings)))

    def test_duplicate_uuid_case_and_format_rejected(self):
        source = binding()
        extra = copy.deepcopy(source['commanders'][0])
        extra['id'] = extra['id'].replace('-', '').upper()
        extra['name'] = '另一个名字'
        source['commanders'].append(extra)
        with self.assertRaisesRegex(ValueError, 'Duplicate canonical'):
            make_registry(source, [])

    def test_generated_hash_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, 'hash collision'):
            make_registry(binding(), [], hash_fn=lambda _: 0x12345678)

    def test_existing_baseline_collision_rejected(self):
        asset = make_registry(binding(), [])['commanders'][0]['assets'][0]
        baseline = dict(type_id=int(asset['type_id'], 16), instance_id=int(asset['instance_id'], 16), name='ReservedFixture')
        with self.assertRaisesRegex(ValueError, 'hash collision'):
            make_registry(binding(), [baseline])

    def test_no_secrets_endpoints_or_verified_claim(self):
        source = binding()
        source['base_url'] = 'https://sentinel.invalid/v1'
        source['api_key'] = 'sentinel-secret-never-export'
        source['game_sync_verified'] = True
        registry = make_registry(source, [])
        serialized = json.dumps(registry)
        self.assertFalse(registry['game_sync_verified'])
        self.assertFalse(registry['side_binding_verified'])
        self.assertNotIn('sentinel', serialized)
        self.assertNotIn('base_url', serialized)
        self.assertNotIn('api_key', serialized)
        source['commanders'][0]['api_key'] = 'another-sentinel'
        with self.assertRaisesRegex(ValueError, 'Unexpected commander fields'):
            make_registry(source, [])

    def test_control_character_and_output_outside_staging_rejected(self):
        source = binding(); source['commanders'][0]['name'] = '铁\x00锤'
        with self.assertRaisesRegex(ValueError, 'control character'):
            make_registry(source, [])
        with self.assertRaisesRegex(ValueError, 'native-ai/staging'):
            safe_output(SDK / 'Mods/ShouldNeverBeWritten')
        with self.assertRaisesRegex(ValueError, 'native-ai/staging'):
            safe_output(ROOT.parent.parent / 'Mods/ShouldNeverBeWritten')


if __name__ == '__main__':
    unittest.main(verbosity=2)
