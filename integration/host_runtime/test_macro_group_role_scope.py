import unittest
import json
import tempfile
from pathlib import Path
from integration.host_runtime.contracts import ContractError
from integration.host_runtime.macro_group_role_scope import verify_role_effect,verify_group_role_field,verify_group_role_fields,HOME,ROOT
from integration.host_runtime.macro_bundle import create_bundle,load_bundle


def sample(frame,offset=0,*,owner='own',active=True):
    members=[dict(owner=owner,thing_id=i,address=str(i),type_hash='own-template',xyz=[HOME[0]-offset,HOME[1]+i,0]) for i in (1,2)]
    return dict(kind='macro_observation',observation=dict(frame=frame,state_scores={'role':dict(score=int(active),group='state')},
        construction_feedback=dict(frame=frame,enemy_details_read=False,own_objects=[]),
        runtimes=[dict(group='state',native_execution_active=True,native_tactic_family='simple_attack',
            owned_groups=[dict(found=True,all_members_resolved=True,members=members)])] if active else []))


class RoleScopeQualificationTests(unittest.TestCase):
    def test_distinct_preserved_native_fields_qualify_each_role_without_requiring_every_attempt_success(self):
        fields=[ROOT/'reports/macro-group-roles-71388-20261028-v1',ROOT/'reports/macro-group-roles-82568-20261028-v1']
        with self.assertRaisesRegex(ContractError,'macro_group_roles_incomplete'):
            verify_group_role_fields(fields[:1],ROOT/'reports/macro-group-role-withdraw-revision-20261028-v1')
        manifest,evidence=verify_group_role_fields(fields,ROOT/'reports/macro-group-role-withdraw-revision-20261028-v1')
        self.assertEqual(manifest['package_sha256'],'bf0bb3105dc9d1124173ff8aa6ccfa15e494ceb550f78e05600092356970c260')
        self.assertGreater(len(evidence),30)

    def test_schema9_pins_role_scope_and_retains_legacy_capabilities(self):
        original=json.loads((ROOT/'reports/macro-group-role-desktop-bootstrap-20261028-v1/macro-budget-bundle.json').read_text())
        args={k:v for k,v in original.items() if k not in ('pins','schema_version','kind')}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bundle.json';public=create_bundle(path,**args)
            self.assertEqual(public['group_roles_granted'],['regroup','reinforce','withdraw'])
            self.assertIn('buildreactor',public['available_actions']);self.assertIn('scout',public['available_actions'])
            value,scope=load_bundle(path);self.assertEqual(value['schema_version'],9)
            self.assertEqual(scope.native_transport_client,'client_group_roles.py')
            changed=json.loads(path.read_text());changed['pins'][str(ROOT/'integration/host_runtime/macro_group_role_scope.py')]='0'*64
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)

    def test_partial_prior_fixed_trial_cannot_grant_three_roles(self):
        with self.assertRaisesRegex(ContractError,'macro_group_roles_incomplete'):
            verify_group_role_field(ROOT/'reports/macro-group-roles-71388-20261028-v1')

    def test_regroup_requires_owned_members_and_release(self):
        rows=[sample(f,100) for f in (10,20,30)]+[sample(f,active=False) for f in (101,102)]
        verify_role_effect(rows,'role','own',1,100,'regroup')
        with self.assertRaisesRegex(ContractError,'foreign_member'):
            verify_role_effect([sample(10,100,owner='foreign')],'role','own',1,100,'regroup')

    def test_near_home_movement_does_not_prove_withdrawal(self):
        rows=[sample(10,200),sample(20,100)]+[sample(f,active=False) for f in (101,102)]
        with self.assertRaisesRegex(ContractError,'effect_or_release_missing'):
            verify_role_effect(rows,'role','own',1,100,'withdraw')

    def test_withdrawal_does_not_require_full_physical_return(self):
        rows=[sample(10,900),sample(20,800)]+[sample(f,active=False) for f in (101,102)]
        verify_role_effect(rows,'role','own',1,100,'withdraw')

    def test_late_withdrawal_sample_does_not_supply_effect(self):
        rows=[sample(10,900),sample(100,800)]+[sample(f,active=False) for f in (101,102)]
        with self.assertRaisesRegex(ContractError,'effect_or_release_missing'):
            verify_role_effect(rows,'role','own',1,100,'withdraw')


if __name__=='__main__':unittest.main()
