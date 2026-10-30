"""Finite capacity reserve, retained lawful fixture, no Native or HTTP calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from host_runtime.native5_capacity_preflight_v1 import check_native5_capacity
from host_runtime.profiles import normalize_profile
from host_runtime.macro_group_role_contract import group_role_catalog_overrides
from test_strategic_unified_wire_v5 import Wire,SOURCE,ROOT,WIRE_ARCHIVE_AVAILABLE


# Guard only archive-backed cases: the isolated pure import stays portable.
class Capacity(unittest.TestCase):
    def fixture(self):
        agent,*_=Wire().fixture(False)
        record=json.loads((SOURCE/'profile.json').read_bytes())
        draft=dict(record['draft'],model=record['effective']['model'])
        ordinary=normalize_profile(draft);draft=dict(draft,custom_traits='')
        base=normalize_profile(draft);remaining=1200-len(base.traits.encode())-1
        normal='根据已知情报调整战略。'*100
        while len(normal.encode())>remaining:normal=normal[:-1]
        normal+='a'*(remaining-len(normal.encode()))
        chinese=normalize_profile(dict(draft,custom_traits=normal));n=(remaining-800)//2
        escaped=normalize_profile(dict(draft,custom_traits='策'*n+(('"'+chr(92))*400)[:800-n]))
        catalog=agent.latest.model_context(agent.engine.binding)['macro_policy_catalog']
        catalog.update(group_role_catalog_overrides())
        return agent.latest.to_dict(),catalog,(ordinary,chinese,escaped)

    @unittest.skipUnless(WIRE_ARCHIVE_AVAILABLE,
        'requires unpublished desktop-bcd88e90 trial events, profile and snapshots')
    def test_style_bounds_and_metadata_only_for_three_existing_providers(self):
        raw,catalog,styles=self.fixture();before=copy.deepcopy(raw)
        for style,fits in zip(styles,(True,True,False)):
            for provider in ('DeepSeek','OpenAI','自定义'):
                result=check_native5_capacity(style,provider,raw,catalog)
                self.assertIs(result['fits'],fits)
                self.assertFalse(result['native_authority_granted'] or result['model_request_created'])
                self.assertNotIn('context',result);self.assertEqual(result['maximum_bytes'],16384)
        self.assertEqual(styles[1].traits_bytes,1200);self.assertEqual(styles[2].traits_bytes,1200)
        self.assertEqual(raw,before)

    @unittest.skipUnless(WIRE_ARCHIVE_AVAILABLE,
        'requires unpublished desktop-bcd88e90 trial events, profile and snapshots')
    def test_missing_provider_or_unqualified_catalog_is_not_capacity_permission(self):
        raw,catalog,styles=self.fixture()
        with self.assertRaises(ValueError):check_native5_capacity(styles[0],None,raw,catalog)
        catalog.pop('expand')
        with self.assertRaises(ValueError):check_native5_capacity(styles[0],'DeepSeek',raw,catalog)

    def test_actual_isolated_desktop_bridge_can_import_pure_checker(self):
        code='import sys;sys.path[:0]='+repr([str(ROOT/'integration'),str(ROOT/'.venv/Lib/site-packages')])+ ';from host_runtime.native5_capacity_preflight_v1 import check_native5_capacity;print("isolated checker import OK")'
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('import OK',result.stdout)

if __name__=='__main__':unittest.main()
