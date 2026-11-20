"""Python mirror of the native enemy-selector read: any enemies, allies and own seat.

Synthetic memory only; no Game, native call or process write.
"""
import struct
import sys
import types
import unittest
from unittest.mock import patch

from host_runtime import native_focus_observation as focus

OWNER, AI, GAME, ENGINE, TACTICAL, SELECTOR, MANAGER, PLAYERS, ENTRIES = (
    0x100000, 0x200000, 0x300000, 0x400000, 0x500000, 0x600000, 0x700000, 0x800000, 0x900000)


class Memory:
    """Sparse little-endian byte memory."""
    def __init__(self):
        self.data = {}

    def put(self, address, raw):
        for index, value in enumerate(raw):
            self.data[address + index] = value

    def word(self, address, value):
        self.put(address, struct.pack('<I', value))

    def read(self, address, size):
        return bytes(self.data.get(address + index, 0) for index in range(size))


def world(own=3, others=None, selector=None, manual=0, defeated=()):
    """A match: ``others`` maps player id -> 'enemy' | 'ally' | other relation."""
    others = {4: 'enemy', 5: 'enemy'} if others is None else others
    memory = Memory()
    for address, raw in focus.API_PINS.items():
        memory.put(address, raw)
    memory.word(0xcd8ce4, GAME); memory.word(GAME, 0xbeb630); memory.word(0xcdd190, ENGINE)
    memory.word(OWNER, 0xc5bce0); memory.word(OWNER + 0x20, own); memory.word(OWNER + 0x90, AI)
    memory.word(AI + 0x6f8, TACTICAL); memory.word(TACTICAL + 0x34, SELECTOR)
    enemies = sorted(player for player, relation in others.items() if relation == 'enemy')
    alive = [player for player in enemies if player not in defeated]
    entries = selector if selector is not None else [(1, player) for player in alive]
    raw = b''.join(struct.pack('<II', priority, player) for priority, player in entries)
    memory.put(ENTRIES, raw)
    header = bytearray(0x32)
    struct.pack_into('<III', header, 4, OWNER, ENTRIES if raw else 0, ENTRIES + len(raw) if raw else 0)
    struct.pack_into('<I', header, 0x20, 2)
    header[0x24] = manual
    memory.put(SELECTOR, bytes(header))
    memory.word(0xcdd1a0, MANAGER); memory.word(MANAGER, 0xc07ab8); memory.word(0xce8c9c, PLAYERS)
    pointers = {own: OWNER}
    for index, player in enumerate(sorted(others)):
        pointers[player] = 0xa00000 + index * 0x1000
        memory.word(pointers[player], 0xc5bce0); memory.word(pointers[player] + 0x20, player)
    for slot, (player, pointer) in enumerate(sorted(pointers.items())):
        memory.word(MANAGER + 0x48 + 4 * slot, pointer)
        memory.put(MANAGER + 0xa0 + slot, bytes([int(player in defeated)]))
        memory.word(PLAYERS + 0x30 + 4 * player, pointer)
    relations = {}
    for player, relation in others.items():
        relations[(OWNER, player)] = relation
        relations[(pointers[player], own)] = relation
    return memory, relations


def binding():
    return dict(owner=OWNER, ai=AI, game=GAME, engine=ENGINE, personality=0x11, personality_data=0x12,
                player_template=0x13)


class FocusObservation(unittest.TestCase):
    def sample(self, memory, relations, own=3):
        identity = dict(player=hex(OWNER), ai_player=hex(AI), personality_wrapper=hex(0x11),
                        personality_data=hex(0x12), player_template=hex(0x13), instance_id=hex(0x799613e0),
                        player_index=own, store_membership_verified=True, side_matches_player=True)
        personality = types.SimpleNamespace(inspect_player=lambda read, owner: dict(identity))
        native_read = types.SimpleNamespace(
            read_player_relation=lambda reader, player, other: relations.get((player, other), 'neutral'))
        with patch.dict(sys.modules, read_selected_personality=personality, native_read=native_read):
            return focus.sample(memory.read, binding())

    def test_two_native_enemies_at_baseline(self):
        value = self.sample(*world())
        self.assertEqual(value['public_opponent_ids'], [4, 5])
        self.assertEqual(value['enemy_mask'], (1 << 4) | (1 << 5))
        self.assertTrue(focus.at_baseline(value))
        self.assertFalse(focus.holds(value, 4))

    def test_any_enemy_ids_with_human_and_ai_allies(self):
        others = {0: 'enemy', 1: 'ally', 6: 'ally', 7: 'enemy', 12: 'enemy'}
        value = self.sample(*world(others=others, selector=[(1, 0), (10, 7), (1, 12)], manual=1))
        self.assertEqual(value['public_opponent_ids'], [0, 7, 12])
        self.assertTrue(focus.holds(value, 7))
        self.assertFalse(focus.holds(value, 12))
        self.assertFalse(focus.holds(value, 1))
        self.assertFalse(focus.at_baseline(value))

    def test_own_seat_is_taken_from_the_binding(self):
        value = self.sample(*world(own=6, others={1: 'enemy', 2: 'enemy', 3: 'ally'}), own=6)
        self.assertEqual(value['own_player_id'], 6)
        self.assertEqual(value['public_opponent_ids'], [1, 2])
        self.assertTrue(focus.at_baseline(value))

    def test_defeated_enemy_leaves_the_automatic_selection(self):
        value = self.sample(*world(defeated=(5,)))
        self.assertEqual(value['priority'][5], 0)
        self.assertTrue(focus.at_baseline(value))
        self.assertFalse(focus.holds(value, 5))

    def test_neutral_or_one_sided_relations_and_foreign_entries_fail(self):
        with self.assertRaisesRegex(ValueError, 'mutual_relation'):
            self.sample(*world(others={4: 'enemy', 5: 'neutral'}))
        memory, relations = world()
        relations[(OWNER, 5)] = 'ally'
        with self.assertRaisesRegex(ValueError, 'mutual_relation'):
            self.sample(memory, relations)
        with self.assertRaisesRegex(ValueError, 'foreign_priority'):
            self.sample(*world(others={4: 'enemy', 2: 'ally'}, selector=[(1, 4), (1, 2)]))
        with self.assertRaisesRegex(ValueError, 'foreign_priority'):
            self.sample(*world(selector=[(1, 4), (1, 4)]))


if __name__ == '__main__':
    unittest.main()
