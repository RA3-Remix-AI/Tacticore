"""Finite calibration-only chain; a native terminal is mandatory before each next lease."""
import argparse,hashlib,json,subprocess,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--natural',type=Path,required=True);p.add_argument('--object-id',type=int,required=True);p.add_argument('--point-report',type=Path,action='append',required=True);p.add_argument('--point-object-id',type=int,action='append',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute or not 1<=len(a.point_report)<=6 or len(a.point_report)!=len(a.point_object_id):raise ValueError('explicit_finite_calibration_chain_required')
 if a.output.exists():raise ValueError('existing_chain_report')
 raw=a.session.read_bytes();s=json.loads(raw.decode('utf-8-sig'));report=dict(calibration_id=str(uuid.uuid4()),session_id=s['session_id'],pid=s['pid'],object_id=a.object_id,scope='calibration_only_no_model_purpose',model_requests=0,started=time.time(),status='running',steps=[]);write(a.output,report)
 for index,(point,point_id) in enumerate(zip(a.point_report,a.point_object_id)):
  if a.session.read_bytes()!=raw:raise ValueError('session_changed')
  target=a.output.with_name(a.output.stem+'-move'+str(index+1)+'.json');log=target.with_suffix('.controller.log')
  args=[sys.executable,str(HERE.parent/'ground-normal-terrain-aux/lease.py'),'--session',str(a.session),'--natural',str(a.natural),'--object-id',str(a.object_id),'--known-point-report',str(point),'--known-point-object-id',str(point_id),'--lease-frames','450','--post-frames','30','--output',str(target),'--execute']
  with log.open('w',encoding='utf-8') as f:child=subprocess.run(args,stdout=f,stderr=f)
  result=json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else {};native=result.get('native',{});request=result.get('request',{})
  step=dict(report=str(target.resolve()),sha256=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None,controller_exit=child.returncode,native=native,request=request);report['steps'].append(step);write(a.output,report)
  safe=native.get('phase')==3 and native.get('error')==0 and native.get('restore_mask')==255 and native.get('active')==0 and native.get('return_verified')==1 and native.get('arrival_samples',0)>=3 and result.get('host_exit')==0
  if not safe:report.update(status='stopped_on_unverified_move',finished=time.time());write(a.output,report);print(json.dumps(dict(report=str(a.output),status=report['status'],last_native=native)));return
 target=a.output.with_name(a.output.stem+'-economy.json');log=target.with_suffix('.controller.log')
 args=[sys.executable,str(HERE/'calibrate_attack.py'),'--session',str(a.session),'--natural',str(a.natural),'--object-id',str(a.object_id),'--backend','ordered-attack','--economy','--ak-only','--seconds','1','--max-distance','350','--post-frames','30','--output',str(target)]
 with log.open('w',encoding='utf-8') as f:child=subprocess.run(args,stdout=f,stderr=f)
 result=json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else {};report.update(status='attack_probe_complete' if target.exists() else 'no_attack_dispatch',attack_report=str(target.resolve()) if target.exists() else None,attack_controller_exit=child.returncode,attack_native=result.get('native'),attack_assessment=result.get('assessment'),finished=time.time());write(a.output,report);print(json.dumps(dict(report=str(a.output),status=report['status'],assessment=result.get('assessment'))))
if __name__=='__main__':main()
