"""Mirror native waypoint name lookup for two fixed public map markers only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'production'),str(ROOT/'native-ai')]
from observe_production import Memory
from read_match_state import snapshot
from read_selected_personality import inspect_player
from macro_observation import cache_scores,pointer,text

PINS={0x8a8629:'8b8898000000',0x8a8647:'e83470fbff',0x85f69b:'8b1d648fce00',
      0x85f6b7:'8b4308',0x85f6ef:'8b5b1c',0x8a86b8:'8b4e0c',0x8a86c2:'8b5610'}

def lookup_public(read,expected):
    if set(expected)!= {'Player_1_Start','Player_2_Start'}:raise ValueError('two_public_names_only')
    word=lambda p:struct.unpack('<I',read(p,4))[0]
    head=word(0xce8f64);at=head;seen=set();found={};links=[]
    while at:
        pointer(at,32)
        if at in seen or len(seen)>=8192:raise ValueError('public_waypoint_list_bound')
        seen.add(at);raw=read(at,32);nameptr=struct.unpack_from('<I',raw,8)[0]
        name=None
        if nameptr:
            size=struct.unpack('<H',read(pointer(nameptr)-4,2))[0]
            if size>256:raise ValueError('public_waypoint_name_bound')
            # Other map markers are not exported and their positions are never decoded.
            if size in (14,):name=read(nameptr,size).decode('ascii',errors='replace')
        if name in expected:
            if name in found:raise ValueError('duplicate_public_waypoint')
            xyz=list(struct.unpack_from('<fff',raw,12))
            if not all(math.isfinite(x) and abs(x)<1e7 for x in xyz):raise ValueError('public_waypoint_position')
            found[name]=dict(xyz=xyz,address=hex(at))
        links.append((at,raw));at=struct.unpack_from('<I',raw,28)[0]
    if word(0xce8f64)!=head or any(read(at,32)!=raw for at,raw in links):raise ValueError('public_waypoint_list_changed')
    return dict(public_markers=found,visited_marker_count=len(seen),all_public_markers_found=set(found)==set(expected))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();s=json.loads(a.session.read_text(encoding='utf-8-sig'));b=json.loads((a.build/'build-manifest.json').read_text())
    if a.output.exists() or s['phase']!='macro_native_interface_probe' or s['mod_sha256']!=b['package_sha256']:
        raise ValueError('fresh_owned_region_read_required')
    m=Memory(s['pid'],s)
    try:
        for at,value in PINS.items():
            if m.read(at,len(bytes.fromhex(value)))!=bytes.fromhex(value):raise ValueError('public_waypoint_native_pin')
        state=snapshot(m.read);owner=next(int(r['player'],0) for r in state['victory_conditions']['participants'] if r['player_index']==3)
        native=inspect_player(m.read,owner);scores=cache_scores(m.read,int(native['ai_player'],0),b['flags']);targets=[]
        for action in ('deployattack','deploydefense'):
            flag=next(r['flag'] for r in b['consumers'] if r['action']==action);group=int(scores[flag]['group'],0)
            if m.u32(group+0x1c)!=1:raise ValueError('one_public_target_heuristic_required')
            heuristic=m.u32(m.u32(group+0x14));config=m.u32(heuristic+4)
            if m.u32(heuristic)!=0xc5ece8:raise ValueError('native_waypoint_heuristic_required')
            name=text(m.read,m.u32(m.u32(config+0x98)+4))
            if name not in ('Player_1_Start','Player_2_Start'):raise ValueError('nonpublic_target_name')
            targets.append(dict(action=action,native_configured_name=name,require_unique_target=bool(m.read(config+0xc3,1)[0])))
        result=dict(kind='native_public_waypoint_resolution_observation',session_id=s['session_id'],pid=s['pid'],
            frame=state['simulation_frame'],configured_targets=targets,**lookup_public(m.read,{'Player_1_Start','Player_2_Start'}),
            native_calls=0,process_writes=0,enemy_live_details_read=False,regional_execution_verified=False,
            parser_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:m.close()

if __name__=='__main__':main()
