"""Explicit public projections and bounded, reproducible JSON diagnostics.

SQLite remains the authority. Exports are immutable projections of one recent
event snapshot, not a replacement ledger or proof of physical control release.
Free-form traits, provider payloads, native addresses and raw logs are excluded.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import re
import sys
import tomllib
import uuid

from .contracts import ContractError, canonical_json, content_hash, identifier

ROOT = Path(__file__).resolve().parents[2]
# A normal macro match can exceed 2,000 repeated native observations. Keep the
# journal's bounded page ceiling and the separate 8 MiB native-reader ceiling.
MAX_EXPORT_EVENTS = 10000
MAX_EXPORT_BYTES = 8 * 1024 * 1024
EVENTS = frozenset({"run_registered", "command_reserved", "dispatch_intent_committed", "command_outcome", "native_sequence_reserved",
    'macro_native_feedback','macro_host_stop_started','model_macro_dispatch_prepared','model_macro_native_acknowledged','model_macro_dispatch_unknown',
    'model_macro_production_prepared','model_macro_production_acknowledged','macro_production_preference_released','macro_production_feedback',
    'model_macro_scout_prepared','model_macro_scout_acknowledged','macro_scout_preference_released','macro_scouting_feedback',
    'model_macro_region_prepared','model_macro_region_acknowledged','macro_region_preference_released','macro_regional_feedback',
    'macro_context_rejected','macro_decision_deferred','macro_sample_deferred',
    'macro_plan_not_dispatched',
    "host_started", "host_stopped", "host_fault", "executor_connected", "natural_observer_started", "entered_match",
    "task_feedback", "task_proposed", "plan_applied", "dispatch_pending", "dispatch_unknown", "decision", "sample_retry", "sampling_failed",
    "native_result_candidate", "native_result_candidate_after_cleanup", "terminal_feedback_incomplete", "executor_restoration_unverified",
    "tactical_restoration_unverified", "reserve_control_release_unverified", "commander_profile_applied",
    "commander_model_backend_constructed", "commander_model_call_started", "commander_model_response_returned",
    "commander_model_call_failed", "commander_model_call_cancelled",'runtime_model_task_feedback',
    'runtime_model_preparation_exhausted','runtime_tactical_waiting_successor','runtime_tactical_epoch_renewed'})
IDENTIFIERS = frozenset({"profile_id", "connection_id", "session_id", "commander_id", "host_id", "task_id", "plan_id", "request_id", "command_id"})
HASHES = frozenset({"effective_hash", "binding_hash", "fingerprint", "channel_hash", "traits_sha256", "game_sha256", "mod_sha256"})
CODES = frozenset({"operation", "status", "reason_code", "state", "stage", "application_scope", "transport_mode", "module", "purpose", "focus", "source"})
NUMBERS = frozenset({"player_id", "profile_revision", "revision", "schema_version", "personality", "traits_bytes", "call_sequence", "calls_started",
    "responses_returned", "snapshot_id", "based_on_game_time_seconds", "at_game_seconds", "first_game_time_seconds", "wall_seconds",
    "seq", "sequence", "host_pid", "consecutive", "generation", "expires_at_game_seconds", "updated_at_game_seconds", "spend_fraction",
    "force_fraction", "priority", "requests", "accepted", "rejected", "timeouts", "adapter_errors", "plan_changes", "dispatches", "started", "completed", "failed", "blocked",'paid_units_available'})
BOOLEANS = frozenset({"model_response_received", "real_network_verified", "behavior_verified", "traits_truncated", "execution_requested",
                      "native_release_verified", "host_dispatch_candidate", "model_consumed",'physical_home','control_released','mission_effect_verified'})


def _scalar(key, value):
    if key in IDENTIFIERS:
        try:return identifier(value)
        except ContractError:return None
    if key in HASHES and isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value):return value
    if key in CODES and isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value):return value
    if key in NUMBERS and type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 2**53 - 1:
        fractional = key.endswith("seconds") or key in {"wall_seconds", "spend_fraction", "force_fraction"}
        if not fractional and type(value) is not int:return None
        if key in {"spend_fraction", "force_fraction"} and value > 1:return None
        return value
    if key in BOOLEANS and type(value) is bool:return value
    if key == "model" and isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", value):return value
    return None


def project_fields(value):
    if not isinstance(value, dict):return {}
    result = {}
    for key, item in value.items():
        projected = _scalar(key, item)
        if projected is not None:result[key] = projected
    return result


def project_event(event, expected=None, binding=None):
    known = event["event_type"] in EVENTS
    result = dict(seq=event["seq"], event_type=event["event_type"] if known else "unprojected_event",
                  created_at=event["created_at"], payload_sha256=content_hash(event["payload"]),
                  payload_projected=known)
    for key in ("command_id", "game_frame", "monotonic_ns"):
        if event.get(key) is not None:result[key] = event[key]
    if known:
        result["facts"] = project_fields(event["payload"])
        if isinstance(event["payload"].get("receipt"), dict):
            result["facts"]["receipt"] = project_fields(event["payload"]["receipt"])
        if event['event_type'] in ('macro_regional_feedback','macro_region_preference_released',
                'model_macro_region_prepared','model_macro_region_acknowledged','macro_scouting_feedback'):
            payload=event['payload']
            if event['event_type']=='macro_region_preference_released':payload=payload.get('feedback',{})
            if isinstance(payload,dict):
                for key in ('observed_frame','view_frame','active_native_tactics','allocated_native_groups',
                        'moved_native_groups','groups_progressing_toward_region','new_legal_contacts_since_intent','defender_groups_near_infrastructure',
                        'groups_near_home_region','withdrawing_native_groups'):
                    value=payload.get(key);maximum=0xffffffff if key.endswith('_frame') else 8192
                    if type(value) is int and 0<=value<=maximum:result['facts'][key]=value
                for key in ('native_execution_observed','policy_released'):
                    if type(payload.get(key)) is bool:result['facts'][key]=payload[key]
                targets={'deployattack':'region_1_3','deploydefense':'region_8_3','regroup':'region_8_3','withdraw':'region_8_3','reinforce':'region_8_3'}
                action=payload.get('action')
                if action in targets and payload.get('target_region')==targets[action]:
                    result['facts'].update(action=action,target_region=targets[action])
                elif event['event_type'].startswith('model_macro_region_'):
                    actions=payload.get('actions',[])
                    regional=[a for a in actions if isinstance(a,str) and a in targets] if type(actions) is list else []
                    if len(regional)==1 and payload.get('target_region')==targets[regional[0]]:
                        result['facts'].update(action=regional[0],target_region=targets[regional[0]])
                result['facts'].update(arrival_verified=False,mission_success_verified=False)
                if (payload.get('goal')=='original_native_defense_of_own_infrastructure'
                        and payload.get('target_region')=='region_8_3'):
                    result['facts']['goal']='original_native_defense_of_own_infrastructure'
                role_goals={'regroup':'regroup_native_force_at_own_home_waypoint',
                    'withdraw':'withdraw_native_group_to_own_home_region','reinforce':'reinforce_own_base_through_original_reactive_defense'}
                role_action=result['facts'].get('action')
                if role_action in role_goals and payload.get('goal')==role_goals[role_action]:result['facts']['goal']=role_goals[role_action]
        if event["event_type"] == "plan_applied":
            payload = event["payload"]; plan = project_plan(payload.get("plan"))
            matches = bool(plan.get("plan_id") and "snapshot_id" in plan and plan.get("plan_id") == payload.get("plan_id")
                and plan.get("snapshot_id") == payload.get("snapshot_id")
                and (binding is None or (plan.get("session_id"),plan.get("commander_id"),plan.get("player_id"))
                    == (binding.session_id,binding.commander_id,binding.player_id)))
            result["plan_binding_matches"] = matches
            if matches:result["facts"]["plan"] = plan
        if event["event_type"] == "task_proposed":
            payload = event["payload"]
            proposals, _ = project_tasks([payload.get("proposal")])
            proposal = proposals[0] if proposals else {}
            matches = bool({"task_id","plan_id","generation"} <= proposal.keys()
                and all(proposal.get(key) == payload.get(key) for key in ("task_id","plan_id","generation"))
                and (binding is None or (payload.get("session_id"),payload.get("commander_id"),payload.get("player_id"))
                    == (binding.session_id,binding.commander_id,binding.player_id)))
            result["proposal_binding_matches"] = matches
            if matches:
                result["facts"]["proposal"] = proposal
                if payload.get("execution_authorized") is False:result["facts"]["execution_authorized"] = False
        if event["event_type"].startswith(("commander_profile_", "commander_model_")):
            payload = event["payload"]
            matches = bool(expected and binding and payload.get("profile_id") == binding.commander_id
                and payload.get("profile_revision") == expected.get("profile_revision")
                and payload.get("effective_hash") == expected.get("effective_hash")
                and payload.get("session_id", binding.session_id) == binding.session_id)
            result["profile_binding_matches"] = matches
            if not matches:result["facts"] = {}
    else:result["event_type_sha256"] = hashlib.sha256(event["event_type"].encode()).hexdigest()
    return result


def recent_events(journal, run_id, *, limit=30, expected=None, binding=None):
    page = journal.latest_events(run_id, limit=limit)
    events = [project_event(event, expected, binding) for event in page["events"]]
    cursor = dict(first_seq=page["first_seq"], last_seq=page["last_seq"], total_count=page["total_count"],
                  overflow=page["total_count"] - len(events), truncated=page["truncated"], window="latest")
    return events, cursor


def project_tasks(jobs):
    if not isinstance(jobs, list):return [], dict(total_count=0, truncated=False, schema_valid=False)
    tasks = []
    for job in jobs[:64]:
        if not isinstance(job, dict):continue
        task = project_fields(job)
        if "task_id" not in task:continue
        if (isinstance(job.get("budget"), dict) and job["budget"].get("unit") == "fraction_of_observed_credits"
            and type(job["budget"].get("fraction")) in (int, float)):
            fraction = job["budget"]["fraction"]
            if math.isfinite(fraction) and 0 <= fraction <= 1:
                task["budget"] = dict(unit="fraction_of_observed_credits", fraction=fraction)
        for key in ("resource_locks", "required_roles"):
            values = job.get(key)
            if isinstance(values, (list, tuple)) and len(values) <= 16 and all(
                isinstance(item, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", item) for item in values):
                task[key] = list(values)
        for key in ("formation_ids",):
            values = job.get(key)
            if isinstance(values, (list, tuple)) and len(values) <= 16:
                try:task[key] = [identifier(item) for item in values]
                except ContractError:pass
        if isinstance(job.get("formation_versions"), (list, tuple)) and len(job["formation_versions"]) <= 16:
            versions = []
            for pair in job["formation_versions"]:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:break
                try:ident = identifier(pair[0])
                except ContractError:break
                if type(pair[1]) is not int or not 0 <= pair[1] <= 2**53 - 1:break
                versions.append([ident, pair[1]])
            else:task["formation_versions"] = versions
        region = job.get("target_region")
        if isinstance(region, str) and re.fullmatch(r"(?:home_base|region_[m0-9]+_[m0-9]+)", region):task["target_region"] = region
        try:task["target_contact_id"] = identifier(job.get("target_contact_id"))
        except ContractError:pass
        task["stage"] = task.get("status", "unknown")
        tasks.append(task)
    return tasks, dict(total_count=len(jobs), truncated=len(jobs) > len(tasks), schema_valid=True)


def project_plan(value):
    """Structured strategy only; no provider text, traits or private pointers."""
    if not isinstance(value, dict):return {}
    keys = {"plan_id","session_id","commander_id","player_id","snapshot_id",
            "based_on_game_time_seconds","expires_at_game_seconds","reason_code"}
    result = project_fields({key:item for key,item in value.items() if key in keys})
    actions=value.get('macro_actions')
    if (isinstance(actions,list) and len(actions)<=5 and all(type(action) is str and action in {
            'budgeteconomy','budgetarmy','budgettech','build_airfield','buildreactor','buildtech','economyrefinery',
            'produceconscript','produceflak','producetank','scout','deployattack','deploydefense','regroup','reinforce','withdraw'} for action in actions)):
        result['macro_actions']=list(actions)
    quantity=value.get('macro_production')
    if (type(quantity) is dict and set(quantity)=={'action','additional_count'}
            and quantity['action'] in ('produceconscript','produceflak','producetank')
            and quantity['action'] in result.get('macro_actions',())
            and type(quantity['additional_count']) is int and 1<=quantity['additional_count']<=3):
        result['macro_production']=dict(quantity)
    enums = dict(stance={"defend","scout","pressure","raid","expand"},
        production_focus={"native_baseline","balanced","anti_air","anti_armor","infantry","naval","economy"},
        economy_policy={"stabilize","expand_if_defensible","save"},
        tech_policy={"hold_current_tier","advance_if_affordable"},origin={"model","local_fallback"})
    for key,allowed in enums.items():
        item=value.get(key)
        if isinstance(item,str) and item in allowed:result[key]=item
    if result.get("reason_code") not in {"air_threat","armor_threat","economy_window","defensive_emergency","balanced_default","tech_window"}:
        result.pop("reason_code",None)
    budget=value.get("budget")
    if (isinstance(budget,dict) and set(budget)=={"economy","army","tech","reserve"}
        and all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in budget.values())
        and abs(sum(budget.values())-1)<=1e-6 and .05<=budget["reserve"]<=.6):
        result["budget"]=dict(budget)
    region=value.get("objective_region")
    if isinstance(region,str) and re.fullmatch(r"(?:home_base|region_[m0-9]+_[m0-9]+)",region):result["objective_region"]=region
    intents=value.get("tactical_tasks")
    if isinstance(intents,list) and len(intents)<=3:
        result["tactical_task_count"]=len(intents)
        result["tactical_tasks_sha256"]=content_hash(intents)
    return result


def project_profile(profile):
    if not isinstance(profile, dict):raise ContractError("diagnostics_unavailable")
    result = project_fields(profile)
    preferences = profile.get("preferences", {})
    if isinstance(preferences, dict):
        result["preferences"] = {key: value for key, value in preferences.items()
            if key in {"attack", "risk", "economy", "scouting", "pursuit"} and type(value) is int and 1 <= value <= 5}
        if preferences.get("preset") in {"steady", "balanced", "pressure", "flank", "custom"}:
            result["preferences"]["preset"] = preferences["preset"]
    for name in ("traits", "custom_traits", "generated_traits"):
        if isinstance(profile.get(name), str):result[name + "_sha256"] = hashlib.sha256(profile[name].encode()).hexdigest()
    result["free_text_included"] = False
    return result


def _file_index(label, path, allowed):
    try:
        path = Path(path).resolve(strict=True)
        if not path.is_relative_to(Path(allowed).resolve()) or not path.is_file():raise OSError()
        before = path.stat(); digest = hashlib.sha256(); count = 0
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block); count += len(block)
        after = path.stat()
        return dict(label=label, sha256=digest.hexdigest(), bytes=count, content_included=False,
                    stable_during_read=before.st_size == after.st_size == count and before.st_mtime_ns == after.st_mtime_ns)
    except OSError:return dict(label=label, available=False, content_included=False)


def software_manifest():
    packages = []
    for name in ("pydantic-ai-slim", "pydantic", "httpx"):
        try:version = metadata.version(name)
        except metadata.PackageNotFoundError:version = "not_installed"
        packages.append(dict(name=name, version=version))
    components = []
    for relative in ("desktop-ui/package.json", "agent_runtime/pyproject.toml", "integration/battle_host.py",
                     "integration/host_runtime/desktop_backend.py", "integration/host_runtime/diagnostics.py",
                     "integration/host_runtime/journal.py", "integration/host_runtime/profiles.py", "integration/host_runtime/host_production.py",
                     "production/persistent/bin-v2/ProductionPersistent.dll", "production/persistent/bin-v2/persistent_host.exe"):
        row = _file_index(relative, ROOT / relative, ROOT)
        if relative.endswith("package.json"):
            try:row["version"] = json.loads((ROOT / relative).read_text(encoding="utf-8"))["version"]
            except (OSError, ValueError, KeyError):pass
        if relative.endswith("pyproject.toml"):
            try:row["version"] = tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))["project"]["version"]
            except (OSError, ValueError, KeyError):pass
        components.append(row)
    return dict(python=sys.version.split()[0], packages=packages, components=components, observation_scope="export_time_files")


def create_export(state_dir, *, run_id, request_id, binding, profile, status, journal, raw_files):
    identifier(run_id); identifier(request_id)
    export_id = str(uuid.uuid5(uuid.UUID(run_id), "diagnostics:" + request_id))
    directory = Path(state_dir).resolve() / "exports"; directory.mkdir(parents=True, exist_ok=True)
    if directory.resolve().parent != Path(state_dir).resolve():raise ContractError("diagnostics_unavailable")
    target = directory / (export_id + ".json")
    if target.exists():
        if target.is_symlink():raise ContractError("diagnostics_unavailable")
        with target.open("rb") as source:raw = source.read(MAX_EXPORT_BYTES + 1)
        if len(raw) > MAX_EXPORT_BYTES:raise ContractError("diagnostics_unavailable")
        document = json.loads(raw)
        if document.get("run_id") != run_id or document.get("export_id") != export_id:raise ContractError("diagnostics_unavailable")
    else:
        page = journal.latest_events(run_id, limit=MAX_EXPORT_EVENTS)
        expected = dict(profile_revision=profile["revision"], effective_hash=profile["effective_hash"]) if profile else None
        timeline = [project_event(event, expected, binding) for event in page["events"]]
        document = dict(schema_version=1, kind="tacticore_redacted_diagnostics", redacted=True, export_id=export_id, run_id=run_id,
            generated_at=datetime.now(timezone.utc).isoformat(), binding=binding.public(), binding_hash=binding.binding_hash,
            effective_profile=project_profile(profile) if profile else None,
            effective_profile_available=profile is not None, status=status, timeline=timeline,
            events=dict(total_count=page["total_count"], exported_count=len(timeline), first_seq=page["first_seq"],
                last_seq=page["last_seq"], truncated=page["truncated"], window="latest",
                source_snapshot_sha256=content_hash(page["events"]), timeline_sha256=content_hash(timeline)),
            software=software_manifest(), raw_file_index=[_file_index(label, path, allowed) for label, path, allowed in raw_files],
            redaction=dict(policy_version=1, free_text_traits=False, provider_payloads=False, raw_log_contents=False,
                           private_native_addresses=False, credentials=False, unknown_event_payloads=False),
            authority="sqlite_command_journal", native_release_verified=False,
            evidence_note="Reported events and file hashes are not independent proof of game outcome or control release.")
        raw = (canonical_json(document) + "\n").encode("utf-8")
        if len(raw) > MAX_EXPORT_BYTES:raise ContractError("diagnostics_unavailable")
        # UUID is derived from request identity. Exclusive creation preserves a
        # repeated export request's exact bytes even across service restarts.
        temporary = directory / ("." + str(uuid.uuid4()) + ".tmp")
        try:
            with temporary.open("xb") as output:
                output.write(raw); output.flush(); os.fsync(output.fileno())
            os.link(temporary, target)
        except FileExistsError:
            return create_export(state_dir, run_id=run_id, request_id=request_id, binding=binding,
                                 profile=profile, status=status, journal=journal, raw_files=raw_files)
        finally:temporary.unlink(missing_ok=True)
    return dict(export_id=export_id, run_id=run_id, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                event_count=document["events"]["total_count"], exported_event_count=document["events"]["exported_count"],
                truncated=document["events"]["truncated"], redacted=True)
