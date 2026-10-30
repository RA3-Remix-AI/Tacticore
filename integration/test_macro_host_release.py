"""Release proof must cover exactly this transport's flags and identity."""
import copy
from types import SimpleNamespace
import unittest
from macro_host import native_release_matches

class MacroReleaseTests(unittest.TestCase):
    def setUp(self):
        self.flags=['flag_'+str(i) for i in range(20)]
        self.binding=SimpleNamespace(session_id='session',game_process_id=12,mod_sha256='a'*64)
        self.session=dict(process_creation_filetime=123)
        self.final=dict(session_id='session',pid=12,process_creation_filetime=123,mod_sha256='a'*64,
            cleanup_verified=True,host_returncode=0,unknown_command_ids=[],
            native=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0),
            independent_flags=dict(flags=[dict(name=f,present=True,value=False) for f in self.flags]))
    def verify(self):return native_release_matches(self.final,self.session,self.binding,self.flags)
    def test_twenty_and_legacy_thirteen_exact_flags(self):
        self.assertTrue(self.verify())
        self.flags=self.flags[:13];self.final['independent_flags']['flags']=self.final['independent_flags']['flags'][:13]
        self.assertTrue(self.verify())
    def test_subset_duplicate_and_replaced_flags_refused(self):
        for mode in ('subset','duplicate','other'):
            with self.subTest(mode=mode):
                value=copy.deepcopy(self.final)
                if mode=='subset':value['independent_flags']['flags']=value['independent_flags']['flags'][:13]
                elif mode=='duplicate':value['independent_flags']['flags'][0]['name']=self.flags[1]
                else:value['independent_flags']['flags'][0]['name']='foreign_flag'
                self.assertFalse(native_release_matches(value,self.session,self.binding,self.flags))
    def test_all_scalar_native_states_require_exact_ints(self):
        for key in self.final['native']:
            with self.subTest(key=key):
                value=copy.deepcopy(self.final);value['native'][key]=bool(value['native'][key])
                self.assertFalse(native_release_matches(value,self.session,self.binding,self.flags))
    def test_unknown_commands_identity_or_live_lease_block(self):
        for change in ({'unknown_command_ids':['unknown']},{'pid':13},{'process_creation_filetime':124},
                       {'session_id':'other'},{'host_returncode':False}):
            value=dict(self.final,**change)
            self.assertFalse(native_release_matches(value,self.session,self.binding,self.flags))
        self.final['native']['lease_held']=1;self.assertFalse(self.verify())
    def test_absent_flags_valid_but_malformed_present_or_positive_flag_refused(self):
        self.final['independent_flags']['flags'][0]=dict(name=self.flags[0],present=False,value=None)
        self.assertTrue(self.verify())
        self.final['independent_flags']['flags'][0]['present']=0;self.assertFalse(self.verify())
        self.final['independent_flags']['flags'][0].update(present=True,value=True);self.assertFalse(self.verify())

if __name__=='__main__':unittest.main()
