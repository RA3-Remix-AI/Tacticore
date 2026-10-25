import unittest
from audit_templates import classify_role
class RoleTests(unittest.TestCase):
 def test_exact_refinery_with_inherited_structure_and_required_function(self):
  role,physical,e=classify_role('SovietRefinery',{'STRUCTURE','SELECTABLE','REFINERY','SUPPLY_GATHERING_CENTER'})
  self.assertEqual((role,physical),('economy','structure'));self.assertEqual(e['classification_revision'],'exact_soviet_refinery_v1')
 def test_other_structure_is_not_economy(self):
  self.assertEqual(classify_role('SovietBarracks',{'STRUCTURE','SELECTABLE'})[0],'structure')
  self.assertEqual(classify_role('UnknownRefinery',{'STRUCTURE','REFINERY','SUPPLY_GATHERING_CENTER'})[0],'structure')
 def test_missing_required_function_fails_to_structure(self):
  for kinds in [{'STRUCTURE','REFINERY'},{'STRUCTURE','SUPPLY_GATHERING_CENTER'}]:self.assertEqual(classify_role('SovietRefinery',kinds)[0],'structure')
if __name__=='__main__':unittest.main()
