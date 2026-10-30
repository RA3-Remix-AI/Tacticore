"""Pure, exact-build read-only budget slice of MacroObserver.sample.

No process opener, native calls, ctypes, heap scan or side effects on import.
The caller supplies the already session-pinned read and identity observer.
"""
import copy
import math
import struct

EXE_SHA256='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
ACCOUNTS=('investment','special_operations','production','defense','technology','slush_fund')
GROUP_VTABLES={0xc5f3cc,0xc5f668,0xc5f664}
PINS={0x8b2e00:'8b86ec000000',0x8b2e08:'8b9ee8000000',0x892de6:'8b421083c00c',
    0x892ded:'8d4f04',0x892c3c:'89b1fc000000',0x892cc3:'f30f114c9114',0x892ce2:'f30f1199c8000000',
    0x889999:'8b4e0885c9',0x8899a2:'8b50045355ffd2',0x8bc12a:'c6400801',
    0x8d5727:'89beb0080000',0x844a3f:'898690000000'}

def pointer(value,size=4):
    if type(value) is not int or value%4 or not 0x10000<=value<=0x100000000-size:raise ValueError('budget_pointer')
    return value

def word(read,at):return struct.unpack('<I',read(at,4))[0]

def text(read,at):
    if not 0x10000<=at<=0xfffffeff:raise ValueError('budget_string_pointer')
    raw=bytearray()
    for offset in range(256):
        byte=read(at+offset,1)
        if byte==b'\0':return raw.decode('utf8')
        if type(byte) is not bytes or len(byte)!=1:raise ValueError('budget_string_read')
        raw.extend(byte)
    raise ValueError('budget_string_bound')

def group_flags(read,group):
    pointer(group,0x2c)
    if word(read,group) not in GROUP_VTABLES:return []
    head=group+4;raw_head=read(head,8);first,last=struct.unpack('<II',raw_head)
    at,previous=first,head;seen=set();copies=[];flags=[]
    while at!=head:
        pointer(at,12)
        if at in seen or len(seen)>=32:raise ValueError('budget_heuristic_list_bound')
        seen.add(at);raw=read(at,12);nxt,back,heuristic=struct.unpack('<III',raw)
        if back!=previous:raise ValueError('budget_heuristic_link')
        pointer(heuristic,8)
        if word(read,heuristic)==0xc5e8f8:
            definition=pointer(word(read,heuristic+4),12)
            flags.append(text(read,word(read,definition+8)))
        copies.append((at,raw));previous,at=at,nxt
    if previous!=last or read(head,8)!=raw_head or any(read(p,len(raw))!=raw for p,raw in copies):
        raise ValueError('budget_heuristic_changed')
    return flags

def budget_slice(read,ai,flags):
    """Same owned +e8 cache / +100 key / six bank fields as frozen observer."""
    header=read(ai+0xe8,8);start,end=struct.unpack('<II',header)
    if end<start or end-start>8192 or (end-start)%12 or bool(start)!=bool(end):raise ValueError('budget_cache_bounds')
    if start:pointer(start,end-start or 4)
    raw=read(start,end-start) if end>start else b'';scores={};definitions=[]
    for offset in range(0,len(raw),12):
        group,score=struct.unpack_from('<If',raw,offset)
        if not group:continue
        for flag in group_flags(read,group):
            if flag not in flags:continue
            if flag in scores:raise ValueError('budget_duplicate_flag')
            if not math.isfinite(score) or not 0<=score<=1000 or raw[offset+8] not in (0,1):raise ValueError('budget_cache_score')
            definition=pointer(word(read,group+0x10),0x14);definitions.append((group,definition))
            scores[flag]=dict(domain='budget',score=score,dirty=bool(raw[offset+8]),group=hex(group),definition=hex(definition))
    selected_raw=read(ai+0x100,4);selected=struct.unpack('<I',selected_raw)[0]
    offsets=(0x18,0x3c,0x60,0x84,0xa8,0xcc);shares_raw=[read(ai+off,4) for off in offsets]
    shares=[struct.unpack('<f',data)[0] for data in shares_raw]
    if any(not math.isfinite(v) or not 0<=v<=1.00001 for v in shares) or abs(sum(shares)-1)>.0001:
        raise ValueError('budget_account_bounds')
    selected_flags=[flag for flag,row in scores.items() if int(row['definition'],0)+0xc==selected]
    if len(selected_flags)>1:raise ValueError('budget_selected_alias')
    if (read(ai+0xe8,8)!=header or (raw and read(start,len(raw))!=raw) or read(ai+0x100,4)!=selected_raw
            or any(read(ai+off,4)!=data for off,data in zip(offsets,shares_raw))
            or any(word(read,group+0x10)!=definition for group,definition in definitions)):
        raise ValueError('budget_slice_changed')
    return dict(state_scores=scores,budget_feedback=dict(selected_budget_key=hex(selected),
        selected_macro_flag=selected_flags[0] if selected_flags else None,account_shares=dict(zip(ACCOUNTS,shares)),
        native_percentages_observed=True,payment_attribution_verified=False))

class BudgetObserver:
    def __init__(self,read,owner,expected_native,flags,*,expected_logic,inspect_identity,executable_sha256):
        if executable_sha256!=EXE_SHA256:raise ValueError('budget_exact_build_required')
        self.read=read;self.owner=pointer(owner,0x94);self.native=copy.deepcopy(expected_native)
        self.logic=pointer(expected_logic,0x54);self.identity=inspect_identity;self.flags=tuple(flags)
        if (len(self.flags)!=3 or len(set(self.flags))!=3 or any(type(f) is not str or not f.endswith(('_budgeteconomy','_budgetarmy','_budgettech')) for f in self.flags)
                or self.native.get('player')!=hex(owner) or self.native.get('player_index')!=3
                or self.native.get('instance_id')!='0x799613e0' or self.native.get('store_membership_verified') is not True
                or self.native.get('side_matches_player') is not True):raise ValueError('budget_identity_contract')
        if {f.rsplit('_',1)[-1] for f in self.flags}!={'budgeteconomy','budgetarmy','budgettech'} or len({f.rsplit('_',1)[0] for f in self.flags})!=1:
            raise ValueError('budget_flag_set')
        self.ai=pointer(int(self.native['ai_player'],0),0x8b4)
        for at,data in PINS.items():
            if read(at,len(bytes.fromhex(data)))!=bytes.fromhex(data):raise ValueError('budget_signature')
        self._identity()
    def _identity(self):
        read=self.read
        if (self.identity()!=self.native or word(read,0xcd8ce4)!=self.logic or word(read,self.logic)!=0xbeb630
                or word(read,self.owner)!=0xc5bce0 or word(read,self.owner+0x20)!=3 or word(read,self.owner+0x90)!=self.ai
                or word(read,self.ai)!=0xc60f60 or word(read,self.ai+8)!=self.owner or word(read,self.ai+0x8a8)!=self.owner
                or word(read,self.ai+0x8b0)!=int(self.native['personality_wrapper'],0)):
            raise ValueError('budget_identity_changed')
    def sample(self):
        self._identity();frame=word(self.read,self.logic+0x50)
        if not frame:raise ValueError('budget_match_not_running')
        value=budget_slice(self.read,self.ai,self.flags);self._identity();after=word(self.read,self.logic+0x50)
        if not frame<=after<=frame+2:raise ValueError('budget_frame_changed')
        return dict(frame=frame,frame_after=after,source='native_macro_budget_domain_read_only',
            native=copy.deepcopy(self.native),**value,own_perspective=True,enemy_details_read=False,
            strategic_runtime_sample_included=False,native_calls=0,process_writes=0,payment_verified=False,capability_granted=False)
