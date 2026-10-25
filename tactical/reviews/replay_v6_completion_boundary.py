"""Pure counterexamples. Never opens a process, starts a child or writes reports."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_mission_combat_v6 import fixture
import mission_combat_v6_qualification as q

def run(hp,before,after):
 r=fixture();r['events']=[e for e in r['events'] if e['kind'] not in [20,24,22,67] or e['kind'] in [20,24] and e['frame']==156 or e['kind']==22 and e['frame']==157]
 r['native'].update(damage_count=1,damage_total=5.,shot_samples=1,rounds_consumed=1,reload_samples=0,last_ammo=2,engagement_initial_hp=hp,damage_goal=hp*.2,lethal_source_hits=int(after==0))
 for e in r['events']:
  if e['kind']==68:e.update(damage_before=hp,damage_after=hp*.2)
  if e['kind'] in [20,24]:e.update(damage_before=before,damage_after=after,damage_reported=5.)
 for i,e in enumerate(r['events']):e['seq']=i+1
 a=q.qualify(r);failed={k:v for k,v in a['checks'].items() if not v}
 assert failed=={'sustained_source_effect':False}
 assert all(a[k] for k in ['effect_verified','damage_goal_reached','retreat_verified','restoration_verified'])
 return dict(synthetic=True,status=a['status'],failed_checks=failed,observed_lethal_hit_count=a['observed_lethal_hit_count'])

if __name__=='__main__':print(json.dumps(dict(nonlethal_goal=run(20.,20.,15.),exact_lethal=run(5.,5.,0.)),indent=2))
