"""Offline trust and lifecycle negatives for the session discovery broker."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from host_runtime.contracts import ContractError
from host_runtime.bridge_service import _result_safe
from host_runtime.session_discovery import (DiscoveryPolicy, MatchObservation, ProcessIdentity,
                                          RunRecord, SessionDiscovery, TrustedFiles)
from host_runtime.scenario import MatchScenario, derive_scenario

PROFILE = '5cfc416a-8b8f-405a-9832-c163f8c1792b'
TWO_STARTS = [dict(name='Player_1_Start', xyz=[857.5, 2015.4, 0.]),
              dict(name='Player_2_Start', xyz=[4404.1, 2016.0, 0.])]
FOUR_STARTS = [dict(name='Player_1_Start', xyz=[700., 700., 0.]), dict(name='Player_2_Start', xyz=[3800., 700., 0.]),
               dict(name='Player_3_Start', xyz=[700., 3800., 0.]), dict(name='Player_4_Start', xyz=[3800., 3800., 0.])]


def scenario(map_id='map_mp_2_black1b', others=((4, 'native_ai', 'enemy'),), alliances=(), starts=TWO_STARTS,
             own=(4404.1, 2016.0), allied_starts=()):
    rows = [dict(player_id=3, kind='model_ai', relation='self')]
    rows += [dict(player_id=index, kind=kind, relation=relation) for index, kind, relation in others]
    return derive_scenario(map_id=map_id, model_player_id=3, participants=rows, alliances=alliances,
                           own_point=own, starts=starts, allied_starts=allied_starts).to_public_dict()


def new_id():
    return str(uuid.uuid4())


class SessionDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.sessions = self.root/'sessions'; self.sessions.mkdir()
        self.state = self.root/'state'; self.state.mkdir()
        names = dict(game='ra3_1.12.game', mod_config='macro.skudef', mod_big='macro.big',
                     registry='registry.json', macro_bundle='bundle.json', package_report='package-report.json')
        values = {}
        for key, name in names.items():
            path = self.root/name; path.write_bytes(('offline-'+key).encode())
            digest_key = 'mod_sha256' if key == 'mod_big' else key+'_sha256'
            values.update({key:path, digest_key:hashlib.sha256(path.read_bytes()).hexdigest()})
        self.policy = DiscoveryPolicy(TrustedFiles(**values), self.sessions, self.state, PROFILE, 7)
        self.process = ProcessIdentity(101, 134376028671883531, '2026-10-28T10:00:00+08:00',
                                        self.policy.files.game, self.policy.files.mod_config)
        self.observation = MatchObservation(101, self.process.creation_filetime, 'logic-1',
            PROFILE, 7, scenario(), True)
        self.processes = [self.process]; self.runs = []; self.registered = []; self.time = 100.0
        self.probe_calls = 0
        self.broker = self.make()

    def make(self):
        return SessionDiscovery(self.policy, lambda:list(self.processes), self.probe, self.register,
                                lambda:list(self.runs), clock=lambda:self.time)

    def probe(self, process, policy):
        self.probe_calls += 1
        return self.observation

    def register(self, session, bundle):
        self.registered.append((session,bundle))
        return dict(registered=True, restart_required=True)

    def tearDown(self):
        self.broker.close(); self.temp.cleanup()

    def candidate(self):
        value = self.broker.discover({})
        _result_safe(value)
        return value['candidates'][0]['candidate_id']

    def prepare(self, candidate=None, request=None):
        return self.broker.prepare({'candidate_id':candidate or self.candidate()}, request or new_id())

    def one_vs_two(self):
        return scenario('map_mp_4_stewart_1', ((4, 'native_ai', 'enemy'), (5, 'native_ai', 'enemy')),
                        alliances=[[4, 5]], starts=FOUR_STARTS, own=(3700., 800.))

    def test_one_vs_two_preparation_retains_both_opponents(self):
        self.observation = replace(self.observation, scenario=self.one_vs_two())
        receipt = self.prepare()
        self.assertTrue(receipt['registered'])
        session_path = self.registered[-1][0]
        session = json.loads(Path(session_path).read_text('utf-8'))
        self.assertEqual(session['scenario']['opponent_player_indices'], [4, 5])
        self.assertEqual(session['scenario']['participant_count'], 3)
        self.assertTrue(session['scenario']['opponents_allied'])
        self.assertEqual(MatchScenario.from_session(session['scenario']).enemy_player_ids, (4, 5))

    def test_native7_session_writer_records_its_epoch(self):
        self.broker.close()
        self.policy=replace(self.policy,native_epoch=7)
        self.observation=replace(self.observation,native_epoch=7,scenario=self.one_vs_two())
        self.broker=self.make()
        self.assertTrue(self.prepare()['registered'])
        session=json.loads(Path(self.registered[-1][0]).read_text('utf-8'))
        self.assertEqual(session['discovery']['native_epoch'],7)

    def test_inconsistent_scenario_is_an_invalid_probe(self):
        broken = dict(self.observation.scenario, mode='human_with_ai')
        self.observation = replace(self.observation, scenario=broken)
        result = self.broker.discover({})
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['issues'], ['session_probe_invalid'])

    def test_human_with_ai_candidate_lists_every_player(self):
        value = scenario('some custom map', ((2, 'human', 'ally'), (4, 'native_ai', 'enemy'),
                                             (5, 'native_ai', 'enemy')),
                         alliances=[[4, 5]], starts=FOUR_STARTS, own=(3700., 800.), allied_starts=('Player_1_Start',))
        self.observation = replace(self.observation, scenario=value)
        candidate = self.broker.discover({})['candidates'][0]
        self.assertEqual(candidate['map'], 'some custom map')
        public = candidate['scenario']
        self.assertEqual(public['mode'], 'human_with_ai')
        self.assertEqual(public['model_player_id'], 3)
        self.assertEqual([(row['player_id'], row['kind'], row['team']) for row in public['players']],
                         [(2, 'human', 1), (3, 'model_ai', 1), (4, 'native_ai', 2), (5, 'native_ai', 2)])
        self.assertTrue(all(row['difficulty'] is None for row in public['players']))
        self.prepare(candidate['candidate_id'])
        session = json.loads(self.registered[0][0].read_text())
        self.assertEqual(session['scenario']['match']['mode'], 'human_with_ai')
        self.assertEqual(session['scenario']['opponent_player_indices'], [4, 5])

    def assertCode(self, code, operation):
        with self.assertRaises(ContractError) as caught:
            operation()
        self.assertEqual(code,caught.exception.code)

    def old_run(self, **changes):
        return replace(RunRecord(new_id(),'stopped',True,0,99,134376028671883500,36), **changes)

    def test_supported_process_produces_only_opaque_safe_summary(self):
        candidate = self.candidate()
        self.assertEqual(self.candidate(),candidate)
        value = json.dumps(self.broker.discover({}),ensure_ascii=False)
        for private in (str(self.root), 'logic-1', str(self.process.creation_filetime), 'executable', 'mod_config'):
            self.assertNotIn(private,value)
        self.assertFalse(self.registered)
        self.assertEqual(list(self.sessions.iterdir()),[])

    def test_empty_enumerator_waits_without_searching_or_registering(self):
        self.processes = []
        result = self.broker.discover({})
        self.assertEqual(result['state'],'waiting_for_supported_session')
        self.assertEqual(result['candidates'],[])
        self.assertEqual(self.probe_calls,0)

    def test_executable_and_modconfig_must_match_bootstrap_paths(self):
        for change in ({'executable':self.root/'other.game'}, {'mod_config':self.root/'other.skudef'}):
            self.processes = [replace(self.process,**change)]
            self.assertEqual(self.broker.discover({})['candidates'],[])
        self.assertEqual(self.probe_calls,0)

    def test_rpc_arguments_cannot_supply_paths_pid_or_capability(self):
        for key in ('pid','path','macro_bundle','executable','session_root','native_epoch'):
            with self.subTest(key=key):
                self.assertCode('unexpected_fields',lambda:self.broker.discover({key:'arbitrary'}))
                self.assertCode('unexpected_fields',lambda:self.broker.prepare({'candidate_id':new_id(),key:'arbitrary'},new_id()))
        self.assertFalse(self.registered)

    def test_process_and_probe_identity_mismatch_are_not_candidates(self):
        self.observation = replace(self.observation,creation_filetime=self.process.creation_filetime+1)
        self.assertEqual(self.broker.discover({})['issues'],['session_probe_invalid'])

    def test_unsupported_scenario_and_origin_never_receive_candidate(self):
        baseline = self.observation
        model_four = derive_scenario(map_id='map_mp_2_black1b', model_player_id=4,
            participants=[dict(player_id=4, kind='model_ai', relation='self'),
                          dict(player_id=3, kind='native_ai', relation='enemy')],
            alliances=(), own_point=(4404.1, 2016.0), starts=TWO_STARTS).to_public_dict()
        allied = scenario()
        allied['players'][0]['faction'] = 'Allied'
        for change in ({'commander_id':new_id()}, {'native_epoch':6}, {'native_epoch':True},
                       {'scenario':allied}, {'scenario':model_four}):
            with self.subTest(change=change):
                self.observation = replace(baseline,**change)
                result = self.broker.discover({})
                self.assertEqual(result['candidates'],[])
                self.assertEqual(result['issues'],['session_scope_unsupported'])

    def test_lobby_paused_and_ended_matches_wait(self):
        baseline = self.observation
        for change, code in (({'ready':False},'session_not_ready'), ({'paused':True},'session_paused'),
                             ({'ended':True},'session_not_ready')):
            self.observation = replace(baseline,**change)
            self.assertEqual(self.broker.discover({})['issues'],[code])

    def test_arbitrary_probe_exception_does_not_leak_details(self):
        def broken(*args):
            raise RuntimeError('PRIVATE_PATH_SECRET_ADDRESS')
        self.broker.probe_match = broken
        result = self.broker.discover({})
        self.assertEqual(result['issues'],['session_probe_unavailable'])
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_new_session_is_immutable_and_registration_is_not_execution(self):
        result = self.prepare()
        _result_safe(result)
        self.assertTrue(result['registered']); self.assertTrue(result['requires_preflight'])
        self.assertFalse(result['native_execution_started'])
        path, bundle = self.registered[0]
        record = json.loads(path.read_text(encoding='utf8'))
        self.assertEqual(record['run_directory'],str(path.parent))
        self.assertEqual(record['process_creation_filetime'],self.process.creation_filetime)
        self.assertEqual(record['scenario']['commander_id'],PROFILE)
        self.assertEqual(record['discovery']['game_instance_id'],'logic-1')
        self.assertEqual(bundle,self.policy.files.macro_bundle)
        self.assertEqual(record['real_model_calls'],0)

    def test_same_request_replays_durable_receipt_without_reregistering(self):
        candidate, request = self.candidate(),new_id()
        first = self.prepare(candidate,request)
        self.broker.close(); self.broker = self.make()
        self.assertEqual(self.prepare(candidate,request),first)
        self.assertEqual(len(self.registered),1)
        self.assertEqual(len(list(self.sessions.iterdir())),1)

    def test_repeated_click_new_request_reuses_exact_prepared_session(self):
        candidate = self.candidate()
        first = self.prepare(candidate)
        second_request = new_id()
        self.assertEqual(self.prepare(candidate,second_request),first)
        self.assertEqual(self.prepare(candidate,second_request),first)
        self.assertEqual(len(self.registered),1)
        self.assertEqual(len(list(self.sessions.iterdir())),1)

    def test_new_discovery_token_after_restart_reuses_prepared_match(self):
        first = self.prepare()
        self.broker.close(); self.broker = self.make()
        second = self.prepare()
        self.assertEqual(second,first)
        self.assertEqual(len(self.registered),1)

    def test_reused_request_id_with_different_candidate_is_conflict(self):
        candidate, request = self.candidate(),new_id()
        self.prepare(candidate,request)
        self.assertCode('request_id_conflict',lambda:self.prepare(new_id(),request))

    def test_unknown_and_expired_candidate_do_not_create_run_directory(self):
        self.assertCode('session_candidate_expired',lambda:self.prepare(new_id()))
        candidate = self.candidate(); self.time += 91
        self.assertCode('session_candidate_expired',lambda:self.prepare(candidate))
        self.assertFalse(self.registered); self.assertFalse(list(self.sessions.iterdir()))

    def test_pid_reuse_after_discovery_is_rejected(self):
        candidate = self.candidate()
        self.processes = [replace(self.process,creation_filetime=self.process.creation_filetime+1)]
        self.assertCode('session_changed',lambda:self.prepare(candidate))
        self.assertFalse(self.registered)

    def test_new_match_same_pid_invalidates_old_candidate(self):
        candidate = self.candidate(); self.observation = replace(self.observation,game_instance_id='logic-2')
        self.assertCode('session_changed',lambda:self.prepare(candidate))
        self.assertFalse(self.registered)

    def test_all_pinned_sources_rechecked_at_prepare(self):
        for field in ('game','mod_config','mod_big','registry','macro_bundle','package_report'):
            with self.subTest(field=field):
                path = getattr(self.policy.files,field); before = path.read_bytes()
                candidate = self.candidate(); path.write_bytes(before+b'changed')
                self.assertCode('discovery_source_changed',lambda:self.prepare(candidate))
                path.write_bytes(before)
        self.assertFalse(self.registered)

    def test_unreleased_running_or_unresolved_prior_run_blocks_switch(self):
        for change in ({'state':'running'}, {'state':'stopping'}, {'native_release_verified':False}, {'unresolved_count':1}):
            with self.subTest(change=change):
                self.runs = [self.old_run(**change)]
                self.assertCode('run_state_conflict',self.prepare)
        self.assertFalse(self.registered)

    def test_insufficient_or_malformed_old_history_has_explicit_reason(self):
        for row in ({'state':'stopped'}, self.old_run(unresolved_count=None), self.old_run(native_epoch=None),
                    self.old_run(native_release_verified=1), self.old_run(state=[])):
            self.runs = [row]
            self.assertCode('run_history_unverifiable',self.prepare)
        self.assertFalse(self.registered)

    def test_same_process_same_epoch_after_release_is_still_unsupported(self):
        self.runs = [self.old_run(pid=self.process.pid,creation_filetime=self.process.creation_filetime,native_epoch=37)]
        self.assertCode('macro_runtime_same_epoch_reattach_unsupported',self.prepare)
        self.observation = replace(self.observation,game_instance_id='logic-new-match')
        self.assertCode('macro_runtime_same_epoch_reattach_unsupported',self.prepare)
        self.runs = [replace(self.runs[0],native_epoch=36)]
        self.assertCode('macro_runtime_same_epoch_reattach_unsupported',self.prepare)
        self.assertFalse(self.registered)

    def test_verified_new_process_after_release_can_prepare_next_session(self):
        self.runs = [self.old_run()]
        self.assertTrue(self.prepare()['registered'])

    def test_archived_history_never_blocks_but_must_not_claim_native_delivery(self):
        self.runs=[self.old_run(creation_filetime=None,native_epoch=None,native_delivery_attempted=False,
            history_protocol='archived_before_runtime_change')]
        self.assertTrue(self.prepare()['registered'])
        self.runs=[replace(self.runs[0],pid=self.process.pid)]
        self.assertTrue(self.prepare()['registered'])
        self.runs=[replace(self.runs[0],native_delivery_attempted=True)]
        self.assertCode('run_history_unverifiable',self.prepare)
        self.runs=[replace(self.runs[0],native_delivery_attempted=False,history_protocol='reviewed_legacy')]
        self.assertCode('run_history_unverifiable',self.prepare)

    def test_never_dispatched_cancelled_start_does_not_burn_native_epoch(self):
        self.runs = [self.old_run(pid=self.process.pid,creation_filetime=self.process.creation_filetime,
                                 native_epoch=37,native_delivery_attempted=False)]
        self.assertTrue(self.prepare()['registered'])

    def test_interrupted_registration_retries_only_identical_metadata_binding(self):
        candidate, request = self.candidate(),new_id()
        calls = []
        def uncertain(path,bundle):
            calls.append((path,bundle))
            raise OSError('PRIVATE')
        self.broker.register_source = uncertain
        self.assertCode('session_registration_uncertain',lambda:self.prepare(candidate,request))
        self.broker.close(); self.broker = self.make()
        self.assertTrue(self.prepare(candidate,request)['registered'])
        self.assertEqual(calls,self.registered)
        self.assertEqual(len(list(self.sessions.iterdir())),1)

    def test_changed_prepared_session_is_never_silently_overwritten(self):
        candidate, request = self.candidate(),new_id()
        self.broker.register_source = lambda *args: {}
        self.assertCode('session_registration_uncertain',lambda:self.prepare(candidate,request))
        path = next(self.sessions.glob('*/session.json')); original = path.read_bytes()
        path.write_bytes(original+b' ')
        self.broker.register_source = self.register
        self.assertCode('session_preparation_changed',lambda:self.prepare(candidate,request))
        self.assertEqual(path.read_bytes(),original+b' ')
        self.assertFalse(self.registered)

    def test_match_change_during_session_creation_prevents_registration(self):
        candidate = self.candidate(); baseline = self.probe_calls
        original = self.broker.probe_match
        def changing(process,policy):
            value = original(process,policy)
            return replace(value,game_instance_id='changed') if self.probe_calls >= baseline+2 else value
        self.broker.probe_match = changing
        self.assertCode('session_changed',lambda:self.prepare(candidate))
        self.assertFalse(self.registered)

    def test_duplicate_process_identity_is_not_silently_collapsed(self):
        self.processes = [self.process,self.process]
        self.assertCode('session_probe_invalid',lambda:self.broker.discover({}))

    def test_unsupported_policy_cannot_broaden_player_or_epoch(self):
        for change in ({'player_id':4}, {'faction':'Allied'}, {'native_epoch':37}, {'native_epoch':5}):
            with self.subTest(change=change):
                self.policy = replace(self.policy,**change)
                self.assertCode('discovery_policy_invalid',self.make)

    def test_any_observed_map_is_prepared_without_rpc_map_input(self):
        self.observation=replace(self.observation,scenario=scenario('map_mp_2_rao1',own=(3700.,2100.)))
        candidate=self.broker.discover({})['candidates'][0]
        self.assertEqual(candidate['map'],'InfinityIsle')
        self.assertEqual(candidate['display_name'],'InfinityIsle / P3 苏军')
        self.assertEqual(candidate['scenario']['mode'],'ai_vs_native')
        prepared=self.prepare(candidate['candidate_id'])
        self.assertEqual(prepared['session']['map'],'InfinityIsle')
        session=json.loads(self.registered[0][0].read_text())
        self.assertEqual(session['scenario']['map_id'],'map_mp_2_rao1')
        self.assertEqual(session['scenario']['origin_region'],'region_7_4')

    def test_changed_map_before_preparation_is_rejected(self):
        candidate=self.candidate()
        self.observation=replace(self.observation,scenario=scenario('map_mp_2_rao1',own=(3700.,2100.)))
        self.assertCode('session_changed',lambda:self.prepare(candidate))
        self.assertFalse(self.registered)

    def test_registration_failure_preserves_typed_reason(self):
        def refuse(*args):
            raise ContractError('run_state_conflict')
        self.broker.register_source = refuse
        self.assertCode('run_state_conflict',self.prepare)


if __name__ == '__main__':
    unittest.main()
