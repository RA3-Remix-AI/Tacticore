"""Finite capacity reserve, retained lawful fixture, no Native or HTTP calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from host_runtime.model_capacity import check_model_capacity
from host_runtime.profiles import normalize_profile
from host_runtime.macro_group_role_contract import group_role_catalog_overrides
from test_strategic_wire import Wire,SOURCE,ROOT,WIRE_ARCHIVE_AVAILABLE


# Guard only archive-backed cases: the isolated pure import stays portable.
class Capacity(unittest.TestCase):
    def test_core_reserves_own_presence_and_continuing_expansion_without_duplicate_strategy(self):
        from fixtures import binding,snapshot
        from engine import Snapshot
        from macro_policy import ACTIONS
        from host_runtime.strategic_contract import FLAG_ACTIONS,GATE_ACTIONS
        from host_runtime.model_capacity import _capacity_envelope
        from host_runtime.macro_forces import NAMED_BUILDINGS
        identity=binding();raw=snapshot()
        actions=FLAG_ACTIONS+tuple(GATE_ACTIONS)
        raw['capabilities']['regions']=['region_1_3','region_8_3']
        targets={action:'region_1_3' if action=='deployattack' else 'region_8_3'
            for action in actions if ACTIONS[action]=='deployment'}
        raw['macro_control']=dict(mode='macro_native',available_actions=list(actions),region_targets=targets)
        observed=Snapshot.from_dict(raw)
        catalog=observed.model_context(identity)['macro_policy_catalog']
        catalog.update(group_role_catalog_overrides())
        effective=normalize_profile(dict(schema_version=1,profile_id=identity.commander_id,
            name='Offline',revision=1,connection_id=identity.connection_id,model='fixture-model',
            doctrine='defense',custom_traits=''))
        envelope=_capacity_envelope(effective,observed,catalog)
        self.assertEqual(set(envelope['own_forces']['building_presence_counts']),set(NAMED_BUILDINGS))
        self.assertEqual(envelope['own_forces']['observed_frame'],'CAPACITY_ONLY_FRAME')
        self.assertEqual(len(envelope['macro_unified_feedback']['observations']),5)
        from macro_policy import restore_public_defaults
        self.assertEqual(len(restore_public_defaults(envelope)['macro_execution_feedback']['native_account_shares']),6)
        from macro_policy import BUDGET_PRESETS
        projected=restore_public_defaults(envelope)['macro_policy_catalog']
        for action,shares in BUDGET_PRESETS.items():
            self.assertEqual(projected[action]['native_account_shares'],shares)
        self.assertNotIn('macro_strategy',envelope['working_memory']['current_strategy'])
        result=check_model_capacity(effective,'DeepSeek',raw,catalog)
        self.assertTrue(result['fits'])
        self.assertFalse(result['native_authority_granted'])

    def test_both_qualified_fourteen_action_grammars_fit_but_their_union_is_refused(self):
        from fixtures import binding,snapshot
        from macro_policy import ACTIONS,public_descriptions
        from host_runtime.model_capacity import LEGACY_ACTIONS,NATIVE_TARGET_ACTIONS
        identity=binding()
        effective=normalize_profile(dict(schema_version=1,profile_id=identity.commander_id,name='Offline',
            revision=1,connection_id=identity.connection_id,model='fixture-model',doctrine='assault',
            custom_traits='己方中等原生电脑在1v2中自然战胜两名同队凶残电脑。'))
        for actions in (LEGACY_ACTIONS,NATIVE_TARGET_ACTIONS):
            targets={a:'region_1_3' if a=='deployattack' else 'region_8_3'
                     for a in actions if ACTIONS[a]=='deployment'}
            raw=snapshot(capabilities=dict(production_focus=['native_baseline'],regions=['region_1_3','region_8_3']),
                macro_control=dict(mode='macro_native',available_actions=['budgetarmy'],production_counts={},region_targets={}))
            catalog=public_descriptions(sorted(actions),region_targets=targets)
            catalog.update(group_role_catalog_overrides())
            result=check_model_capacity(effective,'DeepSeek',raw,catalog)
            self.assertTrue(result['fits']);self.assertEqual(result['catalog_action_count'],14)
        mixed=dict(catalog,deployattack=public_descriptions(['deployattack'],region_targets={'deployattack':'region_1_3'})['deployattack'])
        with self.assertRaisesRegex(ValueError,'fixed_grammar'):
            check_model_capacity(effective,'DeepSeek',raw,mixed)

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
                result=check_model_capacity(style,provider,raw,catalog)
                self.assertIs(result['fits'],fits)
                self.assertFalse(result['native_authority_granted'] or result['model_request_created'])
                self.assertNotIn('context',result);self.assertEqual(result['maximum_bytes'],16384)
        self.assertEqual(styles[1].traits_bytes,1200);self.assertEqual(styles[2].traits_bytes,1200)
        self.assertEqual(raw,before)

    @unittest.skipUnless(WIRE_ARCHIVE_AVAILABLE,
        'requires unpublished desktop-bcd88e90 trial events, profile and snapshots')
    def test_missing_provider_or_unqualified_catalog_is_not_capacity_permission(self):
        raw,catalog,styles=self.fixture()
        with self.assertRaises(ValueError):check_model_capacity(styles[0],None,raw,catalog)
        catalog.pop('expand')
        with self.assertRaises(ValueError):check_model_capacity(styles[0],'DeepSeek',raw,catalog)

    def test_actual_isolated_desktop_bridge_can_import_pure_checker(self):
        code='import sys;sys.path[:0]='+repr([str(ROOT/'integration'),str(ROOT/'.venv/Lib/site-packages')])+ ';from host_runtime.model_capacity import check_model_capacity;print("isolated checker import OK")'
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('import OK',result.stdout)

if __name__=='__main__':unittest.main()
