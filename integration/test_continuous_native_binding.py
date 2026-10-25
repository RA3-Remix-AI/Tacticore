"""Synthetic replay metadata around a recorded trace; never grants or dispatches.

The original calibration stays byte-for-byte intact. UUID changes below create
software fixtures to exercise the host's independent command binding boundary.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid

from continuous_evidence import bound_report,terminal_facts,progress_evidence,_qualifier

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'acceptance/runs/20261025-095141-commander/main-mission04.json'


class RecordedMissionBinding(unittest.TestCase):
    def setUp(self):
        if not SOURCE.is_file():self.skipTest('Recorded mission trace is not installed')
        self.original_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run=Path(self.tmp.name);self.path=self.run/'synthetic-mission.json'
        self.raw=json.loads(SOURCE.read_text(encoding='utf-8-sig'));pre=self.raw['preflight'];rq=self.raw['request'];native=self.raw['native']
        parent=uuid.uuid4();task=uuid.uuid4();actor=pre['selected']['object_id']
        self.entry=dict(task_id=task.hex,command_id=str(parent),module='attack',executor_directory='mission-combat',object_ids=[actor],target_contact_id=rq['target_contact_id'],target_object_id=rq['target_object_id'],target_type_hash=self.raw['private_target']['type_hash'],target_owner_player_id=self.raw['private_target']['owner_player_id'],dispatch_frame=native['issued_frame']-8,expires_frame=native['mission_deadline_frame'])
        for section in (rq,native):section.update(command_id=str(uuid.uuid5(parent,str(actor))),task_id=str(uuid.uuid5(task,str(actor))))
        self.host=SimpleNamespace(session=dict(pid=pre['pid'],session_id=self.raw['session_id'],run_directory=str(self.run),mod_sha256=self.raw['package_sha256']),binding=SimpleNamespace(session_id=self.raw['session_id'],commander_id=pre['commander_id'],player_id=3))
        self.receipt=dict(status='completed',unit_results=[dict(report=str(self.path))])
        self.write()

    def write(self):self.path.write_text(json.dumps(self.raw),encoding='utf-8')

    def tearDown(self):
        if SOURCE.is_file() and hasattr(self,'original_sha'):self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),self.original_sha)

    def test_raw_binding_and_qualified_terminal_work_without_tactical_cwd(self):
        bound=bound_report(self.host,self.receipt,self.entry,terminal=True)
        self.assertEqual(bound['report']['native']['issued_frame'],3392)
        result=terminal_facts(self.host,self.receipt,self.entry)['qualification']
        self.assertTrue(result['effect_verified']);self.assertEqual(result['source_damage_amount'],5)

    def test_foreign_uuid_session_actor_and_deadline_are_rejected(self):
        original=copy.deepcopy(self.raw)
        for section,key,value in [('native','command_id',str(uuid.uuid4())),('request','task_id',str(uuid.uuid4())),('preflight','pid',-1),('native','mission_deadline_frame',7885),('request','target_contact_id','contact_other')]:
            self.raw=copy.deepcopy(original);self.raw[section][key]=value;self.write()
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):bound_report(self.host,self.receipt,self.entry,terminal=True)

    def test_published_old_revision_reconstructs_from_later_raw_history(self):
        qualifier=_qualifier('mission-combat','test_continuous_progress')
        events=self.raw['events'];selected=next(i for i,e in enumerate(events) if e.get('mission_stage')==2 and e.get('current_visible')==1)
        old=dict(self.raw,events=events[:selected+1]);progress=qualifier.progress(old,str(uuid.UUID(self.entry['task_id'])))
        self.assertIsNotNone(progress)
        self.assertIsNotNone(progress_evidence(self.host,self.receipt,self.entry,progress))
        with self.assertRaises(ValueError):progress_evidence(self.host,self.receipt,self.entry,dict(progress,own_hp=progress['own_hp']+1))


if __name__=='__main__':unittest.main()
