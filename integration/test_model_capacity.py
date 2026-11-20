"""Finite capacity reserve, retained lawful fixture, no Native or HTTP calls."""
from pathlib import Path
import subprocess
import sys
import unittest

from host_runtime.model_capacity import check_model_capacity
from host_runtime.profiles import normalize_profile
from host_runtime.macro_group_role_contract import group_role_catalog_overrides
ROOT=Path(__file__).resolve().parents[1]


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

    def test_actual_isolated_desktop_bridge_can_import_pure_checker(self):
        code='import sys;sys.path[:0]='+repr([str(ROOT/'integration'),str(ROOT/'.venv/Lib/site-packages')])+ ';from host_runtime.model_capacity import check_model_capacity;print("isolated checker import OK")'
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('import OK',result.stdout)

if __name__=='__main__':unittest.main()
