"""Read named public starting waypoints from a decoded official CkMp map.

No game access, map writes, hidden live objects or executable capability.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

def starting_waypoints(raw):
    try:return _starting_waypoints(raw)
    except (IndexError,struct.error,UnicodeDecodeError) as error:
        raise ValueError('truncated_or_invalid_waypoint_map') from error

def _starting_waypoints(raw):
    if raw[:4]!=b'CkMp' or len(raw)>16*1024*1024:raise ValueError('supported_decoded_map_required')
    count=struct.unpack_from('<I',raw,4)[0];at=8;names={}
    if not 1<=count<=512:raise ValueError('map_dictionary_bounds')
    for _ in range(count):
        size=raw[at];at+=1;name=raw[at:at+size].decode('ascii');at+=size
        ident=struct.unpack_from('<I',raw,at)[0];at+=4
        if ident in names:raise ValueError('map_dictionary_alias')
        names[ident]=name
    objects=[]
    while at<len(raw):
        ident,version,size=struct.unpack_from('<IHI',raw,at);begin=at+10;end=begin+size
        if end>len(raw) or ident not in names:raise ValueError('map_chunk_bounds')
        if names[ident]=='ObjectsList':
            if version!=3 or objects:raise ValueError('map_objects_version')
            p=begin
            while p<end:
                key,v,n=struct.unpack_from('<IHI',raw,p);b=p+10;e=b+n
                if names.get(key)!='Object' or v!=3 or e>end or n<22:raise ValueError('map_object_bounds')
                length=struct.unpack_from('<H',raw,b+20)[0];kind=raw[b+22:b+22+length].decode('ascii');q=b+22+length
                if kind=='*Waypoints/Waypoint':
                    xyz=struct.unpack_from('<fff',raw,b);total=struct.unpack_from('<H',raw,q)[0];q+=2;properties={}
                    if total>64:raise ValueError('waypoint_property_bounds')
                    for _ in range(total):
                        header=struct.unpack_from('<I',raw,q)[0];q+=4;tag=header&255;name=names.get(header>>8)
                        if tag==0:value=raw[q];q+=1
                        elif tag==1:value=struct.unpack_from('<i',raw,q)[0];q+=4
                        elif tag==2:value=struct.unpack_from('<f',raw,q)[0];q+=4
                        elif tag==3:
                            z=struct.unpack_from('<H',raw,q)[0];q+=2;value=raw[q:q+z].decode('ascii');q+=z
                        else:raise ValueError('waypoint_property_type')
                        if name is None or name in properties or q>e:raise ValueError('waypoint_property_shape')
                        properties[name]=value
                    if q!=e or not all(math.isfinite(x) for x in xyz):raise ValueError('waypoint_object_layout')
                    objects.append(dict(name=properties.get('waypointName'),xyz=list(xyz),waypoint_id=properties.get('waypointID')))
                p=e
            if p!=end:raise ValueError('map_objects_truncated')
        at=end
    if at!=len(raw):raise ValueError('map_trailing_bytes')
    # Expose only the map's public start markers, never other scripted objects.
    selected=[r for r in objects if r['name'] in ('Player_1_Start','Player_2_Start')]
    if len(selected)!=2 or len({r['name'] for r in selected})!=2:raise ValueError('two_public_start_markers_required')
    return sorted(selected,key=lambda r:r['name'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decoded-map',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw=a.decoded_map.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='ec4775f8c2d50ad15576544f00071ed1e409ee70f5a9dc7610282584e6798d66':
        raise ValueError('reviewed_temple_prime_map_bytes_required')
    value=dict(kind='static_public_start_waypoint_observation',map_id='map_mp_2_black1b',
        source=str(a.decoded_map.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),
        parser_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),waypoints=starting_waypoints(raw),
        live_enemy_details_read=False,native_target_resolution_verified=False,capability_granted=False)
    with a.output.open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps(value))

if __name__=='__main__':main()
