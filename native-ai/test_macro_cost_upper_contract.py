"""Arithmetic envelope negative cases, no process or SDK calls."""
import copy
import unittest

import macro_cost_upper_contract as c


def inventory():
    objects = []
    for quality in ('high','l','m'):
        for name in sorted(set(c.ACTIONS.values()) | {'SovietConstructionYard'}):
            objects.append(dict(quality=quality,name='GameObject:'+name,
                production_modules=[dict(multipliers=[])] if name in ('SovietConstructionYard','SovietWarFactory') else [],
                production_bonus_modules=[], cost_modifier_upgrade_modules=[],
                compiled_resource_costs=[dict(account=0, amount=850)], payload_sha256='a'*64))
    return dict(kind='native_compiled_cost_source_inventory',schema_version=1,
        package_sha256=c.assets.PACKAGE_SHA256,qualities=['high','l','m'],parsing_errors=[],
        unresolved_payload_aliases=[],objects=objects,
        attribute_modifiers=[dict(stacking_limit=1,production_cost_values=[999.99])],
        player_templates=[dict(production_cost_bonuses=[dict(own=-0.25,allies=-0.05)])])


def target_object(data):
    """Mutate the tested cost target, independently of hash iteration order."""
    name='GameObject:'+c.ACTIONS['producesickle']
    return next(row for row in data['objects'] if row['quality']=='high' and row['name']==name)


class UpperContractTests(unittest.TestCase):
    def test_nonincreasing_all_state_envelope_does_not_grant_native_upper(self):
        result = c.derive_cost_envelope(inventory())
        self.assertTrue(result['discount_envelope_supported'])
        self.assertTrue(result['discount_changes_within_fixed_definition_universe_allowed'])
        self.assertEqual(len(result['target_conditional_ceilings']), 24)
        self.assertTrue(all(row['conditional_base_ceiling']==850 for row in result['target_conditional_ceilings']))
        self.assertEqual(result['producer_attribute_divisor_lower'], 1)
        self.assertIsNone(result['native_upper_cost']); self.assertIsNone(result['native_reserved_credits'])
        for key in ['native_upper_cost_verified','runtime_definition_binding_verified',
                'request_cost_context_verified','reservation_usable','field_verified','grants_capability']:
            self.assertFalse(result[key])

    def test_multiple_providers_and_toggle_off_are_allowed_by_sign_proof(self):
        data = inventory()
        data['player_templates'] += [dict(production_cost_bonuses=[dict(own=0,allies=-0.05)])]*16
        target_object(data)['production_modules'] = [dict(multipliers=[0.5,0.75])]
        target_object(data)['production_bonus_modules'] = [dict(own=-0.25,allies=0)]
        self.assertTrue(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_positive_player_bonus_blocks_base_upper(self):
        data = inventory(); data['player_templates'][0]['production_cost_bonuses'][0]['own']=0.01
        self.assertFalse(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_production_multiplier_over_one_or_negative_or_nan_blocks(self):
        for value in [1.001,-0.1,float('nan')]:
            data = inventory(); target_object(data)['production_modules']=[dict(multipliers=[value])]
            with self.subTest(value=value):
                self.assertFalse(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_object_bonus_source_also_checked(self):
        data = inventory(); target_object(data)['production_bonus_modules']=[dict(own=0,allies=0.01)]
        self.assertIn('object_production_bonus_can_increase_cost',c.derive_cost_envelope(data)['blockers'])

    def test_attribute_below_one_zero_nonfinite_never_assumed_discount(self):
        for value in [0.9,0,float('inf'),float('nan')]:
            data = inventory(); data['attribute_modifiers'][0]['production_cost_values']=[value]
            self.assertFalse(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_dynamic_stacking_is_not_assumed_safe(self):
        data = inventory(); data['attribute_modifiers'][0]['stacking_limit']=2
        self.assertIn('cost_attribute_variable_stacking_not_proven',c.derive_cost_envelope(data)['blockers'])

    def test_unrelated_attribute_stacking_does_not_affect_cost_envelope(self):
        data = inventory(); data['attribute_modifiers'] += [dict(stacking_limit=100,production_cost_values=[])]
        self.assertTrue(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_cost_modifier_upgrade_unknown_not_omitted(self):
        data = inventory(); target_object(data)['cost_modifier_upgrade_modules']=[dict(token_offset=128)]
        self.assertFalse(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_wrong_currency_multi_resource_or_u16_overflow_not_single_base(self):
        for costs in [[dict(account=1,amount=850)], [dict(account=0,amount=65536)],
                [dict(account=0,amount=850),dict(account=1,amount=1)]]:
            data = inventory(); target_object(data)['compiled_resource_costs']=costs
            self.assertFalse(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_missing_quality_target_and_parse_error_block(self):
        for field, value in [('qualities',['high','l']),('parsing_errors',[dict(reason='bad')]),
                ('unresolved_payload_aliases',[dict(name='missing')])]:
            data=inventory();data[field]=value
            self.assertFalse(c.derive_cost_envelope(data)['discount_envelope_supported'])
        data=inventory();data['objects'].remove(target_object(data))
        self.assertFalse(c.derive_cost_envelope(data)['discount_envelope_supported'])

    def test_fixed_package_identity_required(self):
        data=inventory();data['package_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'fixed_inventory'): c.derive_cost_envelope(data)


if __name__=='__main__':unittest.main()
