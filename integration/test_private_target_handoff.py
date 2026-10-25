import tempfile,types,unittest
from pathlib import Path
from tactical_bridge import TacticalBridge

class PrivateTargetHandoff(unittest.IsolatedAsyncioTestCase):
 async def test_only_current_enemy_positions_reach_local_executor(self):
  with tempfile.TemporaryDirectory() as directory:
   captured=[]
   contacts=[dict(contact_id='visible',currently_visible=True,relation='enemy'),dict(contact_id='last_seen',currently_visible=False,relation='enemy'),dict(contact_id='ally',currently_visible=True,relation='ally')]
   targets={ident:dict(xyz=[index,2,3],observed_frame=1500,address=0xdeadbeef,object_id=100+index,hp=50) for index,ident in enumerate(('visible','last_seen','ally','not_in_snapshot'))}
   collector=types.SimpleNamespace(private_formations={},private_regions={},visibility_proof_path=None,private_targets=targets)
   host=types.SimpleNamespace(output=Path(directory),phase='running',last_snapshot=dict(paused=False,battlefield=dict(contacts=contacts)),collector=collector,agent=types.SimpleNamespace(jobs=lambda:{'jobs':[]}))
   bridge=TacticalBridge(host,dict(supported_purposes=[],grants=[]));bridge.executor=types.SimpleNamespace(update_context=lambda *args:captured.append(args))
   await bridge.dispatch()
   self.assertEqual(captured[0][4],{'visible':dict(xyz=[0,2,3],observed_frame=1500)})
   self.assertNotIn('xyz',str(host.last_snapshot))
