"""Pure-memory identity checks; never opens or modifies a game process."""
import copy,struct,unittest
from read_selected_personality import inspect_player,resolve_registry

class SelectedPersonalityTests(unittest.TestCase):
    def setUp(self):
        self.player=0x10000;self.ai=0x30000;self.wrapper=0x50000;self.data=0x60000
        self.words={self.player:0xc5bce0,self.player+0x20:3,self.player+0x10:0x20000,self.player+0x90:self.ai,
                    self.ai:0xc60f60,self.ai+8:self.player,self.ai+0x8a8:self.player,self.ai+0x8b0:self.wrapper,
                    0xce98ec:0x40000,0x40000:0xc606b8,0x40024:0x80000,0x40028:0x80004,
                    0x80000:self.wrapper,self.wrapper:self.data,self.wrapper+0x18:0x123abc,
                    self.data+0xec:1,self.data+0xf0:0x70000,0x70000:0x20000}
    def read(self,address,length):
        return b''.join(struct.pack('<I',self.words[address+offset]) for offset in range(0,length,4))
    def test_valid_chain(self):
        row=inspect_player(self.read,self.player)
        self.assertEqual(row['instance_id'],'0x123abc');self.assertTrue(row['store_membership_verified'])
    def test_unregistered_personality_rejected(self):
        self.words[0x80000]=0x50010
        with self.assertRaisesRegex(ValueError,'not uniquely registered'):inspect_player(self.read,self.player)
    def test_owner_mismatch_rejected(self):
        self.words[self.ai+0x8a8]=0x99999
        with self.assertRaisesRegex(ValueError,'owner links'):inspect_player(self.read,self.player)
    def test_wrong_side_rejected(self):
        self.words[0x70000]=0x20001
        with self.assertRaisesRegex(ValueError,'Side does not match'):inspect_player(self.read,self.player)
    def test_registry_requires_exact_package(self):
        native=inspect_player(self.read,self.player)
        registry=dict(identity_revision='a',registry_revision='b',compiled_ids_verified=True,package_sha256='abc',commanders=[dict(id='uuid',name='Name',connection_id='conn',assets=[dict(instance_id='0x123abc',asset_id='asset',side='Japan')])])
        self.assertFalse(resolve_registry(native,registry,dict(mod_sha256='def'))['personality_binding_verified'])
        verified=resolve_registry(native,registry,dict(mod_sha256='abc'))
        self.assertTrue(verified['personality_binding_verified']);self.assertFalse(verified['game_sync_verified'])
        duplicate=copy.deepcopy(registry);duplicate['commanders'].append(copy.deepcopy(registry['commanders'][0]))
        with self.assertRaisesRegex(ValueError,'unique commander'):resolve_registry(native,duplicate,dict(mod_sha256='abc'))
if __name__=='__main__':unittest.main(verbosity=2)
