"""Compile actual bounded-engagement and admission function text against memory stubs.

No Windows/game APIs, SDK calls, mappings, hooks or UI occur here.
"""
import json,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parent;D=P/'mission-combat-v7'
class Native7(unittest.TestCase):
 def test_actual_safety_guard_before_goal_sync_and_no_zero_goal_success(self):
  code=(D/'mission_tick.inc').read_text();begin=code.split('static void begin_retreat(uint32_t reason){',1)[1].split('\nstatic void final_stop',1)[0].rstrip();self.assertTrue(begin.endswith('}'));begin=begin[:-1]
  guard=next(line.strip() for line in code.splitlines() if 'own_hp<=p->initial_hp*p->retreat_hp_fraction' in line)
  sample=(D/'lease.cpp').read_text().split('static void sample_weapon(){',1)[1].split('\n}',1)[0]
  source=r'''
#include <stdint.h>
#include <stdio.h>
struct Shared {unsigned mission_stage=6,damage_goal=20,damage_total=20,lethal_source_hits=0,engagement_goal_reached=0,reason_code=0,retreat_started=0,retreat_arrival_samples=0,retreat_last_frame=0,retreat_replans=0,retreat_mode=0,retreat_index=0,checkpoint_count=1,weapon_entry=0x9000,weapon_binding_fail=0,last_ammo=3,object_id=42,shot_samples=0,rounds_consumed=0,reload_samples=0,last_limit=0,ammo_sample_frame=99,ammo_sample_tick=5940;float own_hp=80,initial_hp=100,retreat_hp_fraction=.8f;};
static Shared data,*p=&data;static unsigned stop_count=0,attack_count=0,ammo_events=0,refills=0,asset=0x447ea26e;
static unsigned frame(){return 100;}static unsigned GetTickCount(){return 6000;}static void mission_stage(unsigned x){p->mission_stage=x;}static void issue_stop(unsigned x){if(x==7)stop_count++;}
static bool weapon_identity(){return true;}static unsigned word(unsigned a){return a==0x901c?2:0x7fffffff;}static unsigned current_weapon(unsigned*e,unsigned*a){*e=0x9000;*a=2;return asset;}
static void event(unsigned kind,unsigned,unsigned,float,float,float){if(kind==22)ammo_events++;if(kind==67)refills++;}
static void sample_weapon(){SAMPLE}
static void begin_retreat(uint32_t reason){BEGIN}
static void tick_safety(){GUARD attack_count++;}
#define REQUIRE(x) if(!(x))return __LINE__
int main(){
 tick_safety();REQUIRE(p->engagement_goal_reached==1&&p->reason_code==5&&p->mission_stage==7&&stop_count==1&&attack_count==0);REQUIRE(ammo_events==1&&p->last_ammo==2&&p->rounds_consumed==1&&p->shot_samples==1);sample_weapon();REQUIRE(ammo_events==1&&refills==0);
 data=Shared();data.damage_total=15;stop_count=0;tick_safety();REQUIRE(!p->engagement_goal_reached&&p->reason_code==5&&stop_count==1);
 data=Shared();data.mission_stage=2;data.damage_goal=0;data.damage_total=0;tick_safety();REQUIRE(!p->engagement_goal_reached&&p->reason_code==5);
 data=Shared();data.damage_total=0;data.lethal_source_hits=1;tick_safety();REQUIRE(p->engagement_goal_reached==1&&p->reason_code==5);
 data=Shared();data.damage_goal=0;data.lethal_source_hits=1;tick_safety();REQUIRE(!p->engagement_goal_reached);
 data=Shared();asset=0x41872ecc;ammo_events=0;tick_safety();REQUIRE(p->weapon_binding_fail==1&&ammo_events==0&&p->reason_code==5&&p->mission_stage==7);
 puts("actual_low_hp_goal_and_ammo_sync_ok");return 0;
}
'''.replace('BEGIN',begin).replace('GUARD',guard).replace('SAMPLE',sample)
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder);(path/'core.cpp').write_text(source);subprocess.run([str(P.parent/'toolchain/w64devkit/bin/g++.exe'),'-std=c++17','-O2',str(path/'core.cpp'),'-o',str(path/'core.exe')],check=True,capture_output=True);self.assertIn('actual_low_hp_goal_and_ammo_sync_ok',subprocess.check_output([str(path/'core.exe')],text=True))
   old=(D/'candidate-d099-before-safety-goal-fix/mission_tick.inc').read_text().split('static void begin_retreat(uint32_t reason){',1)[1].split('\nstatic void final_stop',1)[0].rstrip()[:-1]
   oldsource=source.replace(begin,old).split('int main(){',1)[0]+'int main(){tick_safety();REQUIRE(!p->engagement_goal_reached&&p->reason_code==5&&stop_count==1&&attack_count==0);puts("original_same_tick_bug_confirmed");return 0;}'
   (path/'before.cpp').write_text(oldsource);subprocess.run([str(P.parent/'toolchain/w64devkit/bin/g++.exe'),'-std=c++17','-O2',str(path/'before.cpp'),'-o',str(path/'before.exe')],check=True,capture_output=True);self.assertIn('bug_confirmed',subprocess.check_output([str(path/'before.exe')],text=True))
 def test_real_native_functions_with_stubbed_memory_and_clock(self):
  tick=(D/'mission_tick.inc').read_text();engage=tick.split(' if(p->mission_stage==6){',1)[1].split('\n if(p->mission_stage==7){',1)[0].rstrip();self.assertTrue(engage.endswith('}'));engage=engage[:-1]
  admission=(D/'lease.cpp').read_text().split('static bool actor_admission(){',1)[1].split('\n}',1)[0]
  source=r'''
#include <stdint.h>
#include <math.h>
#include <map>
#include <stdio.h>
#include <string.h>
struct Shared {uint32_t unit=0x1000,update=0x2000,engage_started=100,engage_limit=60,weapon_binding_fail=0,lethal_source_hits=0,engagement_goal_reached=0;float damage_total=0,damage_goal=30;};
static Shared data,*p=&data;static std::map<uint32_t,uint32_t> words;static float height;static int reason=0;static bool visible=true,live=true;
static uint32_t word(uint32_t a){return words[a];}static bool unit(){return live;}
static bool read(uint32_t,void* out,unsigned){memcpy(out,&height,4);return true;}
static bool visible_target(){return visible;}static void sample_weapon(){}static void begin_retreat(int code){reason=code;}
static bool actor_admission(){ADMISSION}
static void engagement(uint32_t now){ENGAGE}
static int checked=0;static int check(bool cond,int line){checked++;if(!cond){printf("failed %d\n",line);return 1;}return 0;}
#define REQUIRE(x) if(check((x),__LINE__))return 1
int main(){
 for(unsigned now=100;now<160;now++){reason=0;p->damage_total=29;engagement(now);REQUIRE(reason==0);}
 reason=0;engagement(160);REQUIRE(reason==6);p->damage_total=30;reason=0;engagement(161);REQUIRE(reason==6 && !p->engagement_goal_reached);
 reason=0;engagement(159);REQUIRE(reason==1 && p->engagement_goal_reached);p->engagement_goal_reached=0;reason=0;engagement(160);REQUIRE(reason==1);
 p->damage_total=0;visible=false;reason=0;engagement(150);REQUIRE(reason==2);visible=true;p->weapon_binding_fail=1;reason=0;engagement(150);REQUIRE(reason==11);p->weapon_binding_fail=0;p->lethal_source_hits=1;reason=0;engagement(150);REQUIRE(reason==1);
 words[0x203c]=0x3000;words[0x3004]=0x4000;words[0x2000]=0xc48670;words[0x2024]=0xc48528;words[0x3024]=0x1000;words[0x4018]=0x3000;words[0x1048]=4;height=0;
 for(unsigned id: {1u,16u,10u}){words[0x4004]=id;words[0x4000]=0xc548c0;REQUIRE(actor_admission());}
 for(unsigned id: {7u,54u,77u,96u}){words[0x4004]=id;REQUIRE(!actor_admission());}
 words[0x4004]=10;words[0x4000]=123;REQUIRE(!actor_admission());words[0x4000]=0xc548c0;
 for(unsigned a: {0x1080u,0x1084u,0x1094u,0x1098u,0x1238u,0x3078u}){words[a]=0xffffffff;REQUIRE(!actor_admission());words[a]=0;}
 words[0x1048]=0;REQUIRE(!actor_admission());words[0x1048]=4;height=1;REQUIRE(!actor_admission());height=NAN;REQUIRE(!actor_admission());height=0;live=false;REQUIRE(!actor_admission());
 printf("native7_engagement_admission_%d_cases_ok\n",checked);return 0;
}
'''.replace('ADMISSION',admission).replace('ENGAGE',engage)
  with tempfile.TemporaryDirectory() as folder:
   cpp=Path(folder)/'core.cpp';exe=Path(folder)/'core.exe';cpp.write_text(source)
   subprocess.run([str(P.parent/'toolchain/w64devkit/bin/g++.exe'),'-std=c++17','-O2',str(cpp),'-o',str(exe)],check=True,capture_output=True)
   result=subprocess.check_output([str(exe)],text=True);self.assertRegex(result,r'native7_engagement_admission_8[0-9]_cases_ok')
if __name__=='__main__':unittest.main()
