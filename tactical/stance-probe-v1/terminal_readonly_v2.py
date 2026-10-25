"""Independent read-only STP1 terminal sidecar; never rewrites the source report."""
import argparse,ctypes as c,hashlib,importlib.util,json,math,struct,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('stp1_frozen_terminal_primitives',HERE/'lease.py');legacy=importlib.util.module_from_spec(sp);sp.loader.exec_module(legacy)

def collect_sample(memory,report):
 inert=json.loads((HERE/'inert-layout.json').read_text())
 if inert['dll_sha256']!=report['native_binary_sha256']:raise ValueError('readonly_terminal_binary_revision')
 base=legacy.module_base(memory);pointer=memory.u32(base+inert['shared_pointer_rva']);before=memory.read(pointer,c.sizeof(legacy.Header));n=legacy.plain(legacy.Header.from_buffer_copy(before));rows=legacy.trusted_entries()
 for row in rows:row['actual']=memory.read(int(row['address'],0),len(bytes.fromhex(row['expected']))).hex()
 timer=memory.u32(base+inert['timer_rva']);after=memory.read(pointer,c.sizeof(legacy.Header))
 # Verify membership before touching the old actor address. This is a current
 # liveness sample, separate from the earlier pool-return event in the trace.
 roster=legacy.preflight.module('stp1_ro_v2_owned_roster',legacy.preflight.BRIDGE/'integration/own_candidates.py');own=roster.own_candidates(memory,3,roster.load_catalog());thing=n['thing'];matches=[u for u in own['candidates'] if u['object_id']==n['object_id'] and int(u['address'],0)==thing]
 current=dict(status='not_present_in_current_owned_roster',old_address_not_read=True,roster_frame=own['frame_start'])
 if len(matches)==1:
  current=dict(thing=thing,vtable=memory.u32(thing),object_id=memory.u32(thing+0xdc),owner=memory.u32(thing+0x418),template_ptr=memory.u32(thing+4),update=memory.u32(thing+0x374),team=memory.u32(thing+0x414),stance_module=memory.u32(thing+0x380),hp=memory.f32(memory.u32(thing+0x33c)+4),roster_frame=own['frame_start'])
  if current['stance_module'] and current['object_id']==n['object_id'] and current['owner']==n['owner']:
   current.update(stance_vtable=memory.u32(current['stance_module']),stance_backref=memory.u32(current['stance_module']+8),stance=memory.u32(current['stance_module']+0x38))
 return dict(module_base=base,shared_pointer=pointer,shared_pointer_after=memory.u32(base+inert['shared_pointer_rva']),timer=timer,timer_after=memory.u32(base+inert['timer_rva']),native_header=n,header_before_hex=before.hex(),header_after_hex=after.hex(),entries=rows,current_owned_actor=current,layout=inert)

def verify(record,report):
 n=report['native'];rq=report['request'];sample=record['snapshot'];actual=sample['native_header'];expected={int(x['address'],0):x['expected'] for x in legacy.trusted_entries()};rows=sample['entries'];row_actual={int(x['address'],0):x['actual'] for x in rows};actor=sample['current_owned_actor']
 def guid(key):return str(uuid.UUID(bytes=struct.pack('<4I',*actual[key])))
 checks=dict(frozen_source_unchanged=legacy.unchanged_sources(report),readonly=record['mutations'] is False and record['sdk_calls']==0,exact_large_header=len(bytes.fromhex(sample['header_before_hex']))==c.sizeof(legacy.Header) and sample['header_before_hex']==sample['header_after_hex'],request_binding=all(guid(k)==n[k+'_id'] for k in ('session','commander','command','task')) and actual['pid']==report['preflight']['pid'] and all(actual[k]==rq[k] for k in ('seq','token')),actual_terminal=actual['phase']==3 and actual['error']==0 and actual['active']==0 and actual['restore_mask']==63 and actual['issued_frame']==n['issued_frame'] and actual['returned_frame']==n['returned_frame'],inert=sample['timer']==sample['timer_after']==0 and sample['shared_pointer']==sample['shared_pointer_after'],six_actual_pristine_entries=len(rows)==len(row_actual)==6 and row_actual==expected and all(x['actual']==x['expected'] for x in rows),current_living_owned_actor=actor.get('thing')==n['thing'] and actor.get('object_id')==n['object_id'] and actor.get('owner')==n['owner'] and actor.get('template_ptr')==n['template_ptr'] and actor.get('update')==n['update'] and type(actor.get('hp')) in (int,float) and math.isfinite(actor['hp']) and actor['hp']>0,normal_original_stance_return_record=actual['stance_restored']==actual['return_verified']==1 and actual['return_calls']==actual['detach_calls']==1 and actual['pool_before_enum']==actual['pool_after_enum']==actual['original_stance']==n['original_stance']==0)
 return dict(checks=checks,independent_terminal_verified=all(checks.values()),original_wrapper_status=report['status'],wrapper_end_to_end_verified=False,tactical_source_granted=False,effect_verified=False,completion_claim=False,scope='Current terminal/bytes/liveness crosscheck only. Pool-return timing is proved by the original immutable trace; current team may legitimately differ after native AI resumes.')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('existing_sidecar_preserved')
 raw=a.report.read_bytes();r=json.loads(raw.decode('utf-8-sig'));session=json.loads(a.session.read_text(encoding='utf-8-sig'))
 if session['session_id']!=r['session_id'] or session['pid']!=r['preflight']['pid'] or not legacy.unchanged_sources(r):raise ValueError('readonly_sidecar_original_binding')
 b=legacy.preflight.module('stp1_ro_v2_legacy_memory',HERE.parent/'ordered-combo/lease.py');memory=b.Memory(session['pid'],session)
 try:
  record=dict(protocol='stance_probe_independent_terminal_v2',source_report=str(a.report.resolve()),source_report_sha256=hashlib.sha256(raw).hexdigest(),source_observed_wrapper_status=r['status'],reader_sha256=legacy.sha(__file__),native_binary_sha256=r['native_binary_sha256'],pid=session['pid'],session_id=session['session_id'],mutations=False,sdk_calls=0,snapshot=collect_sample(memory,r));record['assessment']=verify(record,r)
  if a.report.read_bytes()!=raw:raise ValueError('original_report_changed_during_read')
  b.durable(a.output,record);print(json.dumps(dict(sidecar=str(a.output),assessment=record['assessment'])))
 finally:memory.close()

if __name__=='__main__':main()
