"""No process/game calls: bound one-child calibration driver regressions."""
import importlib.util,json,subprocess,sys,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('field',Path(__file__).with_name('field_coordinate.py'));f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
class Driver(unittest.TestCase):
 def test_preflight_rejection_still_has_bound_ids_and_no_retry(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder);output=d/'raw.json';calls=[]
   def run(cmd,**kwargs):
    calls.append(cmd)
    if 'field_plan.py' in cmd[1]:
     p=Path(cmd[cmd.index('--output')+1]);p.write_text('{}',encoding='utf-8');p.with_name(p.stem+'-selection.json').write_text(json.dumps(dict(paused=0,front_id=11,support_id=12,contact_id='contact_x',frame=100)),encoding='utf-8');return subprocess.CompletedProcess(cmd,0,stdout='',stderr='')
    self.assertEqual(Path(cmd[1]).name,'lease_admission_v2.py');uuid.UUID(cmd[cmd.index('--command-id')+1]);uuid.UUID(cmd[cmd.index('--task-id')+1]);self.assertGreater(int(cmd[cmd.index('--seq')+1]),0);return subprocess.CompletedProcess(cmd,64,stdout='',stderr='')
   args=['field','--session',str(d/'session'),'--natural',str(d/'natural'),'--routes',str(d/'routes'),'--output',str(output),'--execute']
   with patch.object(sys,'argv',args),patch.object(f.subprocess,'run',run):
    with self.assertRaises(SystemExit) as e:f.main()
   self.assertEqual(e.exception.code,64);self.assertEqual(len(calls),2)
   r=json.loads((d/'raw-invocation.json').read_text(encoding='utf-8'));self.assertEqual(r['native_attempts'],1);self.assertEqual(r['command_id'],calls[1][calls[1].index('--command-id')+1]);self.assertTrue((d/'raw-child.log').exists())
 def test_no_plan_starts_no_native_child(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder);calls=[]
   def run(cmd,**kwargs):calls.append(cmd);return subprocess.CompletedProcess(cmd,0,stdout='',stderr='')
   with patch.object(sys,'argv',['field','--session',str(d/'session'),'--natural',str(d/'natural'),'--routes',str(d/'routes'),'--output',str(d/'raw'),'--execute']),patch.object(f.subprocess,'run',run):
    with self.assertRaisesRegex(ValueError,'no_readonly_route_ready_no_native_child'):f.main()
   self.assertEqual(len(calls),1);self.assertIn('field_plan.py',calls[0][1])
if __name__=='__main__':unittest.main()
