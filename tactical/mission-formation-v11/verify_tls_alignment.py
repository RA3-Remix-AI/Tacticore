"""Seal actual compiled TLS scalar code and real offset-eight regression; no game access."""
from pathlib import Path
import hashlib,json,re,struct,subprocess
H=Path(__file__).resolve().parent;TOOL=H.parent.parent/'toolchain/w64devkit/bin'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
dll=H/'bin/TacticalMissionFormation11.dll';data=dll.read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];optional=pe+24;base=struct.unpack_from('<I',data,optional+28)[0]
sections=[];n=struct.unpack_from('<H',data,pe+6)[0];section_start=optional+struct.unpack_from('<H',data,pe+20)[0]
for i in range(n):
 o=section_start+i*40;sections.append(struct.unpack_from('<IIII',data,o+8)) # vsize,rva,rawsize,rawptr
def file_offset(va):
 rva=va-base
 for vs,rs,size,ptr in sections:
  if rs<=rva<rs+size:return ptr+rva-rs
 raise ValueError('instruction_not_in_file')
text=subprocess.check_output([str(TOOL/'objdump.exe'),'-d',str(dll)],text=True)
families=['load_dispatch_words','store_dispatch_words','set_dispatch_words','clear_dispatch_words','load_move_context','store_move_context','set_move_context','clear_move_context','restore_move_context'];families.remove('store_move_context')
blocks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\s*$',text);rows=[];dump=[];byte_count=0
for i in range(1,len(blocks),3):
 address,symbol,body=blocks[i:i+3]
 if not any(name in symbol for name in families):continue
 instructions=[]
 for line in body.splitlines():
  m=re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)(.*)',line)
  if not m:continue
  at=int(m[1],16);raw=bytes.fromhex(m[2]);off=file_offset(at)
  if data[off:off+len(raw)]!=raw:raise ValueError('objdump_bytes_not_actual_dll')
  byte_count+=len(raw);instructions.append(dict(rva=at-base,bytes=raw.hex(),assembly=m[3].strip()))
 rows.append(dict(symbol=symbol,address_rva=int(address,16)-base,instructions=instructions));dump.append(address+' <'+symbol+'>:\n'+body)
out=H/'tls-accessors-disassembly.txt';out.write_text('\n'.join(dump),encoding='utf-8')
test=H/'tls-alignment-regression.json';r=json.loads(test.read_text());pending=H/'pending.cpp.inc';source=pending.read_text();revision=H/'revision.json';rev=json.loads(revision.read_text())
checks=dict(actual_dll_bytes_match=byte_count>0,all_eight_accessor_families=all(any(name in row['symbol'] for row in rows) for name in families),no_aligned_simd_tls_access=not re.search(r'\b(?:v?movaps|v?movdqa)\b',out.read_text()),true_volatile_native_tls='static __thread volatile uint32_t move_context_words[4]' in source,no_aggregate_tls_access=not re.search(r'\bmove_context\s*[.=]',source),actual_offset_eight=r.get('passed') is True and r.get('buffer_mod16')==8 and r.get('buffer_mod4')==0 and r.get('context_bytes')==16,actual_begin_and_prior_restore=r.get('begin_and_restore') is True,actual_thread_isolation=r.get('actual_thread_isolation') is True and r.get('main_tls_address')!=r.get('worker_tls_address'),fifteen_real_cases=r.get('cases',0)>=15,no_game_or_sdk=r.get('game_access') is False and r.get('sdk_calls')==0,compiled_joint_dll=rev['native_binary_sha256']==sha(dll),compiled_joint_pending=rev['native_includes_sha256']['pending.cpp.inc']==sha(pending))
if not all(checks.values()):raise ValueError(str(checks))
proof=dict(protocol='mfm10_actual_compiled_tls_scalar_alignment_v1',native_binary_sha256=sha(dll),pending_source_sha256=sha(pending),source_file='pending.cpp.inc',regression_source_sha256=sha(H/'test_tls_alignment_native.cpp'),regression_binary_sha256=sha(H/'bin/test_tls_alignment_native.exe'),regression_report_sha256=sha(test),disassembly_sha256=sha(out),verifier_sha256=sha(__file__),checks=checks,functions=rows,actual_instruction_bytes_verified=byte_count,field_verified=False,sdk_calls=0)
path=H/'tls-alignment-proof.json';path.write_text(json.dumps(proof,indent=2),encoding='utf-8');rev['tls_alignment_proof_sha256']=sha(path);revision.write_text(json.dumps(rev,indent=2),encoding='utf-8');print(json.dumps(dict(checks=len(checks),functions=len(rows),instruction_bytes=byte_count,proof_sha256=sha(path),revision_sha256=sha(revision),field_verified=False)))
