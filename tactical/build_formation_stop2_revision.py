from pathlib import Path
root=Path('bridge-probe/tactical');out=root/'formation-stop-v2';out.mkdir(exist_ok=True)
for name in ['shared.h','lease.cpp','lease.py','host.cpp','build.ps1']:
 s=(root/'formation-stop'/name).read_text().replace('TacticalFormationStop','TacticalFormationStop2').replace('RA3TacticalFormationStop','RA3TacticalFormationStop2').replace('tactical-formation-stop-','tactical-formation-stop2-')
 if name=='shared.h':
  s=s.replace('0x46535431u','0x46535432u').replace('0x36d','0x36f').replace('float min_spacing,max_spacing;', 'uint32_t last_goal_frame;float min_spacing,max_spacing;')
 if name=='lease.cpp':
  s=s.replace('p->version!=3','p->version!=4').replace('if(p->stage==1){bool held=', 'if(now==p->last_goal_frame)return;p->last_goal_frame=now;\n  if(p->stage==1){bool held=')
 if name=='lease.py':
  s=s.replace("overflow paused_samples return_pending'.split()", "overflow paused_samples return_pending last_goal_frame'.split()")
  s=s.replace('s.magic=0x46535431;s.version=3','s.magic=0x46535432;s.version=4')
  s=s.replace('  good=[];holds=[];', "  pairs=[pair for index,pair in enumerate(pairs) if index==0 or pair[0]['frame']!=pairs[index-1][0]['frame']]\n  good=[];holds=[];")
  s=s.replace("  # Pair consecutive same-tick timer samples;", "  sys.path.insert(0,str(HERE.parent));from stop_sequence import settled_stop\n  for i,u in enumerate(units):checks['unit_'+str(i)+'_stable_stop_raw']=settled_stop(events,u['id'])['verified']\n  # Pair consecutive same-tick timer samples;")
 (out/name).write_text(s)
