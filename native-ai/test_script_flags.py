"""Synthetic-memory decoder checks; no game calls or capability claims."""
import struct
import unittest

from read_script_flags import (ENGINE_GLOBAL, FLAG_MAP_OFFSET, CONTEXT_OFFSET,
    fnv1, scoped_name, inspect_flags)


class Memory:
    def __init__(self, flags, context=''):
        self.engine = 0x100000
        self.table = self.engine + FLAG_MAP_OFFSET
        self.data = {}
        self.put(ENGINE_GLOBAL, struct.pack('<I', self.engine))
        self.put(self.engine+CONTEXT_OFFSET, struct.pack('<I', 0x200000 if context else 0))
        if context:
            encoded = context.encode()
            self.put(0x200000-4, struct.pack('<H', len(encoded)))
            self.put(0x200000, encoded+b'\0')
        rows = sorted((fnv1(scope.encode()), fnv1(name.encode()), value) for scope, name, value in flags)
        self.nodes = {}

        def tree(items, parent):
            if not items:
                return 0
            mid = len(items)//2
            scope, name, value = items[mid]
            address = 0x300000 + len(self.nodes)*0x100
            self.nodes[(scope, name)] = address
            left, right = tree(items[:mid], address), tree(items[mid+1:], address)
            self.put(address, struct.pack('<6IB3x', right, left, parent, 1, scope, name, value))
            return address

        root = tree(rows, self.table+4)
        self.put(self.table, struct.pack('<6I', 0, 0, 0, root, 0, len(rows)))

    def put(self, address, raw):
        self.data.update((address+i, byte) for i, byte in enumerate(raw))

    def read(self, address, size):
        return bytes(self.data[address+i] for i in range(size))


class ScriptFlagReadbackTests(unittest.TestCase):
    def test_fnv1_not_fnv1a_and_explicit_namespace(self):
        self.assertEqual(fnv1(b''), 0x811c9dc5)
        self.assertEqual(fnv1(b'a'), 0x050c5d7e)
        self.assertEqual(fnv1(b'hello'), 0xb6fa7167)
        self.assertEqual(scoped_name('/probe', 'Campaign'), ('', 'probe'))
        self.assertEqual(scoped_name('Other/probe', 'Campaign'), ('Other', 'probe'))
        self.assertEqual(scoped_name('probe', 'Campaign'), ('Campaign', 'probe'))

    def test_present_false_is_distinct_from_absent(self):
        memory = Memory([('', 'off', 0), ('', 'on', 1)])
        result = inspect_flags(memory.read, ['/off', '/on', '/missing'])
        self.assertEqual([(row['present'], row['value']) for row in result['flags']],
            [(True, False), (True, True), (False, None)])
        self.assertFalse(result['ai_consumption_verified'])
        self.assertFalse(result['capability_granted'])

    def test_empty_tree_and_current_context(self):
        self.assertIsNone(inspect_flags(Memory([]).read, ['/x'])['flags'][0]['value'])
        memory = Memory([('Campaign', 'x', 1), ('', 'x', 0)], 'Campaign')
        result = inspect_flags(memory.read, ['x', '/x'])['flags']
        self.assertEqual([row['value'] for row in result], [True, False])

    def test_deep_tree_unsigned_two_word_key_and_case(self):
        flags = [(scope, 'name'+str(i), i % 2) for scope in ['', 'a', 'B'] for i in range(40)]
        memory = Memory(flags)
        queries = [scope+'/'+name for scope, name, _ in flags]
        # Inspect in bounded chunks, matching the external readback limit.
        for i in range(0, len(queries), 30):
            values = inspect_flags(memory.read, queries[i:i+30])['flags']
            self.assertEqual([r['value'] for r in values], [bool(f[2]) for f in flags[i:i+30]])
        self.assertFalse(inspect_flags(memory.read, ['a/NAME1'])['flags'][0]['present'])

    def test_cycle_invalid_parent_and_boolean_refused(self):
        for corruption, message in [('cycle', 'invalid_flag_tree_path'),
                                     ('parent', 'invalid_flag_tree_order_or_parent'),
                                     ('bool', 'invalid_flag_boolean')]:
            with self.subTest(corruption=corruption):
                memory = Memory([('', 'x', 1)])
                address = next(iter(memory.nodes.values()))
                if corruption == 'cycle':
                    # Both search directions cycle for any missing key.
                    memory.put(address, struct.pack('<II', address, address))
                elif corruption == 'parent':
                    memory.put(address+8, struct.pack('<I', 0))
                else:
                    memory.put(address+0x18, b'\x02')
                with self.assertRaisesRegex(ValueError, message):
                    inspect_flags(memory.read, ['/other' if corruption == 'cycle' else '/x'])

    def test_changed_path_header_context_and_engine_refused(self):
        for where in ['path', 'header', 'context', 'engine']:
            with self.subTest(where=where):
                memory = Memory([('', 'x', 1)], 'A')
                address = dict(path=next(iter(memory.nodes.values())), header=memory.table,
                    context=0x200000, engine=ENGINE_GLOBAL)[where]
                count = 0

                def unstable(at, size):
                    nonlocal count
                    raw = memory.read(at, size)
                    if at == address:
                        count += 1
                        if count == 2:
                            return raw[:-1] + bytes([raw[-1] ^ 1])
                    return raw

                with self.assertRaises(ValueError):
                    inspect_flags(unstable, ['/x'])

    def test_invalid_inputs_and_nonempty_header_without_root(self):
        for names in [[], ['/x', '/x'], ['/'], ['x\0y'], ['a'*256]]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                inspect_flags(Memory([]).read, names)
        memory = Memory([])
        memory.put(memory.table+0x14, struct.pack('<I', 1))
        with self.assertRaisesRegex(ValueError, 'invalid_flag_tree_header'):
            inspect_flags(memory.read, ['/x'])


if __name__ == '__main__':
    unittest.main()
