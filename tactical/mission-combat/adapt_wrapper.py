"""One-time offline adapter for the independent mission fork."""
from pathlib import Path
P=Path(__file__).resolve().parent
s=(P/'lease.py').read_text(encoding='utf-8')
def sub(a,b):
 global s
 if s.count(a)!=1:raise ValueError((a[:80],s.count(a)))
 s=s.replace(a,b,1)
MISSION_U='mission_deadline_frame mission_stage stage_revision stage_frame reason_code approach_limit engage_limit retreat_limit approach_started engage_started retreat_started retreat_observed_frame retreat_source retreat_anchor retreat_anchor_id retreat_anchor_hash normal_move_facade_calls normal_move_private_calls move_index move_started move_last_progress_frame arrival_last_frame waypoint_samples retreat_arrival_samples approach_move_calls retreat_move_calls checkpoint_count retreat_index heartbeat_tick'
MISSION_F='move_best_distance approach_distance own_hp initial_hp retreat_hp_fraction'
sub("+[(x,U) for x in 'active_weapon_entry active_weapon_asset active_weapon_ammo status84'.split()]","+[(x,U) for x in 'active_weapon_entry active_weapon_asset active_weapon_ammo status84 mission_stage stage_revision stage_frame move_index'.split()]+[('command_xyz',c.c_float*3)]+[(x,c.c_float) for x in 'waypoint_distance own_hp'.split()]")
sub("+[('events',Event*4096)]","+[(x,U) for x in '"+MISSION_U+"'.split()]+[('retreat_goal',c.c_float*3),('waypoint',c.c_float*3),('checkpoint',(c.c_float*3)*16)]+[(x,c.c_float) for x in '"+MISSION_F+"'.split()]+[('events',Event*4096)]")
start=s.index('def assessment(report):');end=s.index('def capture_weapon_binding',start)
s=s[:start]+'''def assessment(report):
 sys.path.insert(0,str(HERE.parent));from mission_combat_qualification import qualify
 return qualify(report)

'''+s[end:]
sub("report['native']['target']=list(shared.target);", "report['native'].update({x:getattr(shared,x) for x in '"+MISSION_U+' '+MISSION_F+"'.split()});report['native']['retreat_goal']=list(shared.retreat_goal);report['native']['waypoint']=list(shared.waypoint);report['native']['checkpoints']=[list(x) for x in shared.checkpoint[:min(shared.checkpoint_count,16)]];report['native']['target']=list(shared.target);")
sub("ap.add_argument('--proof-file',type=Path);", "ap.add_argument('--mission-file',type=Path);ap.add_argument('--expires-frame',type=int);ap.add_argument('--proof-file',type=Path);")
s=s.replace("default=180);ap.add_argument('--post-frames'","default=4500);ap.add_argument('--post-frames'")
sub("contact=dict(contact,template=memory.u32(contact['address']+4));args.dx=40.;args.dy=0.","""contact=dict(contact,template=memory.u32(contact['address']+4));args.dx=40.;args.dy=0.
 if args.mission_file is None:raise ValueError('trusted_mission_file_required')
 mission_raw=args.mission_file.read_bytes();mission=json.loads(mission_raw.decode('utf-8-sig'))
 from mission_contract import validate_mission
 mission=validate_mission(mission,pre,memory,args.expires_frame)
 args.lease_frames=mission['expires_frame']-pre['frame']""")
sub("not 30<=args.lease_frames<=180", "not 300<=args.lease_frames<=4500")
sub("target_role=safety['templates'][contact['type_hash']]['role'],", "mission=mission,mission_protocol='continuous_tactical_v1',expires_frame=mission['expires_frame'],mission_source_sha256=hashlib.sha256(mission_raw).hexdigest(),target_role=safety['templates'][contact['type_hash']]['role'],")
sub("s.magic=0x4f434231;s.version=8;", "s.magic=0x4d435431;s.version=9;")
sub("times=[w.FILETIME() for _ in range(4)]", """s.mission_deadline_frame=mission['expires_frame'];s.retreat_goal[:]=mission['retreat_point']['xyz'];s.retreat_observed_frame=mission['retreat_point']['observed_frame'];s.retreat_source=1 if mission['retreat_point']['source']=='own_home_base' else 2;s.retreat_anchor=mission.get('anchor_address',0);s.retreat_anchor_id=mission['retreat_point'].get('anchor_object_id',0);s.retreat_anchor_hash=mission.get('anchor_hash',0);s.approach_limit=mission['approach_frames'];s.engage_limit=mission['engage_frames'];s.retreat_limit=mission['retreat_frames'];s.retreat_hp_fraction=mission['retreat_hp_fraction'];s.heartbeat_tick=k.GetTickCount()
  times=[w.FILETIME() for _ in range(4)]""")
sub("s.lease_frames=args.lease_frames;", "s.lease_frames=args.lease_frames;")
sub("deadline=time.monotonic()+185", "deadline=time.monotonic()+650")
sub("while time.monotonic()<deadline:\n", "while time.monotonic()<deadline:\n    shared.heartbeat_tick=k.GetTickCount()\n")
sub("or safety_path.read_bytes()!=safety_raw:shared.stop_requested=1", "or safety_path.read_bytes()!=safety_raw or args.mission_file.read_bytes()!=mission_raw:shared.stop_requested=1")
(P/'lease.py').write_text(s,encoding='utf-8')
