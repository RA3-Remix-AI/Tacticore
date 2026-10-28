"""Read-only original Team ID order, not a formation-slot or control grant.

Pinned 839ee0/839f10 -> list+8/+c, 829230 stable erase, 8311b0 append.
The complete paired global Thing list independently checks membership/ownership.
"""
import struct


def _words(raw):
    return struct.unpack('<' + 'I'*(len(raw)//4), raw)


def _pointer(value):
    return type(value) is int and 0x10000 <= value <= 0xfffff000 and value % 4 == 0


def capture(memory, actor, native, *, source_team=None, player_id=3):
    reads=[]
    def read(address, size):
        if not _pointer(address) or not 0 < size <= 0x2000:
            raise ValueError('team_roster_read_bounds')
        raw=memory.read(address,size)
        if len(raw)!=size:raise ValueError('team_roster_short_read')
        reads.append((address,raw))
        return raw
    def word(address):return _words(read(address,4))[0]
    logic=word(0xcd8ce4)
    if word(logic)!=0xbeb630:raise ValueError('team_roster_logic_identity')
    frame=word(logic+0x50);head=word(logic+0xb4)
    if (not native.get('identity') or not native.get('birth_verified') or not native.get('live')
            or native.get('object_id')!=actor.object_id or native.get('generation')!=actor.generation
            or not 0<=frame-native['frame']<=1):
        raise ValueError('team_roster_native_actor_context')
    if word(actor.owner)!=0xc5bce0 or word(actor.owner+0x20)!=player_id:
        raise ValueError('team_roster_owner_binding')
    # Whole Thing storage is read only through its already verified owner field
    # at418. Only the five relevant words are paired; moving xyz is unrelated.
    nodes=[];seen=set();cursor=head
    while cursor:
        if cursor in seen or len(nodes)>=20000 or not _pointer(cursor):
            raise ValueError('team_roster_global_chain_bounds')
        seen.add(cursor)
        if _words(memory.read(cursor,4))[0]!=0xc4db60:
            raise ValueError('team_roster_thing_class')
        raw=memory.read(cursor,0x41c)
        if len(raw)!=0x41c:raise ValueError('team_roster_short_thing')
        values=tuple(struct.unpack_from('<I',raw,o)[0] for o in (0,0x7c,0xdc,0x414,0x418))
        if values[0]!=0xc4db60:raise ValueError('team_roster_thing_class')
        nodes.append((cursor,values));cursor=values[1]
    candidates=[(p,w) for p,w in nodes if w[2]==actor.object_id]
    if len(candidates)!=1 or candidates[0][0]!=actor.thing or candidates[0][1][4]!=actor.owner:
        raise ValueError('team_roster_actor_not_unique')
    current_team=candidates[0][1][3]
    if current_team!=native['team'] or word(actor.thing+0x374)!=actor.update or word(actor.thing+4)!=actor.template_ptr or word(actor.template_ptr+8)!=actor.type_hash:
        raise ValueError('team_roster_actor_tuple_changed')
    team=current_team if source_team is None else source_team
    team_raw=read(team,0x14);team_words=_words(team_raw)
    definition=team_words[1]
    if word(definition+8)!=actor.owner:raise ValueError('team_roster_foreign_team')
    list_address=team_words[4];list_raw=read(list_address,0x14);v=_words(list_raw)
    begin,end,capacity=v[2:5]
    if (not all(_pointer(p) for p in (begin,end,capacity)) or not begin<=end<=capacity
            or (end-begin)%4 or end-begin>0x2000 or capacity-begin>0x2000):
        raise ValueError('team_roster_vector_bounds')
    ids=list(_words(read(begin,end-begin))) if begin!=end else []
    if any(not x for x in ids) or len(ids)!=len(set(ids)):
        raise ValueError('team_roster_duplicate_or_empty_id')
    members=[(p,w) for p,w in nodes if w[3]==team]
    if any(w[4]!=actor.owner for _,w in members):raise ValueError('team_roster_foreign_member')
    expected={w[2] for _,w in members}
    if set(ids)!=expected or len(ids)!=len(members):
        raise ValueError('team_roster_global_membership_mismatch')
    # Pair global relevant fields in one contiguous read per Thing. Do not
    # require unrelated positions or animation bytes to stay unchanged.
    for address,values in nodes:
        raw=memory.read(address,0x41c)
        if len(raw)!=0x41c or tuple(struct.unpack_from('<I',raw,o)[0] for o in (0,0x7c,0xdc,0x414,0x418))!=values:
            raise ValueError('team_roster_global_changed')
    if any(memory.read(address,len(raw))!=raw for address,raw in reads):
        raise ValueError('team_roster_paired_read_changed')
    index=ids.index(actor.object_id) if actor.object_id in ids else None
    return dict(kind='paired_original_team_id_list_order',frame=frame,native_frame=native['frame'],
                actor_id=actor.object_id,actor_generation=actor.generation,actor_current_team=current_team,
                source_team=team,source_team_owner=actor.owner,list_address=list_address,
                team_header_hex=team_raw.hex(),list_header_hex=list_raw.hex(),id_order=ids,
                id_order_hex=struct.pack('<'+'I'*len(ids),*ids).hex(),
                actor_index=index,actor_is_last_member=index is not None and index==len(ids)-1,
                stable_erase_prediction=[x for x in ids if x!=actor.object_id],
                global_head=head,global_count=len(nodes),global_records=[dict(thing=p,words=w) for p,w in nodes],
                paired_reads_verified=True,formation_slot_mapping_verified=False,
                home_future_vacancy_verified=False,native_writes=0,sdk_calls=0,execution_authority_granted=False)


class TeamRosterRecorder:
    """Bounded diagnostic component; failure never controls a native action."""
    def __init__(self,memory,runtime,binding,actor,record):
        self.memory,self.runtime,self.binding,self.actor=memory,runtime,binding,actor
        self.source_team=None;self.last_frame=None;self.last_stage=None
        self.record=record['source_team_order']=dict(samples=[],refusals=[],capacity=64,
            source_bound_before_reserve=False,formation_slot_mapping_verified=False,
            execution_authority_granted=False,native_writes=0,sdk_calls=0)

    def capture(self,stage):
        if len(self.record['samples'])+len(self.record['refusals'])>=self.record['capacity']:
            self.record['incomplete']=True
            return
        try:
            native=self.runtime.observe_actor(self.binding)
            if stage==self.last_stage and self.last_frame is not None and native['frame']-self.last_frame<20:
                return
            self.last_frame,self.last_stage=native['frame'],stage
            team=native['team'] if stage=='before_reserve' else self.source_team
            result=capture(self.memory,self.actor,native,source_team=team)
            if self.source_team is None or stage=='before_reserve':self.source_team=result['source_team']
            if stage=='before_reserve':self.record['source_bound_before_reserve']=True
            result['stage']=stage;self.record['samples'].append(result)
        except Exception as error:
            self.record['refusals'].append(dict(stage=stage,frame=self.last_frame,
                reason=type(error).__name__,detail=str(error)))
