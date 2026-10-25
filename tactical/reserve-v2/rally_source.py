"""Current owned factory facts for a proposed rally; no terrain or route claim."""
import hashlib, importlib.util, math, struct, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def capture(memory,session,birth):
 spec=importlib.util.spec_from_file_location('rsv2_owned_factory_roster',ROOT/'integration/own_candidates.py')
 own_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(own_module)
 # The original production client is imported only for its static ctypes.
 spec=importlib.util.spec_from_file_location('rsv2_production_receipt_layout',ROOT/'production/persistent/client.py')
 producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
 receipt=producer.Receipt.from_buffer_copy(bytes.fromhex(birth['production_readonly']['receipt_hex']))
 factory=receipt.command.factory;factory_id=receipt.command.factory_id
 own=own_module.own_candidates(memory,3,{})
 matches=[r for r in own['candidates'] if r['object_id']==factory_id and int(r['address'],0)==factory]
 if len(matches)!=1:raise ValueError('rally_factory_not_in_current_owned_roster')
 member=matches[0];owner=int(member['owner_address'],0);logic=memory.u32(0xcd8ce4)
 def read():
  # Verify membership again before reading position, template or health.
  identity=memory.read(factory,4);oid=memory.read(factory+0xdc,4);own_raw=memory.read(factory+0x418,4)
  if struct.unpack('<I',identity)[0]!=0xc4db60 or struct.unpack('<I',oid)[0]!=factory_id or struct.unpack('<I',own_raw)[0]!=owner:raise ValueError('rally_factory_ownership_changed')
  template=memory.u32(factory+4);body=memory.u32(factory+0x33c)
  return dict(thing_vtable_hex=identity.hex(),object_id_hex=oid.hex(),owner_hex=own_raw.hex(),
   template_pointer_hex=memory.read(factory+4,4).hex(),type_hash_hex=memory.read(template+8,4).hex(),
   xyz_hex=memory.read(factory+0x38,12).hex(),body_pointer_hex=memory.read(factory+0x33c,4).hex(),hp_hex=memory.read(body+4,4).hex(),
   frame_hex=memory.read(logic+0x50,4).hex(),owner_index_hex=memory.read(owner+0x20,4).hex())
 before=read();after=read()
 if before!=after:raise ValueError('rally_factory_changed_during_read')
 word=lambda key:struct.unpack('<I',bytes.fromhex(before[key]))[0]
 xyz=list(struct.unpack('<3f',bytes.fromhex(before['xyz_hex'])));hp=struct.unpack('<f',bytes.fromhex(before['hp_hex']))[0];frame=word('frame_hex')
 if not own['frame_start']==own['frame_end']==frame==memory.u32(logic+0x50) or memory.u32(0xcd8ce4)!=logic:raise ValueError('rally_factory_mixed_frame')
 if word('owner_index_hex')!=3 or word('type_hash_hex')!=0x80d4ea1e or not math.isfinite(hp) or hp<=0 or not all(math.isfinite(v) for v in xyz):raise ValueError('rally_factory_not_live_owned_barracks')
 return dict(protocol='rsv2_current_owned_factory_v1',session_id=session['session_id'],pid=session['pid'],
  source_report=birth['path'],source_report_sha256=birth['sha256'],source_receipt_sha256=birth['receipt_sha256'],
  source_frame=frame,logic=hex(logic),factory_address=hex(factory),factory_id=factory_id,factory_owner=hex(owner),
  factory_template=hex(word('template_pointer_hex')),factory_hash='0x80d4ea1e',factory_xyz=xyz,factory_hp=hp,
  factory_x_bits=struct.unpack('<I',bytes.fromhex(before['xyz_hex'])[:4])[0],factory_y_bits=struct.unpack('<I',bytes.fromhex(before['xyz_hex'])[4:8])[0],
  sample_before=before,sample_after=after,owned_membership=dict(frame_start=own['frame_start'],frame_end=own['frame_end'],member=member,all_owned_ids=[r['object_id'] for r in own['candidates']]),
  observed_monotonic_ns=time.monotonic_ns(),reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  mutations=False,sdk_calls=0,proposal_terrain_verified=False,route_verified=False)
