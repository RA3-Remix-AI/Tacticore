"""One-shot creation of an isolated, calibration-only regular ground Move facade probe."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=HERE.parent/'recon-air-normal';target=HERE.parent/'ground-normal-aux'
target.mkdir(exist_ok=False)
for name in ('lease.cpp','shared.h','host.cpp','lease.py','build.ps1'):
 text=(source/name).read_text(encoding='utf-8-sig')
 for old,new in [('TacticalAirScoutNormal','TacticalGroundNormalAux'),('RA3TacticalAirScoutNormal','RA3TacticalGroundNormalAux'),('0x41534e31','0x474e4131'),('WM_APP+0x371','WM_APP+0x375'),('0x40acad6d','0x19ab11af'),('0xc4e268','0xc48670'),('0xc4e120','0xc48528'),('Twinblade_air_scout_only','calibration_conscript_ground_move_only')]:text=text.replace(old,new)
 (target/name).write_text(text,encoding='utf-8')
print(target)
