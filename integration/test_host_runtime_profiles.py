"""Pure contract checks: no game process, model request, or credential access."""

from dataclasses import replace
import json
import unittest
import uuid

from host_runtime.contracts import ContractError, ProfileApplication, SessionBinding
from host_runtime.profiles import commander_available, commanders_metadata, normalize_profile, normalize_desktop_profile

PROFILE = "c37de935-529b-4129-85f2-7596ccdc6a12"
CONNECTION = "f76d0537-8b7b-4540-b5ed-c1558b2b7e32"


def binding():
    return SessionBinding.from_dict(
        dict(
            schema_version=1,
            session_id="7233de3c-d636-471d-9fd1-33af63bdc566",
            player_id=3,
            commander_id=PROFILE,
            game_process_id=101,
            game_process_start="2026-10-26T11:00:00+08:00",
            host_id="37c61e0d-13bb-4acb-96a3-bc42459d2e3d",
            game_sha256="a" * 64,
            mod_sha256="b" * 64,
        )
    )


def draft(**changes):
    value = dict(
        schema_version=1,
        profile_id=PROFILE,
        name="铁锤",
        revision=1,
        connection_id=CONNECTION,
        model="",
        commander_id="hammer",
        personality=dict(PRESETS["hammer"]),
        voice_note="保留撤退空间。",
    )
    value.update(changes)
    return value


PRESETS = {
    "hammer": dict(
        aggression=4,
        risk=3,
        persistence=3,
        punish=5,
        preserve=3,
        deception=2,
        grudge=3,
        adaptability=4,
        bait_awareness=5,
    ),
    "bastion": dict(
        aggression=2,
        risk=2,
        persistence=2,
        punish=4,
        preserve=5,
        deception=3,
        grudge=2,
        adaptability=5,
        bait_awareness=4,
    ),
    "ghost": dict(
        aggression=3,
        risk=4,
        persistence=5,
        punish=4,
        preserve=4,
        deception=5,
        grudge=3,
        adaptability=5,
        bait_awareness=3,
    ),
}


class ProfileContracts(unittest.TestCase):
    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_presets_carry_exactly_the_character_document_values(self):
        hashes = set()
        for commander, values in PRESETS.items():
            profile = normalize_profile(draft(commander_id=commander, personality=dict(values)))
            self.assertEqual(profile.personality_dict(), values)
            self.assertEqual(profile.public()["personality"], values)
            self.assertIn("保留撤退空间。", profile.traits)
            hashes.add(profile.effective_hash)
        self.assertEqual(len(hashes), 3)
        self.assertCode(
            "preset_personality_mismatch",
            lambda: normalize_profile(draft(personality=dict(PRESETS["hammer"], risk=4))),
        )

    def test_only_hammer_and_custom_are_available_and_metadata_lists_all(self):
        rows = {row["id"]: row for row in commanders_metadata()}
        self.assertEqual(set(rows), {"hammer", "bastion", "ghost", "custom"})
        self.assertEqual(rows["hammer"]["full_name"], "维克托·莫罗佐夫")
        self.assertEqual(rows["hammer"]["faction"], "Soviet")
        self.assertTrue(commander_available("hammer"))
        self.assertTrue(commander_available("custom"))
        self.assertFalse(commander_available("bastion"))
        self.assertFalse(commander_available("ghost"))

    def test_custom_accepts_any_level_and_rejects_out_of_range(self):
        low = normalize_profile(draft(commander_id="custom", personality={k: 1 for k in PRESETS["hammer"]}))
        high = normalize_profile(draft(commander_id="custom", personality={k: 5 for k in PRESETS["hammer"]}))
        self.assertNotEqual(low.traits, high.traits)
        self.assertNotEqual(low.effective_hash, high.effective_hash)
        for invalid in [True, False, 0, 6, 1.0, "3"]:
            self.assertCode(
                "invalid_personality_level",
                lambda: normalize_profile(
                    draft(commander_id="custom", personality=dict(PRESETS["hammer"], risk=invalid))
                ),
            )
        self.assertCode("invalid_commander", lambda: normalize_profile(draft(commander_id="tank")))
        self.assertCode(
            "unexpected_fields", lambda: normalize_profile(draft(personality=dict(PRESETS["hammer"], pursuit=3)))
        )

    def test_old_doctrine_drafts_load_as_the_hammer_preset(self):
        old = draft(doctrine="defense", custom_traits="旧描述")
        for key in ("commander_id", "personality", "voice_note"):
            del old[key]
        profile = normalize_profile(dict(old, preferences=dict(preset="steady")))
        self.assertEqual(profile.commander_id, "hammer")
        self.assertEqual(profile.personality_dict(), PRESETS["hammer"])
        self.assertEqual(profile.voice_note, "")
        mixed = normalize_profile(dict(draft(), doctrine="defense", custom_traits="旧描述"))
        self.assertEqual(mixed.effective_hash, normalize_profile(draft()).effective_hash)
        partial = draft()
        del partial["voice_note"]
        self.assertCode("unexpected_fields", lambda: normalize_profile(partial))

    def test_voice_note_utf8_limit_is_300_bytes(self):
        note = "中" * 100
        self.assertEqual(normalize_profile(draft(voice_note=note)).voice_note, note)
        self.assertCode("voice_note_too_long", lambda: normalize_profile(draft(voice_note=note + "a")))

    def test_revision_and_voice_note_changes_are_bound_into_hash(self):
        profile = normalize_profile(draft())
        self.assertEqual(profile.effective_hash, normalize_profile(draft()).effective_hash)
        self.assertNotEqual(profile.effective_hash, normalize_profile(draft(revision=2)).effective_hash)
        self.assertNotEqual(profile.effective_hash, normalize_profile(draft(voice_note="先侦察。")).effective_hash)
        self.assertCode("effective_profile_hash_mismatch", lambda: replace(profile, revision=2))

    def test_ids_are_explicitly_mapped_and_secrets_cannot_enter_public_schema(self):
        desktop = dict(
            id="iron",
            name="铁锤",
            callsign="01",
            doctrine="assault",
            traits="",
            connectionId="deepseek",
            modelOverride="",
            revision=1,
        )
        profile = normalize_desktop_profile(
            desktop, profile_ids={"iron": PROFILE}, connection_ids={"deepseek": CONNECTION}
        )
        self.assertEqual(profile.profile_id, PROFILE)
        self.assertEqual(profile.connection_id, CONNECTION)
        self.assertCode(
            "unmapped_profile_id",
            lambda: normalize_desktop_profile(desktop, profile_ids={}, connection_ids={"deepseek": CONNECTION}),
        )
        self.assertCode(
            "duplicate_mapped_id",
            lambda: normalize_desktop_profile(
                desktop, profile_ids={"iron": PROFILE, "ghost": PROFILE}, connection_ids={"deepseek": CONNECTION}
            ),
        )
        for secret in ("api_key", "key", "endpoint", "credential", "appliedToHost"):
            self.assertCode(
                "unexpected_fields",
                lambda: normalize_desktop_profile(
                    {**desktop, secret: "DO_NOT_EXPORT"},
                    profile_ids={"iron": PROFILE},
                    connection_ids={"deepseek": CONNECTION},
                ),
            )
        self.assertNotIn("DO_NOT_EXPORT", json.dumps(profile.public()))

    def test_unknown_schema_missing_binding_identity_and_pid_reuse(self):
        self.assertCode("unsupported_schema_version", lambda: normalize_profile(draft(schema_version=2)))
        self.assertCode("invalid_profile_revision", lambda: normalize_profile(draft(revision=True)))
        original = binding()
        changed = replace(original, game_process_start="2026-10-26T11:01:00+08:00")
        self.assertNotEqual(original.binding_hash, changed.binding_hash)
        for field in ("game_process_start", "host_id", "game_sha256", "mod_sha256"):
            raw = original.public()
            del raw[field]
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
        self.assertCode(
            "unsupported_application_claim",
            lambda: ProfileApplication.from_dict({**receipt.public(), "model_consumed": True}),
        )
        self.assertCode(
            "profile_commander_mismatch",
            lambda: ProfileApplication.accept(
                profile, replace(binding(), commander_id=str(uuid.uuid4())), str(uuid.uuid4())
            ),
        )
        self.assertNotEqual(receipt.effective_hash, normalize_profile(draft(revision=2)).effective_hash)


if __name__ == "__main__":
    unittest.main()
