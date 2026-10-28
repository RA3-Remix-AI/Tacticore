"""Verification callbacks here are synthetic and confer no real game capability."""
from dataclasses import replace
import unittest

from host_runtime.contracts import ContractError, ProfileApplication, canonical_json
import uuid
from host_runtime.capabilities import CapabilityCatalog, VerifiedGrant, policy_execution_support
from test_host_runtime_profiles import binding, draft
from host_runtime.profiles import normalize_profile


def verified(capability, current):
    # Test-only verifier. Production callers must invoke real evidence validation.
    constraints = dict(runtime_family="tactical", executor_directory="synthetic/test-only", execution_ready=True,
                       executor_sha256="d" * 64, evidence_id="synthetic-test-only")
    return VerifiedGrant(capability, "synthetic-test-only", "c" * 64, "d" * 64, "test-only narrow scope", canonical_json(constraints))


class CapabilityContracts(unittest.TestCase):
    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_default_catalog_accepts_soft_advice_but_has_no_executable_axes(self):
        catalog = CapabilityCatalog()
        for row in catalog.describe_axes().values():
            self.assertEqual(row["mode"], "advisory")
            self.assertTrue(row["model_advice"])
            self.assertEqual(row["execution_status"], "unsupported")
            self.assertTrue(row["missing_capabilities"])
        self.assertCode("capability_unsupported", lambda: catalog.require("tactics.attack", binding()))

    def test_verifier_result_is_required_and_bound_to_complete_process_identity(self):
        current = binding()
        catalog = CapabilityCatalog.verify(current, ["tactics.attack"], verified)
        self.assertEqual(catalog.describe_axes()["attack"]["mode"], "executable")
        self.assertEqual(catalog.describe_axes()["attack"]["verified_scopes"][0]["scope"], "test-only narrow scope")
        self.assertEqual(catalog.describe_axes()["risk"]["mode"], "advisory")
        self.assertEqual(catalog.require("tactics.attack", current).scope, "test-only narrow scope")
        self.assertCode("capability_binding_mismatch", lambda: catalog.require("tactics.attack"))
        self.assertCode("capability_binding_mismatch", lambda: catalog.require("tactics.attack", replace(current, game_process_start="2026-10-26T11:01:00+08:00")))
        self.assertCode("capability_unsupported", lambda: catalog.require("economy.expand", current))

    def test_ui_verified_boolean_cannot_create_an_execution_grant(self):
        self.assertCode("invalid_verified_grant", lambda: CapabilityCatalog.verify(binding(), [{"verified": True}], lambda candidate, _: candidate))
        self.assertCode("capability_verifier_required", lambda: CapabilityCatalog.verify(binding(), [], None))
        self.assertCode("duplicate_capability", lambda: CapabilityCatalog.verify(binding(), ["tactics.attack"] * 2, verified))
        self.assertCode("unknown_capability", lambda: CapabilityCatalog.verify(binding(), ["arbitrary.command"], verified))

    def test_policy_expansion_and_tech_are_reported_unsupported_not_infantry_spend(self):
        policy = {"economy_policy": "expand_if_defensible", "tech_policy": "advance_if_affordable"}
        rows = policy_execution_support(policy, CapabilityCatalog(), binding())
        self.assertEqual(rows["economy_policy"]["status"], "unsupported")
        self.assertEqual(rows["tech_policy"]["status"], "unsupported")
        self.assertNotIn("spend_fraction", str(rows))
        catalog = CapabilityCatalog.verify(binding(), ["economy.expand"], verified)
        rows = policy_execution_support(policy, catalog, binding())
        self.assertEqual(rows["economy_policy"]["status"], "executable")
        self.assertTrue(rows["economy_policy"]["per_command_admission_required"])
        self.assertEqual(rows["tech_policy"]["status"], "unsupported")

    def test_capability_change_changes_effective_profile_content_hash(self):
        plain = normalize_profile(draft())
        enabled = normalize_profile(draft(), capability_catalog=CapabilityCatalog.verify(binding(), ["tactics.attack"], verified))
        self.assertNotEqual(plain.effective_hash, enabled.effective_hash)
        self.assertNotEqual(plain.capability_catalog_hash, enabled.capability_catalog_hash)

    def test_profile_and_application_cannot_carry_capabilities_into_another_binding(self):
        current = binding()
        catalog = CapabilityCatalog.verify(current, ["tactics.attack"], verified)
        self.assertCode("profile_capability_binding_mismatch", lambda: normalize_profile(draft(profile_id=str(uuid.uuid4())), capability_catalog=catalog))
        profile = normalize_profile(draft(), capability_catalog=catalog)
        self.assertCode("profile_capability_binding_mismatch", lambda: ProfileApplication.accept(profile, replace(current, game_process_id=102), str(uuid.uuid4())))

    def test_unknown_policy_payload_is_not_echoed_as_diagnostic_text(self):
        self.assertCode("invalid_policy_field", lambda: policy_execution_support({"economy_policy": "DO_NOT_EXPORT", "tech_policy": "hold_current_tier"}, CapabilityCatalog()))

    def test_empty_or_not_ready_constraints_never_become_executable_axes(self):
        empty = VerifiedGrant("tactics.attack", "fixture", "a" * 64, "b" * 64, "primitive observation only")
        catalog = CapabilityCatalog.verify(binding(), [empty], lambda row, _: row)
        self.assertFalse(empty.public()["executable_ready"])
        self.assertEqual(catalog.describe_axes()["attack"]["mode"], "advisory")
        self.assertEqual(catalog.require("tactics.attack", binding()), empty)
        # require returns the proof record; runtime admission must inspect its
        # machine constraints, rather than treating the record as authority.

    def test_execution_constraints_reject_unknown_keys_and_changed_identity(self):
        base = dict(runtime_family="tactical", executor_directory="fixture/test", execution_ready=True,
                    executor_sha256="b" * 64, evidence_id="fixture")
        for change in ({"arbitrary_command": "x"}, {"executor_directory": "../escape"}, {"execution_ready": 1}):
            self.assertCode("invalid_execution_constraints", lambda: VerifiedGrant("tactics.attack", "fixture", "a" * 64, "b" * 64, "fixture", canonical_json({**base, **change})))
        self.assertCode("execution_constraint_identity_mismatch", lambda: VerifiedGrant("tactics.attack", "fixture", "a" * 64, "b" * 64, "fixture", canonical_json({**base, "evidence_id": "other"})))


if __name__ == "__main__":
    unittest.main()
