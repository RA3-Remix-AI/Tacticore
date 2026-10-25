"""Own ground-status samples, not a claim that edges between points are walkable."""
import hashlib
import json
import math
import struct
import uuid
from pathlib import Path

ALLOWED={'0x19ab11af','0x2c358c61'}


def cell(point):
    if len(point)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1e6 for x in point):
        return None
    return tuple(math.floor(x/40) for x in point)


def record(memory,session,candidates,folder,seen,status_reader,ground_reader_sha256):
    folder=Path(folder)
    result=dict(points=0,unknown_or_ineligible=0,ground_positive_samples=0)
    for item in candidates:
        # Do not inspect a foreign object's position or native memory.
        if item.get('owner_index_candidate')!=3 or item.get('type_hash') not in ALLOWED:
            continue
        oid=item['object_id'];kind=item['type_hash'];thing=int(item['address'],0)
        before=status_reader(memory,thing)
        if (before.get('grounded_verified') is not True or before.get('schema_version')!=2 or
                before.get('status')!='verified_native_surface_sample' or
                before.get('helper_sha256')!=ground_reader_sha256):
            result['unknown_or_ineligible']+=1
            continue
        result['ground_positive_samples']+=1
        try:
            if (before.get('object_id')!=oid or before.get('type_hash')!=kind or
                    before.get('owner')!=item['owner_address']):
                continue
            xyz=list(struct.unpack('<fff',memory.read(thing+0x38,12)))
            hp=memory.f32(memory.u32(thing+0x33c)+4)
            after=status_reader(memory,thing)
            frame=before.get('frame')
            if (after!=before or before.get('xyz')!=xyz or before.get('hp')!=hp or
                    type(frame) is not int or frame<=0 or
                    before.get('end_frame')!=frame or cell(xyz) is None or
                    not math.isfinite(hp) or hp<=0 or cell(xyz) in seen):
                continue
            words=before['status_words']
            if len(words)!=7:
                continue
            row=dict(object_id=oid,type_hash=kind,xyz=xyz,hp=hp,status84=words[1],
                     grounded_verified=True,grounded_status=before)
            target=folder/(str(frame).zfill(8)+'-'+str(oid)+'.json')
            if target.exists():
                continue
            data=dict(schema_version=1,session_id=session['session_id'],pid=session['pid'],
                player_id=3,logic_frame_candidate=frame,own_objects=[row],
                source_collector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                ground_reader_sha256=ground_reader_sha256,
                method='same_frame_owned_position_with_verified_native_surface',
                walkable_route_verified=False,mutations=False,model_eligible=False)
            temporary=target.with_name(target.name+'.pending-'+uuid.uuid4().hex)
            temporary.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
            try:
                temporary.rename(target)  # Windows rename refuses an existing source record.
            except FileExistsError:
                temporary.unlink()
                continue
            seen.add(cell(xyz));result['points']+=1
        except (ValueError,RuntimeError,OSError,KeyError,TypeError):
            result['unknown_or_ineligible']+=1
    return result
