import struct
import tempfile
import unittest
from pathlib import Path

from test_macro_observation import Memory
from macro_area_defense_observation import sample_runtime,STATIC_DEFENSE_RUNTIME_VTABLE
from verify_area_defense_observer import verify


class AreaDefenseObserverTests(unittest.TestCase):
    def test_extension_retains_all_qualified_checks_and_has_no_field_grant(self):
        result=verify();self.assertTrue(result['strict_parsers_and_owner_checks_preserved'])
        self.assertFalse(result['new_tactic_field_layout_verified']);self.assertFalse(result['execution_capability_granted'])

    def test_any_other_parser_change_is_rejected(self):
        root=Path(__file__).parent
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            for name in ('macro_observation.py','macro_area_defense_observation.py'):
                (out/name).write_bytes((root/name).read_bytes())
            file=out/'macro_area_defense_observation.py'
            file.write_text(file.read_text().replace('u(0x2c)!=owner','u(0x2c)==0'),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'unreviewed_observer_change'):verify(out)

    def test_synthetic_static_defense_retains_owner_and_intrusive_link_checks(self):
        memory=Memory();args=memory.runtime();memory.put(args[0],struct.pack('<I',STATIC_DEFENSE_RUNTIME_VTABLE))
        self.assertEqual(sample_runtime(memory.read,*args)['native_tactic_family'],'static_defense')
        memory.put(args[0]+0x2c,struct.pack('<I',args[1]+4))
        with self.assertRaisesRegex(ValueError,'runtime_binding'):sample_runtime(memory.read,*args)


if __name__=='__main__':unittest.main()
