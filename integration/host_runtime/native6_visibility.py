"""Same per-match lawful footprint handshake over frozen portable audit data.

No observer fallback, new hidden-field reads, native call or mutation.
"""
from .native6_qualification import current
from .native6_runtime_contract import read
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for folder in ('production','native-ai','visibility'):
    if str(ROOT/folder) not in sys.path:sys.path.insert(0,str(ROOT/folder))
from read_selected_personality import inspect_player,resolve_registry
from native_read import ShroudReader,walk_live_things,object_footprint_status
load=read

def bind_session(memory,session,player_id):
 if type(player_id) is not int or player_id!=3:raise ValueError('Native6 lawful viewer must be P3')
 root,pin,inventory,manifest,cap=current()
 if session.get('mod_sha256')!=cap['package_sha256'] or Path(session['registry'])!=root/'qualification/registry.json':raise ValueError('Native6 visibility session changed')
 safety=cap['safety']
 if memory.pid!=session['pid']:raise ValueError('Visibility PID mismatch')
 for va,expected in cap['expected_signatures'].items():
  if memory.read(int(va,0),len(bytes.fromhex(expected))).hex()!=expected:raise ValueError('Visibility native signature changed: '+va)
 logic=memory.u32(0xcd8ce4);frame=memory.u32(logic+0x50)
 if not frame or memory.u32(logic)!=0xbeb630:raise ValueError('Live match not ready')
 plist=memory.u32(0xce8c9c);player=memory.u32(plist+0x30+4*player_id)
 native=inspect_player(memory.read,player);registry=load(session['registry']);binding=resolve_registry(native,registry,session)
 if native['player_index']!=player_id or not binding['personality_binding_verified']:raise ValueError('Selected computer commander binding failed')
 ai=int(native['ai_player'],0);grid=ShroudReader(memory);own_full=0
 for thing in walk_live_things(memory,logic):
  if memory.u32(thing+0x418)!=player:continue
  if object_footprint_status(memory,thing,player_id,grid)==1:own_full+=1
 if not own_full or not grid.stable() or memory.u32(0xcd8ce4)!=logic or memory.u32(logic+0x50)<frame or memory.u32(player+0x90)!=ai:raise ValueError('Per-session own footprint/view handshake not ready')
 proof={'schema_version':2,'object_visibility_method':'native_footprint_reconstruction','footprint_live_verified':True,'session_id':session['session_id'],'target_player_id':player_id,'package_sha256':session['mod_sha256'],'build_id':pin,'terrain_view_live_verified':True,'object_view_live_verified':True,'conservative_stealth_exclusion_reviewed':True,'no_observer_fallback':True,'detection_verified':False,'commander_id':binding['commander_id'],'handshake':{'game_logic':logic,'player':player,'ai_player':ai,'shroud_manager':grid.manager,'shroud_impl':grid.impl,'frame_min':frame,'own_fully_clear_footprints':own_full},'evidence':'Prior exact-build cross-view/footprint transition evidence plus this session native signatures, computer UUID chain and own-footprint query. No UI flag inputs.','mutations':False}
 return proof,safety
