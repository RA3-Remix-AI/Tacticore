"""Check the Host's stop proof: the native AI is back on its own settings.

At STOP the SDK (client.Probe.independent_release) reads the actual game
state once: manager components at their captured baseline, no commander flag
set, the enemy selector automatic again and the common lease returned. It only
writes independent-release.json when every read matched. This module checks
the few fields of that proof that matter; it does not replay the reads.
"""

import hashlib
import json
from pathlib import Path
import uuid

from .native_focus_observation import at_baseline
from .native_journal import SHARED_SIZE, VERSION, verified as journal_verified

KIND = "native_release_v2"


def restored(proof, *, pid, ticks, session_id):
    """Whether one independent-release proof shows the original settings back."""
    try:
        native = proof["native"]
        binding = native["binding"]
        identity = (
            binding["pid"] == pid
            and (binding["start_low"] | binding["start_high"] << 32) == ticks
            and bytes(binding["session"]) == uuid.UUID(session_id).bytes
        )
        returned = (
            native["version"] == VERSION
            and native["size"] == SHARED_SIZE
            and native["phase"] == 2
            and native["error"] == 0
            and native["cleanup_verified"] == 1
            and native["lease_held"] == 0
            and native["hook_held"] == 0
            and native["applied_mask"] == 0
            and native["flag_deadline"] == 0
        )
        gates = all(gate["phase"] in (0, 4) for gate in native["gates"])
        focus = native["focus"]["phase"] in (0, 4) and at_baseline(proof["enemy_focus"])
        return (
            proof.get("native_release_verified") is True
            and proof.get("host_process_ended") is True
            and proof.get("host_returncode") == 0
            and identity
            and returned
            and gates
            and focus
        )
    except (KeyError, TypeError, ValueError):
        return False


def verified_final(final, proof_path, session, binding):
    """The transport's final-state.json, its proof file and journal agree."""
    try:
        raw = Path(proof_path).read_bytes()
        proof = json.loads(raw)
        journal = Path(proof_path).with_name("native-journal.bin").read_bytes()
        return (
            final.get("native_release_contract") == KIND
            and final.get("cleanup_verified") is True
            and final["session_id"] == binding.session_id
            and final["pid"] == binding.game_process_id
            and final["independent_release_sha256"] == hashlib.sha256(raw).hexdigest()
            and final["native_journal_sha256"] == hashlib.sha256(journal).hexdigest()
            and journal_verified(journal, proof["native"])
            and restored(
                proof,
                pid=binding.game_process_id,
                ticks=session["process_creation_filetime"],
                session_id=binding.session_id,
            )
        )
    except (OSError, KeyError, TypeError, ValueError):
        return False
