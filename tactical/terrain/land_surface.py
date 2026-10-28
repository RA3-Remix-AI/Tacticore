"""Restricted read-only empty land-cell research. No movement authority.

Reads the actor's LocomotorSet surface mask through native PathfindParameters
provenance (params+0x14 -> update+0x1fc; settings+0x14 -> update+0x210),
reproduces footprint0x6882a0/0x68efe0,
and only the mask1/code0/layer1/empty-object branch of the native cell gates.
Other terrain categories and nonempty obstacle lists remain denied/unknown.
"""
import math
import struct
from heightmap import f32,HeightMapReader
from pathgrid import PathGridReader

MASK_TABLE=(9,10,12,24,40,72,72,136,8,520,1032)
CONSTANTS={0xbe6180:0x40000000,0xbe6630:0x41a00000,0xbe6c40:0x42200000,
    0xbe8b30:0,0xbe9d54:0x3d4ccccd,0xbe704c:0x3e99999a}
CELL_GATE=bytes.fromhex('578b7c240c85ff7507b8010000005fc3')


def footprint_width(radius,geometry_override):
    if not (math.isfinite(radius) and 0<=radius<=1000 and math.isfinite(geometry_override)
            and (geometry_override==-1 or 0<=geometry_override<=1000)):
        raise ValueError('footprint_dimensions_invalid')
    diameter=f32(radius*2)
    if 20<diameter<40:diameter=40.
    if geometry_override>0:diameter=geometry_override
    width=math.trunc(f32(f32(diameter*f32(.05))+f32(.3))) or 1
    if not 1<=width<=8:raise ValueError('footprint_outside_research_bound')
    return width


def cell_denials(cell,mask):
    words=cell['cell_words'];flags=words[3];code=flags&15;reasons=[]
    if mask!=1:reasons.append('actor_mask_outside_land1_scope')
    if code>=len(MASK_TABLE) or not (MASK_TABLE[code]&mask):reasons.append('native_terrain_mask_reject5')
    if code!=0:reasons.append('terrain_code_outside_plain_land0_scope')
    if (flags>>4)&63!=1:reasons.append('primary_layer_outside_ground1_scope')
    if flags&0x40000:reasons.append('native_flag18_rejected_conservatively')
    if words[0]:reasons.append('native_object_record_present')
    return reasons


class EmptyLandReader:
    def __init__(self,memory):self.memory=memory;self.grid=PathGridReader(memory);self.height=HeightMapReader(memory)
    def actor(self,thing):
        m=self.memory
        if (any(m.u32(a)!=v for a,v in CONSTANTS.items())
                or m.read(0xcb122c,44)!=struct.pack('<11I',*MASK_TABLE)
                or m.read(0x696fc0,len(CELL_GATE))!=CELL_GATE):raise ValueError('land_native_layout_changed')
        logic=m.u32(0xcd8ce4);frame=m.u32(logic+0x50)
        def raw():
            tpl=m.u32(thing+4);u=m.u32(thing+0x374);geom=m.u32(tpl+0x14)
            return (m.u32(thing),m.u32(thing+0xdc),tpl,m.u32(tpl+8),m.u32(thing+0x418),u,
                m.u32(u),m.u32(u+0x24),m.u32(u+8),m.u32(u+0x180),m.u32(u+0x184),
                geom,m.u32(thing+0x120),m.u32(geom+0x110),m.u32(u+0x1fc),m.u32(u+0x210))
        before=raw()
        if (before[0]!=0xc4db60 or not before[1] or before[3] not in (0x19ab11af,0x2c358c61)
                or before[6:9]!=(0xc48670,0xc48528,thing) or before[14]!=0xc37620):raise ValueError('land_foot_actor_unverified')
        radius,override=(struct.unpack('<f',struct.pack('<I',x))[0] for x in before[12:14])
        width=footprint_width(radius,override);mask=before[15]
        if not frame or m.u32(logic+0x50)!=frame or raw()!=before:raise ValueError('land_actor_snapshot_changed')
        return dict(frame=frame,logic=hex(logic),thing=hex(thing),identity_words=list(before),
            object_id=before[1],owner=hex(before[4]),type_hash=hex(before[3]),mask=mask,
            locomotor_set=hex(before[5]+0x1fc),mask_address=hex(before[5]+0x210),
            mask_source='typed_native_path_parameters_to_actor_locomotor_set_surface_mask',
            ignored_object_words=list(before[9:11]),
            radius=radius,geometry_override=override,footprint_width=width)
    def sample(self,actor,x,y):
        m=self.memory;frame=actor['frame'];width=actor['footprint_width']
        scale=f32(.05);shift=0 if width&1 else f32(.5)
        cx,cy=(math.trunc(f32(f32(f32(v)*scale)+shift)) for v in (x,y))
        left=width//2;right=width-left;cells=[];reasons=[]
        for column in range(cx-left,cx+right):
            for row in range(cy-left,cy+right):
                cell=self.grid.sample(column*20+10,row*20+10)
                if cell['frame']!=frame:raise ValueError('land_cell_cross_frame')
                cells.append(cell);reasons.extend(cell_denials(cell,actor['mask']))
        height=self.height.sample(x,y)
        if height['frame']!=frame or self.actor(int(actor['thing'],0))!=actor:
            raise ValueError('land_footprint_snapshot_changed')
        # Pair every footprint cell after the raster/actor reads, not just each
        # cell separately. No earlier unpaired vacancy survives into a result.
        for cell in cells:
            if m.read(int(cell['cell'],0),48).hex()!=cell['cell_raw_hex']:raise ValueError('land_cell_changed')
        if m.u32(int(actor['logic'],0)+0x50)!=frame:raise ValueError('land_final_frame_changed')
        return dict(schema_version=1,frame=frame,actor=actor,xy=[f32(x),f32(y)],center_cell=[cx,cy],
            footprint_cells=cells,base_height=height,rejection_reasons=sorted(set(reasons)),
            restricted_empty_land_preconditions=not reasons,walkability_verified=False,
            ground_target_permission_granted=False,ordinary_execution_granted=False,native_calls=0,game_writes=0)
