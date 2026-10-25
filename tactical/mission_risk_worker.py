"""Poll local risk independently of JSON capture and model latency."""
import importlib.util
from pathlib import Path
import threading

class MissionRiskWorker:
 def __init__(self, report, session, output, factory=None):
  self.paths=(report,session,output);self.factory=factory
  self.stop=threading.Event();self.lock=threading.Lock();self.thread=None
  self.latest={};self.request=None
 def start(self):
  if self.thread is not None:raise ValueError('risk_worker_already_started')
  self.thread=threading.Thread(target=self._run,name='mission-local-risk',daemon=True)
  self.thread.start();return self
 def _run(self):
  monitor=None
  try:
   factory=self.factory
   if factory is None:
    path=Path(__file__).with_name('local_mission_risk_v1.py')
    spec=importlib.util.spec_from_file_location('bound_mission_local_risk_worker',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    factory=module.MissionRiskMonitor
   monitor=factory(*self.paths)
   while not self.stop.is_set():
    result=monitor.poll()
    with self.lock:
     self.latest=dict(result)
     if result.get('request_written') is True and self.request is None:self.request=dict(result)
    if result.get('state') in ('candidate_disabled','stopped','closed'):break
    if self.stop.wait(.05):break
  except Exception as error:
   with self.lock:self.latest=dict(state='monitor_error',error_type=type(error).__name__,request_written=False)
  finally:
   if monitor is not None:
    try:monitor.close()
    except Exception as error:
     with self.lock:self.latest['close_error_type']=type(error).__name__
 def status(self):
  with self.lock:return dict(latest=dict(self.latest),request=dict(self.request) if self.request else None)
 def close(self):
  self.stop.set()
  if self.thread is not None:self.thread.join(timeout=2)
  return self.status()
