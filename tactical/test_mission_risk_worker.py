import threading
import unittest
from mission_risk_worker import MissionRiskWorker

class RiskWorker(unittest.TestCase):
 def test_constructor_never_constructs_or_attaches_monitor(self):
  calls=[]
  worker=MissionRiskWorker('raw','session','sidecar',lambda *a:calls.append(a))
  self.assertEqual(calls,[]);self.assertIsNone(worker.thread)
 def test_first_real_request_survives_later_deduplicated_polls_and_close(self):
  done=threading.Event();closed=threading.Event()
  class Monitor:
   def __init__(self,*args):self.calls=0
   def poll(self):
    self.calls+=1
    if self.calls==1:return dict(state='retreat_requested',request_written=True,observed_frame=10,request_frame=11)
    done.set();return dict(state='observing',request_written=False)
   def close(self):closed.set()
  worker=MissionRiskWorker('raw','session','sidecar',Monitor).start()
  try:self.assertTrue(done.wait(1))
  finally:status=worker.close()
  self.assertTrue(closed.is_set());self.assertEqual(status['request']['observed_frame'],10)
  self.assertFalse(status['latest']['request_written']);self.assertFalse(worker.thread.is_alive())
 def test_disabled_candidate_stops_without_repeated_poll_or_attach(self):
  done=threading.Event();calls=[]
  class Monitor:
   def __init__(self,*args):pass
   def poll(self):calls.append(1);return dict(state='candidate_disabled',request_written=False)
   def close(self):done.set()
  worker=MissionRiskWorker('raw','session','sidecar',Monitor).start()
  try:self.assertTrue(done.wait(1))
  finally:worker.close()
  self.assertEqual(len(calls),1)
 def test_monitor_failure_closes_channel_without_exposing_exception_text(self):
  done=threading.Event()
  class Monitor:
   def __init__(self,*args):pass
   def poll(self):raise ValueError('private transport detail')
   def close(self):done.set()
  worker=MissionRiskWorker('raw','session','sidecar',Monitor).start()
  try:self.assertTrue(done.wait(1))
  finally:status=worker.close()
  self.assertEqual(status['latest'],dict(state='monitor_error',error_type='ValueError',request_written=False))
  self.assertIsNone(status['request'])

if __name__=='__main__':unittest.main()
