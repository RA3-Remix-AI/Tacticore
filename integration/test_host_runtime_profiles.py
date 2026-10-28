"""Pure contract checks: no game process, model request, or credential access."""
from dataclasses import replace
import json
import unittest
import uuid

from host_runtime.contracts import ContractError, ProfileApplication, SessionBinding
from host_runtime.profiles import normalize_profile, normalize_desktop_profile

PROFILE = "c37de935-529b-4129-85f2-7596ccdc6a12"
CONNECTION = "f76d0537-8b7b-4540-b5ed-c1558b2b7e32"


def binding():
    return SessionBinding.from_dict(dict(schema_version=1, session_id="7233de3c-d636-471d-9fd1-33af63bdc566",
        player_id=3, commander_id=PROFILE, game_process_id=101,
        game_process_start="2026-10-26T11:00:00+08:00", host_id="37c61e0d-13bb-4acb-96a3-bc42459d2e3d",
        game_sha256="a" * 64, mod_sha256="b" * 64))


def draft(**changes):
    value = dict(schema_version=1, profile_id=PROFILE, name="铁锤", revision=1, connection_id=CONNECTION,
                 model="", doctrine="assault", custom_traits="保留撤退空间。")
    value.update(changes)
    return value


def preferences(preset="pressure", **changes):
    value = dict(preset=preset, attack=4, risk=4, economy=2, scouting=3, pursuit=4)
    value.update(changes)
    return value


class ProfileContracts(unittest.TestCase):
    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_four_real_ui_presets_preserve_personality_and_distinct_levels(self):
        cases = [
            ("steady", "defense", 1, (2, 1, 4, 3, 1)),
            ("balanced", "defense", 1, (3, 3, 3, 3, 3)),
            ("pressure", "assault", 0, (4, 4, 2, 3, 4)),
            ("flank", "maneuver", 2, (3, 2, 3, 5, 2)),
        ]
        hashes = set()
        for preset, doctrine, personality, levels in cases:
            prefs = dict(zip(("attack", "risk", "economy", "scouting", "pursuit"), levels), preset=preset)
            profile = normalize_profile(draft(doctrine=doctrine, preferences=prefs))
            self.assertEqual(profile.personality, personality)
            self.assertEqual(profile.levels, levels)
            self.assertIn("保留撤退空间。", profile.traits)
            hashes.add(profile.effective_hash)
        self.assertEqual(len(hashes), 4)

    def test_named_preset_does_not_accept_modified_values_or_wrong_doctrine(self):
        self.assertCode("preset_doctrine_or_values_mismatch", lambda: normalize_profile(draft(preferences=preferences(risk=2))))
        self.assertCode("preset_doctrine_or_values_mismatch", lambda: normalize_profile(draft(doctrine="defense", preferences=preferences())))

    def test_custom_extremes_and_boolean_levels_are_distinct(self):
        for invalid in [True, False, 0, 6, 1.0, "3"]:
            self.assertCode("invalid_preference_level", lambda: normalize_profile(draft(preferences=preferences("custom", risk=invalid))))
        low = normalize_profile(draft(preferences=preferences("custom", risk=1)))
        high = normalize_profile(draft(preferences=preferences("custom", risk=5)))
        self.assertNotEqual(low.traits, high.traits)
        self.assertNotEqual(low.effective_hash, high.effective_hash)

    def test_utf8_exact_limit_is_accepted_and_one_byte_over_rejected(self):
        base = normalize_profile(draft(custom_traits="", preferences=preferences()))
        allowance = 1200 - len(base.generated_traits.encode("utf-8")) - 1
        custom = "中" * (allowance // 3) + "a" * (allowance % 3)
        profile = normalize_profile(draft(custom_traits=custom, preferences=preferences()))
        self.assertEqual(profile.traits_bytes, 1200)
        self.assertEqual(profile.custom_traits, custom)
        self.assertFalse(profile.public()["traits_truncated"])
        self.assertCode("traits_budget_exceeded", lambda: normalize_profile(draft(custom_traits=custom + "a", preferences=preferences())))

    def test_revision_and_custom_trait_changes_are_bound_into_hash(self):
        profile = normalize_profile(draft())
        self.assertEqual(profile.effective_hash, normalize_profile(draft()).effective_hash)
        self.assertNotEqual(profile.effective_hash, normalize_profile(draft(revision=2)).effective_hash)
        self.assertNotEqual(profile.effective_hash, normalize_profile(draft(custom_traits="先侦察。")).effective_hash)
        self.assertCode("effective_profile_hash_mismatch", lambda: replace(profile, revision=2))

    def test_ids_are_explicitly_mapped_and_secrets_cannot_enter_public_schema(self):
        desktop = dict(id="iron", name="铁锤", callsign="01", doctrine="assault", traits="", connectionId="deepseek", modelOverride="", revision=1)
        profile = normalize_desktop_profile(desktop, profile_ids={"iron": PROFILE}, connection_ids={"deepseek": CONNECTION})
        self.assertEqual(profile.profile_id, PROFILE)
        self.assertEqual(profile.connection_id, CONNECTION)
        self.assertCode("unmapped_profile_id", lambda: normalize_desktop_profile(desktop, profile_ids={}, connection_ids={"deepseek": CONNECTION}))
        self.assertCode("duplicate_mapped_id", lambda: normalize_desktop_profile(desktop, profile_ids={"iron": PROFILE, "ghost": PROFILE}, connection_ids={"deepseek": CONNECTION}))
        for secret in ("api_key", "key", "endpoint", "credential", "appliedToHost"):
            self.assertCode("unexpected_fields", lambda: normalize_desktop_profile({**desktop, secret: "DO_NOT_EXPORT"}, profile_ids={"iron": PROFILE}, connection_ids={"deepseek": CONNECTION}))
        self.assertNotIn("DO_NOT_EXPORT", json.dumps(profile.public()))

    def test_unknown_schema_missing_binding_identity_and_pid_reuse(self):
        self.assertCode("unsupported_schema_version", lambda: normalize_profile(draft(schema_version=2)))
        self.assertCode("invalid_profile_revision", lambda: normalize_profile(draft(revision=True)))
        original = binding()
        changed = replace(original, game_process_start="2026-10-26T11:01:00+08:00")
        self.assertNotEqual(original.binding_hash, changed.binding_hash)
        for field in ("game_process_start", "host_id", "game_sha256", "mod_sha256"):
            raw = original.public(); del raw[field]
            self.assertCode("unexpected_fields", lambda: SessionBinding.from_dict(raw))
        self.assertCode("invalid_process_start", lambda: replace(original, game_process_start="unknown"))
        self.assertCode("invalid_process_start", lambda: replace(original, game_process_start="2026-10-26T11:00:00"))

    def test_host_application_is_not_model_consumption_or_behavior_proof(self):
        profile = normalize_profile(draft())
        receipt = ProfileApplication.accept(profile, binding(), str(uuid.uuid4()))
        self.assertEqual(receipt.profile_revision, 1)
        self.assertEqual(receipt.effective_hash, profile.effective_hash)
        self.assertEqual(receipt.status, "host_accepted")
        self.assertFalse(receipt.public()["model_consumed"])
        self.assertFalse(receipt.public()["behavior_verified"])
        self.assertEqual(receipt, ProfileApplication.from_dict(receipt.public()))
        self.assertCode("unsupported_application_claim", lambda: ProfileApplication.from_dict({**receipt.public(), "model_consumed": True}))
        self.assertCode("profile_commander_mismatch", lambda: ProfileApplication.accept(profile, replace(binding(), commander_id=str(uuid.uuid4())), str(uuid.uuid4())))
        self.assertNotEqual(receipt.effective_hash, normalize_profile(draft(revision=2)).effective_hash)


if __name__ == "__main__":
    unittest.main()
