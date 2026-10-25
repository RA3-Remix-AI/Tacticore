"""Verified runtime ObjectStatus reads; no command or inferred SDK bit order."""
INSIDE_GARRISON=0x20000000
IMMOBILE=0x80000

def mobility_status(memory,thing):
 if memory.u32(thing)!=0xc4db60:raise ValueError('mobility_thing_identity')
 oid=memory.u32(thing+0xdc);owner=memory.u32(thing+0x418);flags=memory.u32(thing+0x84)
 if not oid or memory.u32(thing+0xdc)!=oid or memory.u32(thing+0x418)!=owner or memory.u32(thing+0x84)!=flags:raise ValueError('mobility_identity_or_status_changed')
 return dict(object_id=oid,status_word_plus84=hex(flags),inside_garrison=bool(flags&INSIDE_GARRISON),immobile=bool(flags&IMMOBILE),independently_movable=not bool(flags&(INSIDE_GARRISON|IMMOBILE)),source='native_name_value_table_plus_direct_setter_disassembly',mutations=False)
