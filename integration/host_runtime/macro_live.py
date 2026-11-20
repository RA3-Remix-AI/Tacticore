"""Current native-AI identity and legal player-perspective macro observations."""

import hashlib
import json
from pathlib import Path, PureWindowsPath
import sys

from .contracts import ContractError
from .macro_policy_runtime import COMMANDER, MIN_MACRO_MODEL_GAME_SECONDS
from .macro_bundle import load_bundle
from .scenario import MODEL_CONSTRUCTION_YARD, MODEL_PLAYER_ID, MatchScenario, region_for_point

ROOT = Path(__file__).resolve().parents[2]


def require_base_origin(census, required_origin):
    yards = [r for r in census["own_objects"] if r["type_hash"] == MODEL_CONSTRUCTION_YARD]
    if not yards:
        raise ContractError("session_not_ready")
    if len(yards) != 1 or region_for_point(yards[0]["xyz"][0], yards[0]["xyz"][1]) != required_origin:
        raise ContractError("macro_base_defense_origin_outside_qualified_scope")


class MacroSampler:
    def __init__(self, session_path, bundle_path, *, scope=None):
        """Bind the lawful own view of one session. ``scope`` skips reloading the descriptor."""
        for folder in ("integration", "strategy", "production", "native-ai", "visibility"):
            path = str(ROOT / folder)
            if path not in sys.path:
                sys.path.insert(0, path)
        from projection import VisibilityProjection
        from collector import VisibilityCollector

        self.path = Path(session_path)
        self.raw = self.path.read_bytes()
        self.session = json.loads(self.raw.decode("utf-8-sig"))
        self.bundle_path = Path(bundle_path)
        self.bundle_raw = self.bundle_path.read_bytes()
        if scope is None:
            self.bundle, self.scope = load_bundle(bundle_path, self.session)
        else:
            self.bundle, self.scope = scope
        scenario = self.session.get("scenario", {})
        try:
            self.scenario = MatchScenario.from_session(scenario)
        except ContractError:
            raise ContractError("session_mismatch") from None
        if scenario.get("commander_id") != COMMANDER or self.scenario.model_player_id != MODEL_PLAYER_ID:
            raise ContractError("session_mismatch")
        self.opponent_player_ids = self.scenario.enemy_player_ids
        self.registry_path = Path(self.session["registry"])
        self.registry_raw = self.registry_path.read_bytes()
        self.registry = json.loads(self.registry_raw.decode("utf-8-sig"))
        from .native_transport import native_module

        _, sdk = native_module()
        self.memory = sdk.Memory(self.session["pid"], self.session)
        try:
            from .native_visibility import bind_session

            self.proof, self.safety = bind_session(self.memory, self.session, 3)
            if self.proof["commander_id"] != COMMANDER:
                raise ContractError("session_mismatch")
            self.owner = self.proof["handshake"]["player"]
            self.sequence = 0
            self.previous = 0
            self.state = None
            self.collector = VisibilityCollector(
                self.memory,
                self.session,
                3,
                VisibilityProjection(
                    self.session["session_id"], 3, self.session["mod_sha256"], self.proof, self.safety
                ),
            )
        except BaseException:
            self.memory.close()
            raise

    def collect(self):
        from read_match_state import snapshot
        from macro_observation import own_census
        from match_participants import verify_participants, controlled_match_result
        from read_selected_personality import inspect_player, resolve_registry
        from engine import Snapshot

        if (
            self.path.read_bytes() != self.raw
            or self.bundle_path.read_bytes() != self.bundle_raw
            or self.registry_path.read_bytes() != self.registry_raw
        ):
            raise ContractError("session_changed")
        state = snapshot(self.memory.read)
        self.state = state
        if not state["simulation_frame"]:
            raise ContractError("macro_match_ended")
        logic = self.memory.u32(0xCD8CE4)
        if logic != self.proof["handshake"]["game_logic"]:
            raise ContractError("session_changed")
        native = inspect_player(self.memory.read, self.owner)
        identity = resolve_registry(native, self.registry, self.session)
        if (
            identity["commander_id"] != COMMANDER
            or native["player_index"] != 3
            or not identity["personality_binding_verified"]
        ):
            raise ContractError("session_mismatch")
        pointer = self.memory.u32(logic + 0x98)
        path = PureWindowsPath(self.memory.read(pointer, 260).split(b"\0", 1)[0].decode("ascii"))
        expected = self.session["scenario"]["map_id"]
        if (
            path.suffix.lower() != ".map"
            or path.stem.lower() != expected.lower()
            or path.parent.name.lower() != expected.lower()
        ):
            raise ContractError("macro_scenario_map_mismatch")
        model = self.scenario.model_player_id
        self.participants = verify_participants(self.memory, state, self.registry, model)
        if not self.scenario.matches_participants(self.participants):
            raise ContractError("session_mismatch")
        self.match_result = controlled_match_result(
            state, model, self.opponent_player_ids, participant_ids=self.scenario.player_ids
        )
        if self.match_result["terminal"]:
            raise ContractError("macro_native_result_candidate")
        census = own_census(self.memory, self.owner)
        frame = census["frame"]
        required_origin = getattr(self.scope, "required_origin_region", None)
        if self.sequence == 0 and required_origin is not None:
            require_base_origin(census, required_origin)
        if frame < self.previous:
            raise ContractError("macro_frame_regression")
        self.previous = frame
        at = frame / 15
        field = self.collector.collect(at)
        roles = {}
        for row in census["own_objects"]:
            safe = self.safety["templates"].get(row["type_hash"])
            if safe:
                roles[safe["role"]] = roles.get(safe["role"], 0) + 1
        resources = census["resources"]
        if resources.get("resource_available") is not True:
            raise ContractError("macro_credit_observation_unavailable")
        self.sequence += 1
        raw = dict(
            schema_version=1,
            session_id=self.session["session_id"],
            player_id=3,
            snapshot_id=self.sequence,
            game_time_seconds=at,
            source="game_bridge",
            paused=bool(state["pause_flag_candidate"]),
            resources=dict(credits=resources["display_sum"], power_balance=None),
            capabilities=dict(
                production_focus=["native_baseline"], regions=[row["region_id"] for row in field["regions"]]
            ),
            production=dict(queued_count=0, idle_producers=0, own_roles=roles),
            enemy_observations=[],
            events=[],
            battlefield=field,
            # Production requires paired private builder/own-census samples.
            # The live controller may add it after refresh; sampler alone cannot.
            macro_control=dict(
                mode="macro_native",
                available_actions=[action for action in self.scope.available_actions if action.startswith("budget")]
                if at >= getattr(self.scope, "minimum_model_game_seconds", MIN_MACRO_MODEL_GAME_SECONDS)
                else [],
            ),
        )
        intent_contract = getattr(self.scope, "intent_contract", None)
        if intent_contract is not None:
            raw["macro_control"]["intent_contract"] = intent_contract
        if hasattr(self.scope, "regional_action_regions"):
            # Public map navigation locations carry no enemy presence claim.
            raw["capabilities"]["regions"] = sorted(
                set(raw["capabilities"]["regions"]) | set(self.scope.regional_action_regions.values())
            )
        self.latest_census = census
        defeated = {
            index
            for index in self.opponent_player_ids
            if self.match_result["players"][str(index)]["outcome"] == "defeat"
        }
        raw["match_state"] = self.scenario.match_state(state["simulation_frame"], defeated)
        return Snapshot.from_dict(raw).to_dict()

    def close(self):
        self.memory.close()

    def footprint(self):
        # Stable admission identity excludes changing frame/resources/own roster.
        return dict(
            session_sha256=hashlib.sha256(self.raw).hexdigest(),
            registry_sha256=hashlib.sha256(self.registry_raw).hexdigest(),
            bundle_sha256=hashlib.sha256(self.bundle_raw).hexdigest(),
            owner=self.owner,
            ai=self.proof["handshake"]["ai_player"],
            game_logic=self.proof["handshake"]["game_logic"],
            participants=self.participants,
            visibility_build=self.proof["build_id"],
        )
