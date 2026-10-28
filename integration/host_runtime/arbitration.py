"""Pure trusted-host ownership policy. Does not hook or command the game.

Native action classifications and release receipts must come from independently
verified adapters. A model output must never populate this trusted interface.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import re


class ArbitrationError(ValueError):
    pass


def _ident(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise ArbitrationError("invalid_identifier")
    return value


def _frame(value):
    if type(value) is not int or value < 0:
        raise ArbitrationError("invalid_frame")
    return value


@dataclass(frozen=True)
class ActorIdentity:
    session_id: str
    player_id: int
    object_id: int
    generation: int

    def __post_init__(self):
        _ident(self.session_id)
        if type(self.player_id) is not int or not 0 <= self.player_id <= 15:
            raise ArbitrationError("invalid_player")
        if type(self.object_id) is not int or not 1 <= self.object_id <= 0xffffffff:
            raise ArbitrationError("invalid_actor")
        _frame(self.generation)


@dataclass(frozen=True)
class ArbitrationDecision:
    outcome: str
    reason_code: str
    release_requested: bool = False


class ControlArbiter:
    def __init__(self, session_id: str, player_id: int, *, reviewed_micro_actions=()):
        # This is policy configuration from trusted executor capabilities, not a
        # runtime/model-provided whitelist and not itself an execution grant.
        self.session_id = _ident(session_id)
        if type(player_id) is not int or not 0 <= player_id <= 15:
            raise ArbitrationError("invalid_player")
        self.player_id = player_id
        self._reviewed = frozenset(_ident(x) for x in reviewed_micro_actions)
        self._leases = {}
        self._owners = {}

    @staticmethod
    def _key(actor):
        return actor.session_id, actor.player_id, actor.object_id

    def claim(self, lease_id: str, task_id: str, actors, *, issued_frame: int, deadline_frame: int):
        _ident(lease_id); _ident(task_id); _frame(issued_frame); _frame(deadline_frame)
        actors = tuple(actors)
        if not actors or any(not isinstance(a, ActorIdentity) for a in actors):
            raise ArbitrationError("actors_required")
        if any((a.session_id, a.player_id) != (self.session_id, self.player_id) for a in actors):
            raise ArbitrationError("actor_binding_mismatch")
        if len({self._key(a) for a in actors}) != len(actors):
            raise ArbitrationError("duplicate_actor")
        if deadline_frame <= issued_frame:
            raise ArbitrationError("invalid_deadline")
        record = dict(lease_id=lease_id, task_id=task_id, actors=actors,
                      issued_frame=issued_frame, deadline_frame=deadline_frame, state="held")
        if lease_id in self._leases:
            existing = self._leases[lease_id]
            if all(existing.get(k) == v for k, v in record.items()):
                return self.snapshot(lease_id)
            raise ArbitrationError("lease_reused_or_changed")
        if any(self._key(a) in self._owners for a in actors):
            raise ArbitrationError("actor_already_owned")
        self._leases[lease_id] = record
        record['last_frame'] = issued_frame
        for actor in actors:
            self._owners[self._key(actor)] = lease_id
        return self.snapshot(lease_id)

    def decide(self, lease_id: str, actor: ActorIdentity, *, action: str, game_frame: int,
               task_id: str | None = None, source_verified: bool = False):
        _frame(game_frame)
        record = self._leases.get(lease_id)
        if record is None or record['state'] == 'released':
            return ArbitrationDecision("reject", "lease_not_held")
        if actor not in record['actors']:
            return ArbitrationDecision("reject", "actor_identity_mismatch")
        if type(action) is not str or not action or len(action) > 128:
            raise ArbitrationError("invalid_action")
        if game_frame < record['last_frame']:
            return ArbitrationDecision("reject", "observation_clock_regressed")
        record['last_frame'] = game_frame
        if game_frame >= record['deadline_frame']:
            record['state'] = 'return_requested'
            return ArbitrationDecision("stop", "lease_deadline_reached", True)
        if action == "stop":
            record['state'] = 'return_requested'
            return ArbitrationDecision("stop", "host_stop_requested", True)
        if record['state'] != 'held':
            return ArbitrationDecision("reject", "lease_return_pending", True)
        if action == "task_command":
            if task_id != record['task_id'] or source_verified is not True:
                return ArbitrationDecision("reject", "task_command_identity_unverified")
            return ArbitrationDecision("allow", "current_task_command")
        if action.startswith("native_micro:"):
            name = action.partition(":")[2]
            if source_verified is True and name in self._reviewed:
                return ArbitrationDecision("allow", "reviewed_native_micro_action")
            record['state'] = 'return_requested'
            return ArbitrationDecision("stop", "native_micro_action_unverified", True)
        record['state'] = 'return_requested'
        return ArbitrationDecision("stop", "strategic_reassignment" if action == "native_reassign"
                                   else "unknown_native_action", True)

    def confirm_release(self, lease_id: str, actors, *, game_frame: int,
                        source_reference: str, independently_verified: bool):
        _frame(game_frame)
        record = self._leases.get(lease_id)
        if record is None:
            raise ArbitrationError("unknown_lease")
        if tuple(actors) != record['actors'] or independently_verified is not True:
            raise ArbitrationError("release_identity_or_proof_unverified")
        if type(source_reference) is not str or not source_reference or len(source_reference) > 512:
            raise ArbitrationError("release_reference_required")
        if game_frame < record['last_frame']:
            raise ArbitrationError("release_clock_regressed")
        if record['state'] == 'released':
            if record['release_reference'] != source_reference or record['released_frame'] != game_frame:
                raise ArbitrationError("release_receipt_conflict")
            return self.snapshot(lease_id)
        for actor in record['actors']:
            del self._owners[self._key(actor)]
        record.update(state='released', last_frame=game_frame,
                      released_frame=game_frame, release_reference=source_reference)
        return self.snapshot(lease_id)

    def snapshot(self, lease_id: str):
        record = copy.deepcopy(self._leases[lease_id])
        record['actors'] = [asdict(a) for a in record['actors']]
        record['execution_authority_granted'] = False
        return record
