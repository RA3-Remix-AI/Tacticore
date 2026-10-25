"""Sole-runner read-only scene capture. Private raw targets never enter model input."""
import argparse,json,sys,time
from pathlib import Path
BRIDGE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BRIDGE/'integration'))
from live_state import LiveBattleState,RetryableSample,atomic_json

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 session=json.loads(a.session.read_text(encoding='utf-8-sig'));state=LiveBattleState(a.session,session['scenario']['commander_id'],output=a.output,visibility=True)
 for attempt in range(5):
  try:snapshot=state.collect();break
  except RetryableSample:
   if attempt==4:raise
   time.sleep(.05)
 raw=dict(session_id=session['session_id'],pid=session['pid'],frame=round(snapshot['game_time_seconds']*15),model_eligible=False,private_targets=state.private_targets,private_formations=state.private_formations,private_regions=state.private_regions)
 atomic_json(a.output/'private-scene.json',raw)
 print(json.dumps(dict(output=str(a.output),frame=raw['frame'],paused=snapshot['paused'],own_roles=snapshot['production']['own_roles'],credits=snapshot['resources']['credits'],contacts=len(raw['private_targets'])),ensure_ascii=False))
if __name__=='__main__':main()
