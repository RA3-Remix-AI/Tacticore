"""Read-only native macro state/owned-object telemetry, without execution authority.

Cache entries are followed from the bound AI, never selected from arbitrary
matching heap copies. Runtime heap candidates require the bound owner, matching
definition, self link and intact native intrusive links on every sample.
"""
import ctypes as c
import math
import re
import struct

from probe import MBI, k
from read_selected_personality import inspect_player

FLAG_HEURISTIC_VTABLE = 0xc5e8f8
SCOUT_RUNTIME_VTABLE = 0xc60cb8
SIMPLE_ATTACK_RUNTIME_VTABLE = 0xc60d40
STATIC_DEFENSE_RUNTIME_VTABLE = 0xc60bc4
RUNTIME_VTABLES = {SCOUT_RUNTIME_VTABLE,SIMPLE_ATTACK_RUNTIME_VTABLE,STATIC_DEFENSE_RUNTIME_VTABLE}
GROUP_VTABLES = {0xc5f3cc, 0xc5f668, 0xc5f664}
PINS = {
    0xc60bcc: '70058800',             # StaticDefense type-name virtual slot
    0x880570: 'b850e9c500c3',         # returns AIStaticDefenseTactic type name
    0x8bc104: '8b81e0060000',             # AI state cache begin
    0x8bc10a: '8b91e4060000',             # AI state cache end
    0x8bc121: '83c00c',                   # 12-byte entries
    0x8bc12a: 'c6400801',                 # entry+8 is dirty, not active
    0x889999: '8b4e0885c9',               # list-node payload is heuristic
    0x8899a2: '8b50045355ffd2',           # native heuristic virtual result
    0x8ae65f: '895650894654',             # runtime definition and tactic index
    0x8ae676: '89b694000000',             # runtime self link
    0x8cfa8c: 'c706b80cc600',             # native scout tactic runtime
    0x8d3a44: '76358d00',                 # tactic enum zero -> SimpleAttack factory
    0x8d35a5: 'e836c8ffff',               # SimpleAttack constructor
    0x8cfe0a: 'e8d1e7fdff',               # same bounded base runtime layout
    0x8cfe21: 'c706400dc600',             # distinct SimpleAttack runtime vtable
    0x8c968e: 'c6461401',                 # native execution active
    0x8bc135: 'c6431400',                 # native cleanup resets active
    0x84326d: '8d7128',                   # AI object registry table
    0x504e1d: '8b79088bc6f7f7',           # integer ID modulo bucket count
    0x504e35: '8b4008',                   # next hash-chain node
    0x84f0d1: '8b4910',                   # group -> native Team
    0x83510b: '8b4d0c2b4d08',             # Team authoritative Thing-ID vector
    0x83515b: '81c6bc000000',             # GameLogic Thing registry
    0x8b2e00: '8b86ec000000',             # budget state cache end
    0x8b2e08: '8b9ee8000000',             # budget state cache begin
    0x892de6: '8b421083c00c',             # winning budget definition + c
    0x892ded: '8d4f04',                   # native bank = AI + 4
    0x892c3c: '89b1fc000000',             # native bank selected budget key
    0x892cc3: 'f30f114c9114',             # native account percent array stride
    0x892ce2: 'f30f1199c8000000',         # residual share = SLUSH_FUND
}


def word(read, address):
    return struct.unpack('<I', read(address, 4))[0]


def pointer(value, size=4):
    if value % 4 or not 0x10000 <= value <= 0x100000000-size:
        raise ValueError('invalid_macro_pointer')
    return value


def verify_pins(read):
    for address, expected in PINS.items():
        raw=bytes.fromhex(expected)
        if read(address,len(raw))!=raw:
            raise ValueError('macro_observation_signature_mismatch')


def text(read, address):
    # Serialized XML string buffers need not be four-byte aligned.
    if not 0x10000<=address<=0xfffffeff:
        raise ValueError('invalid_macro_string_pointer')
    raw=bytearray()
    for i in range(256):
        byte=read(address+i,1)
        if byte==b'\0':
            return raw.decode('utf-8',errors='strict')
        raw.extend(byte)
    raise ValueError('macro_flag_name_unterminated')


def group_flags(read, group):
    pointer(group,0x2c)
    if word(read,group) not in GROUP_VTABLES:
        return []
    head=group+4; first,last=struct.unpack('<II',read(head,8))
    at,previous=first,head; seen=set(); samples=[]; flags=[]
    while at!=head:
        pointer(at,12)
        if at in seen or len(seen)>=32:
            raise ValueError('macro_heuristic_list_cycle_or_bound')
        seen.add(at)
        raw=read(at,12);next_node,back,heuristic=struct.unpack('<III',raw)
        if back!=previous:
            raise ValueError('macro_heuristic_back_link')
        pointer(heuristic,8)
        if word(read,heuristic)==FLAG_HEURISTIC_VTABLE:
            definition=pointer(word(read,heuristic+4),12)
            name=text(read,word(read,definition+8))
            flags.append(dict(name=name,heuristic=hex(heuristic),definition=hex(definition)))
        samples.append((at,raw));previous,at=at,next_node
    if previous!=last or read(head,8)!=struct.pack('<II',first,last) or any(read(p,len(raw))!=raw for p,raw in samples):
        raise ValueError('macro_heuristic_list_changed')
    return flags


def cache_scores(read, ai, expected_flags, cache_offset=0x6e0, domain='strategic'):
    """Current native cached aggregate scores, not a mission-success receipt."""
    if (cache_offset,domain) not in {(0x6e0,'strategic'),(0x414,'construction'),(0xe8,'budget')}:
        raise ValueError('unsupported_macro_cache_domain')
    header=read(ai+cache_offset,8);start,end=struct.unpack('<II',header)
    if end<start or end-start>8192 or (end-start)%12 or bool(start)!=bool(end):
        raise ValueError('macro_state_cache_bounds')
    if start:
        pointer(start,end-start or 4)
    raw=read(start,end-start) if end>start else b''
    rows={}
    for offset in range(0,len(raw),12):
        group,score=struct.unpack_from('<If',raw,offset)
        if not group:
            continue
        for flag in group_flags(read,group):
            name=flag['name']
            if name not in expected_flags:
                continue
            if name in rows:
                raise ValueError('duplicate_macro_state_cache_entry')
            if not math.isfinite(score) or not 0<=score<=1000 or raw[offset+8] not in (0,1):
                raise ValueError('invalid_macro_state_score')
            rows[name]=dict(flag=name,domain=domain,group=hex(group),score=score,dirty=bool(raw[offset+8]),
                cache_entry=hex(start+offset),heuristic=flag['heuristic'],definition=flag['definition'])
    if read(ai+cache_offset,8)!=header or (raw and read(start,len(raw))!=raw):
        raise ValueError('macro_state_cache_changed')
    return rows


def native_budget(read,ai,scores):
    selected_raw=read(ai+0x100,4);selected=struct.unpack('<I',selected_raw)[0]
    offsets=[0x18,0x3c,0x60,0x84,0xa8,0xcc]
    raw=[read(ai+offset,4) for offset in offsets]
    shares=[struct.unpack('<f',value)[0] for value in raw]
    if any(not math.isfinite(x) or not 0<=x<=1.00001 for x in shares) or abs(sum(shares)-1)>0.0001:
        raise ValueError('native_macro_budget_share_bounds')
    matches=[]
    for name,row in scores.items():
        if row['domain']!='budget':continue
        definition=pointer(word(read,int(row['group'],0)+0x10),0x14)
        if definition+0xc==selected:matches.append(name)
    if len(matches)>1:raise ValueError('native_macro_budget_alias')
    if read(ai+0x100,4)!=selected_raw or any(read(ai+offset,4)!=value for offset,value in zip(offsets,raw)):
        raise ValueError('native_macro_budget_changed')
    return dict(selected_budget_key=hex(selected),selected_macro_flag=matches[0] if matches else None,
        account_shares=dict(zip(['investment','special_operations','production','defense','technology','slush_fund'],shares)),
        native_percentages_observed=True,payment_attribution_verified=False)


def sample_runtime(read, address, owner, groups):
    """Native tactic state; identifiers remain raw until separately resolved."""
    pointer(address,0xa4)
    raw=read(address,0xa4)
    u=lambda offset:struct.unpack_from('<I',raw,offset)[0]
    if u(0) not in RUNTIME_VTABLES or u(0x2c)!=owner or u(0x50) not in groups or u(0x94)!=address:
        raise ValueError('macro_runtime_binding')
    if u(0x58)!=0xc5fe94 or u(0x5c)!=0xc5fe5c:
        raise ValueError('macro_runtime_component')
    link=address+0x60;next_node,previous=u(0x60),u(0x64)
    if word(read,pointer(next_node,8)+4)!=link or word(read,pointer(previous,8))!=link:
        raise ValueError('macro_runtime_unlinked')
    start,end=u(4),u(8)
    if end<start or end-start>128 or (end-start)%4 or bool(start)!=bool(end):
        raise ValueError('macro_owned_id_vector_bounds')
    if start:
        pointer(start,end-start or 4)
    ids=list(struct.unpack('<'+'I'*((end-start)//4),read(start,end-start))) if end>start else []
    if len(set(ids))!=len(ids) or 0 in ids or raw[0x14] not in (0,1) or raw[0x30] not in (0,1):
        raise ValueError('macro_runtime_state_or_ids')
    if read(address,0xa4)!=raw:
        raise ValueError('macro_runtime_changed')
    return dict(address=hex(address),group=hex(u(0x50)),native_execution_active=bool(raw[0x14]),
        native_tactic_family='static_defense' if u(0)==STATIC_DEFENSE_RUNTIME_VTABLE else 'simple_attack' if u(0)==SIMPLE_ATTACK_RUNTIME_VTABLE else 'flank_or_defense_avoidance_attack',
        cleanup_requested=bool(raw[0x30]),native_owned_ids_raw=ids,tactic=hex(u(0x28)),
        tactic_index=u(0x54),target_vector_begin_raw=hex(u(0x18)),target_vector_end_raw=hex(u(0x1c)),
        object_ids_resolved=False,unit_movement_attributed=False,mission_complete_verified=False)


def registry_lookup(read, table, ident):
    """Mirror native integer hash lookup without calling it or refreshing caches."""
    if not 0<ident<=0xffffffff:
        raise ValueError('native_registry_id_bounds')
    pointer(table,12)
    header=read(table+4,8);buckets,count=struct.unpack('<II',header)
    if not 1<=count<=65536:
        raise ValueError('native_registry_bucket_bounds')
    pointer(buckets,4*(count+1))
    bucket=ident%count;slot=buckets+4*bucket
    first=read(slot,4);sentinel=read(buckets+4*count,4)
    at=struct.unpack('<I',first)[0];end=struct.unpack('<I',sentinel)[0]
    seen=set();samples=[];result=0
    while at and at!=end:
        pointer(at,12)
        if at in seen or len(seen)>=128:
            raise ValueError('native_registry_cycle_or_bound')
        seen.add(at);raw=read(at,12);key,value,next_node=struct.unpack('<III',raw)
        if key%count!=bucket:
            raise ValueError('native_registry_wrong_bucket')
        samples.append((at,raw))
        if key==ident:
            result=pointer(value);break
        at=next_node
    if (read(table+4,8)!=header or read(slot,4)!=first or read(buckets+4*count,4)!=sentinel
            or any(read(p,12)!=raw for p,raw in samples)):
        raise ValueError('native_registry_changed')
    return result


def own_group_members(read, ident, owner):
    """Resolve native group IDs to own live Things; never expose enemy details.

    Team+8/+c holds authoritative Thing IDs. The +1c cached Thing* vector is
    deliberately unused because only the game's cache refresh can clear dirty.
    """
    registry=pointer(word(read,0xce8ca4),0x34)
    group=registry_lookup(read,registry+0x28,ident)
    if not group:
        return dict(native_id=ident,found=False,members=[])
    kind=word(read,group+0x39c)
    if kind!=8:
        raise ValueError('macro_owned_id_not_native_group')
    team=pointer(word(read,group+0x10),0x24)
    header=read(team+8,8);start,end=struct.unpack('<II',header)
    if end<start or end-start>2048 or (end-start)%4 or bool(start)!=bool(end):
        raise ValueError('macro_team_id_vector_bounds')
    if start:pointer(start,end-start or 4)
    raw=read(start,end-start) if end>start else b''
    ids=list(struct.unpack('<'+'I'*(len(raw)//4),raw)) if raw else []
    if len(set(ids))!=len(ids) or 0 in ids:
        raise ValueError('macro_team_duplicate_or_zero_id')
    game=pointer(word(read,0xcd8ce4),0xc8);members=[];missing=[]
    for object_id in ids:
        thing=registry_lookup(read,game+0xbc,object_id)
        if not thing:
            missing.append(object_id);continue
        if word(read,thing)!=0xc4db60 or word(read,thing+0xdc)!=object_id:
            raise ValueError('macro_member_thing_identity')
        # Ownership precedes type, position and health reads.
        if word(read,thing+0x418)!=owner:
            raise ValueError('macro_member_not_bound_owner')
        template=pointer(word(read,thing+4),12);body=pointer(word(read,thing+0x33c),8)
        hp=struct.unpack('<f',read(body+4,4))[0]
        xyz=struct.unpack('<fff',read(thing+0x38,12))
        if not math.isfinite(hp) or hp<=0 or not all(math.isfinite(x) and abs(x)<1e7 for x in xyz):
            raise ValueError('macro_member_not_live_or_bad_position')
        row=dict(thing_id=object_id,address=hex(thing),owner=hex(owner),type_hash=hex(word(read,template+8)),
            hp=hp,xyz=list(xyz))
        if word(read,thing+0x418)!=owner or word(read,thing+0xdc)!=object_id or word(read,thing+4)!=template:
            raise ValueError('macro_member_changed')
        members.append(row)
    if (word(read,0xce8ca4)!=registry or registry_lookup(read,registry+0x28,ident)!=group
        or word(read,group+0x10)!=team or word(read,group+0x39c)!=kind or read(team+8,8)!=header
        or (raw and read(start,len(raw))!=raw) or word(read,0xcd8ce4)!=game):
        raise ValueError('macro_group_members_changed')
    return dict(native_id=ident,found=True,native_group=hex(group),team=hex(team),
        authoritative_thing_ids=ids,members=members,missing_thing_ids=missing,all_members_resolved=not missing,
        cache_refreshed=False,enemy_details_read=False)


def own_census(memory,owner):
    """Own object observations and resource balance; no spend attribution."""
    from native_read import walk_live_things
    from observe_production import read_owner
    read=memory.read;game=word(read,0xcd8ce4);frame=word(read,game+0x50)
    index=word(read,owner+0x20);objects=[]
    for thing in walk_live_things(memory,game):
        if word(read,thing+0x418)!=owner:continue
        template=pointer(word(read,thing+4),12);body=word(read,thing+0x33c)
        if not body:continue
        hp=struct.unpack('<f',read(pointer(body,8)+4,4))[0]
        xyz=struct.unpack('<fff',read(thing+0x38,12));oid=word(read,thing+0xdc)
        if not oid or not math.isfinite(hp) or hp<=0 or not all(math.isfinite(x) for x in xyz):continue
        row=dict(thing_id=oid,address=hex(thing),type_hash=hex(word(read,template+8)),hp=hp,xyz=list(xyz),
            status_plus_80_raw=hex(word(read,thing+0x80)))
        if word(read,thing+0x418)!=owner or word(read,thing+4)!=template or word(read,thing+0xdc)!=oid:
            raise ValueError('macro_census_own_identity_changed')
        objects.append(row)
    resources=read_owner(memory,owner,index)
    if word(read,0xcd8ce4)!=game or not 0<=word(read,game+0x50)-frame<=2:
        raise ValueError('macro_census_changed')
    return dict(frame=frame,own_objects=objects,resources=resources,enemy_details_read=False,
        spend_attribution_verified=False,construction_completed_verified=False)


def find_runtime_candidates(memory, owner, groups):
    """Bounded exact-vtable scan. Validation follows; stale matches are omitted."""
    pattern=re.compile(b'|'.join(re.escape(struct.pack('<I',value)) for value in sorted(RUNTIME_VTABLES)))
    candidates=[];address=0x10000
    while address<0x100000000:
        info=MBI()
        if not k.VirtualQueryEx(memory.handle,address,c.byref(info),c.sizeof(info)):
            break
        base,length=info.base or 0,info.region_size
        if not length or base+length<=address:
            break
        if info.state==0x1000 and info.type==0x20000 and not info.protect&0x101:
            for offset in range(0,length,0x2000):
                try:
                    raw=memory.read(base+offset,min(0x2000,length-offset))
                except RuntimeError:
                    continue
                for match in pattern.finditer(raw):
                    at=base+offset+match.start()
                    if at%4==0:
                        try:
                            sample_runtime(memory.read,at,owner,groups)
                        except (ValueError,RuntimeError):
                            pass
                        else:
                            candidates.append(at)
                            if len(candidates)>32:
                                raise ValueError('macro_runtime_candidate_bound')
        address=base+length
    return candidates


class MacroObserver:
    def __init__(self, memory, owner, expected_flags, expected_feedback=None, terrain_feedback=False, construction_feedback=False):
        self.memory=memory;self.owner=owner;self.flags=tuple(expected_flags)
        self.native=inspect_player(memory.read,owner)
        self.ai=int(self.native['ai_player'],0)
        self.feedback=expected_feedback or {}
        verify_pins(memory.read)
        self.candidates=[];self.last_scan_frame=-100000
        self.terrain_feedback=terrain_feedback;self.previous_clear=None;self.initial_clear=None;self.grid_identity=None
        self.construction_feedback=construction_feedback

    def sample(self):
        read=self.memory.read
        if inspect_player(read,self.owner)!=self.native:
            raise ValueError('macro_observation_identity_changed')
        game=word(read,0xcd8ce4);frame=word(read,game+0x50)
        if not frame:
            raise ValueError('macro_observation_no_simulation')
        scores=cache_scores(read,self.ai,self.flags)
        if word(read,self.ai+0x410)!=0xc60314:
            raise ValueError('native_construction_state_manager_mismatch')
        construction=cache_scores(read,self.ai,self.flags,0x414,'construction')
        if set(scores)&set(construction):
            raise ValueError('macro_gate_cross_domain_alias')
        scores.update(construction)
        if word(read,self.ai+0xe4)!=0xc602fc:
            raise ValueError('native_budget_state_manager_mismatch')
        budget=cache_scores(read,self.ai,self.flags,0xe8,'budget')
        if set(scores)&set(budget):raise ValueError('macro_budget_gate_cross_domain_alias')
        scores.update(budget)
        budget_feedback=native_budget(read,self.ai,scores)
        if self.feedback:
            scout=next((row for name,row in scores.items() if name.endswith('_scout')),None)
            if scout is None:
                raise ValueError('native_scout_state_missing')
            definition=pointer(word(read,int(scout['group'],0)+0x10),0x30)
            values={}
            phases=['team_gather_begin','execution_begin','execution_canceled','execution_complete']
            if set(self.feedback)!=set(phases):
                raise ValueError('macro_feedback_fields')
            for offset,phase in zip([0x20,0x24,0x28,0x2c],phases):
                expected=self.feedback[phase]
                value=word(read,pointer(word(read,definition+offset)))
                if value!=expected:
                    raise ValueError('macro_live_feedback_hash_mismatch')
                values[phase]=hex(value)
            scout['live_feedback_hashes']=values
        groups={int(row['group'],0) for row in scores.values()}
        if frame-self.last_scan_frame>=150:
            self.candidates=find_runtime_candidates(self.memory,self.owner,groups)
            self.last_scan_frame=frame
        runtime=[];rejected=0
        for address in self.candidates:
            try:
                row=sample_runtime(read,address,self.owner,groups)
                row['owned_groups']=[]
                for ident in row['native_owned_ids_raw']:
                    try:
                        row['owned_groups'].append(own_group_members(read,ident,self.owner))
                    except (ValueError,RuntimeError) as error:
                        row['owned_groups'].append(dict(native_id=ident,read_error=str(error)))
                row['object_ids_resolved']=bool(row['owned_groups']) and all(
                    g.get('found') and g.get('all_members_resolved') for g in row['owned_groups'])
                runtime.append(row)
            except (ValueError,RuntimeError):
                rejected+=1
        if inspect_player(read,self.owner)!=self.native:
            raise ValueError('macro_observation_identity_changed')
        terrain=None
        if self.terrain_feedback:
            from native_read import ShroudReader,vision_grid_snapshot
            if read(0x992130,8)!=bytes.fromhex('8b4928e9b8f1ffff'):
                raise ValueError('macro_terrain_native_signature')
            grid=ShroudReader(self.memory)
            identity=(grid.manager,grid.impl,grid.cells,grid.width,grid.height)
            if self.grid_identity is not None and self.grid_identity!=identity:
                raise ValueError('macro_terrain_grid_changed')
            terrain_frame=word(read,game+0x50)
            metrics,clear,_=vision_grid_snapshot(self.memory,grid,self.native['player_index'],terrain_frame)
            if not grid.stable() or word(read,0xcd8ce4)!=game or not 0<=word(read,game+0x50)-terrain_frame<=2:
                raise ValueError('macro_terrain_sample_changed')
            if self.initial_clear is None:self.initial_clear=clear
            previous=self.previous_clear if self.previous_clear is not None else clear
            terrain=dict(**metrics,newly_clear_since_previous=len(clear-previous),
                lost_clear_since_previous=len(previous-clear),newly_clear_since_initial=len(clear-self.initial_clear),
                own_perspective=True,observer_fallback=False,enemy_objects_read=False,
                exclusively_attributed_to_macro_scout=False)
            self.grid_identity=identity;self.previous_clear=clear
        construction=own_census(self.memory,self.owner) if self.construction_feedback else None
        return dict(frame=frame,native=self.native,state_scores=scores,runtimes=runtime,terrain_feedback=terrain,
            construction_feedback=construction,
            budget_feedback=budget_feedback,
            stale_or_unstable_runtime_candidates=rejected,source='native_macro_read_only',
            sample_atomic=False,native_calls=0,process_writes=0,macro_effect_verified=False,
            legal_intel_feedback_verified=False,capability_granted=False)
