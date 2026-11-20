"""Read-only proof of match participants, their kinds and relationships."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "native-ai"))
sys.path.insert(0, str(ROOT.parent / "visibility"))

# Player list root, Player vtable and Player+0x20 index / +0x90 AIPlayer are the
# offsets already used by read_selected_personality.inspect_player and the
# original observer check of this module.
PLAYER_LIST = 0xCE8C9C
PLAYER_VTABLE = 0xC5BCE0


def inspect_player(read, address):
    from read_selected_personality import inspect_player as inspect

    return inspect(read, address)


def read_player_relation(memory, player, other_player_index):
    from native_read import read_player_relation as relation

    return relation(memory, player, other_player_index)


def _player_address(memory, players, index):
    return memory.u32(players + 0x30 + 4 * index)


def _is_human(memory, address, index):
    """A player object without an AIPlayer controller."""
    return (
        memory.u32(address) == PLAYER_VTABLE and memory.u32(address + 0x20) == index and memory.u32(address + 0x90) == 0
    )


def verify_participants(memory, native_state, registry, model_player):
    """Classify every combatant and prove each one's relation to the model.

    The model seat must be an AI running a registered commander personality.
    Other AI seats must run a native (unregistered) personality. Seats without
    an AI controller are humans. Every other combatant must be a mutual ally
    or a mutual enemy of the model; mutual alliances between other combatants
    are returned so teams can be derived.
    """
    rows = native_state.get("victory_conditions", {}).get("participants", [])
    indices = [row.get("player_index") for row in rows]
    if (
        type(model_player) is not int
        or not 2 <= len(rows) <= 8
        or any(type(index) is not int or not 0 <= index < 16 for index in indices)
        or len(set(indices)) != len(indices)
        or model_player not in indices
    ):
        raise ValueError("Combatant list is invalid or lacks the model seat")
    players = memory.u32(PLAYER_LIST)
    registered = {
        int(asset["instance_id"], 0)
        for commander in registry.get("commanders", [])
        for asset in commander.get("assets", [])
    }
    addresses, kinds, personalities = {}, {}, {}
    for row in rows:
        index = row["player_index"]
        address = _player_address(memory, players, index)
        if int(row["player"], 0) != address:
            raise ValueError("Participant pointer differs from player list")
        addresses[index] = address
        if _is_human(memory, address, index):
            if index == model_player:
                raise ValueError("Model seat is not an AI player")
            kinds[index] = "human"
            continue
        identity = inspect_player(memory.read, address)
        if identity["player_index"] != index:
            raise ValueError("Participant identity mismatch")
        ours = int(identity["instance_id"], 0) in registered
        if index == model_player and not ours:
            raise ValueError("Model seat does not run a registered commander")
        if index != model_player and ours:
            raise ValueError("Another seat runs a model commander, not a native personality")
        kinds[index] = "model_ai" if index == model_player else "native_ai"
        personalities[index] = identity["instance_id"]
    relations = {}
    for index in indices:
        if index == model_player:
            continue
        forward = read_player_relation(memory, addresses[model_player], index)
        backward = read_player_relation(memory, addresses[index], model_player)
        if forward != backward or forward not in ("ally", "enemy"):
            raise ValueError("Combatant is not a mutual ally or mutual enemy of the model")
        relations[index] = forward
    others = sorted(relations)
    alliances = []
    for position, first in enumerate(others):
        for second in others[position + 1 :]:
            forward = read_player_relation(memory, addresses[first], second)
            backward = read_player_relation(memory, addresses[second], first)
            if forward == backward == "ally":
                alliances.append([first, second])
    if "enemy" not in relations.values():
        raise ValueError("The model has no enemy")
    if memory.u32(PLAYER_LIST) != players or any(
        _player_address(memory, players, index) != address for index, address in addresses.items()
    ):
        raise ValueError("Player-list lifecycle changed")
    participants = [
        dict(player_id=index, kind=kinds[index], relation="self" if index == model_player else relations[index])
        for index in sorted(indices)
    ]
    return dict(
        participants_verified=True,
        model_player_id=model_player,
        participants=participants,
        alliances=alliances,
        model_personality=personalities[model_player],
        native_personalities={
            str(index): value for index, value in sorted(personalities.items()) if index != model_player
        },
    )


def verify_two_ai(memory, native_state, registry, model_player, opponent_player, observer_player=2):
    """Legacy executor contract: exactly two AI enemies and a human observer."""
    result = verify_participants(memory, native_state, registry, model_player)
    rows = {row["player_id"]: row for row in result["participants"]}
    if (
        set(rows) != {model_player, opponent_player}
        or rows[opponent_player]["kind"] != "native_ai"
        or rows[opponent_player]["relation"] != "enemy"
        or observer_player in rows
    ):
        raise ValueError("Actual combatants differ from the expected match")
    observer = _player_address(memory, memory.u32(PLAYER_LIST), observer_player)
    if not observer or not _is_human(memory, observer, observer_player):
        raise ValueError("Observer slot is not a separate human player")
    return dict(
        two_ai_combatants_verified=True,
        mutual_enemy_relationship_verified=True,
        observer_separate_from_combatants=True,
        model_player_id=model_player,
        opponent_player_id=opponent_player,
        observer_player_id=observer_player,
        model_personality=result["model_personality"],
        opponent_personality=result["native_personalities"][str(opponent_player)],
        opponent_native_ai_verified=True,
    )


def controlled_match_result(native_state, model_player, opponent_players, participant_ids=None):
    """Map result slots through combatant identities, retaining partial eliminations.

    ``participant_ids`` is every admitted combatant (allies included). When
    omitted, the match is the model plus its opponents.
    """
    expected = set(participant_ids) if participant_ids is not None else {model_player, *opponent_players}
    if model_player not in expected or not set(opponent_players) <= expected:
        raise ValueError("Result combatants differ from the admitted match")
    participants = native_state.get("victory_conditions", {}).get("participants", [])
    records = native_state.get("result_records", [])
    if len(participants) != len(expected) or {row.get("player_index") for row in participants} != expected:
        raise ValueError("Result combatants differ from the admitted match")
    slots = {}
    for row in records:
        index = row.get("native_index")
        if type(index) is not int or not 0 <= index < 6 or index in slots:
            raise ValueError("Native result slot identity is invalid")
        slots[index] = row
    outcomes = {}
    manager_indices = set()
    for player in participants:
        index = player.get("manager_index")
        if type(index) is not int or index not in slots or index in manager_indices:
            raise ValueError("Result slot cannot be bound to its combatant")
        manager_indices.add(index)
        row = slots[index]
        frames = {name: row.get(name, 0) for name in ("victory_frame", "defeat_frame", "quit_frame")}
        if any(type(frame) is not int or not 0 <= frame <= 0xFFFFFFFF for frame in frames.values()):
            raise ValueError("Native result frame is invalid")
        if frames["victory_frame"] and (frames["defeat_frame"] or frames["quit_frame"]):
            raise ValueError("Native victory conflicts with defeat or quit")
        outcome = (
            "victory"
            if frames["victory_frame"]
            else "defeat"
            if frames["defeat_frame"]
            else "quit"
            if frames["quit_frame"]
            else "ongoing"
        )
        outcomes[str(player["player_index"])] = dict(outcome=outcome, **frames)
    own = outcomes[str(model_player)]["outcome"]
    return dict(
        terminal=own != "ongoing",
        controlled_outcome=own,
        players=outcomes,
        remaining_opponents=sum(outcomes[str(index)]["outcome"] == "ongoing" for index in opponent_players),
        all_opponents_defeated=all(outcomes[str(index)]["outcome"] == "defeat" for index in opponent_players),
    )
