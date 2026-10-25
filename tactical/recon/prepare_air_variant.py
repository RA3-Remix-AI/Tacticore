"""Build an isolated experimental air-only namespace; never controls the game."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT.parent/'recon-air'
OUT.mkdir(exist_ok=False)
for name in ['shared.h','lease.cpp','host.cpp','lease.py','build.ps1','logic.py','probe.py']:
 text=(ROOT/name).read_text(encoding='utf-8')
 for old,new in [('TacticalReconProbe','TacticalAirReconProbe'),('TacticalReconControl','TacticalAirReconControl'),('RA3ReconProbe','RA3AirReconProbe'),('0x52454331','0x52454131'),('WM_APP+0x367','WM_APP+0x36b')]:text=text.replace(old,new)
 if name=='lease.py':
  text=text.replace('[0x19ab11af,0x2c358c61]','[0x40acad6d]')
 if name=='lease.cpp':
  needle='static void install(HWND hwnd){'
  if needle not in text:raise ValueError('install_guard_site_changed')
  text=text.replace(needle,needle+'if(p->type_hash!=0x40acad6d){p->error=10;p->phase=4;return;}')
 (OUT/name).write_text(text,encoding='utf-8')
print(OUT)
