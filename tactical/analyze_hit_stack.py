"""Offline native call-site extraction from own visible-hit traces. Never attaches."""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent
sys.path.insert(0,str(BRIDGE/'reference/Ra3-Copilot/ra3-copilot/tools'))
from precheck_aob import parse_pe,rva_to_off
EXPECTED='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
def analyze(report_path):
 report=json.loads(report_path.read_text(encoding='utf-8-sig'));game=Path(r'E:\RedRar3\Data\RA3_1.12.game');data=game.read_bytes()
 if hashlib.sha256(data).hexdigest()!=EXPECTED or report['executable_sha256']!=EXPECTED:raise ValueError('unsupported_executable')
 base,size,sections=parse_pe(data);rows=[]
 for event in report['events']:
  if event['kind'] not in [20,21,24,25]:continue
  row=dict(frame=event['frame'],source=event['damage_source'],target=event['target_id'],hp_before=event['damage_before'],hp_after=event['damage_after'],damage=event['damage_reported'],kind=event['kind'],call_sites=[])
  addresses=list(dict.fromkeys([event['caller']]+event.get('stack',[])[:event.get('stack_count',0)]+event.get('stack_words',[])[:event.get('stack_word_count',0)]))
  for ret in addresses:
   if not 0x401000<=ret<0xbc7000:continue
   try:off=rva_to_off(ret-base,sections)
   except (ValueError,KeyError,RuntimeError):continue
   call=None
   if off>=5 and data[off-5]==0xe8:call=ret+struct.unpack('<i',data[off-4:off])[0]
   if call is None and ret!=event['caller']:continue
   snippet=subprocess.check_output([str(BRIDGE/'toolchain/w64devkit/bin/objdump.exe'),'-d','--start-address='+hex(max(0x401000,ret-72)),'--stop-address='+hex(ret+40),str(game)],text=True)
   row['call_sites'].append(dict(return_address=hex(ret),direct_call_target=hex(call) if call else None,preceding_bytes=data[max(0,off-8):off].hex(),disassembly=snippet))
  rows.append(row)
 return dict(source_report=str(report_path.resolve()),source_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),executable_sha256=EXPECTED,mutations=False,hits=rows,note='Stack return addresses and direct call sites only. Function boundaries, this pointers and ABI still require independent disassembly review.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('report',type=Path);args=ap.parse_args();result=analyze(args.report);target=args.report.with_name(args.report.stem+'-hit-stack-analysis.json');target.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(dict(output=str(target),hits=len(result['hits']))))
