import hashlib,json,tempfile,unittest
from pathlib import Path
from session_package import verify_session_package

class PackageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.big=self.root/'named.big';self.big.write_bytes(b'package');self.config=self.root/'named.skudef';self.config.write_text('mod-game 1.12\nadd-big named.big\n');self.session=dict(mod_config=str(self.config),mod_sha256=hashlib.sha256(b'package').hexdigest())
 def tearDown(self):self.tmp.cleanup()
 def test_explicit_package(self):self.session['mod_big']=str(self.big);self.assertEqual(verify_session_package(self.session),self.big)
 def test_unique_adjacent_package(self):self.assertEqual(verify_session_package(self.session),self.big)
 def test_quoted_modconfig_argument(self):self.session['arguments']='-ui -modConfig "'+str(self.session.pop('mod_config'))+'"';self.assertEqual(verify_session_package(self.session),self.big)
 def test_traversal_rejected(self):self.config.write_text('add-big ../other.big');self.assertRaisesRegex(RuntimeError,'adjacent',verify_session_package,self.session)
 def test_multiple_packages_rejected(self):self.config.write_text('add-big named.big\nadd-big another.big');self.assertRaisesRegex(RuntimeError,'exactly one',verify_session_package,self.session)
 def test_nested_derived_package_rejected(self):self.config.write_text('add-big nested/named.big');self.assertRaisesRegex(RuntimeError,'adjacent',verify_session_package,self.session)
 def test_hash_mismatch_rejected(self):self.session['mod_sha256']='0'*64;self.assertRaisesRegex(RuntimeError,'Mod changed',verify_session_package,self.session)

if __name__=='__main__':unittest.main()
