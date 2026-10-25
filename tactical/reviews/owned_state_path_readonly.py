"""Current own-object state/path snapshots; never call game functions or SDK."""
import argparse, hashlib, importlib.util, json, struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(path):
    spec = importlib.util.spec_from_file_location('readonly_state_path_primitives', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def capture(session_path):
    mod = load(ROOT/'tactical/mission-formation-v11/lease.py')
    pre, session, raw, _, _, _, memory = mod.b.readiness(session_path)
    try:
        logic = int(pre['logic'], 0)
        first = memory.u32(logic+0x50)
        snapshot = mod.b.own_candidates(memory, 3, mod.b.load_catalog())
        rows = []
        def name(vt):
            getter = memory.u32(vt+8)
            code = memory.read(getter, 6)
            result = dict(getter=hex(getter), bytes=code.hex())
            if code[0] == 0xb8 and code[5] == 0xc3:
                address = struct.unpack('<I', code[1:5])[0]
                result.update(address=hex(address), name=memory.read(address, 96).split(b'\0')[0].decode('ascii', 'replace'))
            return result
        for candidate in snapshot['candidates']:
            thing = int(candidate['address'], 0)
            row = dict(object_id=candidate['object_id'], thing=hex(thing), type_hash=candidate['type_hash'])
            try:
                ident = (memory.u32(thing+0xdc), memory.u32(thing+0x418), memory.u32(thing+0x374))
                if ident[0] != candidate['object_id'] or ident[1] != int(candidate['owner_address'],0):
                    raise ValueError('current_own_identity_changed')
                update = ident[2]
                if not update or memory.u32(update+8) != thing:
                    row['reason'] = 'no_current_bound_update'
                    rows.append(row)
                    continue
                sm = memory.u32(update+0x3c)
                state = memory.u32(sm+4)
                vt = memory.u32(state)
                row.update(owner=hex(ident[1]), update=hex(update), update_vtable=hex(memory.u32(update)),
                           update_backref=hex(memory.u32(update+8)), sm=hex(sm), state=hex(state),
                           state_id=memory.u32(state+4), state_vtable=hex(vt), static_name_getter=name(vt),
                           state_owner_sm=hex(memory.u32(state+0x18)), sm_owner=hex(memory.u32(sm+0x24)),
                           source=memory.u32(update+0x50), path=hex(memory.u32(update+0x150)),
                           team=hex(memory.u32(thing+0x414)), default_team=pre['default_team'], script_team=pre['script_team'],
                           update_16c_vtable=hex(memory.u32(update+0x16c)), update_174_backref=hex(memory.u32(update+0x174)),
                           update_1e4_words=list(struct.unpack('<4I',memory.read(update+0x1e4,16))),
                           xyz=list(struct.unpack('<3f',memory.read(thing+0x38,12))),
                           sm_offset_2c_xyz=list(struct.unpack('<3f',memory.read(sm+0x2c,12))),
                           sm_offset_48_xyz=list(struct.unpack('<3f',memory.read(sm+0x48,12))))
                stance = memory.u32(thing+0x380)
                row['stance_module'] = dict(address=hex(stance))
                if stance:
                    row['stance_module'].update(vtable=hex(memory.u32(stance)),
                        static_name_getter=name(memory.u32(stance)), backref=hex(memory.u32(stance+8)),
                        enum=memory.u32(stance+0x38))
                    data=memory.u32(stance+4);enum_list=memory.u32(memory.u32(data+8));count=memory.u32(enum_list+4)
                    row['stance_module'].update(data=hex(data),enum_list=hex(enum_list),enum_count=count,
                        enum_entries=list(struct.unpack('<'+'I'*(count*2),memory.read(memory.u32(enum_list+8),count*8))) if 0<count<=4 else None)
                body = memory.u32(thing+0x33c)
                row['hp'] = memory.f32(body+4) if body else None
                if row['state_id'] == 16:
                    child = memory.u32(state+0x20)
                    row['state_20_raw'] = hex(child)
                    if child:
                        child_state = memory.u32(child+4)
                        row['state_20_child'] = dict(address=hex(child), vtable=hex(memory.u32(child)),
                            state=hex(child_state), state_id=memory.u32(child_state+4),
                            state_vtable=hex(memory.u32(child_state)), static_name_getter=name(memory.u32(child_state)))
                row['identity_after'] = list((memory.u32(thing+0xdc), memory.u32(thing+0x418), memory.u32(thing+0x374)))
                row['identity_before'] = list(ident)
                row['identity_unchanged'] = row['identity_before'] == row['identity_after']
            except Exception as error:
                row['read_error'] = type(error).__name__+': '+str(error)
            rows.append(row)
        end = memory.u32(logic+0x50)
        if session_path.read_bytes() != raw:
            raise ValueError('session_changed')
        return dict(protocol='owned_current_state_path_readonly_v2', pid=session['pid'], session_id=session['session_id'],
                    session_sha256=hashlib.sha256(raw).hexdigest(), frame_start=first, frame_end=end,
                    paused=memory.u32(logic+0x15c), rows=rows, mutations=False, sdk_calls=0, model_input=False,
                    offset_labels_are_not_claimed_semantics=True)
    finally:
        memory.close()

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();record=capture(args.session)
    args.output.write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(path=str(args.output),frame_start=record['frame_start'],frame_end=record['frame_end'],
        count=len(record['rows']),state16=[x for x in record['rows'] if x.get('state_id')==16],
        errors=sum('read_error' in x for x in record['rows']))))
