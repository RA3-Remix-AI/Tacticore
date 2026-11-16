"""Bounded own-selector reads borrowed from an admitted caller.

No process opener, native calls, writes, object targets or hidden enemy-unit
reads. The caller brackets this slice with fresh OS, frame and transport
identity checks and revalidates the supplied read trace.
"""
import struct

API_PINS = {
    0x8bdb50: bytes.fromhex('83ec10568bf166837e30007750'),
    0x8bdbc0: bytes.fromhex('32c08841248841258b442404894120e8bcfaffffc20400'),
}


def sample(read, binding):
    from read_selected_personality import inspect_player
    from native_read import read_player_relation

    def word(address):
        return struct.unpack('<I', read(address, 4))[0]

    class BorrowedReader:
        u32 = staticmethod(word)

    for address, expected in API_PINS.items():
        if read(address, len(expected)) != expected:
            raise ValueError('native7_enemy_focus_api_changed')
    owner = binding['owner']
    ai = binding['ai']
    if (word(0xcd8ce4) != binding['game'] or word(binding['game']) != 0xbeb630
            or word(0xcdd190) != binding['engine'] or word(owner) != 0xc5bce0
            or word(owner + 0x20) != 3 or word(owner + 0x90) != ai):
        raise ValueError('native7_enemy_focus_current_owner_changed')
    identity = inspect_player(read, owner)
    expected_identity = dict(player=owner, ai_player=ai, personality_wrapper=binding['personality'],
                             personality_data=binding['personality_data'], player_template=binding['player_template'],
                             instance_id=0x799613e0)
    if (identity['player_index'] != 3 or identity['store_membership_verified'] is not True
            or identity['side_matches_player'] is not True
            or any(int(identity[key], 0) != value for key, value in expected_identity.items())):
        raise ValueError('native7_enemy_focus_current_personality_changed')
    tactical = word(ai + 0x6f8)
    selector = word(tactical + 0x34)
    if not tactical or selector < 0x10000 or selector % 4:
        raise ValueError('native7_enemy_focus_selector_root')
    header = read(selector, 0x32)
    selector_owner, begin, end = struct.unpack_from('<III', header, 4)
    scheme = struct.unpack_from('<I', header, 0x20)[0]
    manual, isolated = header[0x24:0x26]
    lock = struct.unpack_from('<H', header, 0x30)[0]
    if (selector_owner != owner or scheme != 2 or manual not in (0, 1) or isolated not in (0, 1)
            or end < begin or end - begin > 16 or (end - begin) % 8 or bool(begin) != bool(end)):
        raise ValueError('native7_enemy_focus_selector_bounds')
    raw = read(begin, end - begin) if end > begin else b''
    priorities = {}
    for offset in range(0, len(raw), 8):
        priority, player = struct.unpack_from('<II', raw, offset)
        if player not in (4, 5) or player in priorities or not 1 <= priority <= 10:
            raise ValueError('native7_enemy_focus_public_opponents_only')
        priorities[player] = priority
    manager = word(0xcdd1a0)
    if word(manager) != 0xc07ab8:
        raise ValueError('native7_enemy_focus_participant_root')
    players = struct.unpack('<20I', read(manager + 0x48, 80))
    defeated = read(manager + 0xa0, 20)
    player_list = word(0xce8c9c)
    combatants = {}
    alive = {}
    for index, pointer in enumerate(players):
        if not pointer:
            continue
        player = word(pointer + 0x20)
        if (word(pointer) != 0xc5bce0 or player not in (3, 4, 5) or player in combatants
                or defeated[index] not in (0, 1) or word(player_list + 0x30 + 4 * player) != pointer):
            raise ValueError('native7_enemy_focus_participant_identity')
        combatants[player] = pointer
        alive[player] = not bool(defeated[index])
    if set(combatants) not in ({3, 4}, {3, 4, 5}) or combatants[3] != owner:
        raise ValueError('native7_enemy_focus_exact_combatants_required')
    opponents=sorted(set(combatants)-{3})
    if not set(priorities)<=set(opponents):
        raise ValueError('native7_enemy_focus_foreign_priority')
    borrowed = BorrowedReader()
    for opponent in opponents:
        if (read_player_relation(borrowed, owner, opponent) != 'enemy'
                or read_player_relation(borrowed, combatants[opponent], 3) != 'enemy'):
            raise ValueError('native7_enemy_focus_mutual_enemy_required')
    if (5 in combatants and (read_player_relation(borrowed, combatants[4], 5) != 'ally'
            or read_player_relation(borrowed, combatants[5], 4) != 'ally')):
        raise ValueError('native7_enemy_focus_allied_opponents_required')
    return dict(source='bound_native_enemy_selector_v1', selector=selector, automatic_scheme=scheme,
                manual=manual, isolated=isolated, enumeration_lock=lock,
                priority_p4=priorities.get(4, 0), priority_p5=priorities.get(5, 0),
                alive_mask=int(alive[4]) | (int(alive.get(5,False)) << 1), own_player_id=3,
                public_opponent_ids=opponents, native_calls=0, process_writes=0,
                enemy_details_read=False, mission_success_verified=False)
