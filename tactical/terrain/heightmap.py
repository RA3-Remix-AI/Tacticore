"""Read-only RA3 base-height research; never proves walkability or grants IO.

Reproduces the scalar/no-normal branch of the pinned image's0x8ed070. No game
function is called. Water, bridges, placement, collisions and routes remain
separate unverified interfaces.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

PREFIX=bytes.fromhex('83ec208bc18b481485c9890424')
XY_SCALE_BITS=0x3dcccccd
HEIGHT_SCALE_BITS=0x3d200000

def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]
def from_bits(value):return struct.unpack('<f',struct.pack('<I',value))[0]

def interpolate(corners,fx,fy):
    """Exact scalar SSE operation order from0x8ed150..0x8ed199."""
    if len(corners)!=4 or any(type(v) is not int or not 0<=v<=65535 for v in corners):
        raise ValueError('heightmap_vertex_invalid')
    if not all(math.isfinite(v) and 0<=v<1 for v in (fx,fy)):
        raise ValueError('heightmap_fraction_invalid')
    h00,h10,h01,h11=map(float,corners);fx,fy=f32(fx),f32(fy)
    middle=h01 if fy>fx else h10
    small=fx if fy>fx else fy
    large=fy if fy>fx else fx
    first=f32(f32(h11-middle)*small)
    second=f32(f32(h00-middle)*f32(1-large))
    return f32(f32(f32(second+first)+middle)*from_bits(HEIGHT_SCALE_BITS))


class HeightMapReader:
    def __init__(self,memory):self.memory=memory
    def _header(self):
        m=self.memory;logic=m.u32(0xcd8ce4)
        if not logic or m.u32(logic)!=0xbeb630:raise ValueError('heightmap_logic_unverified')
        frame=m.u32(logic+0x50)
        if frame==0:raise ValueError('heightmap_scene_inactive')
        root=m.u32(0xce9c40)
        if root<0x10000 or root%4 or m.u32(root)!=0xc0a6f0 or m.u32(0xc0a6f0+0x54)!=0x8ed070:
            raise ValueError('heightmap_root_unverified')
        if m.read(0x8ed070,len(PREFIX))!=PREFIX or m.u32(0xbe6670)!=XY_SCALE_BITS or m.u32(0xc0930c)!=HEIGHT_SCALE_BITS:
            raise ValueError('heightmap_native_layout_changed')
        data=m.u32(root+0x14)
        if data<0x10000 or data%4:raise ValueError('heightmap_data_unavailable')
        width,height,border=m.u32(data+0x24),m.u32(data+0x28),m.u32(data+0x2c)
        grid=m.u32(data+0x44)
        if (not 4<=width<=8192 or not 4<=height<=8192 or border>min(width,height)//2
                or grid<0x10000 or grid%2 or grid+width*height*2>0x100000000):
            raise ValueError('heightmap_bounds_unverified')
        return logic,frame,root,data,width,height,border,grid
    def sample(self,x,y):
        if not all(type(v) in (int,float) and math.isfinite(v) and 0<=v<1000000 for v in (x,y)):
            raise ValueError('heightmap_coordinate_invalid')
        m=self.memory;header=self._header();logic,frame,root,data,width,height,border,grid=header
        x,y=f32(x),f32(y);sx=f32(x*from_bits(XY_SCALE_BITS));sy=f32(y*from_bits(XY_SCALE_BITS))
        ix,iy=math.trunc(sx),math.trunc(sy);column,row=ix+border,iy+border
        if not 1<=column<=width-3 or not 1<=row<=height-3:
            # Do not emulate the native out-of-bounds fallback or return zero
            # for a missing map. Neither is valid placement evidence.
            raise ValueError('heightmap_coordinate_out_of_bounds')
        indices=(row*width+column,row*width+column+1,(row+1)*width+column,(row+1)*width+column+1)
        addresses=[grid+2*i for i in indices]
        raw=[m.read(address,2) for address in addresses]
        corners=[struct.unpack('<H',value)[0] for value in raw]
        fx,fy=f32(sx-f32(ix)),f32(sy-f32(iy));height_value=interpolate(corners,fx,fy)
        if raw!=[m.read(address,2) for address in addresses] or self._header()!=header:
            raise ValueError('heightmap_snapshot_changed')
        return dict(schema_version=1,source='pinned_native_uint16_triangular_heightmap_read_only',
            frame=frame,logic=hex(logic),root=hex(root),map_data=hex(data),grid=hex(grid),
            width=width,height=height,border=border,xy=[x,y],grid_column=column,grid_row=row,
            fractions=[fx,fy],vertex_indices=list(indices),vertex_addresses=[hex(v) for v in addresses],
            vertex_raw_hex=[v.hex() for v in raw],vertices=corners,base_height=height_value,
            xy_scale_bits=hex(XY_SCALE_BITS),height_scale_bits=hex(HEIGHT_SCALE_BITS),
            native_writes=0,query_calls=0,sdk_game_calls=0,walkability_verified=False,
            ground_target_permission_granted=False,ordinary_execution_granted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--x',type=float,required=True);parser.add_argument('--y',type=float,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'integration'))
    from live_state import Memory,verify_session_package
    session_path=args.session.resolve();original=session_path.read_bytes();session=json.loads(original.decode('utf-8-sig'))
    run=Path(session['run_directory']).resolve();output=args.output.resolve()
    if output.parent!=run or output.exists() or session['scenario']['model_requests_enabled'] is not False:
        raise ValueError('heightmap_new_owned_research_output_required')
    verify_session_package(session);memory=Memory(session['pid'],session)
    result=dict(schema_version=1,kind='read_only_base_height_probe',session_id=session['session_id'],pid=session['pid'],
        reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_writes=0,query_calls=0,
        sdk_game_calls=0,ground_target_permission_granted=False,ordinary_execution_granted=False)
    try:
        result.update(status='sampled',sample=HeightMapReader(memory).sample(args.x,args.y))
    except (ValueError,OSError,RuntimeError,struct.error) as error:
        result.update(status='refused',reason_code=str(error))
    finally:memory.close()
    if session_path.read_bytes()!=original:raise ValueError('heightmap_session_changed')
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:result[k] for k in ('status','reason_code') if k in result}))
    return 0 if result['status']=='sampled' else 2

if __name__=='__main__':raise SystemExit(main())
