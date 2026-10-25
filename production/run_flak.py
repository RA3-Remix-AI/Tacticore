"""Guarded one-shot native production experiment. Orchestrator must execute explicitly."""
import argparse,ctypes as c,hashlib,json,os,subprocess,time,uuid
from pathlib import Path
from observe_production import ROOT,Memory,k,w,read_owner,read_factory
from session_package import verify_session_package
from natural_evidence import compatible_natural_calls

def durable_write(path,report):
 # Keep each attempt's complete bytes separate from both the previous report
 # and other writers. Windows readers may briefly deny delete sharing.
 path=Path(path);temporary=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
 with temporary.open('x',encoding='utf-8') as stream:
  json.dump(report,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
 for attempt in range(25):
  try:temporary.replace(path);return
  except PermissionError:
   if attempt==24:raise
   time.sleep(.02)

def output_text(value):
 return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value

def validate_append_queue(factory,limit):
 if not 0<=limit<=2:raise RuntimeError('queue-limit must be 0..2')
 queue=factory.get('queue_candidate',{});nodes=queue.get('nodes')
 if not factory.get('production_interface_available') or not isinstance(nodes,list):raise RuntimeError('Require validated production queue')
 if len(nodes)>limit:raise RuntimeError('Validated queue exceeds explicit queue-limit')
 if int(queue.get('module','0'),0)!=int(factory['interface'],0)-0x24:raise RuntimeError('Queue module mismatch')
 if int(queue.get('head','0'),0)!=(int(nodes[0]['address'],0) if nodes else 0) or int(queue.get('tail','0'),0)!=(int(nodes[-1]['address'],0) if nodes else 0):raise RuntimeError('Queue endpoint mismatch')
 ids=set();addresses=set()
 for node in nodes:
  address=int(node['address'],0);ident=node['production_id_raw'];cost=node['native_cost_plus_30'];paid=node['paid_accumulator_plus_68']
  if node['kind_raw']!=1 or int(node['template_hash'],0) not in (0x19ab11af,0x2c358c61,0x33026fa1,0xa08aabd3) or ident<=0 or ident in ids or address in addresses or not 0<=paid<=cost or cost<=0:raise RuntimeError('Existing queue identity/kind/template/payment mismatch')
  ids.add(ident);addresses.add(address)
 return nodes

def execute(args,report,persist):
 raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));snap=json.loads(args.snapshot.read_text(encoding='utf-8-sig'));obs=json.loads(args.natural_observation.read_text(encoding='utf-8-sig'))
 if report.get('session_id')!=session.get('session_id') or report.get('pid')!=session.get('pid'):raise RuntimeError('Session changed while opening evidence report')
 unknown=ROOT/'unknown_sessions.json'
 if unknown.exists() and session['session_id'] in json.loads(unknown.read_text(encoding='utf-8')):raise RuntimeError('Prior unknown execution in this session; retry prohibited')
 if not session.get('session_id') or session['pid']!=snap['pid'] or obs['pid']!=session['pid']:raise RuntimeError('Session identity mismatch')
 report['mod_big']=str(verify_session_package(session))
 compatible_natural_calls(obs,session['pid'])
 factory=int(args.factory,0);matches=[x for x in snap['candidates'] if int(x['address'],0)==factory and int(x['type_hash'],0)==0x80d4ea1e and x['owner_index_candidate']==3]
 if len(matches)!=1:raise RuntimeError('Require one current Soviet AI barracks candidate')
 candidate=matches[0];owner=int(candidate['owner_address'],0);mem=Memory(session['pid'],session)
 try:
  player=read_owner(mem,owner,3);data=read_factory(mem,candidate,owner)
  report['preflight']=dict(player=player,factory=data)
  limit=getattr(args,'queue_limit',0);validate_append_queue(data,limit)
  if not player['resource_available'] or player['display_sum']<220:raise RuntimeError('Insufficient funds')
  times=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(mem.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())
  if args.session.read_bytes()!=raw:raise RuntimeError('Session changed before dispatch')
  command=[str(ROOT/'bin/run_flak.exe'),str(session['pid']),hex(factory),hex(owner),player['ai_player'],data['interface'],str(times[0].dwLowDateTime),str(times[0].dwHighDateTime),str(obs['window_thread']),str(limit)]
  report.update(session_id=session['session_id'],pid=session['pid'],mod_sha256=session['mod_sha256'],preflight=dict(player=player,factory=data),status='dispatch_pending',command=command,active_enqueue_attempted='unknown',note='Interrupted dispatch is not success. Do not retry this session.');persist()
  try:
   result=subprocess.run(command,capture_output=True,text=True,timeout=20)
  except subprocess.TimeoutExpired as error:
   report.update(status='native_timeout',native_stdout=output_text(error.stdout),native_stderr=output_text(error.stderr),error=str(error))
  except OSError as error:
   report.update(status='native_launch_failed',active_enqueue_attempted=False,error=str(error))
  else:
   report.update(status='native_process_finished',native_exit_code=result.returncode,native_stdout=result.stdout,native_stderr=result.stderr)
   try:
    report['native_result']=json.loads(result.stdout);report['active_enqueue_attempted']=report['native_result'].get('active_enqueue_attempted','unknown')
   except ValueError:report.update(status='native_result_unavailable',note='Native process ended without a valid result; outcome unknown. Do not retry this session.')
  report['session_unchanged_after']=args.session.read_bytes()==raw
 finally:mem.close()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--factory',required=True);ap.add_argument('--natural-observation',type=Path,required=True);ap.add_argument('--queue-limit',type=int,default=0);args=ap.parse_args()
 name='flak-enqueue-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json';local_target=ROOT/name;run_target=None
 report=dict(status='preflight',active_enqueue_attempted=False,spend_verified=False,produced_unit_verified=False,runtime_direction_switch_verified=False,session_path=str(args.session.resolve()))
 def persist():
  durable_write(local_target,report)
  if run_target is not None:durable_write(run_target,report)
 persist()
 try:
  session=json.loads(args.session.read_text(encoding='utf-8-sig'));run_directory=Path(session['run_directory'])
  if not run_directory.is_dir():raise RuntimeError('Recorded run directory unavailable')
  run_target=run_directory/name;report.update(session_id=session.get('session_id'),pid=session.get('pid'),run_report=str(run_target));persist()
  execute(args,report,persist)
 except Exception as error:report.update(status='preflight_rejected' if report['status']=='preflight' else 'wrapper_failed',error=repr(error))
 finally:persist()
 print(json.dumps(dict(report=str(local_target),run_report=str(run_target) if run_target else None,status=report['status'],native_exit_code=report.get('native_exit_code'),native_result=report.get('native_result')),ensure_ascii=False))
 return 0 if report.get('native_exit_code')==0 and report.get('native_result',{}).get('state')==2 else 1
if __name__=='__main__':raise SystemExit(main())
