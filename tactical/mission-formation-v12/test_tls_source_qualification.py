"""Current compiled scalar TLS proof is required, and grants no field ability."""
import unittest
from test_common_qualification import q

class TLSCompiledSource(unittest.TestCase):
 def test_actual_sealed_production_alignment_proof(self):
  a=q.tls_alignment_audit(dict(native_binary_sha256=q.sha(q.HERE/'bin/TacticalMissionFormation12.dll')));self.assertTrue(a['verified'],a);self.assertFalse(a['field_verified'])
 def test_old_unknown_or_wrong_binary_never_uses_the_repair_proof(self):
  for value in (None,'0'*64,'d23ab28b79e0436b038b86bc78d53f3b95da35d727663de435beca18adc95588'):
   self.assertFalse(q.tls_alignment_audit(dict(native_binary_sha256=value))['verified'])

if __name__=='__main__':unittest.main()
