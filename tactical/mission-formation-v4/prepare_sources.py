"""Build an isolated two-stage acquisition/planning revision from frozen MFM3.

No predecessor is changed. Actual SDK entry points and thirteen hooks remain
identical; the new state machine prevents any Move before a bounded, stopped
planning handshake and a native copy/validation of the submitted route.
"""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'mission-formation-v3'

def swap(text,old,new,count=1):
 if text.count(old)!=count:raise ValueError('source_marker_changed:'+old[:100])
 return text.replace(old,new)

def main():
 cpp=(OLD/'lease.cpp').read_text();shared=(OLD/'shared.h').read_text();host=(OLD/'host.cpp').read_text()
 if hashlib.sha256((OLD/'bin/TacticalMissionFormation3.dll').read_bytes()).hexdigest()!='632400b1cbe1cc9e59c7f360f17633bef13251c72a3a8e04ef940f850321de5f':raise ValueError('frozen_predecessor_changed')
 shared=shared.replace('0x4d464d33u','0x4d464d34u').replace('0x380','0x383')
 shared=swap(shared,'float argument_limit;};','float argument_limit;uint32_t planning_ready,route_ready,route_generation,route_commit_frame,planning_ready_frame,committed_route_count;float planning_front[3],planning_support[3],committed_route_xyz[3];};')
 fields='uint32_t planning_ready,route_ready,planning_ready_frame,planning_ready_tick,route_generation,route_committed_generation,route_commit_frame,planning_timeout_ms,planning_threat_clear,planning_threat_frame,planning_failed;float submitted_front[3],submitted_support[3],planning_front[3],planning_support[3];'
 shared=swap(shared,'Event events[T_CAP];',fields+'Event events[T_CAP];')
 (HERE/'shared.h').write_text(shared)
 for name in ('event.cpp.inc','mission_state.cpp.inc'):
  (HERE/name).write_text((OLD/name).read_text())
 event=(HERE/'event.cpp.inc').read_text()
 event=swap(event,' p->events[i]=e;', ' e.planning_ready=p->planning_ready;e.route_ready=p->route_ready;e.route_generation=p->route_committed_generation;e.route_commit_frame=p->route_commit_frame;e.planning_ready_frame=p->planning_ready_frame;e.committed_route_count=frozen_route_count;memcpy(e.planning_front,p->planning_front,12);memcpy(e.planning_support,p->planning_support,12);if(kind==74&&arg<frozen_route_count)memcpy(e.committed_route_xyz,frozen_route[arg],12);\n p->events[i]=e;')
 (HERE/'event.cpp.inc').write_text(event)
 state=(HERE/'mission_state.cpp.inc').read_text()
 # Route commands use a private immutable native copy, not the writable mapping.
 state=state.replace('p->route_count','frozen_route_count').replace('p->route[','frozen_route[')
 old_start='''  if(p->stop_requested||GetTickCount()-start_tick>60000||frozen_route_count<2||frozen_route_count>16||p->mission_deadline_frame<=now+120||p->mission_deadline_frame-now>4500||now<p->target_observed_frame||now-p->target_observed_frame>60||!mobile(p->unit,p->update)||!mobile(p->support.thing,p->support.update)||!button_identity()||!visible_target()||p->support.id==p->object_id||p->support.hash!=0x2c358c61||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}
  read(p->unit+0x38,p->safe_front,12);read(p->support.thing+0x38,p->safe_support,12);float gap=distance(p->safe_front,p->safe_support);if(gap<25||gap>200){p->error=34;finish();return;}
  for(unsigned i=0;i<frozen_route_count;i++){float* prev=i?frozen_route[i-1]:p->safe_front;float d=distance(prev,frozen_route[i]);if(!finite_point(frozen_route[i])||d<25||d>180||fabsf(prev[2]-frozen_route[i][2])>100){p->error=34;finish();return;}}
'''
 new_start='''  if(p->stop_requested||GetTickCount()-start_tick>60000||p->route_ready||p->route_count||p->planning_timeout_ms!=6000||p->mission_deadline_frame<=now+120||p->mission_deadline_frame-now>4500||now<p->target_observed_frame||now-p->target_observed_frame>60||!admissible_actor(p->unit,p->update)||!admissible_actor(p->support.thing,p->support.update)||!button_identity()||!visible_target()||!p->planning_threat_clear||now<p->planning_threat_frame||now-p->planning_threat_frame>60||p->support.id==p->object_id||p->support.hash!=0x2c358c61||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}
  read(p->unit+0x38,p->safe_front,12);read(p->support.thing+0x38,p->safe_support,12);float gap=distance(p->safe_front,p->safe_support);if(gap<25||gap>180){p->error=34;finish();return;}
'''
 state=swap(state,old_start,new_start)
 state=state.replace('p->mission_deadline_frame','frozen_deadline').replace('p->lease_frames','frozen_lease_frames')
 state=swap(state,'}approach_leg(0);return;','}p->mission_stage=8;p->nav_frame=now;stop_both(5);event(76);event(76,0,0,0,0,0,1);return;')
 state=swap(state,' if(p->phase!=1)return;',' if(p->phase!=1)return;\n if(p->mission_deadline_frame!=frozen_deadline||p->lease_frames!=frozen_lease_frames){request_cleanup(48,now);return;}')
 marker=' float front_hp=0,support_hp=0;'
 state=swap(state,marker,' if(p->mission_stage==8||p->mission_stage==9){planning_tick(now);return;}\n'+marker)
 planning=(HERE/'planning.cpp.inc').read_text()
 state=swap(state,'static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){',planning+'\nstatic void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){')
 (HERE/'mission_state.cpp.inc').write_text(state)
 # Store actual compiled include files rather than duplicate stale generated code.
 a=cpp.index('static bool visible_target();');z=cpp.index('\ntypedef void',a);cpp=cpp[:a]+'#include "event.cpp.inc"\n'+cpp[z:]
 a=cpp.index('static float distance(');z=cpp.index('static void install',a);cpp=cpp[:a]+'#include "mission_state.cpp.inc"\n'+cpp[z:]
 cpp=cpp.replace('TacticalMissionFormation3','TacticalMissionFormation4').replace('p->version!=3','p->version!=4')
 cpp=swap(cpp,'static Tactical* p;', 'static float frozen_route[16][3];static uint32_t frozen_route_count,frozen_deadline,frozen_lease_frames;\nstatic Tactical* p;')
 cpp=swap(cpp,' p->phase=5;window=hwnd;', ' frozen_route_count=0;frozen_deadline=p->mission_deadline_frame;frozen_lease_frames=p->lease_frames;memset(frozen_route,0,sizeof(frozen_route));p->phase=5;window=hwnd;')
 (HERE/'lease.cpp').write_text(cpp)
 host=host.replace('TacticalMissionFormation3','TacticalMissionFormation4')
 (HERE/'host.cpp').write_text(host)
 (HERE/'build.ps1').write_text((OLD/'build.ps1').read_text().replace('TacticalMissionFormation3.dll','TacticalMissionFormation4.dll'))
 (HERE/'primitive-provenance.json').write_text(json.dumps({str(x.relative_to(OLD)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [OLD/'lease.cpp',OLD/'shared.h',OLD/'host.cpp',OLD/'event.cpp.inc',OLD/'mission_state.cpp.inc']},indent=2))
if __name__=='__main__':main()
