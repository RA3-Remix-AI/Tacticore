"""Recompute paired private-home vacancy from native raw traces, without game IO."""
import math
import struct


def scalar(word):
    return struct.unpack('<f', struct.pack('<I', word))[0]


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def valid_row(trace, actor):
    return bool(trace.kind in (32, 33, 34) and trace.word_count == 24
                and trace.self == actor.update and trace.target == actor.thing
                and trace.operation == trace.scope == trace.source == trace.caller == 0)


def groups(traces, actor, logic, script_team):
    rows = [t for t in traces if t.kind in (32, 33, 34)]
    result = []
    i = 0
    while i < len(rows):
        h = rows[i]
        w = tuple(h.words)
        count = w[23]
        global_rows = (count + 2)//3
        own_rows = w[9]+1 if w[1] == 1 else 1 if w[1] == 2 else 0
        size = 1 + global_rows + own_rows
        if (not valid_row(h, actor) or h.kind != 32 or w[0] != len(result) + 1
                or w[1] not in (0, 1, 2) or max(w[7],w[18],count) > 20000 or i + size > len(rows)
                or w[5] != logic or w[11:16] != (actor.object_id, actor.thing, actor.owner, script_team, script_team)
                or w[19:23] != (20000, 20, 2, 2) or (w[1] != 1 and count)):
            return None
        home = tuple(scalar(x) for x in w[2:5])
        if not all(math.isfinite(x) for x in home):
            return None
        world = []
        for index, row in enumerate(rows[i+1:i+1+global_rows]):
            n = tuple(row.words)
            if (not valid_row(row, actor) or row.kind != 33 or row.frame != h.frame
                    or n[:2] != (w[0], 3*index) or any(n[20:])):
                return None
            for j in range(3):
                a,b=n[2+6*j:5+6*j],n[5+6*j:8+6*j]
                if 3*index+j<count:
                    if a!=b:return None
                    world.append(a)
                elif any(a+b):return None
        own = []
        for row in rows[i+1+global_rows:i+size]:
            n=tuple(row.words)
            if (not valid_row(row,actor) or row.kind!=34 or row.frame!=h.frame
                    or n[0]!=w[0] or n[1]>=w[7] or n[2:10]!=n[10:18] or any(n[18:])):
                return None
            a=n[2:10];xyz=tuple(scalar(x) for x in a[5:8])
            if a[1]!=0xc4db60 or a[3]!=actor.owner or not a[2] or not all(math.isfinite(x) for x in xyz):return None
            own.append((n[1],a,xyz))
        complete = w[1] == 1
        if complete:
            if (not count or count!=w[7] or count!=w[18] or w[16:18]!=(1,1) or w[8]!=1
                    or size>640 or i+size>2800 or world[0][0]!=w[6]
                    or len({n[0] for n in world})!=len(world)):
                return None
            expected=[]
            for j,n in enumerate(world):
                if not n[0] or n[0]%4 or n[1]!=(world[j+1][0] if j+1<len(world) else 0):
                    return None
                if n[2]==actor.owner:expected.append(j)
            if [n[0] for n in own]!=expected or len({n[1][2] for n in own})!=len(own):return None
            matches=0
            for index,n,xyz in own:
                if (n[0],n[4],n[3])!=world[index]:return None
                if n[0]==actor.thing:
                    if n[2]!=actor.object_id:return None
                    matches+=1
                else:
                    dx,dy,dz=(f32(a-b) for a,b in zip(xyz,home))
                    if f32(math.hypot(dx,dy))<20 and abs(dz)<=2:return None
            if matches!=1 or w[9]!=len(own)-1 or w[10]:return None
        elif w[1]==2:
            if not (w[16]&1) or w[17]!=1 or not w[10] or len(own)!=1:return None
            _,n,xyz=own[0]
            dx,dy,dz=(f32(a-b) for a,b in zip(xyz,home))
            if n[0]!=w[10] or n[0]==actor.thing or f32(math.hypot(dx,dy))>=20 or abs(dz)>2:
                return None
        result.append(dict(group=w[0], frame=h.frame, home=home,
                           clear=complete, complete=complete, global_count=w[7]))
        i += size
    return result


def has_return_proof(proofs, home, frame, samples, script_team):
    """Three fresh distinct clear/stopped frames plus final same-frame read."""
    if proofs is None:
        return False
    streak = []
    for p in proofs:
        if p['home'] != tuple(home) or p['frame'] > frame:
            continue
        candidates = [s for s in samples if s.frame == p['frame'] and s.settled
                      and s.team == script_team and s.stance == 2
                      and s.state_id == 94 and s.state_vtable == 0xc551a0
                      and s.command_source == 1 and not s.path and not (s.state_flags & 0xffff)]
        if not p['clear'] or not candidates:
            streak = []
            continue
        s = candidates[-1]
        xyz = (s.xyz.x, s.xyz.y, s.xyz.z)
        if streak and math.dist(xyz[:2], streak[-1][1][:2]) > 1:
            streak = []
        if not streak or p['frame'] != streak[-1][0]:
            streak.append((p['frame'], xyz))
    return bool(len(streak) >= 3 and streak[-1][0] == frame
                and frame - streak[-3][0] < 90)
