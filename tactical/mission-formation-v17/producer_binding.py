"""Read-only running-producer identity and five installed entry observations."""
import ctypes as c,hashlib,importlib.util,re,struct,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def entries():
 source=(ROOT/'production/persistent/executor.cpp').read_text();block=source.split('static Hook hooks[]={',1)[1].split(';',1)[0]
 rows=[]
 for address,escaped,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block):
  rows.append(dict(address=address,expected=escaped.replace('\\x',''),length=int(length)))
 if len(rows)!=5 or len({r['address'] for r in rows})!=5:raise ValueError('producer_five_hook_source')
 return rows

def loaded_entries(memory):
 helper=module('mf17_producer_module_ro',ROOT/'tactical/readonly_disposal.py');path=ROOT/'production/persistent/bin-v2/ProductionPersistent.dll';base=helper.module_base(memory,path)
 if memory.read(base,2)!=b'MZ':raise ValueError('producer_module_mz')
 nt=memory.u32(base+0x3c)
 if not 0x40<=nt<=0x1000 or memory.read(base+nt,4)!=b'PE\0\0' or memory.read(base+nt+24,2)!=b'\x0b\x01':raise ValueError('producer_module_pe32')
 image_size=memory.u32(base+nt+24+56)
 if not 0x1000<=image_size<=0x10000000:raise ValueError('producer_module_size')
 rows=entries()
 for row in rows:
  raw=memory.read(int(row['address'],0),row['length'])
  if raw[0]!=0xe9 or raw[5:]!=bytes.fromhex(row['expected'])[5:]:raise ValueError('producer_entry_not_expected_detour')
  target=(int(row['address'],0)+5+struct.unpack('<i',raw[1:5])[0])&0xffffffff
  if not base<=target<base+image_size:raise ValueError('producer_entry_other_module')
  row.update(actual=raw.hex(),jump_target=hex(target))
 return dict(module_path=str(path.resolve()),module_sha256=sha(path),module_base=hex(base),pe_offset=nt,image_size=image_size,entries=rows)

def collect(memory,session,pre,slot,*,max_seconds=2):
 if type(max_seconds) not in (int,float) or not 0<max_seconds<=2:raise ValueError('producer_readonly_wait_bound')
 reader=module('mf17_running_birth_ro',ROOT/'tactical/running_birth_source_v1.py')
 expected=dict(pid=session['pid'],thread=pre['window_thread'],owner=int(pre['owner'],0),ai=int(pre['ai'],0),personality=int(pre['personality'],0),personality_id=int(pre['personality_id'],0),player_template=int(pre['player_template'],0),start_low=pre['start_low'],start_high=pre['start_high'],command_id=slot['command_id'],task_id=slot['task_id'],seq=slot['seq'],unit=slot['unit'],cost=slot['cost'],factory=slot['factory'],factory_id=slot['factory_id'],iface=slot['iface'],object=0,object_id=0)
 expected=reader.validate_expected(session,expected);channel=reader._Channel(session,expected);end=time.monotonic()+max_seconds
 try:
  while True:
   runtime=channel.runtime(expected);before=channel.read(0,256);header=reader.Header.from_buffer_copy(before);tick=channel.tick()
   if (header.magic,header.version,header.phase,header.error,header.stop_requested)!=(0x50434d44,1,1,0,0):raise ValueError('producer_not_running')
   if any(getattr(header,key)!=expected[key] for key in reader.BINDING) or reader.ident(header.session)!=session['session_id'] or reader.ident(header.commander)!=session['scenario']['commander_id']:raise ValueError('producer_identity')
   if ((tick-int(header.heartbeat))&0xffffffff)>2000 or not 0<=header.count<=1024:raise ValueError('producer_heartbeat_or_count')
   if header.callback_thread==expected['thread']:break
   if header.callback_thread or time.monotonic()>=end:raise ValueError('producer_callback_not_observed')
   time.sleep(.02)
  loaded=loaded_entries(memory);after=channel.read(0,256);last=reader.Header.from_buffer_copy(after);tick_after=channel.tick()
  if reader.header_identity(last)!=reader.header_identity(header) or (last.phase,last.error,last.stop_requested)!=(1,0,0) or ((tick_after-int(last.heartbeat))&0xffffffff)>2000:raise ValueError('producer_binding_changed')
  return dict(protocol='mf17_running_producer_readonly_at_arm_v1',pid=session['pid'],mutations=False,sdk_calls=0,game_memory_writes=False,header_before_hex=before.hex(),header_after_hex=after.hex(),tick_before=tick,tick_after=tick_after,runtime=runtime,expected=expected,loaded=loaded,reader_sha256=sha(__file__),running_helper_sha256=sha(ROOT/'tactical/running_birth_source_v1.py'))
 finally:channel.close()
