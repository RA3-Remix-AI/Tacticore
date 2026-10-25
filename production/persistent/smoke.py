"""Explicit parent-run attach/optional single order smoke; never starts the game."""
import argparse,json,time,uuid
from client import ProductionExecutor
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',required=True);ap.add_argument('--snapshot',required=True);ap.add_argument('--factory',required=True);ap.add_argument('--commander-id',required=True);ap.add_argument('--natural-observation',required=True);ap.add_argument('--unit',choices=['conscript','flak','bear']);ap.add_argument('--seconds',type=int,default=20);ap.add_argument('--dedup-check',action='store_true');a=ap.parse_args()
 executor=ProductionExecutor(a.session,a.snapshot,a.factory,a.commander_id,a.natural_observation)
 try:
  print(json.dumps(dict(event='ready',status=executor.start()),ensure_ascii=False),flush=True)
  if a.unit:
   frame=executor.memory.u32(executor.memory.u32(0xcd8ce4)+0x50);command=dict(session_id=executor.session['session_id'],player_id=3,commander_id=a.commander_id,command_id=uuid.uuid4().hex,task_id=uuid.uuid4().hex,seq=1,unit=a.unit,budget=1000,reserve=500,expires_frame=frame+450)
   print(json.dumps(dict(event='submit',result=executor.submit(command)),ensure_ascii=False),flush=True)
   if a.dedup_check:
    print(json.dumps(dict(event='same_command',result=executor.submit(command)),ensure_ascii=False),flush=True)
    altered=dict(command,command_id=uuid.uuid4().hex,seq=2);print(json.dumps(dict(event='same_task',result=executor.submit(altered)),ensure_ascii=False),flush=True)
  for _ in range(max(0,min(a.seconds,300))):time.sleep(1);print(json.dumps(dict(event='status',status=executor.status()),ensure_ascii=False),flush=True)
 finally:print(json.dumps(dict(event='stop',status=executor.stop()),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
