import unittest
from land_surface import footprint_width,cell_denials


class Land(unittest.TestCase):
    def test_native_footprint_rounding_and_geometry_override(self):
        self.assertEqual(1,footprint_width(5,0))
        self.assertEqual(1,footprint_width(5,-1))
        self.assertEqual(2,footprint_width(12,0))
        self.assertEqual(1,footprint_width(12,10))
        with self.assertRaises(ValueError):footprint_width(float('nan'),0)
        with self.assertRaises(ValueError):footprint_width(5,-2)
        with self.assertRaises(ValueError):footprint_width(1000,1000)
    def test_empty_land_is_only_a_precondition_and_rejects_obstacles_flags_layers(self):
        def cell(flags=0x10,obj=0):return dict(cell_words=[obj,0,0,flags]+[0]*8)
        self.assertEqual([],cell_denials(cell(),1))
        for sample in (cell(obj=123),cell(flags=0x20),cell(flags=0x40010),cell(flags=0x11),cell(flags=0x12)):
            self.assertTrue(cell_denials(sample,1))
        self.assertTrue(cell_denials(cell(),3))
    def test_ground_mask_rejects_all_other_native_terrain_masks(self):
        for code in range(1,16):
            self.assertIn('native_terrain_mask_reject5',cell_denials(dict(cell_words=[0,0,0,0x10|code]+[0]*8),1))
    def test_actual_mask_source_is_locomotor_set_not_ignored_object_ids(self):
        import struct
        from test_compare_native import References
        from land_surface import EmptyLandReader,CONSTANTS,MASK_TABLE,CELL_GATE
        m,row=References().fixture();t=int(row['address'],0);u=int(row['ai_address'],0)
        for a,v in list(CONSTANTS.items())+[(t+0x120,0x40a00000),(0x80014,0xb0000),(0xb0110,0xbf800000),
                (u+0x180,353),(u+0x184,999),(u+0x1fc,0xc37620),(u+0x210,1)]:
            m.put(a,struct.pack('<I',v))
        m.put(0xcb122c,struct.pack('<11I',*MASK_TABLE));m.put(0x696fc0,CELL_GATE)
        value=EmptyLandReader(m).actor(t)
        self.assertEqual(1,value['mask']);self.assertEqual([353,999],value['ignored_object_words'])
        self.assertEqual(1,value['footprint_width']);self.assertEqual(-1,value['geometry_override'])
        m.put(u+0x1fc,struct.pack('<I',0))
        with self.assertRaises(ValueError):EmptyLandReader(m).actor(t)


if __name__=='__main__':unittest.main()
