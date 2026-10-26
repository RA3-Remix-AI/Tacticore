"""Pure bookkeeping for a trusted, normalized paid-pair controller stream.

No game, SDK, mapping, model, filesystem or network access. Callers must first
independently verify Native/provenance evidence before sending normalized facts.
Proof hashes are retained as references, never promoted into physical evidence.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
import uuid

PROTOCOL = "held_paid_pair_registry_v1"
SCOPE = "prebound_paid_pair"
SLOT_TYPES = {"front": (0x19ab11af, "infantry"), "support": (0x2c358c61, "anti_air")}
MAX_PAID = 305
RESERVE_FLOOR = 1000
RESERVE_FRAMES = 300
HARD_FRAMES = 4500
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
REGION = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
BINDING_FIELDS = {"session_id", "controller_id", "lease_id"}
BEGIN_FIELDS = {"session_id", "commander_id", "player_id", "controller_id", "lease_id", "reserve_start_frame", "reserve_deadline_frame", "hard_deadline_frame", "allocation_scope", "max_paid", "reserve_floor"}
PREARM_FIELDS = (BEGIN_FIELDS - {"reserve_start_frame", "reserve_deadline_frame", "hard_deadline_frame"}) | {"reserve_offset_frames", "hard_offset_frames"}
CLOCK_FIELDS = BINDING_FIELDS | {"reserve_start_frame", "reserve_deadline_frame", "hard_deadline_frame", "observed_frame", "proof_sha256", "validated_before_first_borrow"}
CLAIM_FIELDS = BINDING_FIELDS | {"slot", "object_id", "type_hash", "paid", "producer_reserve", "production_command_id", "production_task_id", "receipt_sha256", "proof_sha256", "observed_frame"}
READY_FIELDS = BINDING_FIELDS | {"slot", "object_id", "observed_frame", "proof_sha256", "validated_ready", "region_id"}
COMMIT_FIELDS = BINDING_FIELDS | {"task_id", "command_id", "seq", "formation_id", "formation_version", "object_ids", "module", "purpose", "request_force_fraction", "allocation_scope", "hard_deadline_frame", "reserve_deadline_frame", "commit_frame", "target"}
TARGET_FIELDS = {"contact_id", "object_id", "type_hash", "owner_player_id", "role", "observed_frame", "proof_sha256", "currently_visible_verified"}
TERMINAL_FIELDS = BINDING_FIELDS | {"status", "reason_code", "observed_frame", "proof_sha256"}
RELEASE_FIELDS = BINDING_FIELDS | {"object_ids", "observed_frame", "proof_sha256", "independently_verified", "channel_release_verified"}


def _keys(record, fields, code):
    if type(record) is not dict or set(record) != fields:
        raise ValueError(code)
    return copy.deepcopy(record)


def _uuid(value):
    if type(value) is not str or not uuid.UUID(value).int:
        raise ValueError("held_uuid")
    return str(uuid.UUID(value))


def _integer(value, low=0, high=0xffffffff):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("held_integer")
    return value


def _hash(value):
    if type(value) is not str or DIGEST.fullmatch(value) is None:
        raise ValueError("held_proof_sha256")
    return value


def _ident(value):
    if type(value) is not str or ID.fullmatch(value) is None:
        raise ValueError("held_identifier")
    return value


def _region(value):
    if type(value) is not str or REGION.fullmatch(value) is None:
        raise ValueError("held_region")
    return value


def _type_hash(value):
    if type(value) is str and re.fullmatch(r"0x[0-9a-fA-F]{8}", value):
        value = int(value, 16)
    return _integer(value, 1)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class HeldFormationRegistry:
    """One session's controller claims; all mutation inputs are TRUSTED facts.

    This is not an input validator for model-controlled controller records.
    It validates bookkeeping identity/limits, not the truth of external proofs.
    The trusted Host serializes calls; this registry starts no worker threads.
    """

    def __init__(self, session_id, commander_id, player_id=3, *, max_ready_age_frames=30, executor_directory="mission-formation-v13", reserve_duration_frames=RESERVE_FRAMES):
        # Caller supplies these only from a source-verified family grant. No
        # model/public record can select or extend the native clock policy.
        policies = {"mission-formation-v13":300, "mission-formation-v14":300, "mission-formation-v15":300, "mission-formation-v16":450, "mission-formation-v17":450, "mission-formation-v18":450}
        if type(executor_directory) is not str or executor_directory not in policies or type(reserve_duration_frames) is not int or reserve_duration_frames not in (300,450) or reserve_duration_frames != policies[executor_directory]:
            raise ValueError("held_untrusted_clock_family_policy")
        self.executor_directory = executor_directory
        self.reserve_duration_frames = reserve_duration_frames
        self.session_id = _uuid(session_id)
        self.commander_id = _uuid(commander_id)
        if type(player_id) is not int or player_id != 3:
            raise ValueError("held_player")
        self.player_id = player_id
        self.max_ready_age_frames = _integer(max_ready_age_frames, 1, 60)
        self._controllers = {}
        self._lease_ids = set()
        self._claims = {}
        self._active = None

    def _controller(self, controller_id):
        key = _uuid(controller_id)
        if key not in self._controllers:
            raise ValueError("held_unknown_controller")
        return self._controllers[key]

    def _binding(self, controller, record):
        if (_uuid(record["session_id"]), _uuid(record["controller_id"]), _uuid(record["lease_id"])) != (self.session_id, controller["controller_id"], controller["lease_id"]):
            raise ValueError("held_binding")
        record.update(session_id=self.session_id, controller_id=controller["controller_id"], lease_id=controller["lease_id"])

    @staticmethod
    def _open(controller):
        if controller["terminal"] is not None or controller["release"] is not None:
            raise ValueError("held_controller_terminal")

    @staticmethod
    def _before_reserve_deadline(controller, frame):
        _integer(frame)
        if not controller["lease_clock_bound"]:
            raise ValueError("held_lease_clock_unbound")
        if not controller["reserve_start_frame"] <= frame < controller["reserve_deadline_frame"]:
            raise ValueError("held_reserve_deadline")

    def _clock_values(self, record):
        start = _integer(record["reserve_start_frame"], 1, 0xffffffff-HARD_FRAMES)
        if type(record["reserve_deadline_frame"]) is not int or record["reserve_deadline_frame"] != start+self.reserve_duration_frames or type(record["hard_deadline_frame"]) is not int or record["hard_deadline_frame"] != start+HARD_FRAMES:
            raise ValueError("held_deadline_not_frozen")
        return {key:record[key] for key in ("reserve_start_frame", "reserve_deadline_frame", "hard_deadline_frame")}

    def prearm_controller(self, record):
        """Claim the sole tactical channel BEFORE installation or production.

        UUIDs and offset policy are fixed here; there is deliberately no lease
        start/deadline yet. Production integration must use prearm -> actual
        Native first-borrow clock proof -> bind_lease_clock -> claim_slot.
        The caller owns a separate bounded startup watchdog while unbound.
        """
        record = _keys(record, PREARM_FIELDS, "held_prearm_fields")
        if (_uuid(record["session_id"]), _uuid(record["commander_id"]), record["player_id"]) != (self.session_id, self.commander_id, self.player_id) or type(record["player_id"]) is not int:
            raise ValueError("held_begin_binding")
        controller_id, lease_id = _uuid(record["controller_id"]), _uuid(record["lease_id"])
        if controller_id == lease_id:
            raise ValueError("held_controller_lease_alias")
        if controller_id in self._controllers or lease_id in self._lease_ids:
            raise ValueError("held_identity_reused")
        if self._active is not None:
            raise ValueError("held_tactical_channel_occupied")
        if record["allocation_scope"] != SCOPE or type(record["max_paid"]) is not int or record["max_paid"] != MAX_PAID or type(record["reserve_floor"]) is not int or record["reserve_floor"] != RESERVE_FLOOR:
            raise ValueError("held_paid_pair_scope")
        if type(record["reserve_offset_frames"]) is not int or record["reserve_offset_frames"] != self.reserve_duration_frames or type(record["hard_offset_frames"]) is not int or record["hard_offset_frames"] != HARD_FRAMES:
            raise ValueError("held_clock_policy_changed")
        record.update(session_id=self.session_id, commander_id=self.commander_id, controller_id=controller_id, lease_id=lease_id)
        formation = "formation_"+uuid.uuid5(uuid.UUID(controller_id), "paid_pair").hex[:16]
        state = dict(record, formation_id=formation, formation_version=1, slots={}, mission_commit=None, mission_commit_sha256=None, terminal=None, release=None, channel_claimed=True, physical_capability_verified=False,
                     lease_clock_bound=False, reserve_start_frame=None, reserve_deadline_frame=None, hard_deadline_frame=None, lease_clock_binding=None)
        self._controllers[controller_id] = state
        self._lease_ids.add(lease_id)
        self._active = controller_id
        return self.controller(controller_id)

    def bind_lease_clock(self, controller_id, record):
        """Bind once to the trusted actual Native pre-first-borrow event.

        observed_frame is that actual clock-freeze EVENT frame, not the later
        collection wall time or arm/queue-start frame. Identical proof replay is
        idempotent. Changing any clock/proof, rebinding after a claim, or binding
        a failed prearm lifecycle is rejected. No physical evidence is granted.
        """
        record = _keys(record, CLOCK_FIELDS, "held_clock_fields")
        controller = self._controller(controller_id)
        self._binding(controller, record)
        values = self._clock_values(record)
        _hash(record["proof_sha256"])
        if record["validated_before_first_borrow"] is not True or type(record["observed_frame"]) is not int or record["observed_frame"] != values["reserve_start_frame"]:
            raise ValueError("held_clock_not_actual_preborrow")
        if controller["lease_clock_bound"]:
            if controller["lease_clock_binding"] != record:
                raise ValueError("held_lease_clock_rebind")
            return self.controller(controller_id)
        self._open(controller)
        if controller["slots"] or controller["mission_commit"] is not None:
            raise ValueError("held_clock_after_borrow")
        controller.update(values, lease_clock_bound=True, lease_clock_binding=record)
        return self.controller(controller_id)

    def begin_controller(self, record):
        """Shortcut for ALREADY normalized fixed-clock bookkeeping fixtures.

        This method does not observe a Native clock and must not be used to
        substitute the arm/production time for the real first-borrow event.
        Live production integration uses prearm_controller + bind_lease_clock.
        """
        record = _keys(record, BEGIN_FIELDS, "held_begin_fields")
        values = self._clock_values(record)
        prearm = {key:value for key,value in record.items() if key not in values}
        prearm.update(reserve_offset_frames=self.reserve_duration_frames, hard_offset_frames=HARD_FRAMES)
        state = self.prearm_controller(prearm)
        controller = self._controller(state["controller_id"])
        controller.update(values, lease_clock_bound=True,
                          lease_clock_binding=dict(source="trusted_fixed_clock_shortcut", **values))
        return self.controller(state["controller_id"])

    def claim_slot(self, controller_id, record):
        """Record one real Native borrow after independent source verification."""
        record = _keys(record, CLAIM_FIELDS, "held_claim_fields")
        controller = self._controller(controller_id)
        self._binding(controller, record)
        self._open(controller)
        self._before_reserve_deadline(controller, record["observed_frame"])
        if controller["mission_commit"] is not None:
            raise ValueError("held_claim_after_mission")
        slot = record["slot"]
        if type(slot) is not str or slot not in SLOT_TYPES or slot in controller["slots"]:
            raise ValueError("held_slot_duplicate_or_unknown")
        actor = _integer(record["object_id"], 1)
        if actor in self._claims:
            raise ValueError("held_actor_already_claimed")
        kind = _type_hash(record["type_hash"])
        if kind != SLOT_TYPES[slot][0]:
            raise ValueError("held_slot_type")
        paid = _integer(record["paid"], 1, MAX_PAID)
        if paid+sum(s["paid"] for s in controller["slots"].values()) > MAX_PAID:
            raise ValueError("held_paid_budget")
        _integer(record["producer_reserve"], RESERVE_FLOOR, 100000)
        for field in ("production_command_id", "production_task_id"):
            record[field] = _uuid(record[field])
            if any(s[field] == record[field] for s in controller["slots"].values()):
                raise ValueError("held_production_identity_reused")
        for field in ("receipt_sha256", "proof_sha256"):
            _hash(record[field])
        if any(s["receipt_sha256"] == record["receipt_sha256"] for s in controller["slots"].values()):
            raise ValueError("held_receipt_reused")
        record.update(type_hash=kind, role=SLOT_TYPES[slot][1], ready=None, claimed_frame=record["observed_frame"])
        controller["slots"][slot] = record
        self._claims[actor] = controller["controller_id"]
        return self.controller(controller_id)

    def mark_slot_ready(self, controller_id, record):
        """Store trusted actual readiness metadata; never proves a Stop itself."""
        record = _keys(record, READY_FIELDS, "held_ready_fields")
        controller = self._controller(controller_id)
        self._binding(controller, record)
        self._open(controller)
        self._before_reserve_deadline(controller, record["observed_frame"])
        if controller["mission_commit"] is not None:
            raise ValueError("held_ready_after_mission")
        if type(record["slot"]) is not str:
            raise ValueError("held_ready_slot")
        slot = controller["slots"].get(record["slot"])
        if slot is None or record["object_id"] != slot["object_id"] or type(record["object_id"]) is not int:
            raise ValueError("held_ready_actor_changed")
        if record["validated_ready"] is not True:
            raise ValueError("held_ready_not_validated")
        _hash(record["proof_sha256"])
        _region(record["region_id"])
        previous = slot["ready"]
        minimum = previous["observed_frame"] if previous else slot["claimed_frame"]
        if record["observed_frame"] < minimum:
            raise ValueError("held_ready_regression")
        if previous and record["observed_frame"] == previous["observed_frame"] and record != previous:
            raise ValueError("held_ready_same_frame_changed")
        slot["ready"] = record
        return self.controller(controller_id)

    def _ready(self, controller, frame):
        _integer(frame)
        return (controller["lease_clock_bound"] and controller["terminal"] is None and controller["release"] is None and controller["mission_commit"] is None
                and controller["reserve_start_frame"] <= frame < controller["reserve_deadline_frame"]
                and set(controller["slots"]) == set(SLOT_TYPES)
                and all(s["ready"] is not None and 0 <= frame-s["ready"]["observed_frame"] <= self.max_ready_age_frames for s in controller["slots"].values()))

    def public_formations(self, observed_frame):
        """Existing five-field public schema; never contains Native IDs/proofs.

        A real two-role controlled pair is required even for an unavailable
        descriptor. Fresh readiness gates new assignment; in-flight tasks keep
        the same descriptor/version unavailable until terminal release.
        """
        _integer(observed_frame)
        if self._active is None:
            return []
        controller = self._controller(self._active)
        if set(controller["slots"]) != set(SLOT_TYPES) or any(s["ready"] is None for s in controller["slots"].values()):
            return []
        return [dict(formation_id=controller["formation_id"], version=controller["formation_version"], roles={"infantry":1,"anti_air":1}, region_id=controller["slots"]["front"]["ready"]["region_id"], available=self._ready(controller,observed_frame))]

    def private_formations(self):
        if self._active is None:
            return {}
        controller = self._controller(self._active)
        if set(controller["slots"]) != set(SLOT_TYPES):
            return {}
        return {controller["formation_id"]:dict(version=1,role="mixed",object_ids=[controller["slots"][name]["object_id"] for name in SLOT_TYPES],control_owner="mf13",controller_id=controller["controller_id"],lease_id=controller["lease_id"],allocation_scope=SCOPE,request_force_fraction=1,hard_deadline_frame=controller["hard_deadline_frame"],reserve_deadline_frame=controller["reserve_deadline_frame"],proof_metadata={name:copy.deepcopy(slot) for name,slot in controller["slots"].items()},physical_capability_verified=False)}

    def commit_mission(self, controller_id, record):
        """One exact mission/target, under original lease deadlines.

        Same canonical digest is idempotent, including after terminal status.
        This records an offered mapping, not Native acceptance or task effects.
        """
        record = _keys(record, COMMIT_FIELDS, "held_commit_fields")
        controller = self._controller(controller_id)
        self._binding(controller, record)
        for field in ("task_id", "command_id"):
            record[field] = _uuid(record[field])
        _integer(record["seq"],1)
        _integer(record["commit_frame"],1)
        if record["formation_id"] != controller["formation_id"] or type(record["formation_version"]) is not int or record["formation_version"] != 1:
            raise ValueError("held_commit_formation")
        if (record["allocation_scope"],record["module"],record["purpose"]) != (SCOPE,"combined_arms","coordinate_force") or type(record["request_force_fraction"]) not in (int,float) or record["request_force_fraction"] != 1:
            raise ValueError("held_commit_scope")
        if type(record["hard_deadline_frame"]) is not int or record["hard_deadline_frame"] != controller["hard_deadline_frame"] or type(record["reserve_deadline_frame"]) is not int or record["reserve_deadline_frame"] != controller["reserve_deadline_frame"]:
            raise ValueError("held_commit_deadline_changed")
        if type(record["object_ids"]) is not list or any(type(actor) is not int for actor in record["object_ids"]) or set(controller["slots"]) != set(SLOT_TYPES) or record["object_ids"] != [controller["slots"][name]["object_id"] for name in SLOT_TYPES]:
            raise ValueError("held_commit_pair_changed")
        target = _keys(record["target"],TARGET_FIELDS,"held_target_fields")
        _ident(target["contact_id"])
        _integer(target["object_id"],1)
        target["type_hash"] = _type_hash(target["type_hash"])
        _integer(target["owner_player_id"],0,15)
        _integer(target["observed_frame"],1)
        _hash(target["proof_sha256"])
        if target["object_id"] in {s["object_id"] for s in controller["slots"].values()} or target["owner_player_id"] == self.player_id or type(target["role"]) is not str or target["role"] not in {"infantry","anti_air","anti_armor","armor","economy","structure"} or target["currently_visible_verified"] is not True or not 0 <= record["commit_frame"]-target["observed_frame"] <= 45:
            raise ValueError("held_target_invalid")
        record["target"] = target
        # Normalize numerical equality so 1 and 1.0 are one canonical request.
        record["request_force_fraction"] = 1
        digest = hashlib.sha256(_canonical(record)).hexdigest()
        if controller["mission_commit"] is not None:
            if controller["mission_commit_sha256"] != digest:
                raise ValueError("held_mission_commit_conflict")
            return copy.deepcopy(controller["mission_commit"])
        self._open(controller)
        self._before_reserve_deadline(controller,record["commit_frame"])
        if not self._ready(controller,record["commit_frame"]):
            raise ValueError("held_pair_not_ready")
        record.update(mission_id=record["task_id"], child_command_id=str(uuid.uuid5(uuid.UUID(record["command_id"]),"formation")),child_task_id=str(uuid.uuid5(uuid.UUID(record["task_id"]),"formation")),commit_sha256=digest,native_acceptance_verified=False,physical_effect_verified=False)
        controller["mission_commit"] = record
        controller["mission_commit_sha256"] = digest
        return copy.deepcopy(record)

    def record_terminal(self, controller_id, record):
        """Retain terminal metadata for tasked AND untasked controllers."""
        record = _keys(record,TERMINAL_FIELDS,"held_terminal_fields")
        controller = self._controller(controller_id)
        self._binding(controller,record)
        if record["status"] not in {"completed","failed","cancelled"}:
            raise ValueError("held_terminal_status")
        _ident(record["reason_code"])
        _hash(record["proof_sha256"])
        base_start = controller["reserve_start_frame"] if controller["lease_clock_bound"] else 0
        _integer(record["observed_frame"],base_start)
        minimum = max([base_start]+[s["ready"]["observed_frame"] if s["ready"] else s["claimed_frame"] for s in controller["slots"].values()]+([controller["mission_commit"]["commit_frame"]] if controller["mission_commit"] else []))
        if record["observed_frame"] < minimum:
            raise ValueError("held_terminal_clock_regressed")
        if controller["mission_commit"] is None and record["status"] == "completed":
            raise ValueError("held_untasked_cannot_complete_mission")
        if controller["terminal"] is not None and controller["terminal"] != record:
            raise ValueError("held_terminal_changed")
        controller["terminal"] = record
        return self.controller(controller_id)

    def record_verified_release(self, controller_id, record):
        """Release only after the caller independently verified every claim.

        The explicit flags are assertions from a trusted integration verifier;
        this module cannot inspect raw SDK/hook/physical restoration evidence.
        """
        record = _keys(record,RELEASE_FIELDS,"held_release_fields")
        controller = self._controller(controller_id)
        self._binding(controller,record)
        if controller["terminal"] is None:
            raise ValueError("held_release_requires_terminal")
        _integer(record["observed_frame"],controller["terminal"]["observed_frame"])
        _hash(record["proof_sha256"])
        actual = sorted(s["object_id"] for s in controller["slots"].values())
        if type(record["object_ids"]) is not list or any(type(actor) is not int for actor in record["object_ids"]) or sorted(record["object_ids"]) != actual:
            raise ValueError("held_release_actor_set")
        if record["independently_verified"] is not True or record["channel_release_verified"] is not True:
            raise ValueError("held_release_not_independently_verified")
        record["object_ids"] = actual
        if controller["release"] is not None:
            if controller["release"] != record:
                raise ValueError("held_release_changed")
            return self.controller(controller_id)
        for actor in actual:
            if self._claims.get(actor) != controller["controller_id"]:
                raise ValueError("held_release_claim_binding")
        for actor in actual:
            del self._claims[actor]
        controller["release"] = record
        controller["channel_claimed"] = False
        self._active = None
        return self.controller(controller_id)

    @property
    def channel_owner(self):
        return self._active

    def claimed_actor_ids(self):
        return frozenset(self._claims)

    def exclude_from_free(self, object_ids):
        values = list(object_ids)
        if any(type(actor) is not int or actor <= 0 for actor in values) or len(values) != len(set(values)):
            raise ValueError("held_free_actor_ids")
        return [actor for actor in values if actor not in self._claims]

    def assert_free(self, object_ids):
        values = list(object_ids)
        if self.exclude_from_free(values) != values:
            raise ValueError("held_actor_not_free")

    def controller(self, controller_id):
        return copy.deepcopy(self._controller(controller_id))

    def audit(self):
        return dict(protocol=PROTOCOL,session_id=self.session_id,commander_id=self.commander_id,player_id=self.player_id,channel_owner=self._active,claimed_actor_ids=sorted(self._claims),controllers=copy.deepcopy(list(self._controllers.values())),physical_capability_verified=False,proof_boundary="Trusted normalized metadata only; caller independently verifies Native provenance/readiness/release.")
