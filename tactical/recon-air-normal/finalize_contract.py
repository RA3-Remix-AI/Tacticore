"""Offline one-time contract refinement before this namespace is ever loaded."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for name in ['shared.h','lease.cpp','host.cpp','lease.py','probe.py']:
 p=ROOT/name;t=p.read_text(encoding='utf-8').replace('RA3TacticalAirScoutNormalNormal','RA3TacticalAirScoutNormal')
 if name=='shared.h':t=t.replace('lease_frames,post_frames;','lease_frames,post_frames,expires_frame;')
 if name=='lease.cpp':
  t=t.replace('float xyz[3];read(p->unit+0x38,xyz,12);float dx=xyz[0]-p->target[0],dy=xyz[1]-p->target[1];\n  if(dx*dx', 'if(p->expires_frame&&(p->expires_frame<=now||p->expires_frame-now>900||p->lease_frames+2>p->expires_frame-now)){p->error=46;finish();return;}\n  float xyz[3];read(p->unit+0x38,xyz,12);float dx=xyz[0]-p->target[0],dy=xyz[1]-p->target[1];\n  if(dx*dx')
  t=t.replace('event(3);if(p->phase==1){float xyz[3];','event(3);if(p->phase==1){if(p->expires_frame&&now+2>=p->expires_frame)p->return_pending=1;float xyz[3];')
 if name=='lease.py':
  t=t.replace('lease_frames post_frames\'.split()', 'lease_frames post_frames expires_frame\'.split()')
  t=t.replace("ap.add_argument('--output',type=Path);", "ap.add_argument('--expires-frame',type=int,default=0);ap.add_argument('--output',type=Path);")
  t=t.replace("layout=json.loads(subprocess.check_output", "if args.expires_frame and not pre['frame']+args.lease_frames+2<=args.expires_frame<=pre['frame']+900:raise ValueError('native_original_expiry_bounds')\n layout=json.loads(subprocess.check_output")
  t=t.replace("arrival_radius=15))", "arrival_radius=15,object_id=pre['selected']['object_id'],expires_frame=args.expires_frame))")
  t=t.replace('s.post_frames=args.post_frames;', 's.post_frames=args.post_frames;s.expires_frame=args.expires_frame;')
  t=t.replace("report['native']['target']=list(shared.target);", "report['native'].update(lease_frames=shared.lease_frames,expires_frame=shared.expires_frame);report['native']['target']=list(shared.target);")
  t=t.replace("checks['monotonic_frame_log']=", "checks['original_expiry_preserved']=not request.get('expires_frame') or native.get('expires_frame')==request['expires_frame'] and returned<=request['expires_frame']\n checks['monotonic_frame_log']=")
 p.write_text(t,encoding='utf-8')
print('Contract refined; rebuild binary and verify layout before any SDK use.')
