import copy
import json
from pathlib import Path
import unittest

from .contracts import ContractError
from .macro_forces import observe_forces,compact_forces

ROOT=Path(__file__).resolve().parents[2]


class ForceObservationTests(unittest.TestCase):
    def fixture(self):
        safe={'templates':{
            '0x19ab11af':dict(template='SovietAntiInfantryInfantry',role='infantry',source_audited_no_intrinsic_stealth=True),
            '0xc16ff13f':dict(template='SovietConstructionYard',role='structure',source_audited_no_intrinsic_stealth=True)}}
        rows=[dict(thing_id=1,type_hash='0x19ab11af',hp=50.,xyz=[1200.,1800.,200.],address='PRIVATE'),
            dict(thing_id=2,type_hash='0xc16ff13f',hp=1.,xyz=[4400.,2016.,210.])]
        return dict(frame=1500,own_objects=rows,enemy_details_read=False),safe

    def test_home_and_mobile_locations_are_presence_with_no_recruitment_claim(self):
        census,safety=self.fixture();v=compact_forces(observe_forces(census,safety),100.)
        self.assertEqual(v['named_unit_counts']['conscript'],1)
        self.assertEqual(v['regions'],[dict(region_id='region_8_3',mobile=0,construction_yards=1),
            dict(region_id='region_2_3',mobile=1,construction_yards=0)])
        self.assertFalse(v['recruitability_verified']);self.assertFalse(v['ready_for_combat_verified'])
        for private in ('PRIVATE','xyz','thing_id','0x','hp'):self.assertNotIn(private,json.dumps(v))

    def test_unknown_templates_are_counted_as_unclassified_without_guessing_role(self):
        census,safety=self.fixture();census['own_objects'][0]['type_hash']='unknown'
        v=observe_forces(census,safety)
        self.assertEqual(v['unclassified_objects'],1);self.assertEqual(v['mobile_role_counts'],{})
        self.assertEqual(v['named_unit_counts']['conscript'],0)

    def test_foreign_details_duplicates_and_nonfinite_positions_cannot_be_projected(self):
        for change in ('foreign','duplicate','nan','wrong_template'):
            census,safety=self.fixture()
            if change=='foreign':census['enemy_details_read']=True
            elif change=='duplicate':census['own_objects'].append(copy.deepcopy(census['own_objects'][0]))
            elif change=='nan':census['own_objects'][0]['xyz'][0]=float('nan')
            else:safety['templates']['0x19ab11af']['template']='SovietEngineer'
            with self.assertRaises(ContractError):observe_forces(census,safety)

    def test_region_limit_preserves_home_and_reports_omissions(self):
        census,safety=self.fixture()
        for i in range(3,12):
            census['own_objects'].append(dict(thing_id=i,type_hash='0x19ab11af',hp=50.,xyz=[512.*i,512.,0.]))
        v=compact_forces(observe_forces(census,safety),100.)
        self.assertEqual(len(v['regions']),4);self.assertEqual(v['omitted_region_count'],7)
        self.assertEqual(v['regions'][0]['construction_yards'],1)
        self.assertEqual(sum(v['mobile_role_counts'].values()),10)

    def test_stale_private_fields_and_false_readiness_claims(self):
        value=observe_forces(*self.fixture());value.update(address='PRIVATE',ready_for_combat_verified=True,recruitability_verified=True)
        value['regions'][0]['native_id']='PRIVATE'
        v=compact_forces(value,100.)
        self.assertNotIn('PRIVATE',json.dumps(v));self.assertFalse(v['recruitability_verified'])
        with self.assertRaisesRegex(ContractError,'stale'):compact_forces(value,103.)
        value['regions'][0]['mobile']=8000
        with self.assertRaisesRegex(ContractError,'consistency'):compact_forces(value,100.)

    def test_actual_frozen_roster_reports_five_flak_units_without_unit_ids(self):
        safety=json.loads((ROOT/'reports/macro-visibility-4a65c9b6-derived-20261028-v1/template-safety.json').read_text())
        path=ROOT/'reports/macro-desktop-f12886bd-6242-497a-9fdd-87a4862102e7/policy-probe.jsonl'
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line);census=row.get('observation',{}).get('construction_feedback')
                if row['kind']=='macro_observation' and census and census['frame']==3543:break
            else:self.fail('frozen own roster missing')
        value=compact_forces(observe_forces(census,safety),3543/15)
        self.assertEqual(value['named_unit_counts']['flak_trooper'],5)
        self.assertEqual(value['named_unit_counts']['conscript'],0)
        self.assertEqual(value['named_unit_counts']['hammer_tank'],0)
        self.assertFalse(value['recruitability_verified'])
        self.assertLess(len(json.dumps(value)),2048)

    def test_provider_receives_current_presence_and_defers_stale_observation(self):
        from .macro_policy_runtime import MacroRequestAudit
        facts=observe_forces(*self.fixture())
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1500,native_effect_verified=False)
        audit=MacroRequestAudit(None,lambda *a,**k:None,feedback_supplier=lambda:budget,forces_supplier=lambda:facts)
        value=audit.prepare(dict(game_time_seconds=100.,working_memory={}))
        self.assertEqual(value['own_forces']['named_unit_counts']['conscript'],1)
        self.assertFalse(value['own_forces']['recruitability_verified'])
        self.assertTrue(audit.fresh_for_game_seconds(100.))
        facts['observed_frame']=1469
        self.assertFalse(audit.fresh_for_game_seconds(100.))
        with self.assertRaisesRegex(ContractError,'stale'):audit.prepare(dict(game_time_seconds=100.))


if __name__=='__main__':unittest.main()
