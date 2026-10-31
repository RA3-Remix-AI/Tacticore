import struct
import tempfile
from pathlib import Path
import unittest
from manifest import parse

class ManifestReader(unittest.TestCase):
    def fixture(self):
        header=[0]*12;header[3]=1;header[8]=8;header[10]=4;header[11]=2
        record=[11,22,33,44,0,1,0,0,12,8,4,0]
        return bytearray(struct.pack('<12I',*header)+struct.pack('<12I',*record)+struct.pack('<II',55,66)+b'foo\0'+b'x\0')
    def test_manifest_rows_have_exact_asset_references_and_stream_offsets(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mod.manifest';path.write_bytes(self.fixture());rows=parse(path)
            self.assertEqual(rows[0],dict(index=0,type_id=11,instance_id=22,type_hash=33,instance_hash=44,
                refs=[(55,66)],name='foo',source='x',binary_offset=4,binary_size=12,relo_offset=4,relo_size=8,
                imp_offset=4,imp_size=4,flags=0))
    def test_truncation_unterminated_names_and_reference_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mod.manifest'
            for kind in ('truncated','name','reference'):
                raw=self.fixture()
                if kind=='truncated':raw=raw[:-1]
                elif kind=='name':raw[-3]=1
                else:struct.pack_into('<I',raw,48+4*5,2)
                path.write_bytes(raw)
                with self.assertRaises(ValueError):parse(path)

if __name__=='__main__':unittest.main()
