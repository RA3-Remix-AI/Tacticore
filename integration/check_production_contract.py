"""Exercise real production start prerequisites, stopping before kernel mapping.

This creates no native mapping, hook, controller, or SDK command and makes no
model request. Read-only live sampling and derived logs go to a new directory.
"""
import argparse,json,sys
from pathlib import Path
from unittest.mock import patch
from live_state import LiveBattleState,atomic_json
from battle_host import production_executor_type

class MappingBoundary(Exception):pass

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--commander',required=True)
 args=parser.parse_args();args.output=args.output.resolve()
 if args.output.exists():raise ValueError('Use a new diagnostic output directory')
 args.output.mkdir(parents=True);original=json.loads(args.session.read_text(encoding='utf-8-sig'));session=dict(original,run_directory=str(args.output));local=args.output/'session.json';atomic_json(local,session)
 collector=LiveBattleState(local,args.commander,3,output=args.output)
 collector.collect();own=json.loads((args.output/'own-state.json').read_text(encoding='utf-8'))
 factories=[x for x in own['factories'] if x.get('template')=='SovietBarracks' and x.get('production_interface_available')]
 if not factories:raise ValueError('No live Soviet barracks')
 kind=production_executor_type();runtime=sys.modules[kind.__module__]
 executor=kind(local,collector.latest_snapshot_path,min(factories,key=lambda x:int(x['address'],0))['address'],args.commander,Path(original['run_directory'])/'natural-production.json')
 reached=False
 try:
  with patch.object(runtime.k,'CreateFileMappingW',side_effect=MappingBoundary):
   try:executor.start()
   except MappingBoundary:reached=True
 finally:
  if executor.memory is not None:executor.memory.close()
 result=dict(pid=original['pid'],session_id=original['session_id'],reached_create_mapping_boundary=reached,native_mapping_created=False,native_controller_started=False,model_requests=0,game_commands=0,production_module=kind.__module__)
 atomic_json(args.output/'result.json',result);print(json.dumps(result))
 if not reached:raise RuntimeError('Expected mapping boundary was not reached')

if __name__=='__main__':main()
