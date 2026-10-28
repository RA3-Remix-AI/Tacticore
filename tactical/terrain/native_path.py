"""Paired read-only own-foot path nodes used by the native yield scan.

No queries, writes, path changes, ground references or movement grants.
Offsets come from 6a0a10/69d770/6a05f0 in the pinned RA3 1.12 image.
"""
import math
import struct

CODE_PINS = {
    0x6a05f0: bytes.fromhex('83ec54558b6c2464578b7c2460'),
    0x696570: bytes.fromhex('83ec28a1303ece008b4028'),
    0x694930: bytes.fromhex('83ec0856578b7c241c8bf1'),
    0x70cdba: bytes.fromhex('e83138f9ff'),
}
FOOT_HASHES = {0x19ab11af, 0x2c358c61, 0x33026fa1}


class NativePathReader:
    def __init__(self, memory):
        self.memory = memory

    def sample(self, row, frame):
        reads = []
        def read(address, size):
            if not 0x10000 <= address < 0x100000000 or address + size > 0x100000000:
                raise ValueError('native_path_read_bounds')
            raw = self.memory.read(address, size)
            if len(raw) != size:
                raise ValueError('native_path_short_read')
            reads.append((address, raw))
            return raw
        def word(address): return struct.unpack('<I', read(address, 4))[0]
        def pointer(address):
            value = word(address)
            if value < 0x10000 or value % 4:
                raise ValueError('native_path_pointer_unverified')
            return value
        for address, raw in CODE_PINS.items():
            if read(address, len(raw)) != raw:
                raise ValueError('native_path_code_changed')
        logic = pointer(0xcd8ce4)
        if word(logic) != 0xbeb630 or word(logic+0x50) != frame or frame <= 0:
            raise ValueError('native_path_frame_unverified')
        thing, update, owner = (int(row[k], 0) for k in ('address','ai_address','owner_address'))
        template = pointer(thing+4)
        ident, type_hash = word(thing+0xdc), word(template+8)
        if (word(thing) != 0xc4db60 or ident != row['object_id'] or type_hash != int(row['type_hash'],0)
                or type_hash not in FOOT_HASHES or word(thing+0x418) != owner
                or word(thing+0x374) != update or word(update) != 0xc48670
                or word(update+0x24) != 0xc48528 or word(update+8) != thing):
            raise ValueError('native_path_actor_unverified')
        team, body = pointer(thing+0x414), pointer(thing+0x33c)
        if word(pointer(team+4)+8) != owner or word(thing+0x238) != 0:
            raise ValueError('native_path_own_team_unverified')
        xyz_raw = read(thing+0x38,12); xyz = struct.unpack('<3f',xyz_raw)
        hp = struct.unpack('<f',read(body+4,4))[0]
        flags = struct.unpack('<7I',read(thing+0x80,28))
        if (tuple(row['xyz']) != xyz or not all(math.isfinite(v) for v in (*xyz,hp)) or hp <= 0
                or flags[0]&0x181 or flags[1]&0x20080000 or flags[5]&2 or flags[6]&0x88000):
            raise ValueError('native_path_live_pose_unverified')
        path = pointer(update+0x150)
        # Constructor6a0a10 initializes through +48; do not read the old a0
        # research span, which extended beyond this demonstrated object.
        header = read(path,0x4c); words = struct.unpack('<19I',header)
        if words[0] != 0xc18cd4 or words[2] != 0xc18cc4 or not 0 < words[1] <= 100000:
            raise ValueError('native_path_type_unverified')
        params = words[15]
        params_raw = read(params,24); params_words = struct.unpack('<6I',params_raw)
        if params_words[:2] != (0xc18ca0,0xc1893c) or params_words[3] != ident:
            raise ValueError('native_path_parameters_actor_unverified')
        settings = params_words[5]
        if settings != update+0x1fc or word(settings) != 0xc37620:
            raise ValueError('native_path_settings_unverified')
        mask = word(settings+0x14)
        if mask != 1:
            raise ValueError('native_path_surface_mask_unverified')
        nodes, seen, current = [], set(), words[4]
        while current:
            if current < 0x10000 or current % 4 or current in seen or len(nodes) >= 64:
                raise ValueError('native_path_node_chain_invalid_or_too_long')
            seen.add(current)
            raw = read(current,0x1c)
            node = struct.unpack('<7I',raw); point = struct.unpack('<3f',raw[12:24])
            if not all(math.isfinite(v) and abs(v)<1000000 for v in point):
                raise ValueError('native_path_node_pose_unverified')
            nodes.append(dict(address=hex(current), next=hex(node[2]), xyz=list(point),
                              layer_word=node[6], raw_hex=raw.hex()))
            current = node[2]
        if not nodes or int(nodes[-1]['address'],0) != words[5] or (words[9] and words[9] not in seen):
            raise ValueError('native_path_head_tail_or_current_unverified')
        template_c0, template_cc = word(template+0xc0), word(template+0xcc)
        thing98 = word(thing+0x98)
        # This is one statically observed prerequisite, not proof that the
        # native function was entered or that it accepted any blocking actor.
        outer_gate = bool(template_c0&0x30000 or template_cc&0x8000000 or thing98&0x2000 or header[0x1f])
        for address, raw in reads:
            if self.memory.read(address,len(raw)) != raw:
                raise ValueError('native_path_paired_read_changed')
        return dict(schema_version=1,source='pinned_own_native_path_nodes_readonly',frame=frame,
            object_id=ident,type_hash=hex(type_hash),thing=hex(thing),update=hex(update),owner=hex(owner),
            team=hex(team),xyz=list(xyz),path=hex(path),path_raw_hex=header.hex(),params=hex(params),
            params_raw_hex=params_raw.hex(),settings=hex(settings),surface_mask=mask,
            template_c0=template_c0,template_cc=template_cc,thing98=thing98,
            path_flag_1f=header[0x1f],static_outer_yield_scan_gate=outer_gate,
            nodes=nodes,node_count=len(nodes),layer1_only=all(n['layer_word']==1 for n in nodes),
            paired_reads=[dict(address=hex(a),raw_hex=r.hex()) for a,r in reads],
            native_writes=0,query_calls=0,sdk_game_calls=0,actor_borrow_qualified=False,
            native_yield_source_verified=False,route_or_target_permission_granted=False)
