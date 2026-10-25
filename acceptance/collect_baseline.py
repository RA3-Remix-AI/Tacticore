"""Read-only sampling of the owned session; not proof of queue/cost/production."""
import argparse,collections,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--samples',type=int,default=6);ap.add_argument('--interval',type=float,default=3)
    args=ap.parse_args()
    if not 1<=args.samples<=30 or not .5<=args.interval<=30:raise ValueError('Sampling bounds')
    session=json.loads((ROOT/'acceptance/active-session.json').read_text(encoding='utf-8-sig'))
    out=Path(session['run_directory']);out.mkdir(parents=True,exist_ok=True)
    previous=None;entries=[];started=time.monotonic()
    for index in range(args.samples):
        begin=time.monotonic()
        result=subprocess.run([sys.executable,str(ROOT/'probe.py'),'--pid',str(session['pid'])],capture_output=True,text=True,encoding='utf-8',timeout=30,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
        if result.returncode:raise RuntimeError('Readonly probe failed: '+result.stderr[:200])
        reference=json.loads(result.stdout.strip());snapshot=Path(reference['report']);data=json.loads(snapshot.read_text(encoding='utf-8'))
        if data['pid']!=session['pid']:raise RuntimeError('Session mismatch')
        counts=collections.Counter();current={};objects=[]
        for candidate in data['candidates']:
            catalog=candidate['catalog']
            if not catalog:continue
            counts[str(candidate['owner_index_candidate'])+':'+str(catalog['cls'])]+=1
            identity=(candidate['address'],candidate['owner_address'],candidate['type_hash'])
            current[identity]=candidate
            if previous is not None and identity not in previous:objects.append(candidate)
        record=dict(sample_index=index,elapsed_wall_seconds=round(time.monotonic()-started,3),snapshot=str(snapshot),snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),known_object_counts=dict(counts),appearance_candidates=objects)
        entries.append(record)
        (out/'baseline-observations.json').write_text(json.dumps(dict(session=session,evidence_kind='read_only_partial_object_samples',samples=entries,queue_verified=False,cost_verified=False,production_verified=False,note='Appearance is not production: first observation, address reuse, death and catalog gaps confound it. No runtime strategy change was performed.'),ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(sample=index,known_objects=len(current),new_appearances=len(objects))),flush=True)
        previous=current
        if index+1<args.samples:time.sleep(max(0,args.interval-(time.monotonic()-begin)))

if __name__=='__main__':main()
