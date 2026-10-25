"""Private status sampling with inert memory; no game or model operations."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from ground_history import record


class Memory:
    def __init__(self):self.position_reads=0
    def read(self,address,length):
        self.position_reads+=1
        return struct.pack('<fff',100.,120.,210.)
    def u32(self,address):return 0x3000
    def f32(self,address):return 100.


class GroundHistory(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);self.memory=Memory();self.seen=set()
        self.session=dict(session_id='offline-fixture',pid=123)
        self.row=dict(owner_index_candidate=3,type_hash='0x19ab11af',object_id=31,
                      address='0x1000',owner_address='0x2000')
        self.status=dict(schema_version=2,status='verified_native_surface_sample',helper_sha256='fixture-reader',xyz=[100.,120.,210.],hp=100.,grounded_verified=True,object_id=31,type_hash='0x19ab11af',
                         owner='0x2000',frame=150,end_frame=150,
                         status_words=['0x0']*5+['0x1','0x0'])

    def run_record(self,rows=None,reader=None):
        return record(self.memory,self.session,rows or [self.row],self.folder,self.seen,
                      reader or (lambda m,t:copy.deepcopy(self.status)),'fixture-reader')

    def test_positive_point_keeps_seven_words_without_claiming_a_walkable_edge(self):
        self.assertEqual(self.run_record()['points'],1)
        path=next(self.folder.glob('*.json'));data=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['own_objects'][0]['grounded_status']['status_words'],self.status['status_words'])
        self.assertEqual(data['own_objects'][0]['xyz'],[100.,120.,210.])
        self.assertFalse(data['walkable_route_verified']);self.assertFalse(data['model_eligible'])
        original=path.read_bytes();self.assertEqual(self.run_record()['points'],0)
        self.assertEqual(original,path.read_bytes())

    def test_unknown_air_or_foreign_never_exports_position(self):
        self.status['grounded_verified']=False
        self.assertEqual(self.run_record()['points'],0)
        foreign=dict(self.row,owner_index_candidate=4)
        def forbidden(*args):raise AssertionError('Foreign native memory read')
        self.assertEqual(self.run_record([foreign],forbidden)['points'],0)
        self.assertEqual(self.memory.position_reads,0)
        self.assertFalse(list(self.folder.iterdir()))

    def test_changed_frame_or_identity_cannot_create_a_point(self):
        for change in ({'frame':151,'end_frame':151},{'object_id':32}):
            calls=[]
            def reader(m,t):
                value=copy.deepcopy(self.status)
                if calls:value.update(change)
                calls.append(True);return value
            self.assertEqual(self.run_record(reader=reader)['points'],0)
        self.assertFalse(list(self.folder.iterdir()))


if __name__=='__main__':unittest.main()
