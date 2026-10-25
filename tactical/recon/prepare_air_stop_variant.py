"""Isolated Twinblade Stop/Move scout experiment; offline build preparation only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'stop-move';OUT=ROOT.parent/'recon-air'
OUT.mkdir(exist_ok=True)
for name in ['shared.h','lease.cpp','host.cpp','lease.py','build.ps1']:
 text=(SOURCE/name).read_text(encoding='utf-8')
 for old,new in [('TacticalStopMove','TacticalAirScout'),('RA3TacticalStopMove','RA3TacticalAirScout'),('0x54534d31','0x41535231'),('WM_APP+0x36a','WM_APP+0x370')]:text=text.replace(old,new)
 if name=='lease.py':
  text=text.replace('[0x19ab11af,0x2c358c61]','[0x40acad6d]').replace('<=120 or not 30<=args.lease_frames<=180','<=600 or not 30<=args.lease_frames<=450')
  text=text.replace("report.update(native_binary_sha256=", "report.update(native_source_sha256=hashlib.sha256((HERE/'lease.cpp').read_bytes()).hexdigest(),native_shared_sha256=hashlib.sha256((HERE/'shared.h').read_bytes()).hexdigest(),experimental_scope='Twinblade_air_scout_only',native_binary_sha256=")
 if name=='lease.cpp':
  text=text.replace('(p->type_hash!=0x19ab11af&&p->type_hash!=0x2c358c61)','p->type_hash!=0x40acad6d').replace('p->lease_frames>180','p->lease_frames>450').replace('dx*dx+dy*dy>14400','dx*dx+dy*dy>360000').replace('0xc48670','0xc4e268').replace('0xc48528','0xc4e120')
 (OUT/name).write_text(text,encoding='utf-8')
for name in ['logic.py','probe.py']:
 text=(ROOT/name).read_text(encoding='utf-8')
 for old,new in [('TacticalReconProbe','TacticalAirScout'),('RA3ReconProbe','RA3TacticalAirScout'),('0x52454331','0x41535231')]:text=text.replace(old,new)
 if name=='logic.py':
  text=text.replace("'0x2c358c61':'flak'","'0x2c358c61':'flak','0x40acad6d':'air'").replace("not in (31,63)","not in (31,63,127,255)").replace("'move_and_return_primitive_verified'","'stop_move_and_return_primitive_verified'").replace("n.get('restore_mask')==31","n.get('restore_mask')==127")
 if name=='probe.py':
  text=text.replace("get('restore_mask')==31","get('restore_mask')==127")
  text=text.replace("signatures={0x6eff70:","signatures={0x54b0a0:'83ec5c8b442460566a01508bf1',0x721ad0:'83ec08558be98b45088b4804',0x6eff70:")
  text=text.replace("'kind':'independent_recon_calibration'","'kind':'independent_air_scout_calibration'")
 (OUT/name).write_text(text,encoding='utf-8')
print(OUT)
