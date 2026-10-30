"""Supplied-reader own expansion telemetry, rooted in the native tactic manager.

No process APIs, heap search, native calls or mutation. Dependencies which know
the existing own-AI/cache/group ABI are explicitly supplied by the observer.
Runtime membership, execution and strategic outcome are separate statements.
"""
import struct
import time

STRATEGY_VTABLE = 0xc5fd78
TACTIC_MANAGER_VTABLE = 0xc5f3ec
TACTIC_COMPONENT_VTABLE = 0xc5f3d0
EXPANSION_VTABLE = 0xc60c34
MAX_ENTRIES = 1024
MAX_MATCHES = 8
MAX_FRAMES = 2
MAX_ELAPSED_NS = 250_000_000

# Exact original PE: constructors, own-AI root writer, live scheduler, insertion,
# cleanup and active-byte consumers. None are called by this module.
PINS = {
    0x8d582e: '8986f8060000',
    0x8bf1b2: 'c70678fdc500c7460468fdc500897e08',
    0x8bf1e4: '578d4e78e8f37efeff',
    0x8a70f3: 'c706ecf3c500c74604d0f3c500894608',
    0x8a7103: '33ed896e0c896e10896e14',
    0x8d105a: '8b477c8b500c8d777c8bceffd2',
    0x8d1081: '8b068b5018538bceffd2',
    0xc5f3e8: 'd06d8d00',
    0x8d6dd4: '8d5dfc568bcbe80104fdff8b730c3b7310',
    0x8d6df0: '8b3e8bcfe857cfffff8bcfe8a027ffff83c6043b731075e8',
    0x8d03a6: '8b809000000053565705e0060000',
    0x8d0428: '8b4b248b2cb1',
    0x8d04f4: '578b4c24146a0055e80f96ffff',
    0x8c9b21: '8b4424145089462c8b442414508bce89742414e807f6ffff',
    0x8c9b39: '8b47103b47148d4f0c731185c08d500489510474125f8930',
    0x8a71e0: '538bd98b4310578b7b0c3bf87448',
    0x8a7200: '8b0f807930007422',
    0x8c968a: '807e4900c6461401',
    0x8bc135: 'c6431400',
    # Runtime+28 is a native task binding, not the compiled tactic definition.
    0x8c9116: '897e288b4f0c3bf1',
    0x8bc145: '8b432833c93bc1740ac640760189480c894b28',
    # Old +60 links are component-local, NOT a manager membership chain.
    0x8ae650: '8d4e58',
    0x8ae665: 'e8a6ebffff',
    0x8ad215: '8d7e04',
    0x8ad223: 'e808e6fbff',
    0x86b839: '8d77048936897604',
}


def pointer(value, size=4):
    if type(value) is not int or value % 4 or not 0x10000 <= value <= 0x100000000-size:
        raise ValueError('expansion_root_pointer')
    return value


def word(read, address):
    return struct.unpack('<I', read(address, 4))[0]


def verify_pins(read):
    for address, expected in PINS.items():
        raw = bytes.fromhex(expected)
        if read(address, len(raw)) != raw:
            raise ValueError('expansion_root_native_signature')


class SequentialRead:
    """Bound total reads/time and preserve every ordered raw request for replay."""
    def __init__(self, read, clock):
        self.read = read; self.clock = clock; self.started = clock()
        self.trace = []; self.total = 0

    def __call__(self, address, size):
        if (type(address) is not int or type(size) is not int or size < 0 or size > 8192
                or len(self.trace) >= 4096 or self.total+size > 262144):
            raise ValueError('expansion_sequential_read_bound')
        if self.clock()-self.started > MAX_ELAPSED_NS:
            raise ValueError('expansion_sample_time_span')
        raw = self.read(address, size)
        if type(raw) is not bytes or len(raw) != size:
            raise ValueError('expansion_short_raw_read')
        self.trace.append((address, size, raw)); self.total += size
        return raw

    def revalidate(self):
        # Actual reads in their original order, not replay from a dictionary.
        original = tuple(self.trace)
        for address, size, raw in original:
            if self(address, size) != raw:
                raise ValueError('expansion_sequential_read_changed')


def rooted_addresses(read, owner, ai):
    """Authoritative current native task vector, not allocated state prototypes."""
    if word(read, pointer(owner)+0x90) != ai:
        raise ValueError('expansion_root_owner_ai')
    strategy = pointer(word(read, pointer(ai)+0x6f8), 0x90)
    if word(read, strategy) != STRATEGY_VTABLE or word(read, strategy+8) != owner:
        raise ValueError('expansion_strategy_manager_identity')
    manager = strategy+0x78
    if (word(read, manager) != TACTIC_MANAGER_VTABLE or
            word(read, manager+4) != TACTIC_COMPONENT_VTABLE or word(read, manager+8) != owner):
        raise ValueError('expansion_tactic_manager_identity')
    header = read(manager+0xc, 12)
    begin, end, capacity = struct.unpack('<III', header)
    if (end < begin or capacity < end or capacity-begin > MAX_ENTRIES*4 or
            (end-begin) % 4 or (capacity-begin) % 4 or
            bool(begin) != bool(end) or bool(begin) != bool(capacity)):
        raise ValueError('expansion_runtime_root_bounds')
    if begin:
        pointer(begin, capacity-begin or 4)
    raw = read(begin, end-begin) if end > begin else b''
    addresses = list(struct.unpack('<'+'I'*(len(raw)//4), raw)) if raw else []
    if len(addresses) != len(set(addresses)) or 0 in addresses:
        raise ValueError('expansion_runtime_root_duplicate')
    for address in addresses:
        pointer(address, 0xa4)
    return addresses, dict(strategy_manager=hex(strategy), tactic_manager=hex(manager),
        runtime_vector_begin=hex(begin), runtime_vector_end=hex(end),
        runtime_vector_capacity=hex(capacity), total_native_runtime_entries=len(addresses),
        source='bound_own_ai_strategy_manager_tactic_vector', heap_candidates_used=False)


def sample(read, owner, ai, flag, identity, inspect_identity, cache_scores, runtime_sampler,
           *, clock=time.monotonic_ns, include_trace=False):
    """Coherent own root/cache/runtime sample. Errors mean unknown, never absence.

    runtime_sampler verifies the exact native tactic/definition and resolves only
    owned groups. A rooted inactive object is not an active task or adoption.
    """
    ordered = []
    def actual_read(address, size):
        raw = read(address, size)
        if include_trace:
            ordered.append((address, size, raw))
        return raw
    seq = SequentialRead(actual_read, clock)
    game = pointer(word(seq, 0xcd8ce4), 0x54)
    frame = word(seq, game+0x50)
    if not frame:
        raise ValueError('expansion_no_simulation')
    # The changing frame counter is checked separately at the end; all other
    # ordered raw reads below must revalidate byte-for-byte.
    seq.trace = []
    if inspect_identity(seq, owner) != identity:
        raise ValueError('expansion_owner_identity')
    verify_pins(seq)
    addresses, root = rooted_addresses(seq, owner, ai)
    scores = cache_scores(seq, ai, [flag]); state = scores.get(flag)
    rows = []
    if state is not None:
        group = pointer(int(state['group'], 0), 0x2c)
        definition = pointer(word(seq, group+0x10), 0x40)
        for address in addresses:
            # An unrelated runtime is only inspected for its type word. No
            # target/object pointers of other tasks or owners are followed.
            if word(seq, address) != EXPANSION_VTABLE:
                continue
            if word(seq, address+0x2c) != owner:
                raise ValueError('expansion_root_foreign_runtime')
            if word(seq, address+0x50) != group:
                continue
            if len(rows) >= MAX_MATCHES:
                raise ValueError('expansion_root_match_bound')
            row = runtime_sampler(seq, address, owner, group, definition)
            row.update(authoritative_runtime_membership_verified=True,
                       authoritative_runtime_root=hex(int(root['tactic_manager'], 0)))
            rows.append(row)
    if inspect_identity(seq, owner) != identity:
        raise ValueError('expansion_owner_identity')
    seq.revalidate()
    if word(actual_read, 0xcd8ce4) != game:
        raise ValueError('expansion_game_identity')
    frame_after = word(actual_read, game+0x50); elapsed = clock()-seq.started
    if not 0 <= frame_after-frame <= MAX_FRAMES or not 0 <= elapsed <= MAX_ELAPSED_NS:
        raise ValueError('expansion_sample_coherence')
    active = [row for row in rows if row['native_execution_active'] and not row['cleanup_requested']]
    result = dict(frame=frame, frame_after=frame_after, sample_elapsed_ns=elapsed,
        sample_atomic=False, sequential_reads_revalidated=True, max_frame_span=MAX_FRAMES,
        max_elapsed_ns=MAX_ELAPSED_NS, observation_complete=True, root=root, state_score=state,
        runtimes=rows, native_runtime_object_observed=bool(rows),
        native_runtime_observed=bool(active), native_execution_active=bool(active),
        inactive_runtime_objects=sum(not row['native_execution_active'] for row in rows),
        cleanup_runtime_objects=sum(bool(row['cleanup_requested']) for row in rows),
        adoption_status='active_native_task_observed' if active else 'not_observed',
        native_adoption_verified=False, strategic_success_verified=False,
        waiting=not bool(active), waiting_reason=None if active else 'native_active_task_not_observed',
        native_calls=0, process_writes=0, targets_read=False, enemy_details_read=False,
        expansion_completed_verified=False)
    if include_trace:
        result['ordered_raw_reads'] = [dict(address=address, size=size, raw_hex=raw.hex())
            for address, size, raw in ordered]
    return result
