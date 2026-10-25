"""Reproduce the native-only engine-free regression; never a game capability proof."""
from pathlib import Path
import hashlib,json,subprocess
H=Path(__file__).resolve().parent
common=(H/'common.cpp.inc').read_text();a=common.index('static void normal_return()');b=common.index('static void request_cleanup',a)
expected='// Actual common normal_return, only Transfer facade replaced by in-memory fake.\n'+common[a:b].replace('((Transfer)0x838820)','fake_transfer')
assert (H/'test_return_fixture.inc').read_text()==expected
out=subprocess.check_output([str(H/'bin/test_breadcrumb_native.exe'),str(H/'simulation-2km-native.json')],text=True)
rows=[json.loads(line) for line in out.splitlines() if line.strip()];sim,tests=rows
checks=dict(no_game_access=tests['game_access'] is False and tests['sdk_calls']==0,all_39_cases=tests['passed'] is True and tests['cases']>=39,original_normal_return_extracted=True,forward_budget=sim['forward_frames']<=2100,retreat_budget=sim['retreat_frames']<=1800,total_original_deadline=sim['forward_frames']+sim['retreat_frames']<=4500,phase_regroup_bounds=sim['forward_regroups']<=8 and sim['retreat_regroups']<=8,global_regroup_bound=sim['forward_regroups']+sim['retreat_regroups']<=16,min_physical_gap=sim['min_actual_gap']>=25,min_source_goal_clearance=sim['min_source_goal_clear']>=25,both_original_home_arrivals=sim['home_arrivals']==[3,3])
r=dict(scope='pure_cpp_native_function_regression_not_field',checks=checks,simulation=sim,cases=tests,source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [H/'test_breadcrumb_native.cpp',H/'test_return_fixture.inc',H/'common.cpp.inc',H/'breadcrumb.cpp.inc',H/'bin/test_breadcrumb_native.exe']},capability_granted=False)
(H/'native-software-regression.json').write_text(json.dumps(r,indent=2),encoding='utf-8');assert all(checks.values());print(json.dumps(dict(checks_passed=len(checks),cases=tests['cases'],capability_granted=False)))
