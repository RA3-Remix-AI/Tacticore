"""Bounded own enemy-selector reads borrowed from an admitted caller.

No process opener, native calls, writes, object targets or hidden enemy-unit
reads. The caller brackets this slice with fresh OS, frame and transport
identity checks and revalidates the supplied read trace.
"""

import struct

MAX_PLAYERS = 16

API_PINS = {
    0x8BDB50: bytes.fromhex("83ec10568bf166837e30007750"),
    0x8BDBC0: bytes.fromhex("32c08841248841258b442404894120e8bcfaffffc20400"),
}


def sample(read, binding):
    from read_selected_personality import inspect_player
    from native_read import read_player_relation

    def word(address):
        return struct.unpack("<I", read(address, 4))[0]

    class BorrowedReader:
        u32 = staticmethod(word)

    for address, expected in API_PINS.items():
        if read(address, len(expected)) != expected:
            raise ValueError("native_enemy_focus_api_changed")
    owner = binding["owner"]
    ai = binding["ai"]
    if (
        word(0xCD8CE4) != binding["game"]
        or word(binding["game"]) != 0xBEB630
        or word(0xCDD190) != binding["engine"]
        or word(owner) != 0xC5BCE0
        or word(owner + 0x20) >= MAX_PLAYERS
        or word(owner + 0x90) != ai
    ):
        raise ValueError("native_enemy_focus_current_owner_changed")
    identity = inspect_player(read, owner)
    expected_identity = dict(
        player=owner,
        ai_player=ai,
        personality_wrapper=binding["personality"],
        personality_data=binding["personality_data"],
        player_template=binding["player_template"],
        instance_id=0x799613E0,
    )
    if (
        identity["player_index"] != word(owner + 0x20)
        or identity["store_membership_verified"] is not True
        or identity["side_matches_player"] is not True
        or any(int(identity[key], 0) != value for key, value in expected_identity.items())
    ):
        raise ValueError("native_enemy_focus_current_personality_changed")
    tactical = word(ai + 0x6F8)
    selector = word(tactical + 0x34)
    if not tactical or selector < 0x10000 or selector % 4:
        raise ValueError("native_enemy_focus_selector_root")
    header = read(selector, 0x32)
    selector_owner, begin, end = struct.unpack_from("<III", header, 4)
    scheme = struct.unpack_from("<I", header, 0x20)[0]
    manual, isolated = header[0x24:0x26]
    lock = struct.unpack_from("<H", header, 0x30)[0]
    if (
        selector_owner != owner
        or scheme != 2
        or manual not in (0, 1)
        or isolated not in (0, 1)
        or end < begin
        or end - begin > 8 * MAX_PLAYERS
        or (end - begin) % 8
        or bool(begin) != bool(end)
    ):
        raise ValueError("native_enemy_focus_selector_bounds")
    raw = read(begin, end - begin) if end > begin else b""
    own = word(owner + 0x20)
    manager = word(0xCDD1A0)
    if word(manager) != 0xC07AB8:
        raise ValueError("native_enemy_focus_participant_root")
    players = struct.unpack("<20I", read(manager + 0x48, 80))
    defeated = read(manager + 0xA0, 20)
    player_list = word(0xCE8C9C)
    combatants = {}
    alive_mask = 0
    for index, pointer in enumerate(players):
        if not pointer:
            continue
        player = word(pointer + 0x20)
        if (
            word(pointer) != 0xC5BCE0
            or player >= MAX_PLAYERS
            or player in combatants
            or defeated[index] not in (0, 1)
            or word(player_list + 0x30 + 4 * player) != pointer
        ):
            raise ValueError("native_enemy_focus_participant_identity")
        combatants[player] = pointer
        if not defeated[index]:
            alive_mask |= 1 << player
    if combatants.get(own) != owner:
        raise ValueError("native_enemy_focus_own_player_required")
    borrowed = BorrowedReader()
    enemy_mask = 0
    for player in sorted(set(combatants) - {own}):
        toward = read_player_relation(borrowed, owner, player)
        back = read_player_relation(borrowed, combatants[player], own)
        if toward == back == "enemy":
            enemy_mask |= 1 << player
        elif not toward == back == "ally":
            raise ValueError("native_enemy_focus_mutual_relation_required")
    priority = [0] * MAX_PLAYERS
    seen = set()
    for offset in range(0, len(raw), 8):
        value, player = struct.unpack_from("<II", raw, offset)
        if player >= MAX_PLAYERS or player in seen or not enemy_mask & (1 << player) or not 1 <= value <= 10:
            raise ValueError("native_enemy_focus_foreign_priority")
        seen.add(player)
        priority[player] = value
    enemies = [player for player in range(MAX_PLAYERS) if enemy_mask & (1 << player)]
    return dict(
        source="bound_native_enemy_selector_v2",
        selector=selector,
        automatic_scheme=scheme,
        manual=manual,
        isolated=isolated,
        enumeration_lock=lock,
        own_player_id=own,
        enemy_mask=enemy_mask,
        alive_mask=alive_mask,
        priority=priority,
        public_opponent_ids=enemies,
        native_calls=0,
        process_writes=0,
        enemy_details_read=False,
        mission_success_verified=False,
    )


def automatic_priority(sample):
    """Native automatic selection: priority 1 for every hostile, alive player."""
    mask = sample["enemy_mask"] & sample["alive_mask"]
    return [int(bool(mask & (1 << player))) for player in range(MAX_PLAYERS)]


def at_baseline(sample):
    """The own selector is in the native AI's original automatic state."""
    return (
        not sample["manual"]
        and not sample["isolated"]
        and not sample["enumeration_lock"]
        and sample["priority"] == automatic_priority(sample)
    )


def returned_to_automatic(sample, ownership):
    """Check the selector after stop without confusing stock teardown with an override."""
    if ownership["phase"] not in (0, 4):
        return False
    if at_baseline(sample):
        return True

    # The last opponent can be marked defeated before the stock selector has
    # dropped its weight-1 entry. Only an untouched automatic selector can pass
    # in that window. A selector we acquired still needs its exact baseline.
    if (
        ownership["phase"] != 0
        or ownership["baseline_captured"] != 0
        or ownership["call_reservations"] != 0
        or ownership["selector"] != 0
        or ownership["deadline_frame"] != 0
        or ownership["deadline_ms"] != 0
        or sample["automatic_scheme"] != 2
        or sample["manual"] != 0
        or sample["isolated"] != 0
        or sample["enumeration_lock"] != 0
    ):
        return False
    enemies, alive = sample["enemy_mask"], sample["alive_mask"]
    own = 1 << sample["own_player_id"]
    weights = sample["priority"]
    return (
        0 < enemies < 1 << MAX_PLAYERS
        and not enemies & (alive | own)
        and bool(alive & own)
        and len(weights) == MAX_PLAYERS
        and all(
            type(weight) is int and 0 <= weight <= ((enemies >> player) & 1) for player, weight in enumerate(weights)
        )
    )


def holds(sample, target):
    """The own selector currently prefers ``target`` and nothing else changed."""
    expected = automatic_priority(sample)
    if type(target) is not int or not 0 <= target < MAX_PLAYERS or not expected[target]:
        return False
    expected[target] = 10
    return sample["manual"] == 1 and sample["isolated"] == 0 and sample["priority"] == expected
