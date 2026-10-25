"""A completed primitive trial cannot authorize this round's effect acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuous_contract import PROTOCOL
import run_native_opponent_match as runner


class ContinuousMatchPreflight(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.run=root/'run';self.run.mkdir();self.session=root/'active.json'
        self.scenario=dict(trial_kind='model_vs_native_full_match',acceptance_fresh=True,observer_player_index=2,computer_player_index=3,opponent_player_index=4,participant_count=2,observer_local_player=True,model_requests_enabled=True,commander_id=runner.COMMANDER,opponent='native_soviet_oleg',map_id='map_mp_2_feasel6',continuous_missions_required=True,starting_credits=10000,model_side_native_difficulty='medium',opponent_difficulty='medium',lobby_verified=True,calibration_commands_dispatched=0)
        self.write()
        self.grant=dict(supported_purposes=tuple((name,(purpose,)) for name,purpose in sorted(runner.REQUIRED)),grants=[dict(module=name,purpose=purpose,stop_schema=dict(mission_protocol=PROTOCOL,mission_duration_frames=4500)) for name,purpose in sorted(runner.REQUIRED)])

    def write(self):self.session.write_text(json.dumps(dict(session_id='test',run_directory=str(self.run),phase='llm_full_match',scenario=self.scenario)),encoding='utf-8')

    def check(self):
        with patch.object(runner,'verify_manifest',return_value=self.grant):return runner.preflight(self.session,Path('unused'),require_missions=True)

    def test_new_protocol_is_required_for_each_purpose(self):
        self.assertEqual(self.check()[0]['scenario']['opponent_player_index'],4)
        for item in self.grant['grants']:item['stop_schema']={}
        with self.assertRaises(ValueError):self.check()

    def test_one_old_primitive_among_new_missions_is_insufficient(self):
        self.grant['grants'][1]['stop_schema']={}
        with self.assertRaises(ValueError):self.check()

    def test_lobby_records_explicit_acceptance_kind(self):
        self.scenario['continuous_missions_required']='true';self.write()
        with self.assertRaises(ValueError):self.check()

    def test_duration_cannot_be_unbounded(self):
        self.grant['grants'][0]['stop_schema']['mission_duration_frames']=4501
        with self.assertRaises(ValueError):self.check()

    def test_calibration_or_already_armed_run_still_rejected(self):
        for marker in ('calibration.json','full-match-runner.json'):
            with self.subTest(marker=marker):
                target=self.run/marker;target.write_text('{}')
                with self.assertRaises(ValueError):self.check()
                target.unlink()

    def test_preflight_never_arms_or_writes_into_fresh_run(self):
        before=set(self.run.iterdir());self.check()
        self.assertEqual(set(self.run.iterdir()),before)

    def test_calibration_settings_cannot_be_relabelled_as_final_match(self):
        for key,value in [('starting_credits',40000),('opponent_difficulty','easy'),
                          ('model_side_native_difficulty','easy'),('lobby_verified',False),
                          ('calibration_commands_dispatched',1),('starting_credits',True)]:
            with self.subTest(key=key,value=value):
                original=self.scenario[key];self.scenario[key]=value;self.write()
                with self.assertRaises(ValueError):self.check()
                self.scenario[key]=original;self.write()


if __name__=='__main__':unittest.main()
