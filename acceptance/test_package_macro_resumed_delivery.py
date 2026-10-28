"""Package tests use temporary synthetic public artifacts, never live services."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import package_macro_resumed_delivery as pack
from test_macro_resumed_goal import Fixture,put


class PackageFixture:
    def __init__(self,root):
        self.f=Fixture(root);self.root=root;f=self.f;host=f.run/'battle-host'
        f.export=put(root/'reports/exports/diagnostics-export.json',pack.load(f.export))
        f.original=put(root/'reports/original-profile.json',pack.load(f.original))
        f.restored=put(root/'reports/restored-profile.json',pack.load(f.restored))
        for p in (f.download,f.export):put(p,dict(kind='tacticore_redacted_diagnostics',redacted=True,
            run_id=f.run_id,binding=dict(session_id=f.session),redaction={k:False for k in pack.REDACTION_FIELDS}))
        role=pack.load(f.role)
        role['evidence']={str(p):pack.digest(p) for p in (host/'host-events.jsonl',f.download,f.export)}
        put(f.role,role);f.role_value=role;f.reports[str(f.role.resolve())]=role
        release=pack.load(host/'macro-release.json');release['kind']='macro_policy_native_release';put(host/'macro-release.json',release)
        review=pack.load(f.review);review['kind']='actual_browser_macro_group_role_timeline_review';put(f.review,review)
        historical=root/'delivery/historical'
        (historical/'settlement.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic historical')
        put(historical/'diagnostics.json',dict(kind='tacticore_redacted_diagnostics',redacted=True,
            run_id='old-run',binding=dict(session_id='old-session'),redaction={k:False for k in pack.REDACTION_FIELDS}))
        public=pack.load(f.original)
        public.pop('draft');public.pop('effective');public.update(effective_hash='old-effective',credential_material_included=False)
        put(historical/'commander-config.json',public)
        (historical/'macro-timeline.html').write_text((f.review.parent/'macro-timeline.html').read_text(encoding='utf8'),encoding='utf8')
        old=pack.load(historical/'manifest.json')
        for name in old['files']:
            p=historical/name;old['files'][name]=dict(sha256=pack.digest(p),bytes=p.stat().st_size)
        put(historical/'manifest.json',old)
        g7=pack.load(f.g7);g7['evidence']={str(historical/'manifest.json'):pack.digest(historical/'manifest.json')};put(f.g7,g7)
        self.trusted={stage:pack.digest(p) for stage,p in [('G6',f.domain),('G7',f.g7),('G8',f.g8)]}
        artifacts=[]
        def add(name,source,kind):
            artifacts.append(dict(name=name,source=str(source.resolve()),type=kind,sha256=pack.digest(source),bytes=source.stat().st_size))
            return name
        required={}
        singles={'current_diagnostics':(f.download,'diagnostics'),'current_export':(f.export,'diagnostics'),
            'current_profile':(host/'profile.json','public_profile'),'executed_client':(f.run/'executed-client.json','execution_record'),
            'native_release':(host/'macro-release.json','native_release'),'original_profile':(f.original,'public_profile'),
            'restored_profile':(f.restored,'public_profile'),'restoration':(f.restoration,'restoration_proof'),
            'current_screenshot':(f.screen,'screenshot'),'G6':(f.domain,'assessment'),'G7':(f.g7,'assessment'),
            'G8':(f.g8,'assessment'),'G7_manifest':(historical/'manifest.json','artifact_manifest'),'regression':(f.regression,'regression_evidence')}
        for key,(source,kind) in singles.items():required[key]=add(key+source.suffix,source,kind)
        required['role_assessments']=[add('role-assessment.json',f.role,'assessment')]
        required['timeline_reviews']=[add('role-browser-review.json',f.review,'timeline_review')]
        add('role-timeline.html',f.review.parent/'macro-timeline.html','timeline_html')
        add('role-timeline.json',f.review.parent/'macro-timeline.json','timeline_data')
        required['G7_artifacts']={}
        for key,(name,kind) in pack.G7_FILES.items():required['G7_artifacts'][key]=add('G7-'+name,historical/name,kind)
        for key,row in pack.load(f.regression)['logs'].items():add(key+'-tests.log',Path(row['path']),'test_log')
        self.spec=put(root/'reports/resumed-delivery-spec.json',dict(schema_version=1,kind='macro_public_delivery_spec',
            current_run_id=f.run_id,current_session_id=f.session,artifacts=artifacts,required=required))
        self.output=root/'delivery/new-package'

    def package(self):
        with patch.object(pack,'ROOT',self.root),patch.object(pack,'TRUSTED_FROZEN_REPORTS',self.trusted):
            return pack.package(self.spec,self.output)

    def mutate_spec(self,change):
        doc=pack.load(self.spec);change(doc);put(self.spec,doc)


class PublicDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.f=PackageFixture(Path(self.temp.name))

    def test_explicit_frozen_public_inputs_produce_complete_inventory_without_goal_claim(self):
        result=self.f.package();manifest=pack.load(self.f.output/'manifest.json')
        self.assertFalse(result['formal_goal_complete']);self.assertFalse(manifest['formal_goal_complete'])
        self.assertEqual(manifest['completion_status'],'requires_independent_G0_G8_assessment')
        self.assertFalse(manifest['credential_material_included']);self.assertFalse(manifest['native_replay_fidelity_verified'])
        self.assertEqual(set(manifest['files']),{p.name for p in self.f.output.iterdir()}-{'manifest.json'})
        for name,row in manifest['files'].items():
            self.assertEqual(pack.digest(self.f.output/name),row['sha256'])
            self.assertEqual((self.f.output/name).stat().st_size,row['bytes'])
        self.assertIn('不保证重现外部宏观指令',(self.f.output/'README.txt').read_text(encoding='utf8'))

    def test_partial_role_evidence_stays_partial_and_cannot_set_completion(self):
        role=pack.load(self.f.f.role);role['independently_qualified_model_deployment_roles']=[]
        role['all_three_model_role_feedback_loops_verified']=False;role['formal_goal_complete']=False;put(self.f.f.role,role)
        def update(doc):
            row=next(r for r in doc['artifacts'] if r['name']=='role-assessment.json')
            row.update(sha256=pack.digest(self.f.f.role),bytes=self.f.f.role.stat().st_size)
        self.f.mutate_spec(update)
        self.assertFalse(self.f.package()['formal_goal_complete'])

    def test_new_bundle_satisfies_independent_aggregator_delivery_contract(self):
        self.f.package();f=self.f.f
        f.reports[str(f.g7.resolve())]=pack.load(f.g7)
        args=replace(f.args,delivery=self.f.output,original_export=f.export,
            original_profile=f.original,restored_profile=f.restored)
        result=f.evaluate(args)
        self.assertTrue(result['final_checks']['final_delivery_bound_artifacts'])
        self.assertTrue(result['final_checks']['standalone_playable_role_timelines'])
        self.assertTrue(result['final_checks']['replay_and_scope_limits_disclosed'])
        # Only the independent assessor can conclude from synthetic mocked
        # phase results; packaging itself never grants completion.
        self.assertFalse(pack.load(self.f.output/'manifest.json')['formal_goal_complete'])

    def test_input_hash_size_or_expected_frozen_stage_changes_fail_before_output(self):
        original=pack.load(self.f.spec)
        self.f.mutate_spec(lambda d:d['artifacts'][0].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'public_source_changed'):self.f.package()
        self.assertFalse(self.f.output.exists())
        put(self.f.spec,original)
        self.f.mutate_spec(lambda d:d['artifacts'][0].update(bytes=d['artifacts'][0]['bytes']+1))
        with self.assertRaisesRegex(ValueError,'public_source_changed'):self.f.package()
        self.assertFalse(self.f.output.exists())

    def test_unknown_stage_snapshot_cannot_be_presented_as_an_approved_G7(self):
        value=pack.load(self.f.f.g7);value['checks']={'unrelated':True};put(self.f.f.g7,value)
        def update(d):
            row=next(r for r in d['artifacts'] if r['name']==d['required']['G7'])
            row.update(sha256=pack.digest(self.f.f.g7),bytes=self.f.f.g7.stat().st_size)
        self.f.mutate_spec(update)
        with self.assertRaisesRegex(ValueError,'approved_frozen_stage_artifact_required'):self.f.package()

    def test_flat_names_case_aliases_and_reused_output_are_rejected(self):
        original=pack.load(self.f.spec)
        self.f.mutate_spec(lambda d:d['artifacts'][0].update(name='../escape.json'))
        with self.assertRaisesRegex(ValueError,'flat_public_artifact_name_required'):self.f.package()
        put(self.f.spec,original)
        self.f.mutate_spec(lambda d:d['artifacts'].append(dict(d['artifacts'][0],name=d['artifacts'][0]['name'].upper())))
        with self.assertRaisesRegex(ValueError,'duplicate_artifact_name'):self.f.package()
        put(self.f.spec,original);self.f.output.mkdir()
        with self.assertRaisesRegex(ValueError,'fresh_delivery_child_required'):self.f.package()

    def test_protected_library_is_refused_before_its_contents_are_read(self):
        secret=self.f.root/'reports/library.v2.json';secret.write_text('{"private":true}',encoding='utf8')
        self.f.mutate_spec(lambda d:d['artifacts'][0].update(source=str(secret),bytes=secret.stat().st_size))
        calls=[];old_bytes=Path.read_bytes;old_text=Path.read_text
        def spy_bytes(path,*a,**k):
            if path==secret:calls.append('bytes')
            return old_bytes(path,*a,**k)
        def spy_text(path,*a,**k):
            if path==secret:calls.append('text')
            return old_text(path,*a,**k)
        with patch.object(Path,'read_bytes',spy_bytes),patch.object(Path,'read_text',spy_text):
            with self.assertRaisesRegex(ValueError,'explicit_public_source_required'):self.f.package()
        self.assertEqual(calls,[])

    def test_secret_payload_or_nonredacted_diagnostics_are_rejected(self):
        original=pack.load(self.f.f.download)
        for field,value in [('redacted',False),('api_key','not-public')]:
            doc=dict(original);doc[field]=value;put(self.f.f.download,doc)
            def update(d):
                r=d['artifacts'][0];r.update(sha256=pack.digest(self.f.f.download),bytes=self.f.f.download.stat().st_size)
            self.f.mutate_spec(update)
            with self.subTest(field=field),self.assertRaises(ValueError):self.f.package()

    def test_normalized_nested_named_credentials_are_rejected(self):
        profile=self.f.f.original;original=pack.load(profile)
        for key in ('key','api_token','client_secret','token','api-key','encrypted_api_key',
                'apiKey','private key','credential_value','connectionString'):
            doc=copy.deepcopy(original);doc['connection']={key:'synthetic-not-public'};put(profile,doc)
            def update(d):
                r=next(r for r in d['artifacts'] if r['name']==d['required']['original_profile'])
                r.update(sha256=pack.digest(profile),bytes=profile.stat().st_size)
            self.f.mutate_spec(update)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'private_payload_rejected'):
                self.f.package()
            self.assertFalse(self.f.output.exists())

    def test_download_and_export_must_be_same_bytes_and_current_session(self):
        value=pack.load(self.f.f.export);value['binding']['session_id']='other';put(self.f.f.export,value)
        def update(d):
            r=next(r for r in d['artifacts'] if r['name']==d['required']['current_export'])
            r.update(sha256=pack.digest(self.f.f.export),bytes=self.f.f.export.stat().st_size)
        self.f.mutate_spec(update)
        with self.assertRaisesRegex(ValueError,'actual_download_export_binding'):self.f.package()

    def test_each_role_retains_its_own_actual_download_export_pair(self):
        role=pack.load(self.f.f.role);role['run_id']='another-run';put(self.f.f.role,role)
        def update(d):
            r=next(r for r in d['artifacts'] if r['name']=='role-assessment.json')
            r.update(sha256=pack.digest(self.f.f.role),bytes=self.f.f.role.stat().st_size)
        self.f.mutate_spec(update)
        with self.assertRaisesRegex(ValueError,'role_actual_download_export_pair_missing'):self.f.package()

    def test_missing_review_file_or_unrelated_historical_replay_is_rejected(self):
        original=pack.load(self.f.spec)
        self.f.mutate_spec(lambda d:d['artifacts'].__setitem__(slice(None),[r for r in d['artifacts'] if r['name']!='role-timeline.json']))
        with self.assertRaisesRegex(ValueError,'timeline_review_artifact_missing'):self.f.package()
        put(self.f.spec,original)
        replay=self.f.root/'acceptance/runs/unrelated.RA3Replay';replay.write_bytes(b'unrelated replay')
        def update(d):
            r=next(r for r in d['artifacts'] if r['name']==d['required']['G7_artifacts']['replay'])
            r.update(source=str(replay),sha256=pack.digest(replay),bytes=replay.stat().st_size)
        self.f.mutate_spec(update)
        with self.assertRaisesRegex(ValueError,'G7_same_match_artifact_changed'):self.f.package()

    def test_mid_copy_source_change_cannot_publish_a_manifest(self):
        original_copy=shutil.copy2;changed=False
        def changing_copy(source,dest,*a,**k):
            nonlocal changed
            value=original_copy(source,dest,*a,**k)
            if not changed:
                changed=True;Path(source).write_bytes(b'changed after copy')
            return value
        with patch.object(pack.shutil,'copy2',side_effect=changing_copy):
            with self.assertRaisesRegex(ValueError,'public_source_changed_during_copy'):self.f.package()
        self.assertFalse((self.f.output/'manifest.json').exists())

    def test_spec_changed_while_copying_cannot_publish_a_manifest(self):
        original_copy=shutil.copy2;changed=False
        def changing_copy(source,dest,*a,**k):
            nonlocal changed
            result=original_copy(source,dest,*a,**k)
            if not changed:
                changed=True
                doc=pack.load(self.f.spec);doc['current_session_id']='changed'
                put(self.f.spec,doc)
            return result
        with patch.object(pack.shutil,'copy2',side_effect=changing_copy):
            with self.assertRaisesRegex(ValueError,'delivery_changed_before_publication'):self.f.package()
        self.assertFalse((self.f.output/'manifest.json').exists())


if __name__=='__main__':unittest.main()
