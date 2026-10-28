"""One explicit real-provider request using a saved style and synthetic facts.

No game process, execution grant, actuator or raw request/response body is used.
The protected library is an explicit registered reference; credentials stay in
the existing Profile loader and never enter the report.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "strategy"))
from engine import Binding, ContractError as PolicyError, Snapshot, validate_policy
from http_adapter import load_profile, system_prompt
from host_runtime.application import apply_commander_draft, create_applied_backend
from host_runtime.desktop_registry import load_registration
from host_runtime.profile_store import ProfileStore
import fixtures


def write_new(path, report):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


async def probe(args):
    if not args.real_model:
        raise ValueError("explicit_real_model_required")
    if args.output.exists():
        raise ValueError("probe_output_must_be_new")
    home = Path(os.environ["LOCALAPPDATA"]) / "Tacticore"
    registration = load_registration(home)
    library = Path(registration["library_path"])
    store = ProfileStore(library, home / "desktop-runtime")
    try:
        record = store.get_profile(args.commander)["profile"]
    finally:
        store.close()
    base = load_profile(library, args.commander)
    applied = apply_commander_draft(base, record["draft"])
    if applied.effective.effective_hash != record["effective"]["effective_hash"]:
        raise ValueError("stored_effective_profile_changed")
    binding = Binding(str(uuid.uuid4()), 3, base.commander_id, base.commander_name, base.connection_id)
    raw = fixtures.snapshot()
    raw.update(session_id=binding.session_id, player_id=binding.player_id,
               enemy_observations=[], events=[],
               capabilities={"production_focus": ["native_baseline"], "regions": ["home_base"]})
    snapshot = Snapshot.from_dict(raw)
    context = snapshot.model_context(binding)
    prompt = system_prompt(applied.profile, context)
    events = []
    backend = create_applied_backend(applied, event_sink=lambda kind, data: events.append(dict(kind=kind, facts=data)),
                                     backend="pydantic", timeout=20, max_tokens=768,
                                     max_input_bytes=16384, max_inflight=1, http_retries=0)
    report = dict(schema_version=1, kind="saved_commander_application_real_provider_probe",
                  source="synthetic_observations_real_provider", registration_id=registration["registration_id"],
                  protected_library_sha256=registration["library_sha256"], profile_id=base.commander_id,
                  profile_revision=applied.effective.revision, effective_hash=applied.effective.effective_hash,
                  provider=base.provider, model=applied.profile.model, prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                  traits_sha256=hashlib.sha256(applied.profile.traits.encode("utf-8")).hexdigest(),
                  traits_bytes=applied.effective.traits_bytes, traits_truncated=False,
                  raw_request_persisted=False, raw_response_persisted=False, credentials_persisted=False,
                  game_access=False, sdk_game_commands=0, execution_authority_granted=False,
                  real_network_response_verified=False, policy_accepted=False, behavior_effect_verified=False)
    started = time.monotonic()
    try:
        result = await backend(context)
        report["real_network_response_verified"] = backend.observation().get('real_network_verified') is True
        report["response_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        try:
            policy = validate_policy(result, snapshot, snapshot, binding, 20)
            report["policy_accepted"] = True
            report["decision_summary"] = {key: getattr(policy, key) for key in ("stance", "production_focus", "economy_policy", "tech_policy")}
        except PolicyError:
            report["policy_rejection"] = "policy_contract_rejected"
    except Exception as error:
        report["error_type"] = type(error).__name__
        # No provider exception text, URL, prompt or body is exported.
    report.update(elapsed_seconds=round(time.monotonic()-started, 3),
                  model_consumption=backend.observation(), transport_metrics=dict(backend.metrics), events=events)
    write_new(args.output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commander", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--real-model", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(probe(args))
        print(json.dumps({key: result[key] for key in ("profile_revision", "effective_hash", "real_network_response_verified", "policy_accepted", "behavior_effect_verified", "elapsed_seconds")}, ensure_ascii=True))
        return 0 if result["real_network_response_verified"] and result["policy_accepted"] else 2
    except Exception as error:
        print(json.dumps({"probe_started": False, "error_type": type(error).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
