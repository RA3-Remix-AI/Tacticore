"""Run frozen formation test modules in fresh processes to prevent name collisions.

These suites use fake kernels, children and native-function simulations. This
runner never invokes a game host, an execution CLI or a model endpoint.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('version',choices=('5','6'))
 args=parser.parse_args()
 folder=Path(__file__).resolve().parents[1]/('mission-formation-v'+args.version)
 total=0
 modules=[]
 for path in sorted(folder.glob('test_*.py')):
  result=subprocess.run([sys.executable,'-m','unittest',path.stem,'-q'],cwd=folder,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
  output=result.stdout+result.stderr
  if result.returncode:
   print(output[-8000:],file=sys.stderr)
   raise SystemExit(result.returncode)
  count=re.search(r'Ran (\d+) tests?',output)
  if not count:raise RuntimeError('Missing unittest result: '+path.name)
  total+=int(count[1]);modules.append(path.name)
 print(json.dumps(dict(version=args.version,modules=modules,test_count=total,status='passed',real_game_commands=0,real_model_requests=0)))

if __name__=='__main__':main()
