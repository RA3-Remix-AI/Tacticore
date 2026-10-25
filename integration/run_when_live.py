"""Arm a read-only waiter while paused; start one existing CLI after resume.

No DLL, hook, input event, model request, or game write occurs in this waiter.
The selected CLI retains all of its own fresh identity and capability checks.
"""
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'production'))
from observe_production import Memory

def ready(initial_frame,current_frame,pause):
 if current_frame<initial_frame:raise ValueError('Game clock moved backwards')
 return initial_frame>0 and current_frame>initial_frame and pause==0

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--session',type=Path,required=True);parser.add_argument('--script',type=Path,required=True)
 parser.add_argument('--max-wait-seconds',type=int,default=180);parser.add_argument('arguments',nargs=argparse.REMAINDER)
 args=parser.parse_args();session_path=args.session.resolve();script=args.script.resolve()
 if not script.is_relative_to(ROOT.parent) or script.suffix!='.py' or not script.is_file():raise ValueError('Expected an existing bridge CLI')
 if not 1<=args.max_wait_seconds<=300:raise ValueError('Wait bound')
 arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
 raw=session_path.read_bytes();session=json.loads(raw.decode('utf-8-sig'));memory=Memory(session['pid'],session);begin=time.monotonic()
 try:
  logic=memory.u32(0xcd8ce4)
  if memory.u32(logic)!=0xbeb630:raise ValueError('Active simulation missing')
  initial=memory.u32(logic+0x50)
  if initial<=0:raise ValueError('Active match required')
  print(json.dumps(dict(state='armed_readonly_wait',session_id=session['session_id'],pid=session['pid'],initial_frame=initial,script=str(script),commands_dispatched=0)),flush=True)
  while time.monotonic()-begin<args.max_wait_seconds:
   if session_path.read_bytes()!=raw or memory.u32(0xcd8ce4)!=logic or memory.u32(logic)!=0xbeb630:raise ValueError('Session or simulation changed')
   frame=memory.u32(logic+0x50)
   if ready(initial,frame,memory.u32(logic+0x15c)):break
   time.sleep(.05)
  else:raise TimeoutError('No resume before wait bound; no child started')
 finally:memory.close()
 if session_path.read_bytes()!=raw:raise ValueError('Session changed before child')
 print(json.dumps(dict(state='starting_single_child',session_id=session['session_id'],frame=frame)),flush=True)
 result=subprocess.run([sys.executable,str(script),*arguments],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 return result.returncode

if __name__=='__main__':raise SystemExit(main())
