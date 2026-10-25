"""Bounded live-list own-player candidates. No enemy records leave this module."""
import math
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'visibility'))
from native_read import walk_live_things

def load_catalog():
    source=ROOT.parent/'reference/Ra3-Copilot/ra3-copilot/src/battle_catalog.h'
    result={}
    for match in re.finditer(r'\{\s*0x([0-9A-Fa-f]+)u, u8"([^"]*)", "([^"]*)", (\d+), (\d+), (\d+)\s*\}',source.read_text(encoding='utf-8')):
        ident,name,template,side,cls,category=match.groups()
        result[int(ident,16)]=dict(name=name,template=template,side=int(side),cls=int(cls),category=int(category))
    return result

def own_candidates(memory,player_index,catalog):
    if type(player_index) is not int or not 0<=player_index<16:raise ValueError('Invalid own player index')
    logic=memory.u32(0xcd8ce4)
    if not logic or memory.u32(logic)!=0xbeb630:raise ValueError('GameLogic unavailable')
    frame=memory.u32(logic+0x50)
    players=memory.u32(0xce8c9c)
    owner=memory.u32(players+0x30+4*player_index)
    if not owner or memory.u32(owner)!=0xc5bce0 or memory.u32(owner+0x20)!=player_index:raise ValueError('Own player unavailable')
    candidates=[];seen=set()
    for thing in walk_live_things(memory,logic):
        if memory.u32(thing+0x418)!=owner:continue
        ident=memory.u32(thing+0xdc)
        if not ident or ident in seen:raise ValueError('Live object identity unavailable or duplicated')
        seen.add(ident)
        xyz=struct.unpack('<fff',memory.read(thing+0x38,12))
        if not all(math.isfinite(x) and abs(x)<1000000 for x in xyz):raise ValueError('Own object position unavailable')
        template=memory.u32(thing+4)
        type_hash=memory.u32(template+8)
        candidates.append(dict(address=hex(thing),owner_address=hex(owner),owner_index_candidate=player_index,object_id=ident,type_hash=hex(type_hash),ai_address=hex(memory.u32(thing+0x374)),xyz=xyz,catalog=catalog.get(type_hash,{})))
    if memory.u32(0xcd8ce4)!=logic or memory.u32(0xce8c9c)!=players or memory.u32(players+0x30+4*player_index)!=owner or memory.u32(logic+0x50)<frame:raise ValueError('Own-player lifecycle changed')
    return dict(owner_index_filter=player_index,candidate_count=len(candidates),candidates=candidates,source='native_live_list_own_only',frame_start=frame,frame_end=memory.u32(logic+0x50))
