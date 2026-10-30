"""Conditional base-price envelope from actual compiled discount definitions.

The proof quantifies over discount activation/removal, not frozen current
discounts. It is not a production grant: installed/loaded source closure,
native target-base binding and request/payment context require separate proof.
"""
import hashlib
import math
from pathlib import Path

import macro_cost_asset_audit as assets
import macro_cost_observation as current

PINS = {
    0x4da950: '5153568b318b168b4234578b7a308bd88d3cfb3bc774178b7a308bd38d14fa8b7c24143938741383c0083bc275f55f5eb8020000005b59c20800f30f1040048b7c24188b06f30f11078b4024ba010000003bc2f30f1144240c89542414761583c10c3b01894424147d048d4c24148b1189542414f30f100d0062be000f2fc1721bf30f5cc1f30f2aca33f6f30f59c1f30f11075f8bc65e5b59c20800be010000003bd67e0fd944240cdb442414e8b0f46b00d91f5f8bc65e5b59c20800',
    0x8529b0: '0f57c083ec10538b5c2418f30f100b0f2ec89ff6c444578bf97b2a8b47208d4c241c518d8f90120000f30f114c240c89442420e808d4fffff30f10442408f30f11000f57c0f30f104b080f2ec89ff6c4447b2a8b57208d44241c508d8fac120000f30f114c240c89542420e8d0d3fffff30f10442408f30f11000f57c0f30f104b100f2ec89ff6c4447b2a8b4f208d54241c894c241c528d8fc8120000f30f114c240ce898d3fffff30f10442408f30f11000f57c0f30f104b040f2ec89ff6c4447a20f30f104b0c0f2ec89ff6c4447a12f30f104b140f2ec89ff6c4440f8bf00000008b47208b0c85488cce00568d542420894c24208b0d9c8cce0052e86e66feff8bf085f60f84c60000008d642400f30f104b040f2ec89ff6c4447b2a8b47208d4c240c518d8e90120000f30f114c241489442410e805d3fffff30f10442410f30f11000f57c0f30f104b0c0f2ec89ff6c4447b2a8b57208d44240c508d8eac120000f30f114c241889542410e8cdd2fffff30f10442414f30f11000f57c0f30f104b140f2ec89ff6c4447b2a8b4f208d54240c894c240c528d8ec8120000f30f114c241ce895d2fffff30f10442418f30f11000f57c08b0d9c8cce008d44242050e8a865feff8bf085f60f853effffff5e5f',
    0x8532d0: '83ec18538bd98b43288b48108b0105b0000000568b70048b008d14c5000000002bd0578d3c963bf77461558b6c242c90392e754ff30f1046048b4b28f30f11442410f30f104608f30f11442414f30f10460cf30f11442418f30f104610f30f1144241cf30f1046148d442410f30f11442420f30f10461850f30f11442428e85df6ffff83c61c3bf775a65d5f5e5b83c418c20400',
    0x7c7c20: '83ec188b44241c56508bf1e840e2feff0f57c08b46f48b4ef88b8918040000f30f11442404f30f11442408f30f1144240cf30f11442410f30f11442414f30f11442418f30f1080c4010000f30f11442404f30f1080c8010000f30f11442408f30f1080cc010000f30f1144240cf30f1080d0010000f30f11442410f30f1080d40100008d542404f30f11442414f30f1080d801000052f30f1144241ce8efac08005e83c418c20400',
    0x4ecc60: '81ecb8000000538b9c24c0000000555733ff3bdf8be90f84700600008b03807839008b0de48ccd0074108b40048b51503b54853c0f82520600008b8424cc0000003bc78b51508954241c7d098bcbe81d7dfeff3bc77e0c8944241403c289442410eb0c897c2414c7442410ffffff3f8b138b4d0833c03842385689442440897c2444897c2448894c2410744d8b75283b752c74458b063bc3742f8b0b8b008b51043b500475238b4c2414394e0473638b10528d4c242ce8f5a4f2ff8d442428508d4c2444e857c0010083c6103b752c75c38b7c24448b4424403bc78bf00f849f0000008b0dc48ccd0056e841a7feff85c00f8c800000008b0dc48ccd008b51282b5124c1fa023bc27d288b49248b0c81eb228b44244085c0740950e8b09af2ff83c4045e5f5d32c05b81c4b8000000c2080033c980bdb400000000753a8a9db4000000c685b4000000018b45283b452c74183908740a83c0103b452c75f4eb0a5051508bcde8468effff889db40000008b9c24cc00000083c6083bf70f8561ffffff8b75283b752cc744241c000000000f84840000008b8424cc0000008d49008b3e3bf8740c83c6103b752c75f28bd8eb688b4424148b5c24108946043b453873118b54241852538d4d10894538e8cde61e008b4424203b460473078b0f8b7910eb058b178b7a1485ff74158bcfe8cd6e040084c0750a6a00538bcfe8ffd703008b068b08837924010f865d0400008b9c24cc0000008974241c837c241c008b542414895c24308b9c24cc000000c744243800000000c744243c01000000895424340f85370100006a3c8d8424900000006a008d7304b90f0000008d7c245850f3a5e8a16bfeff83c40c8d4c2450518b4c24148d94249000000052e8e0e620006a3c8d8424900000006a008d7340b90f0000008d7c245850f3a5e8696bfeff83c40c8d8c248c000000518b4c24148d54245452e8a8e620008b038b482085c9741433c0833c81000f85e400000083c00183f80772ee8b7c24108b0b8b412885c07408508bcfe8c60a1f008b138b422c85c074168b0085c074108b8ff400000085c9740650e8f7c004008b437c85c0741a8b0885c974148b400485c00f85a300000050518bcfe8c6c628008b7424148bc63b453873118b54241852578d4d10894538e85ae51e00a1e48ccd00397050732f8b4c241083b9f40000000074228b138b721085f674198bcee8536d040084c0750e8b4424106a00508bcee881d603008b0b8b41348b51308bf08d14d63bc20f84fa0000008b51308bce8d0cd18d64240083380f747a83c0083bc175f4e9dd0000008b7c24106a01518bcfe811a52300e915ffffff8b0de48ccd0085c989442424742cdb442424d97c24240fb7442424d889bc0100000d000c000089442428d96c2428df7c24288b442428d96c24248b4c242003c1894424380f841cffffff8b7424143bf00f8214ffffffe911fffffff30f1040040f2f05308bbe00f30f11442414765b8b5424108bb23c03000085f6744df30f10050062be006a008d442424506a108bcdf30f1144242ce851d9feff84c08b3e8b57486a018bce740effd2d9442424d84c2418dec1eb06ffd2d84424188b8784000000518bced91c24ffd08b0b8b41348b51308bf08d14d63bc274398b51308bce8d0cd1833801740983c0083bc175f4eb23f30f1040040f2f05308bbe0076158b5424108b8a3c03000085c974078b018b502cffd28b0b8b41348b51308bf08d14d63bc274558b51308bce8d0cd1833810740983c0083bc175f4eb3ff30f1040040f2f05308bbe00f30f11442414762b8b5424108bb23c03000085f6741d8b3e8b47486a018bceffd0d84c24188b9784000000518bced91c24ffd28b54241c85d20f85740000008b452c3b45308d4d28732785c08d7010897104742c8b4c243089088b4c24348948048b4c24388948088b4c243c89480ceb0f8d5424305250e8a97cffff8b54241c8b038b480483448d78018d448d788b038b48348b70308bf98d34f73bce74148b70308bc78d04f0833921743783c1083bc875f48b7424108b0b8b41348b79308bd88d3cfb3bc70f847b0000008b79308bcb8d0cf990833815745483c0083bc175f4eb648b742410f30f10050062be006a008d4c241c516a218bcef30f11442424e8900e1f00d9442418518bced91c24e8e1fa20008b96f4000000f30f10442418f30f11825c0200008b54241ceb89f30f1040040f2f05308bbe00760b8bcee882091f008b54241c85d274168b028b08b801000000394124760501420ceb0389420c8b44244085c0740950e85695f2ff83c4045e5f5db0015b81c4b8000000c208005f5d32c05b81c4b8000000c20800',
    0x4e5c10: '81ec880000008b84248c0000005355568bf18b480c85c957897424147e0683c1ff89480c8b400c85c08b6e088b9c24a00000008944241c0f85120100008b9424a40000008b4e2c8d42103bc1730b525150e8ca9a1f0083c40c83462cf0',
}
ACTIONS = dict(buildpower='SovietPowerPlant', buildbarracks='SovietBarracks',
    buildfactory='SovietWarFactory', buildrefinery='SovietRefinery',
    buildbattlelab='SovietTechStructure', producesickle='SovietAntiInfantryVehicle',
    producebullfrog='SovietAntiAirShip_Ground', buildreactor='SovietPowerPlantAdvanced')


def _finite(value): return type(value) in (int, float) and math.isfinite(value)


def derive_cost_envelope(inventory):
    """Derive conditional ceilings; never adapt into NativeCostFact.

    The caller must recompute the asset inventory from the pinned archive
    bytes. Parsing this JSON alone does not prove what the game loaded.
    """
    if (inventory.get('kind') != 'native_compiled_cost_source_inventory'
            or inventory.get('schema_version') != 1
            or inventory.get('package_sha256') != assets.PACKAGE_SHA256):
        raise ValueError('cost_envelope_fixed_inventory_required')
    blockers = []
    if inventory.get('parsing_errors') != []: blockers.append('compiled_asset_parse_incomplete')
    if inventory.get('unresolved_payload_aliases') != []: blockers.append('compiled_payload_alias_unresolved')
    if set(inventory.get('qualities', [])) != {'high', 'l', 'm'}:
        blockers.append('quality_stream_coverage_incomplete')
    objects = inventory.get('objects', []); attributes = inventory.get('attribute_modifiers', [])
    players = inventory.get('player_templates', [])
    if not objects or not attributes or not players: blockers.append('compiled_cost_catalog_empty')
    for row in objects:
        for module in row['production_modules']:
            if any(not _finite(value) or not 0 <= value <= 1 for value in module['multipliers']):
                blockers.append('production_multiplier_can_increase_cost')
        for module in row['production_bonus_modules']:
            if any(not _finite(module[key]) or module[key] > 0 for key in ('own', 'allies')):
                blockers.append('object_production_bonus_can_increase_cost')
        if row['cost_modifier_upgrade_modules']:
            blockers.append('cost_modifier_upgrade_context_not_mirrored')
    for row in players:
        for bonus in row['production_cost_bonuses']:
            if any(not _finite(bonus[key]) or bonus[key] > 0 for key in ('own', 'allies')):
                blockers.append('player_template_bonus_can_increase_cost')
    for row in attributes:
        values = row['production_cost_values']
        if values and (type(row['stacking_limit']) is not int or not 0 <= row['stacking_limit'] <= 1):
            blockers.append('cost_attribute_variable_stacking_not_proven')
        if any(not _finite(value) or value < 1 for value in values):
            blockers.append('cost_attribute_divisor_can_be_below_one')
    ceilings = []
    for quality in ('high', 'l', 'm'):
        by_name = {row['name']:row for row in objects if row['quality']==quality}
        for producer in ('SovietConstructionYard', 'SovietWarFactory'):
            row = by_name.get('GameObject:'+producer)
            if row is None or not row['production_modules']:
                blockers.append('required_producer_definition_missing')
        for action, template in ACTIONS.items():
            row = by_name.get('GameObject:'+template)
            costs = row.get('compiled_resource_costs') if row else None
            valid = (type(costs) is list and len(costs)==1 and costs[0].get('account')==0
                and type(costs[0].get('amount')) is int and 0 <= costs[0]['amount'] <= 65535)
            if not valid:
                blockers.append('target_single_native_resource_zero_base_not_proven')
            ceilings.append(dict(action=action, template=template, quality=quality,
                conditional_base_ceiling=costs[0]['amount'] if valid else None,
                payload_sha256=row.get('payload_sha256') if row else None))
    supported = not blockers
    return dict(schema_version=1, kind='conditional_native_cost_discount_envelope',
        package_sha256=assets.PACKAGE_SHA256, discount_envelope_supported=supported,
        blockers=sorted(set(blockers)), target_conditional_ceilings=ceilings,
        production_multiplier_upper=1 if supported else None,
        player_bonus_multiplier_upper=1 if supported else None,
        producer_attribute_divisor_lower=1 if supported else None,
        discount_changes_within_fixed_definition_universe_allowed=True,
        proof_scope='getter_and_restricted_single_unit_price_within_fixed_compiled_definition_universe',
        required_external_conditions=[
            'fresh_scope_uses_exact_audited_executable_package_and_stock_streams',
            'no_additional_loaded_cost_definition_or_native_dynamic_definition_source',
            'runtime_target_hash_schema_and_u16_base_bound_to_audited_target_ceiling',
            'producer_definition_bound_to_audited_nonincreasing_modifiers',
            'native_bonus_and_attribute_definitions_belong_to_audited_universe',
            'ordinary_single_request_context_and_additional_count_one',
            'native_construction_request_cost_context_separately_proven_for_build_actions',
            'own_credits_and_native_reserved_credits_coherent_and_verified'],
        native_upper_cost=None, native_upper_cost_verified=False,
        runtime_definition_binding_verified=False, request_cost_context_verified=False,
        native_reserved_credits=None, reservation_usable=False,
        field_verified=False, grants_capability=False)


def audit_executable(path):
    result = current.audit_executable(path); raw = Path(path).read_bytes()
    for at, expected in PINS.items():
        wanted = bytes.fromhex(expected)
        if raw[at-0x400000:at-0x400000+len(wanted)] != wanted:
            raise ValueError('cost_bound_native_pin_changed')
    return dict(result, kind='native_cost_conditional_bound_static_audit',
        bound_contract_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        bound_byte_checks=[dict(address=hex(at),bytes=value) for at,value in PINS.items()],
        native_upper_cost_verified=False, field_verified=False, grants_capability=False)
