import copy
import json
from pathlib import Path
import unittest

from .contracts import ContractError
from .macro_forces import observe_forces, compact_forces, NAMED_BUILDINGS

ROOT = Path(__file__).resolve().parents[2]


class ForceObservationTests(unittest.TestCase):
    def test_all_audited_mobile_types_survive_provider_projection(self):
        census, safety = self.fixture()
        safety["templates"]["0x60f0b4e9"] = dict(
            template="SovietAntiInfantryVehicle", role="armor", source_audited_no_intrinsic_stealth=True
        )
        census["own_objects"].append(dict(thing_id=3, type_hash="0x60f0b4e9", hp=100.0, xyz=[100.0, 100.0, 0.0]))
        facts = observe_forces(census, safety)
        value = compact_forces(facts, 100.0)
        self.assertEqual(value["unit_type_counts"], {"SovietAntiInfantryInfantry": 1, "SovietAntiInfantryVehicle": 1})
        self.assertEqual(value["named_unit_counts"]["hammer_tank"], 0)
        from .macro_policy_runtime import MacroRequestAudit

        budget = dict(
            status="native_delegation_observed",
            selected_policy=None,
            actions=[],
            observed_frame=1500,
            native_effect_verified=False,
        )
        audit = MacroRequestAudit(
            None, lambda *a, **k: None, feedback_supplier=lambda: budget, forces_supplier=lambda: facts
        )
        context = audit.prepare(dict(game_time_seconds=100.0, working_memory={}))
        self.assertEqual(context["own_forces"]["unit_type_counts"], value["unit_type_counts"])
        del facts["unit_type_counts"]
        self.assertNotIn("unit_type_counts", compact_forces(facts, 100.0))

    def test_unit_type_projection_rejects_unbounded_or_inconsistent_counts(self):
        for counts in (
            {"0x12345678": 1},
            {"SovietAntiInfantryVehicle": True},
            {"SovietAntiInfantryVehicle": 2},
            {"Unit" + str(i): 0 for i in range(65)},
        ):
            value = observe_forces(*self.fixture())
            value["unit_type_counts"] = counts
            with self.subTest(counts=counts), self.assertRaises(ContractError):
                compact_forces(value, 100.0)

    def test_own_miner_forms_are_economic_presence_with_no_enemy_or_income_grant(self):
        census, safety = self.fixture()
        before = copy.deepcopy(safety)
        for ident, template in [(3, "0xf6dac2a4"), (4, "0x951764b9")]:
            census["own_objects"].append(dict(thing_id=ident, type_hash=template, hp=1.0, xyz=[100.0, 100.0, 0.0]))
        value = compact_forces(observe_forces(census, safety), 100.0)
        self.assertEqual(value["economic_unit_presence_counts"], {"ore_collector": 2})
        self.assertEqual(
            value["economic_unit_regions"], [dict(region_id="region_0_0", ore_collectors=2, health_total=2.0)]
        )
        self.assertEqual(value["mobile_role_counts"], {"infantry": 1})
        self.assertFalse(value["income_verified"])
        self.assertEqual(safety, before)
        value["income_verified"] = True
        self.assertFalse(compact_forces(value, 100.0)["income_verified"])
        del value["economic_unit_presence_counts"]
        self.assertNotIn("economic_unit_presence_counts", compact_forces(value, 100.0))

    def test_own_miner_count_bounds_and_foreign_census_are_rejected(self):
        for count in (True, -1, 8193):
            value = observe_forces(*self.fixture())
            value["economic_unit_presence_counts"] = {"ore_collector": count}
            with self.subTest(count=count), self.assertRaises(ContractError):
                compact_forces(value, 100.0)
        census, safety = self.fixture()
        census["enemy_details_read"] = True
        with self.assertRaises(ContractError):
            observe_forces(census, safety)

    def fixture(self):
        safe = {
            "templates": {
                "0x19ab11af": dict(
                    template="SovietAntiInfantryInfantry", role="infantry", source_audited_no_intrinsic_stealth=True
                ),
                "0xc16ff13f": dict(
                    template="SovietConstructionYard", role="structure", source_audited_no_intrinsic_stealth=True
                ),
            }
        }
        rows = [
            dict(thing_id=1, type_hash="0x19ab11af", hp=50.0, xyz=[1200.0, 1800.0, 200.0], address="PRIVATE"),
            dict(thing_id=2, type_hash="0xc16ff13f", hp=1.0, xyz=[4400.0, 2016.0, 210.0]),
        ]
        return dict(frame=1500, own_objects=rows, enemy_details_read=False), safe

    def test_home_and_mobile_locations_are_presence_with_no_recruitment_claim(self):
        census, safety = self.fixture()
        v = compact_forces(observe_forces(census, safety), 100.0)
        self.assertEqual(v["named_unit_counts"]["conscript"], 1)
        self.assertEqual(
            v["regions"],
            [
                dict(region_id="region_8_3", mobile=0, construction_yards=1),
                dict(region_id="region_2_3", mobile=1, construction_yards=0),
            ],
        )
        self.assertFalse(v["recruitability_verified"])
        self.assertFalse(v["ready_for_combat_verified"])
        for private in ("PRIVATE", "xyz", "thing_id", "0x", "hp"):
            self.assertNotIn(private, json.dumps(v))

    def test_building_presence_uses_audited_own_census_without_builder_or_operation_claims(self):
        census, safety = self.fixture()
        for name, (template, asset) in NAMED_BUILDINGS.items():
            safety["templates"][template] = dict(
                template=asset,
                role="economy" if name == "refinery" else "structure",
                source_audited_no_intrinsic_stealth=True,
            )
        census["own_objects"].append(
            dict(thing_id=3, type_hash=NAMED_BUILDINGS["refinery"][0], hp=1.0, xyz=[4400.0, 2016.0, 210.0])
        )
        value = compact_forces(observe_forces(census, safety), 100.0)
        self.assertEqual(value["building_presence_counts"]["construction_yard"], 1)
        self.assertEqual(value["building_presence_counts"]["refinery"], 1)
        self.assertEqual(value["building_presence_counts"]["battle_lab"], 0)
        self.assertTrue(value["presence_includes_unfinished_foundations"])
        self.assertFalse(value["building_operation_verified"])
        self.assertNotIn("builder_frame", value)
        self.assertNotIn("construction_queues", value)

    def test_unsupported_building_templates_and_older_observations_remain_unknown(self):
        census, safety = self.fixture()
        value = observe_forces(census, safety)
        self.assertEqual(value["building_presence_counts"], {"construction_yard": 1})
        del value["building_presence_counts"]
        self.assertNotIn("building_presence_counts", compact_forces(value, 100.0))

    def test_building_binding_and_public_count_bounds_are_enforced(self):
        census, safety = self.fixture()
        safety["templates"]["0xc16ff13f"]["template"] = "SovietRefinery"
        with self.assertRaisesRegex(ContractError, "template_binding"):
            observe_forces(census, safety)
        for counts in ({"refinery": True}, {"refinery": -1}, {"refinery": 8193}, {"invented": 1}):
            value = observe_forces(*self.fixture())
            value["building_presence_counts"] = counts
            with self.subTest(counts=counts), self.assertRaises(ContractError):
                compact_forces(value, 100.0)

    def test_unknown_templates_are_counted_as_unclassified_without_guessing_role(self):
        census, safety = self.fixture()
        census["own_objects"][0]["type_hash"] = "unknown"
        v = observe_forces(census, safety)
        self.assertEqual(v["unclassified_objects"], 1)
        self.assertEqual(v["mobile_role_counts"], {})
        self.assertEqual(v["named_unit_counts"]["conscript"], 0)

    def test_foreign_details_duplicates_and_nonfinite_positions_cannot_be_projected(self):
        for change in ("foreign", "duplicate", "nan", "wrong_template"):
            census, safety = self.fixture()
            if change == "foreign":
                census["enemy_details_read"] = True
            elif change == "duplicate":
                census["own_objects"].append(copy.deepcopy(census["own_objects"][0]))
            elif change == "nan":
                census["own_objects"][0]["xyz"][0] = float("nan")
            else:
                safety["templates"]["0x19ab11af"]["template"] = "SovietEngineer"
            with self.assertRaises(ContractError):
                observe_forces(census, safety)

    def test_region_limit_preserves_home_and_reports_omissions(self):
        census, safety = self.fixture()
        for i in range(3, 12):
            census["own_objects"].append(dict(thing_id=i, type_hash="0x19ab11af", hp=50.0, xyz=[512.0 * i, 512.0, 0.0]))
        v = compact_forces(observe_forces(census, safety), 100.0)
        self.assertEqual(len(v["regions"]), 4)
        self.assertEqual(v["omitted_region_count"], 7)
        self.assertEqual(v["regions"][0]["construction_yards"], 1)
        self.assertEqual(sum(v["mobile_role_counts"].values()), 10)

    def test_stale_private_fields_and_false_readiness_claims(self):
        value = observe_forces(*self.fixture())
        value.update(address="PRIVATE", ready_for_combat_verified=True, recruitability_verified=True)
        value["regions"][0]["native_id"] = "PRIVATE"
        v = compact_forces(value, 100.0)
        self.assertNotIn("PRIVATE", json.dumps(v))
        self.assertFalse(v["recruitability_verified"])
        with self.assertRaisesRegex(ContractError, "stale"):
            compact_forces(value, 103.0)
        value["regions"][0]["mobile"] = 8000
        with self.assertRaisesRegex(ContractError, "consistency"):
            compact_forces(value, 100.0)

    def test_provider_receives_current_presence_and_defers_stale_observation(self):
        from .macro_policy_runtime import MacroRequestAudit

        facts = observe_forces(*self.fixture())
        budget = dict(
            status="native_delegation_observed",
            selected_policy=None,
            actions=[],
            observed_frame=1500,
            native_effect_verified=False,
        )
        audit = MacroRequestAudit(
            None, lambda *a, **k: None, feedback_supplier=lambda: budget, forces_supplier=lambda: facts
        )
        value = audit.prepare(dict(game_time_seconds=100.0, working_memory={}))
        self.assertEqual(value["own_forces"]["named_unit_counts"]["conscript"], 1)
        self.assertFalse(value["own_forces"]["recruitability_verified"])
        self.assertTrue(audit.fresh_for_game_seconds(100.0))
        facts["observed_frame"] = 1469
        self.assertFalse(audit.fresh_for_game_seconds(100.0))
        with self.assertRaisesRegex(ContractError, "stale"):
            audit.prepare(dict(game_time_seconds=100.0))


if __name__ == "__main__":
    unittest.main()
