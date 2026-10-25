import ctypes as c,json,subprocess,unittest,uuid
from client import Command,Receipt,Persistent,ProductionExecutor,NATIVE_BIN,uuid_words,uuid_string,validate_command,require_unpaused
SESSION=str(uuid.uuid4());COMMANDER=str(uuid.uuid4())
def command():return dict(session_id=SESSION,player_id=3,commander_id=COMMANDER,command_id=uuid.uuid4().hex,task_id=uuid.uuid4().hex,seq=1,unit='flak',budget=300,reserve=500,expires_frame=200)
class ContractTests(unittest.TestCase):
 def test_hex_uuids_roundtrip(self):
  raw=uuid.uuid4().hex;self.assertEqual(uuid.UUID(uuid_string(uuid_words(raw))).hex,raw)
 def test_valid_three_templates(self):
  for unit in ['conscript','flak','bear']:
   raw=command();raw['unit']=unit;self.assertEqual(validate_command(raw,SESSION,COMMANDER,100,500)['unit'],unit)
 def test_wrong_session(self):
  raw=command();raw['session_id']=str(uuid.uuid4());self.assertRaisesRegex(ValueError,'binding',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_wrong_commander(self):
  raw=command();raw['commander_id']=str(uuid.uuid4());self.assertRaisesRegex(ValueError,'binding',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_wrong_player(self):
  raw=command();raw['player_id']=2;self.assertRaisesRegex(ValueError,'binding',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_bool_is_not_budget(self):
  raw=command();raw['budget']=True;self.assertRaisesRegex(ValueError,'budget',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_low_reserve(self):
  raw=command();raw['reserve']=499;self.assertRaisesRegex(ValueError,'reserve',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_expired_task(self):
  raw=command();raw['expires_frame']=99;self.assertRaisesRegex(ValueError,'expiry',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_excessive_future_expiry(self):
  raw=command();raw['expires_frame']=1001;self.assertRaisesRegex(ValueError,'expiry',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_unlisted_unit(self):
  raw=command();raw['unit']='SovietApocalypse';self.assertRaisesRegex(ValueError,'not_allowed',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_addresses_forbidden(self):
  raw=command();raw['factory_address']='0x1234';self.assertRaisesRegex(ValueError,'fields',validate_command,raw,SESSION,COMMANDER,100,500)
 def test_native_layout_matches_python(self):
  layout=json.loads(subprocess.check_output([str(NATIVE_BIN/'persistent_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(command=c.sizeof(Command),receipt=c.sizeof(Receipt),persistent=c.sizeof(Persistent),request=Persistent.request.offset,ledger=Persistent.ledger.offset))
 def test_running_pause_flag_zero_is_allowed(self):
  memory=type('Memory',(),{'u32':lambda self,p:0x10000 if p==0xcd8ce4 else 0})();require_unpaused(memory)
 def test_paused_native_flag_rejects_before_dispatch(self):
  memory=type('Memory',(),{'u32':lambda self,p:0x10000 if p==0xcd8ce4 else 3})();self.assertRaisesRegex(ValueError,'game_paused',require_unpaused,memory)
class FeedbackTests(unittest.TestCase):
 def setUp(self):
  self.client=ProductionExecutor.__new__(ProductionExecutor);self.client.owner=123;self.client.originals={};self.r=Receipt();self.r.command.id[:]=uuid_words(str(uuid.uuid4()));self.r.command.task[:]=uuid_words(str(uuid.uuid4()));self.r.command.hash=0x2c358c61;self.r.state=2;self.r.cost=220;self.r.queue_id=7
 def test_enqueue_ack_only_starts(self):self.assertTrue(self.client._receipt_view(self.r)['started']);self.assertFalse(self.client._receipt_view(self.r)['completed'])
 def test_node_disappearance_cannot_complete(self):self.r.node=0;self.assertFalse(self.client._receipt_view(self.r)['completed'])
 def complete(self):
  self.r.paid=220;self.r.debit_count=90;self.r.created=1;self.r.completed=1;self.r.live_samples=1;self.r.object_id=77;self.r.object_owner=123;self.r.object_hash=self.r.command.hash
 def test_all_native_evidence_completes(self):self.complete();self.assertTrue(self.client._receipt_view(self.r)['completed'])
 def test_first_scan_cannot_replace_create(self):self.complete();self.r.created=0;self.assertFalse(self.client._receipt_view(self.r)['completed'])
 def test_wrong_owner_cannot_complete(self):self.complete();self.r.object_owner=124;self.assertFalse(self.client._receipt_view(self.r)['completed'])
 def test_missing_payment_chain_cannot_complete(self):self.complete();self.r.payment_error=1;self.assertFalse(self.client._receipt_view(self.r)['completed'])
 def test_original_hex_task_id_preserved(self):
  task=uuid.uuid4().hex;key=uuid_string(self.r.command.id);self.client.originals[key]=dict(command_id=uuid.UUID(key).hex,task_id=task);self.assertEqual(self.client._receipt_view(self.r)['task_id'],task)
 def test_model_feedback_has_no_addresses(self):self.complete();result=self.client._receipt_view(self.r);self.assertFalse(any(key in result for key in ['node','object','factory','owner','iface','address']))
if __name__=='__main__':unittest.main()
