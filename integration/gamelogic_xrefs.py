"""Static, read-only PE xref inventory for the version-pinned GameLogic global."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
GAME=Path(r'E:\RedRar3\Data\RA3_1.12.game')
raw=GAME.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
pe=struct.unpack_from('<I',raw,0x3c)[0]
nsections=struct.unpack_from('<H',raw,pe+6)[0]
optsize=struct.unpack_from('<H',raw,pe+20)[0]
base=struct.unpack_from('<I',raw,pe+24+28)[0]
sections=pe+24+optsize
addresses=[]
for i in range(nsections):
 p=sections+i*40
 if raw[p:p+8].rstrip(b'\0')!=b'.text':continue
 size,rva,filesize,offset=struct.unpack_from('<IIII',raw,p+8)
 chunk=raw[offset:offset+filesize];cursor=0
 while True:
  at=chunk.find(struct.pack('<I',0xcd8ce4),cursor)
  if at<0:break
  addresses.append(base+rva+at);cursor=at+4
objdump=ROOT.parent/'toolchain/w64devkit/bin/objdump.exe'
ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=80);args=ap.parse_args()
if not 0<=args.limit<=5000:raise ValueError('limit out of range')
(ROOT/'gamelogic-xrefs.json').write_text(json.dumps({'global':'0xcd8ce4','references':[hex(a) for a in addresses],'note':'Static operand occurrences, not proven GameLogic calls or live game time.'},indent=2),encoding='utf-8')
out=ROOT/'gamelogic-xrefs.txt'
with out.open('w',encoding='utf-8') as log:
 for a in addresses[:args.limit]:
  r=subprocess.run([str(objdump),'-d','-M','intel',f'--start-address={a-8}',f'--stop-address={a+64}',str(GAME)],capture_output=True,text=True,check=True)
  log.write(r.stdout)
(ROOT/'gamelogic-xrefs.json').write_text(json.dumps({'global':'0xcd8ce4','references':[hex(a) for a in addresses],'note':'Static operand occurrences, not proven GameLogic calls or live game time.'},indent=2),encoding='utf-8')
print(json.dumps({'references':len(addresses),'output':str(out)}))
