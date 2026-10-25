"""Private path sampling boundaries; no process or game operations."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

import battle_host
from record_own_routes import cell,unseen_candidates


class PrivateRouteInputs(unittest.TestCase):
 def test_enemy_coordinates_are_not_inspected_or_exported(self):
  class Enemy(dict):
   def get(self,key,*args):
    if key=='xyz':raise AssertionError('Enemy position must not be read')
    return super().get(key,*args)
  enemy=Enemy(type_hash='0x19ab11af',owner_index_candidate=4)
  own=dict(type_hash='0x19ab11af',owner_index_candidate=3,xyz=[90.,120.,260.])
  self.assertEqual(unseen_candidates(dict(candidates=[enemy,own]),set()),[own])

 def test_record_once_per_known_cell_preserves_real_height(self):
  first=dict(type_hash='0x2c358c61',owner_index_candidate=3,xyz=[90.,120.,260.])
  upper=dict(first,xyz=[90.,120.,320.]);seen={cell(first['xyz'])}
  self.assertEqual(unseen_candidates(dict(candidates=[first,upper]),seen),[upper])
  self.assertEqual(upper['xyz'],[90.,120.,320.])

 def test_invalid_or_unreviewed_positions_cannot_create_route_nodes(self):
  rows=[dict(type_hash='unknown',owner_index_candidate=3,xyz=[1,2,3]),dict(type_hash='0x33026fa1',owner_index_candidate=3,xyz=[float('nan'),2,3]),dict(type_hash='0x19ab11af',owner_index_candidate=3,xyz=[True,2,3])]
  self.assertFalse(unseen_candidates(dict(candidates=rows),set()))


class OwnedRouteLifecycle(unittest.IsolatedAsyncioTestCase):
 async def test_stop_is_session_scoped_to_owned_readonly_child(self):
  with tempfile.TemporaryDirectory() as folder:
   host=battle_host.Host.__new__(battle_host.Host);host.output=Path(folder);host.binding=SimpleNamespace(session_id='this-match')
   host.route_process=Mock();host.route_process.poll.return_value=None;host.route_process.wait.return_value=0;host.route_log=Mock()
   await host.stop_route_recorder()
   self.assertEqual(json.loads((host.output/'route-recorder-stop.json').read_text()),dict(session_id='this-match'))
   host.route_process.terminate.assert_not_called();host.route_log.close.assert_called_once()

 async def test_completed_child_does_not_write_stop_to_new_session(self):
  with tempfile.TemporaryDirectory() as folder:
   host=battle_host.Host.__new__(battle_host.Host);host.output=Path(folder);host.binding=SimpleNamespace(session_id='next-match')
   host.route_process=Mock();host.route_process.poll.return_value=0;host.route_log=Mock()
   await host.stop_route_recorder()
   self.assertFalse((host.output/'route-recorder-stop.json').exists());host.route_process.terminate.assert_not_called()


if __name__=='__main__':unittest.main()
