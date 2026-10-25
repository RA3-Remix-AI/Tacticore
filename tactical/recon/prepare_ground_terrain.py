"""Independent revision: preserve real observed ground goal Z across legal slopes."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=HERE.parent/'ground-normal-aux';target=HERE.parent/'ground-normal-terrain-aux'
target.mkdir(exist_ok=False)
for name in ('lease.cpp','shared.h','host.cpp','lease.py','build.ps1','test_boundary.py'):
 text=(source/name).read_text(encoding='utf-8-sig')
 for old,new in [('TacticalGroundNormalAux','TacticalGroundNormalTerrainAux'),('RA3TacticalGroundNormalAux','RA3TacticalGroundNormalTerrainAux'),('0x474e4131','0x47544e31'),('WM_APP+0x375','WM_APP+0x376'),('calibration_conscript_ground_move_only','calibration_ground_conscript_true_observed_height')]:text=text.replace(old,new)
 if name=='lease.cpp':text=text.replace('fabsf(xyz[2]-p->target[2])>2','fabsf(xyz[2]-p->target[2])>300||!isfinite(xyz[0])||!isfinite(xyz[1])||!isfinite(xyz[2])||!isfinite(p->target[0])||!isfinite(p->target[1])||!isfinite(p->target[2])')
 if name=='lease.py':
  text=text.replace("abs(xyz[2]-pre['selected']['xyz'][2])>2","abs(xyz[2]-pre['selected']['xyz'][2])>300")
  old="pre['selected']['xyz'][0]+args.dx,pre['selected']['xyz'][1]+args.dy,pre['selected']['xyz'][2]"
  assert text.count(old)==2
  text=text.replace(old,"pre['selected']['xyz'][0]+args.dx,pre['selected']['xyz'][1]+args.dy,point['xyz'][2]")
 if name=='test_boundary.py':text=text.replace("['xyz'][2]=240","['xyz'][2]=600")
 (target/name).write_text(text,encoding='utf-8')
print(target)
