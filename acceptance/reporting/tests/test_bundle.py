"""Synthetic evidence only; no game, model, protected settings or network."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from acceptance.reporting import BundleError, build_review_bundle
from acceptance.reporting import bundle


def uid(): return str(uuid.uuid4())
def raw(value): return json.dumps(value, ensure_ascii=False).encode("utf-8")


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "run"; self.root.mkdir()
        self.output = self.base / "review"
        self.manifest = self.base / "private-manifest.json"
        self.binding = dict(run_id=uid(), session_id=uid(), player_id=3, commander_id=uid(), profile_revision=3, effective_hash="a" * 64)
        self.sources = []

    def add_envelope(self, layer="configuration", **changes):
        value = dict(schema_version=1, kind="tacticore_evidence_envelope", binding=copy.deepcopy(self.binding),
                     layer=layer, complete=True, record_count=1,
                     records=[dict(event_id=uid(), facts={"status": "completed", "mission_effect_verified": True})])
        value.update(changes)
        return self.add_source(value, "evidence_envelope_v1", layer=layer)

    def add_source(self, value, adapter, **changes):
        name = f"source_{len(self.sources) + 1:03d}"
        path = self.root / (name + ".json")
        path.write_bytes(raw(value))
        source = dict(source_id=name, path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size, adapter=adapter)
        source.update(changes); self.sources.append(source)
        return path, value

    def config(self):
        value = dict(schema_version=1, binding=self.binding, sources=self.sources)
        self.manifest.write_bytes(raw(value))
        return value

    def build(self):
        self.config()
        return build_review_bundle(self.root, self.manifest, self.output)

    def repin(self, path):
        for source in self.sources:
            if source["path"] == path.name:
                source.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)

    def diagnostics(self):
        binding = {k: self.binding[k] for k in ("session_id", "player_id", "commander_id")}
        profile = dict(revision=3, effective_hash=self.binding["effective_hash"])
        rows = [dict(seq=1, event_type="commander_profile_applied", facts={}),
                dict(seq=2, event_type="commander_model_response_returned", facts={"model_consumed": True}),
                dict(seq=3, event_type="command_reserved", command_id=uid(), facts={"operation": "produce"}),
                dict(seq=4, event_type="task_feedback", facts={"status": "completed"}),
                dict(seq=5, event_type="host_stopped", facts={"physical_home": True, "control_released": True, "mission_effect_verified": False})]
        return dict(schema_version=1, kind="tacticore_redacted_diagnostics", redacted=True,
                    run_id=self.binding["run_id"], binding=binding, binding_hash=bundle._digest(bundle._canonical(binding)),
                    effective_profile=profile, effective_profile_available=True, timeline=rows,
                    events=dict(total_count=len(rows), exported_count=len(rows), first_seq=1, last_seq=len(rows), truncated=False, timeline_sha256=bundle._digest(bundle._canonical(rows))),
                    status={**self.binding, "state": "stopped", "native_release_verified": True})

    def test_all_layers_provided_is_not_field_or_goal_verification(self):
        for layer in bundle.LAYERS: self.add_envelope(layer)
        report = self.build()
        self.assertEqual(report["review_status"], "structurally_complete")
        self.assertEqual(report["semantic_verification"], "externally_unverified")
        self.assertFalse(report["full_goal_complete"])

    def test_missing_layers_are_explicit(self):
        self.add_envelope()
        report = self.build()
        self.assertEqual(report["layers"]["effect"]["status"], "missing")
        self.assertEqual(report["review_status"], "needs_attention")

    def test_missing_file_invalid_not_provided(self):
        path, _ = self.add_envelope(); path.unlink()
        report = self.build()
        self.assertEqual(report["source_index"][0]["reason_code"], "source_missing")
        self.assertEqual(report["layers"]["configuration"]["status"], "invalid")

    def test_hash_or_size_changes_invalid(self):
        path, _ = self.add_envelope(); path.write_bytes(path.read_bytes() + b" ")
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_pin_mismatch")

    def test_truncated_source_is_invalid(self):
        self.add_envelope(complete=False)
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_truncated")

    def test_record_count_mismatch(self):
        self.add_envelope(record_count=2)
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_count_mismatch")

    def test_cross_session_rejected(self):
        binding = dict(self.binding, session_id=uid())
        self.add_envelope(binding=binding)
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_binding_mismatch")

    def test_cross_profile_receipt_rejected(self):
        self.add_envelope(records=[dict(event_id=uid(), facts={"profile_revision": 2})])
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_binding_mismatch")

    def test_duplicate_record_ids_rejected(self):
        row = dict(event_id=uid(), facts={})
        self.add_envelope(records=[row, row], record_count=2)
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "duplicate_or_invalid_record_id")

    def test_duplicate_record_across_sources_is_invalid(self):
        row = dict(event_id=uid(), facts={"status": "completed"})
        self.add_envelope(records=[row]); self.add_envelope("effect", records=[row])
        self.assertEqual(self.build()["source_index"][1]["reason_code"], "duplicate_record_id_across_sources")

    def test_duplicate_source_ids_rejected_before_output(self):
        self.add_envelope(); self.add_envelope("effect")
        self.sources[1]["source_id"] = self.sources[0]["source_id"]
        with self.assertRaisesRegex(BundleError, "duplicate_or_invalid_source_id"): self.build()
        self.assertFalse(self.output.exists())

    def test_duplicate_source_paths_case_insensitive(self):
        self.add_envelope(); self.add_envelope("effect")
        self.sources[1]["path"] = self.sources[0]["path"].upper()
        with self.assertRaisesRegex(BundleError, "duplicate_source_path"): self.build()

    def test_source_path_traversal_rejected(self):
        self.add_envelope(); self.sources[0]["path"] = "../private.json"
        with self.assertRaisesRegex(BundleError, "source_path_outside_root"): self.build()

    def test_absolute_windows_path_rejected(self):
        self.add_envelope(); self.sources[0]["path"] = "C:/private.json"
        with self.assertRaisesRegex(BundleError, "invalid_source_path"): self.build()

    def test_control_characters_in_path_are_rejected_without_exception_leak(self):
        self.add_envelope(); self.sources[0]["path"] = "file\x00.json"
        with self.assertRaisesRegex(BundleError, "invalid_source_path"): self.build()

    def test_symlink_source_rejected(self):
        path, _ = self.add_envelope()
        link = self.root / "link.json"
        try: link.symlink_to(path)
        except OSError: self.skipTest("OS symlink privilege unavailable")
        self.sources[0]["path"] = link.name
        with self.assertRaisesRegex(BundleError, "symlink_or_reparse_point"): self.build()

    def test_duplicate_json_keys_rejected(self):
        path, _ = self.add_envelope(); path.write_bytes(b'{"x":1,"x":2}'); self.repin(path)
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "duplicate_json_key")

    def test_nonfinite_json_and_exponent_overflow_rejected(self):
        for payload in (b'{"x":NaN}', b'{"x":1e999}'):
            with self.assertRaisesRegex(BundleError, "nonfinite_json"): bundle._strict_json(payload)

    def test_read_only_sources_and_manifest_unchanged(self):
        path, _ = self.add_envelope(); self.config()
        before = {p: p.read_bytes() for p in (path, self.manifest)}
        build_review_bundle(self.root, self.manifest, self.output)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_changed_input_during_build_cannot_publish(self):
        path, _ = self.add_envelope(); self.config()
        original_read = bundle._read; reads = {"manifest": 0}
        def racing_read(p, maximum):
            if p == self.manifest:
                reads["manifest"] += 1
                if reads["manifest"] == 2: path.write_bytes(path.read_bytes() + b" ")
            return original_read(p, maximum)
        with patch.object(bundle, "_read", side_effect=racing_read):
            with self.assertRaisesRegex(BundleError, "source_changed"):
                build_review_bundle(self.root, self.manifest, self.output)
        self.assertFalse(self.output.exists())

    def test_output_never_overwrites_existing_directory(self):
        self.add_envelope(); self.output.mkdir(); marker = self.output / "keep.txt"; marker.write_text("keep")
        with self.assertRaisesRegex(BundleError, "output_already_exists"): self.build()
        self.assertEqual(marker.read_text(), "keep")

    def test_output_inside_run_root_rejected(self):
        self.add_envelope(); self.output = self.root / "export"
        with self.assertRaisesRegex(BundleError, "output_overlaps_inputs"): self.build()

    def test_arbitrary_secrets_text_paths_and_payloads_do_not_leave(self):
        secret = "sk-FAKE-SECRET-DO-NOT-EXPORT"
        path, value = self.add_envelope()
        value.update(api_key=secret, provider_payload={"authorization": secret}, notes=secret)
        value["records"][0]["facts"].update(api_key=secret, model=secret, reason_code=secret)
        renamed = self.root / (secret + ".json")
        path.rename(renamed); self.sources[0]["path"] = renamed.name
        renamed.write_bytes(raw(value)); self.repin(renamed)
        report = self.build()
        for output in self.output.iterdir(): self.assertNotIn(secret, output.read_text(encoding="utf-8"))
        self.assertFalse(report["source_paths_included"])

    def test_real_diagnostics_schema_adapter_without_claiming_settlement(self):
        self.add_source(self.diagnostics(), "host_diagnostics_v1")
        report = self.build()
        for layer in bundle.LAYERS[:-1]: self.assertEqual(report["layers"][layer]["status"], "provided")
        self.assertEqual(report["layers"]["natural_settlement"]["status"], "missing")
        self.assertFalse(report["full_goal_complete"])

    def test_diagnostics_truncation_rejected(self):
        value = self.diagnostics(); value["events"]["truncated"] = True
        self.add_source(value, "host_diagnostics_v1")
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_truncated")

    def test_host_stopped_alone_is_not_control_release_material(self):
        value = self.diagnostics()
        value["timeline"] = [dict(seq=1, event_type="host_stopped", facts={"state": "stopped"})]
        value["status"] = {**self.binding, "state": "stopped"}
        value["events"].update(total_count=1, exported_count=1, first_seq=1, last_seq=1, timeline_sha256=bundle._digest(bundle._canonical(value["timeline"])))
        self.add_source(value, "host_diagnostics_v1")
        self.assertEqual(self.build()["layers"]["control_release"]["status"], "missing")

    def test_settlement_candidate_is_explicitly_only_a_candidate(self):
        value = self.diagnostics()
        value["timeline"].append(dict(seq=6, event_type="native_result_candidate", facts={}))
        value["events"].update(total_count=6, exported_count=6, last_seq=6, timeline_sha256=bundle._digest(bundle._canonical(value["timeline"])))
        self.add_source(value, "host_diagnostics_v1")
        report = self.build()
        self.assertEqual(report["layers"]["natural_settlement"]["records"][0]["claim_kind"], "settlement_candidate")
        self.assertFalse(report["full_goal_complete"])

    def test_diagnostics_timeline_tamper_detected(self):
        value = self.diagnostics(); value["timeline"][1]["facts"] = {}
        self.add_source(value, "host_diagnostics_v1")
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "diagnostics_timeline_hash_mismatch")

    def test_real_global_event_sequences_may_start_late_and_have_gaps(self):
        value = self.diagnostics()
        for row, seq in zip(value["timeline"], [819, 820, 937, 984, 1148]): row["seq"] = seq
        value["events"].update(first_seq=819, last_seq=1148, timeline_sha256=bundle._digest(bundle._canonical(value["timeline"])))
        self.add_source(value, "host_diagnostics_v1")
        self.assertEqual(self.build()["source_index"][0]["status"], "provided")

    def test_out_of_order_global_event_sequence_rejected(self):
        value = self.diagnostics()
        value["timeline"][1]["seq"], value["timeline"][2]["seq"] = 3, 2
        value["events"]["timeline_sha256"] = bundle._digest(bundle._canonical(value["timeline"]))
        self.add_source(value, "host_diagnostics_v1")
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_sequence_order")

    def test_diagnostics_record_binding_conflict_rejected(self):
        value = self.diagnostics(); value["timeline"][0]["facts"] = {"session_id": uid()}
        value["events"]["timeline_sha256"] = bundle._digest(bundle._canonical(value["timeline"]))
        self.add_source(value, "host_diagnostics_v1")
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_binding_mismatch")

    def test_diagnostics_conflicting_profile_identity_rejected(self):
        value = self.diagnostics(); value["effective_profile"]["profile_id"] = uid()
        self.add_source(value, "host_diagnostics_v1")
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "source_binding_mismatch")

    def test_boolean_schema_version_is_not_version_one(self):
        self.add_envelope(schema_version=True)
        self.assertEqual(self.build()["source_index"][0]["reason_code"], "envelope_schema_unsupported")

    def test_invalid_source_cannot_be_overridden_by_later_valid_source(self):
        self.add_envelope(complete=False); self.add_envelope()
        self.assertEqual(self.build()["layers"]["configuration"]["status"], "invalid")


if __name__ == "__main__": unittest.main()
