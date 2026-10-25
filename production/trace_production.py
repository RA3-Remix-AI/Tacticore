"""Parent-executed passive trace, optional one-shot enqueue, durable queue samples."""
import argparse,concurrent.futures,ctypes as c,json,queue,subprocess,threading,time,uuid
from pathlib import Path
from observe_production import ROOT,Memory,k,w,read_owner,read_factory,EXPECTED
from session_package import verify_session_package
from run_flak import durable_write,execute as execute_one
from natural_evidence import compatible_natural_calls

def stop_trace(pid):
 k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE
 k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
 k.UnmapViewOfFile.argtypes=[c.c_void_p]
 handle=k.OpenFileMappingW(6,False,'Local\\RA3ProductionTrace_'+str(pid))
 if not handle:return False
 view=k.MapViewOfFile(handle,6,0,0,48)
 if view:c.c_long.from_address(view+44).value=2;k.UnmapViewOfFile(view)
 k.CloseHandle(handle);return bool(view)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--factory',required=True);ap.add_argument('--natural-observation',type=Path,required=True);ap.add_argument('--seconds',type=int,default=45);ap.add_argument('--enqueue-once',action='store_true');ap.add_argument('--queue-limit',type=int,default=0);args=ap.parse_args()
 name='production-trace-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
 local_report=ROOT/(name+'.json');report=dict(status='preflight',passive_observer=True,enqueue_requested=args.enqueue_once,active_enqueue_attempted=False,production_primitive_verified=False,runtime_direction_switch_verified=False)
 run_report=None;mem=None;host=None;stream=None;errors=None;future=None;pool=None
 def persist():
  durable_write(local_report,report)
  if run_report:durable_write(run_report,report)
 persist()
 try:
  if not 10<=args.seconds<=300:raise RuntimeError('Trace duration must be 10..300 seconds')
  raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));run=Path(session['run_directory'])
  if not session.get('session_id') or not run.is_dir():raise RuntimeError('Require recorded session and existing run directory')
  run_report=run/(name+'.json');report.update(session_id=session['session_id'],pid=session['pid'],mod_big=str(verify_session_package(session)),mod_sha256=session['mod_sha256']);persist()
  if args.enqueue_once and session['session_id'] in json.loads((ROOT/'unknown_sessions.json').read_text()):raise RuntimeError('Unknown previous execution; retry prohibited')
  snap=json.loads(args.snapshot.read_text(encoding='utf-8-sig'));obs=json.loads(args.natural_observation.read_text(encoding='utf-8-sig'))
  if snap['pid']!=session['pid'] or snap['sha256']!=EXPECTED or obs['pid']!=session['pid']:raise RuntimeError('Snapshot/natural sample session mismatch')
  compatible_natural_calls(obs,session['pid'])
  matches=[x for x in snap['candidates'] if int(x['address'],0)==int(args.factory,0) and int(x['type_hash'],0)==0x80d4ea1e and x['owner_index_candidate']==3]
  if len(matches)!=1:raise RuntimeError('Require one Soviet AI barracks')
  candidate=matches[0];owner=int(candidate['owner_address'],0);mem=Memory(session['pid'],session);player=read_owner(mem,owner,3);factory=read_factory(mem,candidate,owner)
  if not factory.get('production_interface_available'):raise RuntimeError('Production interface unavailable')
  times=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(mem.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())
  command=[str(ROOT/'bin/observe_trace.exe'),str(session['pid']),args.factory,hex(owner),player['ai_player'],factory['interface'],str(times[0].dwLowDateTime),str(times[0].dwHighDateTime),str(obs['window_thread']),str(args.seconds)]
  report.update(status='trace_dispatch_pending',preflight=dict(player=player,factory=factory),command=command,stream=str(run/(name+'.jsonl')),stderr=str(run/(name+'.stderr.txt')));persist()
  if args.session.read_bytes()!=raw:raise RuntimeError('Session changed before trace dispatch')
  stream=(run/(name+'.jsonl')).open('a',encoding='utf-8');errors=(run/(name+'.stderr.txt')).open('w',encoding='utf-8')
  host=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=errors,text=True,bufsize=1);lines=queue.Queue()
  def reader():
   for line in host.stdout:lines.put(line)
   lines.put(None)
  threading.Thread(target=reader,daemon=True).start();started=time.monotonic();sample_at=started;count=0;session_valid=True
  def save_record(record):
   stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush();os_fsync(stream)
  def action():
   action_report=dict(status='preflight',session_id=session['session_id'],pid=session['pid'],active_enqueue_attempted=False,spend_verified=False,produced_unit_verified=False)
   action_path=run/(name+'-enqueue.json')
   def action_save():durable_write(action_path,action_report)
   action_save()
   try:execute_one(args,action_report,action_save)
   except Exception as error:action_report.update(status='preflight_rejected' if action_report['status']=='preflight' else 'wrapper_failed',error=repr(error))
   finally:action_save()
   return action_report
  while time.monotonic()-started<args.seconds+25:
   try:line=lines.get(timeout=.1)
   except queue.Empty:line=''
   if line is None:break
   if line:
    try:record=json.loads(line)
    except ValueError:record=dict(record='invalid_native_output',raw=line)
    save_record(record);count+=1
    if record.get('record')=='installed':
     report['installed']=record;report['status']='tracing';persist()
     if args.enqueue_once and record.get('state')==1 and record.get('callback_thread')==obs['window_thread']:
      report['enqueue_report']=str(run/(name+'-enqueue.json'));report['active_enqueue_attempted']='unknown';persist()
      pool=concurrent.futures.ThreadPoolExecutor(max_workers=1);future=pool.submit(action)
    if record.get('record')=='stopped':report['stopped']=record
   if time.monotonic()>=sample_at and session_valid:
    try:
     if args.session.read_bytes()!=raw:raise RuntimeError('Active session changed')
     player=read_owner(mem,owner,3)
     if player['ai_player']!=report['preflight']['player']['ai_player']:raise RuntimeError('AIPlayer identity changed')
     save_record(dict(record='readonly_snapshot',wall_seconds=round(time.monotonic()-started,3),game_frame=mem.u32(mem.u32(0xcd8ce4)+0x50),player=player,factory=read_factory(mem,candidate,owner)))
    except Exception as error:
     session_valid=False;report['session_error']=repr(error);stop_trace(session['pid']);persist()
    sample_at=time.monotonic()+.25
   if future and future.done() and 'enqueue_result' not in report:report['enqueue_result']=future.result();report['active_enqueue_attempted']=report['enqueue_result']['active_enqueue_attempted'];persist()
  if host.poll() is None:
   stop_trace(session['pid']);report['timeout']=True
   try:host.wait(timeout=7)
   except subprocess.TimeoutExpired:report['host_still_running']=True
  report.update(status='trace_finished' if session_valid else 'trace_session_invalid',native_exit_code=host.poll(),records=count,session_unchanged_after=args.session.read_bytes()==raw)
  if future:
   try:report['enqueue_result']=future.result(timeout=25);report['active_enqueue_attempted']=report['enqueue_result']['active_enqueue_attempted']
   except Exception as error:report['enqueue_error']=repr(error)
 except Exception as error:report.update(status='preflight_rejected' if report['status']=='preflight' else 'trace_failed',error=repr(error))
 finally:
  if host and host.poll() is None and report.get('pid'):stop_trace(report['pid'])
  if mem:mem.close()
  if stream:stream.close()
  if errors:errors.close()
  if pool:pool.shutdown(wait=False)
  persist()
 print(json.dumps(dict(report=str(local_report),run_report=str(run_report) if run_report else None,status=report['status']),ensure_ascii=False))
 return 0 if report.get('native_exit_code')==0 and report.get('session_unchanged_after') else 1

def os_fsync(stream):
 import os
 os.fsync(stream.fileno())

if __name__=='__main__':raise SystemExit(main())
