"""Pure read-only reconstruction of native RA3 1.12 shroud point query.
No native calls; 0/1/3 are terrain shroud statuses, not stealth visibility.
"""
import math, struct

def f32(v): return struct.unpack('<f',struct.pack('<f',v))[0]
class ShroudReader:
 def __init__(self,memory):
  self.m=memory; self.manager=memory.u32(0xce2fa0)
  if not self.manager or memory.u32(self.manager)!=0xc6aefc: raise ValueError('ShroudManager vtable mismatch')
  self.impl=memory.u32(self.manager+0x28)
  self.header=memory.read(self.impl+4,0x44)
  self.origin=struct.unpack_from('<ff',self.header,0)
  self.scale=struct.unpack_from('<f',self.header,0x34)[0]
  self.width,self.height,self.cells=struct.unpack_from('<III',self.header,0x38)
  self.default=memory.u32(0xd074a4)
  if self.default not in (0,1,3):raise ValueError('Unknown native default shroud status')
  if not all(math.isfinite(x) for x in (*self.origin,self.scale)) or not 0<self.scale<=10 or not 1<=self.width<=4096 or not 1<=self.height<=4096 or self.width*self.height>4000000 or not self.cells:raise ValueError('Shroud grid bounds unavailable')
 def query(self,player_index,xy):
  if type(player_index)!=int or not 0<=player_index<20:raise ValueError('Player index outside native range')
  if len(xy)<2 or not all(math.isfinite(x) for x in xy[:2]):raise ValueError('Non-finite position')
  # Native SSE subss/mulss and cvttss2si use float32 and truncate toward zero.
  gx=int(f32(f32(f32(xy[0])-self.origin[0])*self.scale))
  gy=int(f32(f32(f32(xy[1])-self.origin[1])*self.scale))
  if not 0<=gx<self.width or not 0<=gy<self.height:return 3
  cell=self.cells+(gy*self.width+gx)*0x34
  if self.m.read(cell+0x32,1)[0]:return 3
  counter=struct.unpack('<H',self.m.read(cell+4+2*player_index,2))[0]
  return 0 if counter==0 else self.default if counter==0xffff else 1
 def stable(self):
  return self.m.u32(0xce2fa0)==self.manager and self.m.u32(self.manager+0x28)==self.impl and self.m.read(self.impl+4,8)==self.header[:8] and self.m.read(self.impl+0x38,16)==self.header[0x34:0x44] and self.m.u32(0xd074a4)==self.default
 def metadata(self):return {'origin':list(self.origin),'scale':self.scale,'width':self.width,'height':self.height,'default_shroud_status':self.default}

def walk_live_things(memory,logic,limit=10000):
 """Native GameLogic live list (4e9c0b/4e9c9e); internal only, no export."""
 thing=memory.u32(logic+0xb4);seen=set()
 while thing:
  if thing in seen or len(seen)>=limit or thing%4 or memory.u32(thing)!=0xc4db60:raise ValueError('Live object list changed/corrupt')
  seen.add(thing); nxt=memory.u32(thing+0x7c)
  yield thing
  thing=nxt

def cached_object_shroud(memory,thing,player_index):
 """6fba90 -> 990370. Zero means invalidated cache, never visible.
Do not apply native observer/unshrouded fallback: that could leak full map.
"""
 record=memory.u32(thing+0x9c)
 return memory.u32(record+0x24+4*player_index) if record else None

def read_player_relation(memory,player,other_player_index):
 """Exact read-only equivalent of Player::844680 (0 enemy,1 neutral,2 ally).
SAME_PLAYER is checked explicitly. Native missing-map/key fallback is neutral.
"""
 own_index=memory.u32(player+0x20)
 if not 0<=own_index<20 or not 0<=other_player_index<20:raise ValueError('Relationship player range')
 if own_index==other_player_index:return 'self'
 container=memory.u32(player+0xfc)
 if not container or memory.u32(container+0x10)==0:return 'neutral'
 buckets,count=memory.u32(container+8),memory.u32(container+0xc)
 if not buckets or not 1<=count<=4096:raise ValueError('Relationship hash bounds')
 node=memory.u32(buckets+(other_player_index%count)*4);seen=set()
 while node:
  if node in seen or len(seen)>=100:raise ValueError('Relationship cycle')
  seen.add(node)
  if memory.u32(node)==other_player_index:return {0:'enemy',1:'neutral',2:'ally'}.get(memory.u32(node+4),'unknown')
  node=memory.u32(node+8)
 return 'neutral'

def runtime_invisibility_safe(memory,thing):
 """Exclude either active invisibility category tested by native 6fda40.
No per-player stealth detection is inferred; intrinsic-capability source audit
is independently mandatory. Unknown modules/templates remain excluded.
"""
 return not memory.u32(thing+0xc8)&((1<<11)|(1<<12))

def object_footprint_status(memory,thing,player_index,grid):
 """Read-only reconstruction of 9903B0's cell aggregation (no cache writes).
Only result1 (all referenced cells clear, flagF9 clear) enables admission. Native
render callbacks can alter non-clear 3/4 states; those remain conservatively
non-visible here. Missing object record never uses native full-map fallback.
"""
 if not 0<=player_index<20:raise ValueError('Footprint player range')
 record=memory.u32(thing+0x9c)
 if not record:return None
 if memory.u32(record)!=grid.impl:raise ValueError('Footprint belongs to different shroud grid')
 if memory.read(record+0xf8,1)[0]:return None # pending geometry rebuild (993264/99327E)
 first,count=memory.u32(record+0x1c),memory.u32(record+0x20)
 if count>4096 or (count and not first):raise ValueError('Footprint bounds')
 fog=shroud=total=0
 for i in range(count):
  cell=memory.u32(first+16*i)
  if not cell:continue
  relative=cell-grid.cells
  if relative<0 or relative%0x34 or relative//0x34>=grid.width*grid.height:raise ValueError('Footprint cell outside grid')
  total+=1
  if memory.read(cell+0x32,1)[0]:shroud+=1;continue
  counter=struct.unpack('<H',memory.read(cell+4+2*player_index,2))[0]
  if counter==0:fog+=1
  elif counter==0xffff:
   if grid.default==0:fog+=1
   elif grid.default==3:shroud+=1
 if memory.u32(thing+0x9c)!=record or memory.u32(record+0x1c)!=first or memory.u32(record+0x20)!=count or memory.read(record+0xf8,1)[0]:raise ValueError('Footprint changed during sample')
 if not total or shroud==total:return 4
 if fog+shroud==total:return 3
 if not fog and not shroud and not memory.read(record+0xf9,1)[0]:return 1
 return 2

def vision_grid_snapshot(memory,grid,player_index,frame,region_size=512,max_frontiers=12):
 """Private shroud metrics/frontier geometry; no enemy object reads.
Unknown frontier coordinates derive only from a fog cell adjacent to this
player's CLEAR cell and public grid bounds. Reachability is not inferred.
"""
 if not 0<=player_index<20 or grid.width*grid.height>250000:raise ValueError('Bounded vision metrics')
 total=grid.width*grid.height;clear=set();fog=set();by_region={}
 def region_at(i):
  x=grid.origin[0]+(i%grid.width+.5)/grid.scale;y=grid.origin[1]+(i//grid.width+.5)/grid.scale
  def slug(n):return 'm'+str(-n) if n<0 else str(n)
  return 'region_'+slug(math.floor(x/region_size))+'_'+slug(math.floor(y/region_size)),x,y
 # production.Memory deliberately caps each read at 8192 bytes.
 for first in range(0,total,156):
  count=min(156,total-first);raw=memory.read(grid.cells+first*0x34,count*0x34)
  for j in range(count):
   offset=j*0x34
   if raw[offset+0x32]:continue
   counter=struct.unpack_from('<H',raw,offset+4+2*player_index)[0]
   status=0 if counter==0 else grid.default if counter==0xffff else 1
   i=first+j
   if status==1:
    clear.add(i);rid,_,_=region_at(i);by_region[rid]=by_region.get(rid,0)+1
   elif status==0:fog.add(i)
 frontier={}
 for i in sorted(fog):
  x,y=i%grid.width,i//grid.width
  neighbors=([i-1] if x else [])+([i+1] if x+1<grid.width else [])+([i-grid.width] if y else [])+([i+grid.width] if y+1<grid.height else [])
  if any(n in clear for n in neighbors):
   rid,wx,wy=region_at(i);frontier.setdefault(rid,[wx,wy,0.0])
   if len(frontier)>=max_frontiers:break
 return ({'viewer_player_id':player_index,'observed_frame':frame,'clear_cell_count':len(clear),'total_cell_count':total,'clear_cells_by_region':by_region},frozenset(clear),frontier)
