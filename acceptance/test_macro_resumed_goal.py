"""Synthetic acceptance joins; never open the game, RPC or a provider."""
from dataclasses import replace
import copy
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import assess_macro_resumed_goal as goal


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8')
    return path


class Fixture:
    """Only synthetic bytes are written under the test temporary directory."""
    def __init__(self,root):
        self.root=root;self.run=root/'acceptance/runs/schema9';host=self.run/'battle-host'
        self.session='12345678-1234-4234-8234-123456789012';self.run_id='run-17'
        put(self.run/'session.json',dict(session_id=self.session,pid=123,mod_sha256=goal.ATTACK_FIRST_SHA))
        put(self.run/'macro-budget-bundle.json',dict(schema_version=9))
        source_root=Path(goal.__file__).resolve().parents[1]
        for name in ('macro_timeline.html','export_macro_timeline.py'):
            shutil.copy2(source_root/'acceptance'/name,root/'acceptance'/name)
        self.scope=SimpleNamespace(public=lambda:dict(available_actions=['regroup','reinforce','withdraw']))
        original=dict(profile_id='commander',name='name',revision=15,connection_id='connection',model='model',
            personality=1,doctrine='defense',preferences=dict(risk=1),custom_traits='original',library_hash='library',
            draft=dict(profile_id='commander',revision=15,custom_traits='original',preferences=dict(risk=1)),
            effective=dict(effective_hash='original-hash'))
        restored=json.loads(json.dumps(original));restored.update(revision=18,effective=dict(effective_hash='restored-hash'));restored['draft']['revision']=18
        self.original=put(root/'reports/original.json',original);self.restored=put(root/'reports/restored.json',restored)
        profile=json.loads(json.dumps(original));profile['revision']=17;profile['draft']['revision']=17
        put(host/'profile.json',profile)
        self.restoration=put(root/'reports/restoration.json',dict(restore_required=False,restored_via_actual_ui=True,
            host_stopped_before_restore=True,original_revision=15,restored_revision=18,
            original_effective_hash='original-hash',restored_effective_hash='restored-hash',
            original_snapshot_sha256=goal.sha(self.original),restored_snapshot_sha256=goal.sha(self.restored),
            current_run_id=self.run_id,current_session_id=self.session))
        native=root/'reports'/('macro-desktop-'+self.run_id)
        put(native/'final-state.json',dict(cleanup_verified=True))
        (native/'policy-probe.jsonl').write_text('',encoding='utf8')
        put(host/'macro-release.json',dict(run_id=self.run_id,binding=dict(session_id=self.session,game_process_id=123),
            native_release_verified=True,final_state_sha256=goal.sha(native/'final-state.json')))
        put(host/'host-status.json',dict(session_id=self.session,pid=123,runtime_macro=dict(run_id=self.run_id),
            state='stopped',reason_code='user_stop',jobs=[]))
        events=[dict(kind='model_macro_request_context',context=dict(control_mode='macro_native')),
            dict(kind='commander_model_response_returned'),dict(kind='plan_applied',plan=dict(tactical_tasks=[],runtime_task=None)),
            dict(kind='model_macro_request_context',context=dict(control_mode='macro_native')),
            dict(kind='commander_model_response_returned'),dict(kind='macro_host_stop_started')]
        (host/'host-events.jsonl').write_text('\n'.join(json.dumps(r) for r in events)+'\n',encoding='utf8')
        (host/'macro-snapshots.jsonl').write_text('',encoding='utf8')
        self.source_hashes={};frozen=[]
        for index,name in enumerate(goal.REGRESSION_SOURCES):
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic '+name,encoding='utf8')
            self.source_hashes[str(path.resolve())]=goal.sha(path)
            copy=host/'source'/('copy-'+str(index)+'.py');copy.parent.mkdir(exist_ok=True);shutil.copy2(path,copy)
            frozen.append(dict(path=str(path.resolve()),copy=copy.name,sha256=goal.sha(copy)))
        put(host/'sources.json',dict(sources=frozen))
        self.exe=root/'desktop-ui/current.exe';self.exe.write_bytes(b'synthetic exe')
        self.frontend=root/'desktop-ui/dist';(self.frontend).mkdir(parents=True)
        (self.frontend/'index.html').write_text('synthetic frontend',encoding='utf8')
        retained=self.run/'executed-client-dist';shutil.copytree(self.frontend,retained)
        put(self.run/'executed-client.json',dict(executable=str(self.exe),executable_sha256=goal.sha(self.exe),
            frontend=[dict(path='index.html',sha256=goal.sha(self.frontend/'index.html'))],opening_wait_armed_via_actual_ui=True,profile_revision=17))
        self.screen=self.run/'client-stopped.png';self.screen.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')
        self.download=put(self.run/'downloaded-redacted-diagnostics.json',dict(redacted=True,run_id=self.run_id))
        self.export=put(root/'exports/diag.json',dict(redacted=True,run_id=self.run_id))
        role=dict(kind=goal.REPORT_SPECS['role'][0],session_id=self.session,run_id=self.run_id,
            independently_qualified_model_deployment_roles=list(goal.ROLE_GOALS),shared_checks=dict(real=True),
            role_results=[dict(action=r) for r in goal.ROLE_GOALS],bounded_role_lifecycles_verified=True,
            no_new_commands_after_stop_verified=True,all_three_model_role_feedback_loops_verified=True,
            evidence={str(host/'host-events.jsonl'):goal.sha(host/'host-events.jsonl'),
                str(self.download):goal.sha(self.download),str(self.export):goal.sha(self.export)},assessor_sha256='synthetic')
        self.role=put(root/'reports/role/assessment.json',role);self.role_value=role
        domains=dict(kind=goal.REPORT_SPECS['G6'][0],checks={k:True for k in goal.DOMAIN_CHECKS},
            assessor_sha256='synthetic',evidence={})
        self.domain=put(root/'reports/domain/assessment.json',domains)
        historical=root/'delivery/historical';historical.mkdir(parents=True)
        oldfiles={}
        for name in ('settlement.png','diagnostics.json','commander-config.json','natural.RA3Replay','macro-timeline.html'):
            path=historical/name;path.write_bytes(('frozen G7 '+name).encode());oldfiles[name]=dict(sha256=goal.sha(path),bytes=path.stat().st_size)
        oldmanifest=put(historical/'manifest.json',dict(files=oldfiles))
        g7=dict(kind=goal.REPORT_SPECS['G7'][0],session_id='older-natural-match',full_G7_verified=True,checks={k:True for k in goal.STAGE_CHECKS['G7']},
            real_model_responses=58,native_macro_plan_dispatches=52,prior_strategy_memory_rounds=30,
            model_side_outcome='defeat',assessor_sha256='synthetic',evidence={str(oldmanifest):goal.sha(oldmanifest)})
        self.g7=put(root/'reports/g7/assessment.json',g7)
        g8=dict(kind=goal.REPORT_SPECS['G8'][0],full_G8_verified=True,checks={k:True for k in goal.STAGE_CHECKS['G8']},
            win_rate_improvement_verified=False,causal_live_style_behavior_difference_verified=False,assessor_sha256='synthetic',evidence={})
        self.g8=put(root/'reports/g8/assessment.json',g8)
        self.reports={str(p.resolve()):load for p,load in [(self.role,role),(self.domain,domains),(self.g7,g7),(self.g8,g8)]}
        timeline=root/'reports/timeline';timeline.mkdir(parents=True)
        role_events=[dict(t=i,type='regional',goal=g) for i,g in enumerate(goal.ROLE_GOALS.values())]
        self.projected=role_events
        data=dict(kind='recorded_macro_timeline',schema_version=1,session_id=self.session,run_id=self.run_id,profile_revision=17,native_release_verified=True,
            game_replay_fidelity_verified=False,unit_animation_recorded=False,
            events=role_events+[dict(t=80.,type='stop',native_release_verified=True)],
            sources=[dict(name=p.name,sha256=goal.sha(p)) for p in [host/'host-events.jsonl',host/'macro-snapshots.jsonl',
                host/'sources.json',host/'profile.json',native/'policy-probe.jsonl']])
        put(timeline/'macro-timeline.json',data)
        (timeline/'macro-timeline.html').write_text(goal.render_timeline_html(data),encoding='utf8')
        review=dict(files={name:goal.sha(timeline/name) for name in ('macro-timeline.json','macro-timeline.html')},
            play_verified=True,pause_verified=True,seek_verified=True,group_role_feedback_visible=True,stop_release_visible=True,
            template_sha256=goal.TIMELINE_TEMPLATE_SHA,exporter_sha256=goal.TIMELINE_EXPORTER_SHA)
        self.review=put(timeline/'browser-review.json',review)
        logs={}
        for name in ('macro','host','strategy','ui'):
            log=root/'reports'/('test-'+name+'.log')
            log.write_text('ℹ tests 2\nℹ pass 2\nℹ fail 0\nℹ cancelled 0\n' if name=='ui' else 'Ran 2 tests in 0.01s\n\nOK\n',encoding='utf8')
            logs[name]=dict(path=str(log),sha256=goal.sha(log),tests=2,command=['synthetic-test',name],result='passed')
        self.regression=put(root/'reports/regression.json',dict(schema_version=1,kind='macro_regression_evidence',sources=self.source_hashes,logs=logs))
        self.delivery=root/'delivery/final';self.delivery.mkdir()
        required=[self.download,host/'profile.json',self.run/'executed-client.json',host/'macro-release.json',
            self.original,self.restored,self.restoration,self.screen,self.domain,self.g7,self.g8,self.role,
            self.review,timeline/'macro-timeline.html',timeline/'macro-timeline.json',*[historical/n for n in oldfiles]]
        for i,path in enumerate(required):shutil.copy2(path,self.delivery/(str(i)+'-'+path.name))
        (self.delivery/'README.txt').write_text('原生录像不保证重现外部宏观指令。',encoding='utf8')
        self.write_manifest()
        self.args=goal.Inputs(run=self.run,run_id=self.run_id,role_assessments=(self.role,),domain_assessment=self.domain,
            complete_match_assessment=self.g7,contribution_assessment=self.g8,download=self.download,original_export=self.export,
            original_profile=self.original,restored_profile=self.restored,restoration=self.restoration,delivery=self.delivery,
            current_executable=self.exe,current_frontend=self.frontend,current_screenshot=self.screen,
            timeline_reviews=(self.review,),regression_evidence=self.regression)
        self.common=dict(evidence={},checks={k:True for k in ('exact_pre_execution_sources_retained','current_profile_consumed',
            'exact_public_request_context_retained','real_provider_response','macro_unit_jobs_absent','native_cleanup_verified',
            'user_stop_completed','multiple_real_model_rounds','downloaded_export_matches')})
        self.native=(None,dict(cleanup_verified=True,unknown_command_ids=[],native=dict(last_frame=1200)),dict(package_sha256=goal.ATTACK_FIRST_SHA),[],{})

    def write_manifest(self):
        files={p.name:dict(sha256=goal.sha(p),bytes=p.stat().st_size) for p in self.delivery.iterdir() if p.name!='manifest.json'}
        put(self.delivery/'manifest.json',dict(files=files,native_replay_fidelity_verified=False,
            client_cross_machine_portability_verified=False,credential_material_included=False,unit_micro_control=False))

    def evaluate(self,args=None):
        with patch.object(goal,'ROOT',self.root),patch.object(goal,'assess',return_value=self.common),\
                patch.object(goal,'trial',return_value=self.native),patch.object(goal,'load_bundle',return_value=({'schema_version':9},self.scope)),\
                patch.object(goal,'verify_report',side_effect=lambda p,stage:(self.reports[str(p.resolve())],{})),\
                patch.object(goal,'replay_roles',return_value=self.role_value),\
                patch.object(goal,'project_timeline',side_effect=lambda *a:copy.deepcopy(self.projected)):
            return goal.evaluate(args or self.args)


class ResumedGoalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(Path(self.tmp.name))

    def test_synthetic_complete_join_keeps_scope_limits_and_explicit_provenance(self):
        result=self.f.evaluate()
        self.assertTrue(result['formal_goal_complete'])
        self.assertEqual(set(result['phase_checks']),{'G'+str(i) for i in range(9)})
        self.assertFalse(result['client_cross_machine_portability_verified'])
        self.assertFalse(result['portable_release_is_completion_gate'])
        self.assertEqual(result['reused_complete_match_session_id'],'older-natural-match')

    def test_missing_regression_or_any_role_does_not_complete(self):
        value=self.f.evaluate(replace(self.f.args,regression_evidence=None))
        self.assertFalse(value['formal_goal_complete']);self.assertFalse(value['phase_checks']['G2'])
        self.f.role_value['independently_qualified_model_deployment_roles']=['withdraw']
        value=self.f.evaluate();self.assertFalse(value['phase_checks']['G6'])
        self.assertEqual(value['missing_independent_model_deployment_roles'],['regroup','reinforce'])

    def test_changing_only_a_role_report_green_list_is_rejected(self):
        self.f.reports[str(self.f.role.resolve())]=dict(self.f.role_value,independently_qualified_model_deployment_roles=['withdraw'])
        with self.assertRaisesRegex(ValueError,'role_report_replay_mismatch'):self.f.evaluate()

    def test_role_report_cannot_relabel_the_session_of_actual_raw_evidence(self):
        self.f.reports[str(self.f.role.resolve())]=dict(self.f.role_value,session_id='another-session')
        with self.assertRaisesRegex(ValueError,'role_report_session_mismatch'):self.f.evaluate()

    def test_current_fault_late_command_or_executable_change_cannot_reuse_old_g7(self):
        host=self.f.run/'battle-host';path=host/'host-events.jsonl';before=path.read_text(encoding='utf8')
        for kind in ('host_fault','commander_model_call_started'):
            path.write_text(before+json.dumps(dict(kind=kind))+'\n',encoding='utf8')
            self.assertFalse(self.f.evaluate()['formal_goal_complete'])
        path.write_text(before,encoding='utf8');self.f.exe.write_bytes(b'changed')
        self.assertFalse(self.f.evaluate()['phase_checks']['G5'])

    def test_second_stop_cannot_hide_new_commands_after_first_stop(self):
        path=self.f.run/'battle-host/host-events.jsonl'
        with path.open('a',encoding='utf8') as stream:
            stream.write(json.dumps(dict(kind='commander_model_call_started'))+'\n')
            stream.write(json.dumps(dict(kind='macro_host_stop_started'))+'\n')
        value=self.f.evaluate()
        self.assertFalse(value['phase_checks']['G5']);self.assertFalse(value['final_checks']['no_new_commands_after_user_stop'])

    def test_omitting_a_critical_host_source_is_rejected_even_if_tests_hash_current_source(self):
        path=self.f.run/'battle-host/sources.json';ledger=goal.load(path)
        ledger['sources']=[r for r in ledger['sources'] if Path(r['path']).name not in ('macro_host.py','http_adapter.py')]
        put(path,ledger)
        with self.assertRaisesRegex(ValueError,'required_host_frozen_sources_missing'):self.f.evaluate()

    def test_role_execution_sources_must_match_current_run_even_in_another_research_run(self):
        with patch.object(goal,'ROOT',self.f.root):
            current,_=goal.frozen_sources(self.f.run/'battle-host');role=dict(current)
            role[str((self.f.root/'strategy/http_adapter.py').resolve())]='different-revision'
            with self.assertRaisesRegex(ValueError,'role_execution_source_differs_from_current_run'):
                goal.require_role_source_match(role,current)

    def test_actual_restored_fields_override_a_claimed_restored_flag(self):
        restored=goal.load(self.f.restored);restored['draft']['preferences']['risk']=5;put(self.f.restored,restored)
        proof=goal.load(self.f.restoration);proof['restored_snapshot_sha256']=goal.sha(self.f.restored);put(self.f.restoration,proof)
        value=self.f.evaluate();self.assertFalse(value['final_checks']['temporary_style_restored'])

    def test_timeline_embedded_data_or_source_mismatch_is_not_playback_proof(self):
        html=self.f.review.parent/'macro-timeline.html';html.write_text('unrelated HTML',encoding='utf8')
        review=goal.load(self.f.review);review['files'][html.name]=goal.sha(html);put(self.f.review,review)
        self.assertFalse(self.f.evaluate()['final_checks']['standalone_playable_role_timelines'])

    def test_matching_html_json_and_review_cannot_replace_raw_timeline_events(self):
        folder=self.f.review.parent;data=goal.load(folder/'macro-timeline.json')
        data['events'][0]['goal']='invented-regroup-success'
        put(folder/'macro-timeline.json',data)
        (folder/'macro-timeline.html').write_text(goal.render_timeline_html(data),encoding='utf8')
        review=goal.load(self.f.review)
        for name in ('macro-timeline.json','macro-timeline.html'):review['files'][name]=goal.sha(folder/name)
        put(self.f.review,review)
        self.assertFalse(self.f.evaluate()['final_checks']['standalone_playable_role_timelines'])

    def test_inert_json_html_or_unapproved_player_source_is_not_playable(self):
        folder=self.f.review.parent;data=goal.load(folder/'macro-timeline.json')
        html=folder/'macro-timeline.html';html.write_text('<script id="timeline-data" type="application/json">'+json.dumps(data)+'</script>',encoding='utf8')
        review=goal.load(self.f.review);review['files'][html.name]=goal.sha(html);put(self.f.review,review)
        self.assertFalse(self.f.evaluate()['final_checks']['standalone_playable_role_timelines'])
        (self.f.root/'acceptance/macro_timeline.html').write_text('no player',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'timeline_player_source_not_approved'):self.f.evaluate()

    def test_same_game_research_runs_are_identified_by_report_host_not_global_session_id(self):
        duplicate=self.f.root/'acceptance/runs/continuation'
        put(duplicate/'session.json',dict(session_id=self.f.session,pid=123,continuation_of=str(self.f.run),fresh_match=False,research_continuation=True))
        with patch.object(goal,'ROOT',self.f.root):
            run,download,original=goal.role_report_inputs(self.f.role_value)
        self.assertEqual(run,self.f.run)
        self.assertEqual({download,original},{self.f.download,self.f.export})

    def test_delivery_addition_hash_change_or_missing_bound_artifact_is_rejected(self):
        extra=self.f.delivery/'unlisted.txt';extra.write_text('unlisted',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'delivery_inventory_incomplete'):self.f.evaluate()
        extra.unlink();target=next(p for p in self.f.delivery.iterdir() if p.name.endswith('client-stopped.png'))
        target.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact_hash_changed'):self.f.evaluate()

    def test_regression_passed_boolean_does_not_replace_actual_log_or_source(self):
        reg=goal.load(self.f.regression);log=Path(reg['logs']['host']['path']);log.write_text('Ran 2 tests in 0.01s\nFAILED (failures=1)\n',encoding='utf8')
        reg['logs']['host']['sha256']=goal.sha(log);put(self.f.regression,reg)
        with self.assertRaisesRegex(ValueError,'regression_log_not_passed'):self.f.evaluate()

    def test_current_schema8_is_refused(self):
        with patch.object(goal,'ROOT',self.f.root),patch.object(goal,'assess',return_value=self.f.common),\
                patch.object(goal,'trial',return_value=self.f.native),patch.object(goal,'load_bundle',return_value=({'schema_version':8},self.f.scope)):
            with self.assertRaisesRegex(ValueError,'current_schema9_group_roles_required'):goal.evaluate(self.f.args)


class EvidenceIntegrityTests(unittest.TestCase):
    def test_stage_cannot_be_forged_with_current_assessor_hash_and_unrelated_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=root/'unrelated.txt';raw.write_text('unrelated',encoding='utf8')
            source_root=Path(goal.__file__).resolve().parents[1]
            for stage in ('G6','G7','G8'):
                kind,name=goal.REPORT_SPECS[stage];folder=root/stage;folder.mkdir()
                shutil.copy2(source_root/'acceptance'/name,folder/'assessor.py')
                body=dict(kind=kind,assessor_sha256=goal.sha(folder/'assessor.py'),checks=dict(unrelated=True),
                    evidence={str(raw):goal.sha(raw)},full_G7_verified=True,full_G8_verified=True)
                path=put(folder/'assessment.json',body)
                with self.subTest(stage=stage),self.assertRaisesRegex(ValueError,'assessment_check_schema'):
                    goal.verify_report(path,stage)
                body['checks']={k:True for k in goal.STAGE_CHECKS[stage]};put(path,body)
                with self.subTest(stage=stage,complete_keys=True),self.assertRaisesRegex(ValueError,'untrusted_frozen_stage_snapshot'):
                    goal.verify_report(path,stage)
    def test_nested_report_or_helper_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=root/'raw.txt';raw.write_text('raw',encoding='utf8')
            child=root/'child';child.mkdir();(child/'assessor.py').write_text('child source',encoding='utf8')
            put(child/'assessment.json',dict(assessor_sha256=goal.sha(child/'assessor.py'),evidence={str(raw):goal.sha(raw)}))
            parent=root/'parent';parent.mkdir();(parent/'assessor.py').write_text('parent source',encoding='utf8')
            helper=parent/'effect-helper.py';helper.write_text('helper',encoding='utf8')
            report=put(parent/'assessment.json',dict(assessor_sha256=goal.sha(parent/'assessor.py'),
                evidence={str(child/'assessment.json'):goal.sha(child/'assessment.json'),str(helper):goal.sha(helper)}))
            _,evidence=goal.verify_report(report);self.assertIn(str(raw),evidence)
            raw.write_text('changed raw',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'assessment_evidence_changed'):goal.verify_report(report)
            raw.write_text('raw',encoding='utf8');helper.write_text('changed helper',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'assessment_evidence_changed'):goal.verify_report(report)

    def test_unknown_missing_ledger_format_cannot_be_treated_as_legacy_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'assessor.py';source.write_text('source',encoding='utf8')
            path=put(root/'assessment.json',dict(kind='made_up_success',assessor_sha256=goal.sha(source),formal_goal_complete=True))
            with self.assertRaisesRegex(ValueError,'assessment_source_ledger_missing'):goal.verify_report(path)

    def test_inventory_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);outside=root/'outside';outside.write_text('outside',encoding='utf8');folder=root/'pack';folder.mkdir()
            with self.assertRaisesRegex(ValueError,'artifact_relative_path_required'):
                goal.verify_files(folder,{'../outside':goal.sha(outside)})


if __name__=='__main__':unittest.main()
