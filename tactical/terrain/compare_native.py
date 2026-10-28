"""Compare read-only raster samples with native own foot surface references.

No executor, production, injection, native query, command or actor lease exists
in this driver. Agreement is height evidence only, never placement permission.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import time

from heightmap import HeightMapReader

FOOT_HASHES={0x19ab11af,0x2c358c61,0x33026fa1}

def native_reference(memory,row,frame,reader):
    m=memory;t=int(row['address'],0);u=int(row['ai_address'],0);owner=int(row['owner_address'],0)
    logic=m.u32(0xcd8ce4)
    if m.u32(logic+0x50)!=frame:raise ValueError('reference_frame_changed')
    def identity():
        tpl=m.u32(t+4);team=m.u32(t+0x414);body=m.u32(t+0x33c)
        return (m.u32(t),m.u32(t+0xdc),tpl,m.u32(tpl+8),m.u32(t+0x418),m.u32(t+0x374),
            m.u32(u),m.u32(u+0x24),m.u32(u+8),team,m.u32(m.u32(team+4)+8),body,m.u32(t+0x238))
    before=identity()
    if (before[0]!=0xc4db60 or before[1]!=row['object_id'] or before[3]!=int(row['type_hash'],0)
            or before[3] not in FOOT_HASHES or before[4]!=owner or before[5]!=u
            or before[6:9]!=(0xc48670,0xc48528,t) or before[10]!=owner or before[12]!=0
            or before[11]<0x10000):
        raise ValueError('reference_identity_unverified')
    pose=m.read(t+0x38,12);xyz=struct.unpack('<3f',pose)
    cache=m.u32(t+0x48);height_raw=m.read(t+0x5c,4);cached=struct.unpack('<f',height_raw)[0]
    hp_raw=m.read(before[11]+4,4);hp=struct.unpack('<f',hp_raw)[0]
    flags_raw=m.read(t+0x80,28);flags=struct.unpack('<7I',flags_raw)
    if (not cache&4 or not all(math.isfinite(v) for v in (*xyz,cached,hp)) or hp<=0 or abs(cached)>.5
            or flags[0]&0x181 or flags[1]&0x20080000 or flags[5]&2 or flags[6]&0x88000
            or xyz!=tuple(row['xyz'])):
        raise ValueError('reference_surface_cache_or_status_unverified')
    terrain=reader.sample(xyz[0],xyz[1])
    if (terrain['frame']!=frame or m.u32(0xcd8ce4)!=logic or m.u32(logic+0x50)!=frame
            or identity()!=before or m.read(t+0x38,12)!=pose or m.u32(t+0x48)!=cache
            or m.read(t+0x5c,4)!=height_raw or m.read(before[11]+4,4)!=hp_raw or m.read(t+0x80,28)!=flags_raw):
        raise ValueError('reference_snapshot_changed')
    surface=xyz[2]-cached;delta=terrain['base_height']-surface
    return dict(frame=frame,object_id=row['object_id'],thing=hex(t),owner=hex(owner),type_hash=row['type_hash'],
        update=hex(u),identity_words=list(before),xyz=list(xyz),pose_raw_hex=pose.hex(),
        height_cache_word=cache,cached_surface_height=cached,cached_height_raw_hex=height_raw.hex(),
        hp=hp,hp_raw_hex=hp_raw.hex(),status_words=list(flags),status_raw_hex=flags_raw.hex(),
        native_surface_z=surface,base_height_delta=delta,height_agrees=abs(delta)<=.001,
        raster=terrain,walkability_verified=False,ground_target_permission_granted=False)


def collect(session_path,output,seconds=60,require_nonflat=False):
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'integration'))
    from live_state import Memory,verify_session_package,own_candidates
    original=session_path.read_bytes();session=json.loads(original.decode('utf-8-sig'));run=Path(session['run_directory']).resolve()
    if (output.parent!=run or output.exists() or not 1<=seconds<=60
            or session['scenario'].get('model_requests_enabled') is not False
            or session['scenario'].get('trial_kind')!='read_only_terrain_geometry_research'):
        raise ValueError('new_owned_readonly_terrain_session_required')
    verify_session_package(session)
    archive=run/(output.stem+'-code');archive.mkdir()
    sources=[]
    for name in ('heightmap.py','compare_native.py'):
        source=Path(__file__).with_name(name);target=archive/name;shutil.copyfile(source,target)
        sources.append(dict(file=name,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    result=dict(schema_version=1,kind='own_native_surface_vs_raster_readonly_comparison',session_id=session['session_id'],
        pid=session['pid'],process_start=session['start_time'],source_files=sources,observations=[],mismatches=[],
        rejection_counts={},wall_budget_seconds=seconds,native_writes=0,query_calls=0,sdk_game_calls=0,
        production_commands=0,leases=0,walkability_verified=False,ground_target_permission_granted=False,
        ordinary_execution_granted=False,require_nonflat=require_nonflat)
    memory=Memory(session['pid'],session);reader=HeightMapReader(memory);started=time.monotonic();seen=set();counts=Counter()
    matches=result['observations'];mismatches=result['mismatches']
    try:
        while time.monotonic()-started<seconds and len(matches)<64:
            if session_path.read_bytes()!=original:raise ValueError('terrain_session_changed')
            try:
                census=own_candidates(memory,session['scenario']['computer_player_index'],{})
                if census['frame_start']==0 or census['frame_start']!=census['frame_end']:
                    raise ValueError('reference_census_not_single_active_frame')
                for row in census['candidates']:
                    if int(row['type_hash'],0) not in FOOT_HASHES:continue
                    if not require_nonflat and sum(x['object_id']==row['object_id'] for x in matches)>=8:continue
                    key=(row['object_id'],census['frame_start'])
                    if key in seen:continue
                    try:sample=native_reference(memory,row,census['frame_start'],reader)
                    except (ValueError,OSError,RuntimeError,struct.error) as error:
                        counts[str(error) if isinstance(error,ValueError) else type(error).__name__]+=1
                        continue
                    seen.add(key)
                    if sample['height_agrees']:
                        nonflat=len(set(sample['raster']['vertices']))>1
                        flat_count=sum(len(set(x['raster']['vertices']))==1 for x in matches)
                        if nonflat or (sum(x['object_id']==row['object_id'] for x in matches)<8
                                and (not require_nonflat or flat_count<24)):matches.append(sample)
                    elif len(mismatches)<32:mismatches.append(sample)
                    if len(matches)>=64:break
            except (ValueError,OSError,RuntimeError,struct.error) as error:
                counts[str(error) if isinstance(error,ValueError) else type(error).__name__]+=1
            actors={x['object_id'] for x in matches};frames={x['frame'] for x in matches}
            nonflat_frames={x['frame'] for x in matches if len(set(x['raster']['vertices']))>1}
            if len(matches)>=9 and len(actors)>=3 and len(frames)>=3 and (not require_nonflat or len(nonflat_frames)>=3):break
            time.sleep(.15)
        result.update(status='references_agree' if len(matches)>=9 and len({x['object_id'] for x in matches})>=3
            and len({x['frame'] for x in matches})>=3
            and (not require_nonflat or len({x['frame'] for x in matches if len(set(x['raster']['vertices']))>1})>=3)
            else 'insufficient_references',
            matched_samples=len(matches),matched_actors=len({x['object_id'] for x in matches}),
            matched_frames=len({x['frame'] for x in matches}),rejection_counts=dict(counts),
            nonflat_samples=sum(len(set(x['raster']['vertices']))>1 for x in matches),
            elapsed_seconds=time.monotonic()-started)
    finally:memory.close()
    if session_path.read_bytes()!=original:raise ValueError('terrain_session_changed')
    for source in sources:
        if hashlib.sha256(Path(__file__).with_name(source['file']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('terrain_research_code_changed')
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=60)
    parser.add_argument('--require-nonflat',action='store_true')
    args=parser.parse_args();result=collect(args.session.resolve(),args.output.resolve(),args.seconds,args.require_nonflat)
    print(json.dumps({name:result[name] for name in ('status','matched_samples','matched_actors','matched_frames','nonflat_samples','rejection_counts')}))
    return 0 if result['status']=='references_agree' else 1

if __name__=='__main__':raise SystemExit(main())
