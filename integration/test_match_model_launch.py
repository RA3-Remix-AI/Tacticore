import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run_native_opponent_match as runner

class MatchModelLaunch(unittest.TestCase):
 def test_explicit_library_and_backend_reach_host_without_secret_arguments(self):
  library=Path('profiles with spaces/连接库.json')
  command=runner.host_command(Path('session.json'),Path('sources.json'),library,'pydantic')
  self.assertEqual(command[command.index('--library')+1],str(library.resolve()))
  self.assertEqual(command[command.index('--model-backend')+1],'pydantic')
  self.assertNotIn('--api-key',command)

 def test_preflight_reads_only_selected_library_and_exports_redacted_readiness(self):
  library=Path('selected.json');profile=SimpleNamespace(connection_id='connection',provider='DeepSeek',key='DO_NOT_EXPORT_THIS_KEY')
  with patch.object(runner,'check_backend_available') as check,patch.object(runner,'load_profile',return_value=profile) as load:
   value=runner.model_connection(library,'pydantic')
  check.assert_called_once_with('pydantic');load.assert_called_once_with(library,runner.COMMANDER)
  self.assertTrue(value['credential_available']);self.assertNotIn(profile.key,json.dumps(value))

 def test_missing_backend_does_not_load_credentials_or_fall_back(self):
  with patch.object(runner,'check_backend_available',side_effect=RuntimeError('missing')),patch.object(runner,'load_profile') as load:
   with self.assertRaises(RuntimeError):runner.model_connection(Path('selected.json'),'pydantic')
  load.assert_not_called()
