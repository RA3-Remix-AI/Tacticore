"""Offline raw-value review; no process attachment or collector imports."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct


def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def review(source,session_path,archive):
    result=json.loads(source.read_text(encoding='utf-8-sig'))
    session=json.loads(session_path.read_text(encoding='utf-8-sig'))
    checks={}
    checks['session_binding']=(result['session_id']==session['session_id'] and result['pid']==session['pid']
        and result['process_start']==session['start_time']
        and session['scenario']['trial_kind']=='read_only_terrain_geometry_research'
        and session['scenario']['model_requests_enabled'] is False and session['scenario']['lobby_verified'] is True
        and sha(Path(session['scenario']['lobby_screenshot']))==session['scenario']['lobby_screenshot_sha256'])
    checks['archived_reader_sources']=(set(x['file'] for x in result['source_files'])=={'heightmap.py','compare_native.py'}
        and all(sha(archive/x['file'])==x['sha256'] for x in result['source_files']))
    checks['readonly_no_permission']=(all(result[x]==0 for x in ('native_writes','query_calls','sdk_game_calls','production_commands','leases'))
        and all(result[x] is False for x in ('walkability_verified','ground_target_permission_granted','ordinary_execution_granted')))
    observations=result['observations'];mismatches=result['mismatches'];raw_ok=True;identity_ok=True;grid_ok=True;delta_ok=True
    for row in observations+mismatches:
        raster=row['raster'];xyz=struct.unpack('<3f',bytes.fromhex(row['pose_raw_hex']))
        cached=struct.unpack('<f',bytes.fromhex(row['cached_height_raw_hex']))[0]
        hp=struct.unpack('<f',bytes.fromhex(row['hp_raw_hex']))[0]
        flags=struct.unpack('<7I',bytes.fromhex(row['status_raw_hex']))
        raw_ok &= (tuple(row['xyz'])==xyz and row['cached_surface_height']==cached and row['hp']==hp
            and tuple(row['status_words'])==flags and row['height_cache_word']&4!=0
            and all(math.isfinite(v) for v in (*xyz,cached,hp)) and hp>0 and abs(cached)<=.5
            and not flags[0]&0x181 and not flags[1]&0x20080000 and not flags[5]&2 and not flags[6]&0x88000)
        words=row['identity_words'];t=int(row['thing'],0);u=int(row['update'],0);owner=int(row['owner'],0)
        identity_ok &= (len(words)==13 and words[0]==0xc4db60 and words[1]==row['object_id']
            and words[3]==int(row['type_hash'],0) and words[3] in (0x19ab11af,0x2c358c61,0x33026fa1)
            and words[4:9]==[owner,u,0xc48670,0xc48528,t] and words[10]==owner and words[11]>=0x10000 and words[12]==0)
        sx,sy=(f32(v*f32(.1)) for v in xyz[:2]);ix,iy=math.trunc(sx),math.trunc(sy)
        column,r=ix+raster['border'],iy+raster['border'];w=raster['width'];h=raster['height']
        indices=[r*w+column,r*w+column+1,(r+1)*w+column,(r+1)*w+column+1]
        fx,fy=f32(sx-ix),f32(sy-iy)
        vertices=[struct.unpack('<H',bytes.fromhex(v))[0] for v in raster['vertex_raw_hex']]
        grid_ok &= (4<=w<=8192 and 4<=h<=8192 and 1<=column<=w-3 and 1<=r<=h-3
            and raster['grid_column']==column and raster['grid_row']==r and raster['vertex_indices']==indices
            and [int(v,0) for v in raster['vertex_addresses']]==[int(raster['grid'],0)+2*i for i in indices]
            and raster['vertices']==vertices and raster['xy']==list(xyz[:2]) and raster['fractions']==[fx,fy]
            and raster['frame']==row['frame'] and raster['xy_scale_bits']=='0x3dcccccd'
            and raster['height_scale_bits']=='0x3d200000')
        # Barycentric triangle formula, independent of the collector routine.
        a,b,c,d=vertices
        height=((1-fy)*a+(fy-fx)*c+fx*d if fy>fx else (1-fx)*a+(fx-fy)*b+fy*d)/25.6
        surface=xyz[2]-cached;delta=raster['base_height']-surface
        delta_ok &= (abs(height-raster['base_height'])<=.0001 and row['native_surface_z']==surface
            and row['base_height_delta']==delta and row['height_agrees']==(abs(delta)<=.001)
            and row['walkability_verified'] is False and row['ground_target_permission_granted'] is False
            and all(raster[x]==0 for x in ('native_writes','query_calls','sdk_game_calls'))
            and all(raster[x] is False for x in ('walkability_verified','ground_target_permission_granted','ordinary_execution_granted')))
    checks.update(raw_native_pose_cache_status=bool(observations) and raw_ok,own_foot_identity=identity_ok,
        original_vertex_geometry=grid_ok,independent_triangles_and_native_delta=delta_ok)
    actors={x['object_id'] for x in observations};frames={x['frame'] for x in observations}
    nonflat=[x for x in observations if len(set(x['raster']['vertices']))>1]
    checks['distinct_references']=(len(observations)>=9 and len(actors)>=3 and len(frames)>=3
        and result['matched_samples']==len(observations) and result['matched_actors']==len(actors)
        and result['matched_frames']==len(frames) and all(x['height_agrees'] for x in observations)
        and all(not x['height_agrees'] for x in mismatches))
    checks['requested_slope_coverage']=(not result.get('require_nonflat',False) or len({x['frame'] for x in nonflat})>=3)
    return dict(schema_version=1,kind='offline_native_terrain_comparison_review',status='passed' if all(checks.values()) else 'not_passed',
        source=str(source),source_sha256=sha(source),session_sha256=sha(session_path),checks=checks,
        matched_samples=len(observations),matched_actors=len(actors),matched_frames=len(frames),nonflat_samples=len(nonflat),
        native_mismatches=len(mismatches),triangles=sorted({'upper' if x['raster']['fractions'][1]>x['raster']['fractions'][0] else 'lower' for x in nonflat}),
        height_range=[min(x['raster']['base_height'] for x in observations),max(x['raster']['base_height'] for x in observations)] if observations else [],
        walkability_verified=False,ground_target_permission_granted=False,ordinary_execution_granted=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','session','archive','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=review(args.source.resolve(),args.session.resolve(),args.archive.resolve())
    with args.output.open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
    print(json.dumps(result));raise SystemExit(0 if result['status']=='passed' else 1)
