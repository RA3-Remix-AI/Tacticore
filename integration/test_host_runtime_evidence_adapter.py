"""Synthetic injected verifier tests; no live capability or game access."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from host_runtime.contracts import ContractError
from host_runtime.evidence_adapter import EvidenceVerifiers, build_catalog
from host_runtime.capabilities import VerifiedGrant
from host_runtime.contracts import canonical_json
from test_host_runtime_profiles import binding


class EvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.current = binding(); self.calls = []
        self.session = dict(session_id=self.current.session_id, pid=self.current.game_process_id,
            start_time=self.current.game_process_start, mod_sha256=self.current.mod_sha256,
            scenario=dict(commander_id=self.current.commander_id, computer_player_index=self.current.player_id))
        self.production = self.root / "production.json"
        self.production.write_text(json.dumps(dict(mod_sha256=self.current.mod_sha256, preflight=dict(player=dict(owner_index=3)))), encoding="utf-8")
        self.persistent = self.root / "persistent-production-status.json"
        self.persistent.write_text(json.dumps(dict(commander_id=self.current.commander_id, player_id=3, session_id=self.current.session_id)), encoding="utf-8")
        self.audit = self.root / "persistent-production.jsonl"
        self.audit.write_text(json.dumps(dict(event="attach_preflight", commander_id=self.current.commander_id, session_id=self.current.session_id)) + '\n', encoding="utf-8")
        self.tactical = self.root / "tactical.json"; self.tactical.write_text('{}', encoding="utf-8")

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def verify_session(self, current, session):
        self.calls.append(("session", current, session))

    def verify_production(self, path, session):
        self.calls.append(("production", path, session))
        return dict(evidence_id="test-production", source_report=str(path), report_sha256=self.digest(path),
                    supported_foci=("anti_air",), assessment=dict(production_primitive_verified=True, checks=dict(raw_recomputed=True)))

    def verify_persistent(self, path, session):
        self.calls.append(("persistent", path, session))
        return dict(status_sha256=self.digest(path), audit_sha256=self.digest(self.audit), supported_foci=("infantry", "balanced"))

    def verify_tactical(self, path, session, commander):
        self.calls.append(("tactical", path, session, commander))
        return dict(evidence_id="test-tactical", grants=[dict(module="combined_arms", purpose="coordinate_force",
            session_id=self.current.session_id, player_id=3, commander_id=self.current.commander_id,
            source="game_bridge", executable_sha256=self.current.game_sha256, package_sha256=self.current.mod_sha256,
            source_report=str(self.tactical), source_sha256=self.digest(self.tactical),
            evidence_uuid="ebed6c36-1d92-4fc3-81d6-8c52d8b9b6b4", native_binary_sha256="e" * 64, native_host_sha256="f" * 64,
            stop_schema=dict(actor_roles=["infantry", "anti_air"], mission_protocol="continuous_tactical_v1"),
            executor_directory="synthetic-test-only", scope="test-only fixed two-role source", limits=dict(lease_frames=4500),
            raw_assessment=dict(approach_verified=True, retreat_verified=True, restoration_verified=True))])

    def verifiers(self, **changes):
        values = dict(production=self.verify_production, persistent=self.verify_persistent,
            tactical=self.verify_tactical, session=self.verify_session,
            production_integrity=lambda: ("d" * 64, dict(executable_sha256=self.current.game_sha256, package_sha256=self.current.mod_sha256)),
            one_shot_executor=lambda: "9" * 64)
        values.update(changes)
        return EvidenceVerifiers(**values)

    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_real_verifier_boundary_is_called_and_test_injection_cannot_claim_live_proof(self):
        bundle = build_catalog(self.current, self.session, production_report=self.production,
            persistent_status=self.persistent, tactical_manifest=self.tactical, verifiers=self.verifiers())
        self.assertTrue(bundle.test_only)
        self.assertEqual(bundle.public()["verification_mode"], "injected_test_verifiers")
        self.assertEqual([c[0] for c in self.calls], ["session", "production", "persistent", "tactical"])
        self.assertIn("one-shot", bundle.catalog.require("production.anti_air", self.current).scope)
        self.assertFalse(bundle.execution_constraints["production.anti_air"]["execution_ready"])
        self.assertEqual(bundle.execution_constraints["production.anti_air"]["runtime_family"], "production_one_shot")
        self.assertEqual(bundle.execution_constraints["production.anti_air"]["executor_sha256"], "9" * 64)
        self.assertIn("persistent", bundle.catalog.require("production.infantry", self.current).scope)
        self.assertEqual(bundle.execution_constraints["production.infantry"]["runtime_family"], "production_persistent_v2")
        self.assertEqual(bundle.execution_constraints["production.infantry"]["allowed_units"], ["conscript"])
        self.assertIn("fixed two-role", bundle.catalog.require("tactics.coordinate_force", self.current).scope)
        self.assertIn("subset", bundle.catalog.require("tactics.move_hold_return", self.current).scope)
        self.assertFalse(bundle.execution_constraints["tactics.move_hold_return"]["execution_ready"])
        self.assertCode("capability_unsupported", lambda: bundle.catalog.require("tactics.pursuit", self.current))
        self.assertCode("capability_unsupported", lambda: bundle.catalog.require("economy.expand", self.current))

    def test_identity_mismatch_rejected_before_calling_verifiers(self):
        for key, value in [("session_id", "wrong"), ("pid", 999), ("start_time", "changed"), ("mod_sha256", "c" * 64)]:
            self.assertCode("evidence_session_binding_mismatch", lambda: build_catalog(self.current, {**self.session, key: value}, verifiers=self.verifiers()))
        self.assertFalse(self.calls)
        alternate = replace(self.current, player_id=4)
        session = {**self.session, "scenario": dict(commander_id=alternate.commander_id, computer_player_index=4)}
        self.assertCode("legacy_executor_player_unsupported", lambda: build_catalog(alternate, session, verifiers=self.verifiers()))

    def test_existing_verifier_failure_cannot_be_replaced_by_status_or_hash(self):
        def refused(*_):
            raise ValueError("synthetic raw check failed")
        self.assertCode("existing_evidence_verification_failed", lambda: build_catalog(self.current, self.session,
            production_report=self.production, verifiers=self.verifiers(production=refused)))
        fake = lambda path, session: dict(verified=True, source_report=str(path), report_sha256=self.digest(path))
        self.assertCode("production_raw_evidence_unverified", lambda: build_catalog(self.current, self.session,
            production_report=self.production, verifiers=self.verifiers(production=fake)))

    def test_persistent_proof_needs_base_and_unchanged_audit(self):
        self.assertCode("persistent_requires_base_production_evidence", lambda: build_catalog(self.current, self.session,
            persistent_status=self.persistent, verifiers=self.verifiers()))
        def stale(path, session):
            result = self.verify_persistent(path, session); result["audit_sha256"] = "f" * 64; return result
        self.assertCode("persistent_audit_changed", lambda: build_catalog(self.current, self.session,
            production_report=self.production, persistent_status=self.persistent, verifiers=self.verifiers(persistent=stale)))

    def test_tactical_source_binding_and_purpose_are_rechecked(self):
        def wrong(path, session, commander):
            result = self.verify_tactical(path, session, commander); result["grants"][0]["session_id"] = "wrong"; return result
        self.assertCode("tactical_binding_mismatch", lambda: build_catalog(self.current, self.session,
            tactical_manifest=self.tactical, verifiers=self.verifiers(tactical=wrong)))
        def changed(path, session, commander):
            result = self.verify_tactical(path, session, commander); result["grants"][0]["source_sha256"] = "f" * 64; return result
        self.assertCode("tactical_source_changed", lambda: build_catalog(self.current, self.session,
            tactical_manifest=self.tactical, verifiers=self.verifiers(tactical=changed)))
        def unknown(path, session, commander):
            result = self.verify_tactical(path, session, commander); result["grants"][0]["purpose"] = "win_game"; return result
        self.assertCode("unsupported_tactical_scope", lambda: build_catalog(self.current, self.session,
            tactical_manifest=self.tactical, verifiers=self.verifiers(tactical=unknown)))

    def test_persistent_raw_source_must_bind_original_commander(self):
        self.audit.write_text(json.dumps(dict(event="attach_preflight", commander_id="different", session_id=self.current.session_id)) + '\n', encoding="utf-8")
        self.assertCode("persistent_source_commander_mismatch", lambda: build_catalog(self.current, self.session,
            production_report=self.production, persistent_status=self.persistent, verifiers=self.verifiers()))

    def test_incomplete_retreat_cannot_derive_move_return_capability(self):
        def incomplete(path, session, commander):
            result = self.verify_tactical(path, session, commander); result["grants"][0]["raw_assessment"]["retreat_verified"] = False; return result
        bundle = build_catalog(self.current, self.session, tactical_manifest=self.tactical, verifiers=self.verifiers(tactical=incomplete))
        self.assertCode("capability_unsupported", lambda: bundle.catalog.require("tactics.move_hold_return", self.current))

    def test_runtime_report_requires_explicit_pin(self):
        for args in (dict(runtime_report=self.tactical), dict(runtime_sha256="a" * 64)):
            self.assertCode("runtime_evidence_pin_required", lambda: build_catalog(self.current, self.session,
                verifiers=self.verifiers(), **args))

    def test_explicit_runtime_verifier_replaces_only_nonexecutable_legacy_subset(self):
        constraints = dict(runtime_family="tactical", executor_directory="tactical/runtime", execution_ready=True,
            executor_sha256="d" * 64, evidence_id="a" * 64, native_host_sha256="e" * 64,
            purpose="move_hold_return", mission_protocol="tactical_runtime_v1", actor_roles=["infantry"])
        fake = VerifiedGrant("tactics.move_hold_return", "a" * 64, "a" * 64, "d" * 64,
            "synthetic injected verifier test, no field authority", canonical_json(constraints))
        with patch("host_runtime.runtime_evidence.verify_pinned_runtime", return_value=fake) as verifier:
            bundle = build_catalog(self.current, self.session, tactical_manifest=self.tactical,
                runtime_report=self.tactical, runtime_sha256="a" * 64, verifiers=self.verifiers())
        verifier.assert_called_once_with(self.tactical.resolve(), "a" * 64, self.current)
        self.assertTrue(bundle.test_only)
        self.assertEqual("a" * 64, bundle.public()["runtime_evidence_id"])
        self.assertEqual("tactical/runtime", bundle.execution_constraints["tactics.move_hold_return"]["executor_directory"])
        self.assertFalse(bundle.runtime["combat_effect_verified"])
        self.assertEqual("synthetic-test-only", bundle.execution_constraints["tactics.coordinate_force"]["executor_directory"].split("/")[-1])


if __name__ == "__main__":
    unittest.main()
