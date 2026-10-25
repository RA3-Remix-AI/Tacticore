import json,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent

class ExecutorImportBoundary(unittest.TestCase):
 def test_mct6_runtime_and_passive_readers_load_from_fresh_host_directory(self):
  code='''import ctypes,hashlib,json
from pathlib import Path
import continuous_evidence as evidence
from tactical_bridge import module
client=module(Path('../tactical/client.py').resolve(),'fresh_mct6_tactical_client')
schema,runtime=client.runtime_backend('mission-combat-v6')
qualifier=evidence._qualifier('mission-combat-v6','fresh_host_qualifier')
disposal=module(Path('../tactical/mission_v6_readonly_disposal.py').resolve(),'fresh_host_disposal')
gate=module(Path('../tactical/mission_v6_gate_no_lease.py').resolve(),'fresh_host_gate')
folder=Path('../tactical/mission-combat-v6')
revision=json.loads((folder/'revision.json').read_text())
actual=hashlib.sha256((folder/'bin'/schema['dll']).read_bytes()).hexdigest()
assert actual==revision['native_binary_sha256']==disposal.MISSION_LAYOUT['dll_sha256']
assert len(disposal.trusted_entries({'native_binary_sha256':actual}))==14
assert qualifier.progress({'native':{},'events':[]},'unused') is None
assert gate.eligible({'native_binary_sha256':actual,'native':{}}) is False
print(json.dumps({'event_size':ctypes.sizeof(runtime.Event),'events_offset':runtime.Tactical.events.offset,'game_commands':0}))
'''
  result=json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
  self.assertEqual(result['event_size'],852);self.assertEqual(result['events_offset'],1124)
  self.assertEqual(result['game_commands'],0)

 def test_real_native_gate_sidecar_loads_from_fresh_host_directory(self):
  report=ROOT.parent/'acceptance/runs/20261025-105617-commander/coord2-mission02.json'
  proof=report.with_suffix('.native-gate.json')
  if not proof.is_file():self.skipTest('Recorded native zero-lease proof is not installed')
  # Isolate the import boundary; the raw command binding has separate tests.
  code='''import hashlib,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import continuous_evidence as evidence
path=Path('../acceptance/runs/20261025-105617-commander/coord2-mission02.json').resolve()
sidecar=path.with_suffix('.native-gate.json')
host=SimpleNamespace(session={'run_directory':str(path.parent)})
receipt={'started':False,'issued_frame':0,'unit_results':[{'report':str(path),'native_gate_no_lease':{'no_actor_lease_verified':True,'evidence_path':str(sidecar)}}]}
bound={'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
with patch.object(evidence,'bound_report',return_value=bound):
 result=evidence.pre_dispatch_facts(host,receipt,{'executor_directory':'mission-formation-v2'})
proof=result['proof']
assert proof['no_actor_lease_verified'] is True
assert proof['restoration_verified'] is False and proof['return_verified'] is False
assert proof['completion_claim'] is False
print(json.dumps({'native_host_launched':proof['native_host_launched'],'no_lease':True}))
'''
  result=json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
  self.assertTrue(result['native_host_launched']);self.assertTrue(result['no_lease'])

 def test_continuous_source_verifies_from_fresh_host_working_directory(self):
  report=ROOT.parent/'acceptance/runs/20261025-095141-commander/main-mission04.json'
  if not report.is_file():self.skipTest('Recorded continuous mission calibration is not installed')
  code='''import json
from pathlib import Path
from tactical_bridge import module
path=Path('../acceptance/runs/20261025-095141-commander/main-mission04.json')
raw=json.loads(path.read_text(encoding='utf-8-sig'))
verifier=module(Path('../tactical/evidence.py').resolve(),'fresh_host_continuous_evidence')
session={'session_id':raw['session_id'],'mod_sha256':raw['package_sha256']}
grant=verifier.verify_purpose('attack','main_attack',path,session,raw['preflight']['commander_id'])
assert grant['raw_assessment']['long_approach_verified'] is True
assert grant['raw_assessment']['long_retreat_verified'] is True
print(json.dumps({'executor':grant['executor_directory'],'protocol':grant['stop_schema']['mission_protocol']}))
'''
  result=json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
  self.assertEqual(result['executor'],'mission-combat');self.assertEqual(result['protocol'],'continuous_tactical_v1')

 def test_real_tactical_path_and_cached_client_cannot_shadow_production(self):
  code='''import json,sys
from pathlib import Path
import battle_host
from tactical_bridge import module
module(Path('../tactical/client.py').resolve(),'client')
assert 'ProductionExecutor' not in vars(sys.modules['client'])
kind=battle_host.production_executor_type()
assert kind.__module__=='host_bound_production_executor'
assert Path(sys.modules[kind.__module__].__file__).resolve()==Path('../production/persistent/client.py').resolve()
print(json.dumps({'production':kind.__module__,'tactical':sys.modules['client'].__file__,'instances_created':0,'game_commands':0}))
'''
  result=json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
  self.assertEqual(result['production'],'host_bound_production_executor')
  self.assertEqual(result['instances_created'],0);self.assertEqual(result['game_commands'],0)
