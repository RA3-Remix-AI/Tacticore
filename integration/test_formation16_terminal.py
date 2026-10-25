"""Actual frozen hook signatures, synthetic terminal receipt; no game access."""
import copy
import json
from pathlib import Path
import re
import unittest
import continuous_evidence as evidence

class Formation16Terminal(unittest.TestCase):
 family='mission-formation-v8'
 hooks=16
 def fixture(self):
  folder=Path(__file__).resolve().parents[1]/'tactical'/self.family
  layout=json.loads((folder/'inert-layout.json').read_text())
  source=(folder/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
  hooks=re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',source)
  self.assertEqual(len(hooks),self.hooks)
  entries=[dict(address=address,expected=escaped.replace('\\x',''),actual=escaped.replace('\\x','')) for address,escaped,size in hooks]
  pre=dict(pid=1,commander_id='commander',owner='0x9000',logic='0xa000')
  request=dict(command_id='command',task_id='task',seq=1,token=2)
  terminal=dict(pid=1,session_id='session',commander_id='commander',**request,owner=pre['owner'],logic=pre['logic'],native_binary_sha256=layout['dll_sha256'],mutations=False,timer=0,active=0,restore_mask=(1<<self.hooks)-1,layout=layout,entries=entries)
  report=dict(preflight=pre,request=request,native={},session_id='session',native_binary_sha256=layout['dll_sha256'],terminal_readonly=terminal)
  facts=dict(report=report,control_release=dict(actors=[dict(role=i,object_id=10+i,released=True) for i in range(2)]))
  return facts,dict(executor_directory=self.family,object_ids=[10,11])

 def check(self,facts,entry):evidence.verify_formation_release(facts,entry,object())

 def test_all_sixteen_actual_signature_rows_are_required(self):
  facts,entry=self.fixture();self.check(facts,entry)
  for change in ('drop','duplicate','wrong_byte'):
   bad=copy.deepcopy(facts);rows=bad['report']['terminal_readonly']['entries']
   if change=='drop':rows.pop()
   elif change=='duplicate':rows[-1]=dict(rows[0])
   else:rows[-1]['actual']='00'
   with self.assertRaises(ValueError):self.check(bad,entry)

 def test_receipt_cannot_choose_legacy_restore_mask_or_hook_count(self):
  facts,entry=self.fixture();entry.update(restore_mask=8191,hook_count=13)
  facts['report']['terminal_readonly']['restore_mask']=8191
  with self.assertRaises(ValueError):self.check(facts,entry)

 def test_both_role_releases_remain_mandatory(self):
  facts,entry=self.fixture();facts['control_release']['actors'][1]['released']=False
  with self.assertRaises(ValueError):self.check(facts,entry)


class Formation9Terminal(Formation16Terminal):
 family='mission-formation-v9'


class Formation10Terminal(Formation16Terminal):
 family='mission-formation-v10'


class Formation12Terminal(Formation16Terminal):
 family='mission-formation-v12'
 hooks=17
