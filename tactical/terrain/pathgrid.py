"""Read-only layer1 cell lookup from 0x68d010/0x544720; no passability grant.

The cell terrain code and other words remain uninterpreted. Actor locomotor,
footprint, layers, dynamic obstacles and query predicates are separate work.
"""
import math
import struct
from heightmap import f32

PREFIX_COORD=bytes.fromhex('8b542408f30f1002f30f5905f411cb00')
PREFIX_CELL=bytes.fromhex('538b5c240c568bf13b5e0c57')
SCALE_BITS=0x3d4ccccd


class PathGridReader:
    def __init__(self,memory):self.memory=memory
    def _header(self):
        m=self.memory;logic=m.u32(0xcd8ce4)
        if m.u32(logic)!=0xbeb630:raise ValueError('pathgrid_logic_unverified')
        frame=m.u32(logic+0x50)
        if frame==0:raise ValueError('pathgrid_scene_inactive')
        root=m.u32(0xce3e30)
        if root<0x10000 or root%4 or m.u32(root)!=0xc18e20:raise ValueError('pathgrid_root_unverified')
        data=m.u32(root+0x28)
        if data<0x10000 or data%4 or not m.u32(data+8)&0xff:raise ValueError('pathgrid_data_unavailable')
        bounds=struct.unpack('<4i',m.read(data+0xc,16));table=m.u32(data+4)
        left,bottom,right,top=bounds
        if not (0<=left<=right<8192 and 0<=bottom<=top<8192 and table>=0x10000 and table%4==0):
            raise ValueError('pathgrid_bounds_unverified')
        if (m.u32(0xcb11f4)!=SCALE_BITS or m.read(0x68d010,len(PREFIX_COORD))!=PREFIX_COORD
                or m.read(0x544720,len(PREFIX_CELL))!=PREFIX_CELL):raise ValueError('pathgrid_native_layout_changed')
        return logic,frame,root,data,table,bounds
    def sample(self,x,y):
        if not all(type(v) in (int,float) and math.isfinite(v) and 0<=v<1000000 for v in (x,y)):
            raise ValueError('pathgrid_coordinate_invalid')
        m=self.memory;header=self._header();logic,frame,root,data,table,bounds=header
        scale=struct.unpack('<f',struct.pack('<I',SCALE_BITS))[0]
        x,y=f32(x),f32(y);column,row=math.trunc(f32(x*scale)),math.trunc(f32(y*scale))
        left,bottom,right,top=bounds
        if not(left<=column<=right and bottom<=row<=top):raise ValueError('pathgrid_coordinate_out_of_bounds')
        pointer=m.u32(table+column*4);cell=pointer+48*row
        if pointer<0x10000 or pointer%4 or cell+48>0x100000000:raise ValueError('pathgrid_column_unverified')
        raw=m.read(cell,48);words=struct.unpack('<12I',raw)
        if m.read(cell,48)!=raw or m.u32(table+column*4)!=pointer or self._header()!=header:
            raise ValueError('pathgrid_snapshot_changed')
        return dict(schema_version=1,source='pinned_layer1_pathfind_cell_read_only',frame=frame,logic=hex(logic),
            root=hex(root),data=hex(data),column_table=hex(table),column_pointer=hex(pointer),
            bounds=list(bounds),xy=[x,y],column=column,row=row,layer=1,cell=hex(cell),
            cell_raw_hex=raw.hex(),cell_words=list(words),raw_terrain_nibble=words[3]&15,scale_bits=hex(SCALE_BITS),
            native_writes=0,query_calls=0,sdk_game_calls=0,walkability_verified=False,
            ground_target_permission_granted=False,ordinary_execution_granted=False)
