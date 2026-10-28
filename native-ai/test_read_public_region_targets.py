import struct
import unittest
from read_public_region_targets import lookup_public

class PublicRegionLookupTests(unittest.TestCase):
    def memory(self,names):
        chunks={0xce8f64:struct.pack('<I',0x10000)}
        for i,name in enumerate(names):
            node=0x10000+i*0x100;string=0x20000+i*0x100
            chunks[string-4]=struct.pack('<H',len(name));chunks[string]=name.encode()
            raw=bytearray(32);struct.pack_into('<I',raw,8,string)
            struct.pack_into('<fff',raw,12,*([1.,2.,3.] if name.startswith('Player_') else [float('nan')]*3))
            struct.pack_into('<I',raw,28,node+0x100 if i+1<len(names) else 0);chunks[node]=bytes(raw)
        def read(at,size):
            for start,raw in chunks.items():
                if start<=at and at+size<=start+len(raw):return raw[at-start:at-start+size]
            raise RuntimeError('unmapped_test_read')
        return read,chunks

    def test_only_two_public_markers_exported_other_coordinates_not_decoded(self):
        read,_=self.memory(['Other_location','Player_1_Start','Player_2_Start'])
        value=lookup_public(read,{'Player_1_Start','Player_2_Start'})
        self.assertTrue(value['all_public_markers_found']);self.assertEqual(len(value['public_markers']),2)
        self.assertEqual(value['visited_marker_count'],3)

    def test_missing_public_marker_is_explicit(self):
        read,_=self.memory(['Player_1_Start'])
        self.assertFalse(lookup_public(read,{'Player_1_Start','Player_2_Start'})['all_public_markers_found'])

    def test_cycles_and_duplicate_public_names_are_rejected(self):
        read,chunks=self.memory(['Player_1_Start']);raw=bytearray(chunks[0x10000]);struct.pack_into('<I',raw,28,0x10000);chunks[0x10000]=bytes(raw)
        with self.assertRaisesRegex(ValueError,'list_bound'):lookup_public(read,{'Player_1_Start','Player_2_Start'})
        read,_=self.memory(['Player_1_Start','Player_1_Start'])
        with self.assertRaisesRegex(ValueError,'duplicate_public'):lookup_public(read,{'Player_1_Start','Player_2_Start'})

    def test_arbitrary_map_marker_cannot_be_requested(self):
        read,_=self.memory(['Player_1_Start','Player_2_Start'])
        with self.assertRaisesRegex(ValueError,'two_public_names'):lookup_public(read,{'Other_location'})

if __name__=='__main__':unittest.main()
