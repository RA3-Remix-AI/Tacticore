"""Independent raw native empty-land endpoint proof review; no game access."""
import math
import struct

def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]
def scalar(word):return struct.unpack('<f',struct.pack('<I',word))[0]
def bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]

def valid_row(trace,actor):
    return bool(trace.kind in (29,30,31) and trace.word_count==24 and trace.words[0]==1
        and 1<=trace.words[1]<=64 and trace.self==actor.update and trace.target==actor.thing
        and trace.operation==trace.scope==trace.source==trace.caller==0)

def groups(traces,actor,logic):
    """Check every consecutive three-row proof and independently recompute it."""
    selected=[t for t in traces if t.kind in (29,30,31)];result=[]
    if len(selected)%3:return None
    for offset in range(0,len(selected),3):
        rows=selected[offset:offset+3];a,h,c=(tuple(t.words) for t in rows)
        if (not all(valid_row(t,actor) for t in rows) or [t.kind for t in rows]!=[29,30,31]
                or len({t.frame for t in rows})!=1 or [a[1],h[1],c[1]]!=[offset//3+1]*3):return None
        target=tuple(scalar(w) for w in a[11:14]);origin=tuple(scalar(w) for w in a[14:17])
        if (a[2:5]!=(actor.object_id,actor.template_ptr,actor.owner) or a[5]<0x10000
                or a[6:11]!=(bits(5),bits(-1),0xc37620,1,1) or a[17]!=logic or a[18]!=rows[0].frame
                or a[19:24]!=(0xc4db60,0xc48670,0xc48528,actor.thing,0x19ab11af)
                or not all(math.isfinite(v) for v in target+origin) or min(target[:2])<0 or max(target[:2])>=1000000
                or not 30<=math.dist(target[:2],origin[:2])<=120 or abs(target[2]-origin[2])>2):return None
        width,height,border=h[5:8];hc,hr=h[8:10];vertices=h[10:14]
        if (not 4<=width<=8192 or not 4<=height<=8192 or border>min(width,height)//2
                or not all(v>=0x10000 and v%4==0 for v in h[2:4]) or h[4]<0x10000 or h[4]%2
                or h[4]+width*height*2>0x100000000 or h[17:19]!=(0x3dcccccd,0x3d200000)
                or h[21:]!=(0x8ed070,0,0) or any(v>65535 for v in vertices)):return None
        sx,sy=(f32(v*f32(.1)) for v in target[:2]);ix,iy=math.trunc(sx),math.trunc(sy)
        fx,fy=f32(sx-ix),f32(sy-iy)
        if (hc!=ix+border or hr!=iy+border or not 1<=hc<=width-3 or not 1<=hr<=height-3
                or h[19]!=hr*width+hc or h[20]!=h[4]+2*h[19] or h[14:16]!=(bits(fx),bits(fy))):return None
        # Recompute triangular interpolation in the pinned scalar SSE order.
        middle=vertices[2] if fy>fx else vertices[1];small,large=(fx,fy) if fy>fx else (fy,fx)
        first=f32((vertices[3]-middle)*small);second=f32((vertices[0]-middle)*f32(1-large))
        z=f32(f32(f32(first+second)+middle)*.0390625)
        if h[16]!=bits(z) or a[13]!=bits(z):return None
        left,bottom=c[22]&0xffff,c[22]>>16;right,top=c[23]&0xffff,c[23]>>16
        col,row=(math.trunc(f32(v*f32(.05))) for v in target[:2]);raw=c[9:21];flags=raw[3]
        if (not all(v>=0x10000 and v%4==0 for v in c[2:6]) or c[21]!=0x3d4ccccd
                or not 0<=left<=col<=right<8192 or not 0<=bottom<=row<=top<8192 or c[6:8]!=(col,row)
                or c[8]!=c[5]+48*row or c[8]+48>0x100000000 or raw[0]!=0
                or flags&15 or (flags>>4)&63!=1 or flags&0x40000):return None
        result.append(dict(group=a[1],frame=rows[0].frame,target=target,origin=origin))
    return result

def has_move_proof(proofs,point,frame):
    target=(point.x,point.y,point.z)
    return proofs is not None and any(p['target']==target and p['frame']==frame for p in proofs)
