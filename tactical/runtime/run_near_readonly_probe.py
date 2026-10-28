"""Run a bounded, research-only game-thread sampler. No unit control or model.

Only the new session explicitly marked near_weapon_and_visible_contact_readonly
is accepted. Native game-entry bytes are compared before/after the probe.
"""
import argparse,ctypes as c,hashlib,json,os,secrets,struct,subprocess,sys,uuid
from ctypes import wintypes as w
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility'),
              str(ROOT/'reference/Ra3-Copilot/ra3-copilot/tools')]
from tactical.runtime import layout as base
from observe_production import Memory,k
from session_package import verify_session_package
from read_selected_personality import inspect_player
from capability import bind_session,DEFAULT_CAPABILITY,DEFAULT_SAFETY
from tactical.reusable.lease import window_thread
from precheck_aob import parse_pe,rva_to_off

U,I,Q=base.U,base.I,base.Q
MAGIC=0x54525031;CAPACITY=16384
class Bootstrap(c.Structure):
    _fields_=[('binding',base.Binding),('native',base.NativeBinding),('duration_ms',U),('policy_schema',U),
              ('mod_path',c.c_wchar*1024),('capability_path',c.c_wchar*1024),('safety_path',c.c_wchar*1024)]
class Row(c.Structure):
    _fields_=[('ticket',I),('kind',U),('frame',U),('thread',U),('monotonic_ms',Q),('words',U*40),('xyz',base.Point),('hp',base.F)]
class Shared(c.Structure):
    _fields_=[(n,U)for n in ['magic_word','protocol','structure_size','token']]+[('bootstrap',Bootstrap)]+[(n,I)for n in ['state','error','active','stop','count','overflow']]+[
        ('callback_thread',U),('pulse_requested',I),('pulse_acknowledged',I),('started_ms',Q),('last_ms',Q)]+[(n,U)for n in ['own_rejected','visible_samples','registry_refusals','max_step_ms']]+[('rows',Row*CAPACITY)]

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
def durable(path,value):
    with path.open('x',encoding='utf-8')as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def local_layout():return dict(bootstrap=c.sizeof(Bootstrap),row=c.sizeof(Row),shared=c.sizeof(Shared),rows_offset=Shared.rows.offset,capacity=CAPACITY,bootstrap_offset=Shared.bootstrap.offset)

# Original 13 runtime entries plus the two diagnostic attack observation points.
# No detours are installed by this probe; exact current bytes must stay original.
ENTRIES=(0x571d90,0x76d9d0,0x54b0a0,0x721ad0,0x838820,0x8d8880,0x8cd630,0x7640f0,
         0x76e690,0x830220,0x830320,0x787500,0x693960,0x572280,0x6f7c60)
def entry_snapshot(memory,game):
    raw=Path(game).read_bytes();image,_,sections=parse_pe(raw);result={}
    for address in ENTRIES:
        start=rva_to_off(address-image,sections);expected=raw[start:start+24].hex();actual=memory.read(address,24).hex()
        if actual!=expected:raise ValueError('Game-entry bytes are not original:'+hex(address))
        result[hex(address)]=actual
    return result

def run(session_path,build,output,seconds):
    if not 1<=seconds<=90:raise ValueError('Read-only native lifetime is 1..90 seconds')
    raw_session=session_path.read_bytes();session=load(session_path)
    scenario=session['scenario']
    if scenario.get('trial_kind')!='near_weapon_and_visible_contact_readonly' or scenario.get('model_requests_enabled')is not False or scenario.get('diagnostic_only')is not True or not scenario.get('lobby_verified'):
        raise ValueError('A verified read-only owned fixture session is required')
    verify_session_package(session)
    manifest=load(build/'manifest.json')
    for row in manifest['outputs']:
        if sha(build/row['file'])!=row['sha256']:raise ValueError('Read-only executable differs from frozen build')
    for row in manifest['sources']:
        if sha(build/'source'/row['file'])!=row['sha256']:raise ValueError('Read-only frozen input changed')
    native_layout=json.loads(subprocess.check_output([str(build/'readonly_probe_host.exe'),'--layout'],text=True))
    if native_layout!=local_layout() or native_layout!=manifest['layout']:raise ValueError('Read-only x86 layout mismatch')
    output.mkdir(parents=True,exist_ok=False)
    memory=Memory(session['pid'],session);mapping=None;view=None;process=None
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];kernel.CreateFileMappingW.restype=w.HANDLE
    kernel.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];kernel.MapViewOfFile.restype=c.c_void_p
    kernel.UnmapViewOfFile.argtypes=[c.c_void_p];kernel.UnmapViewOfFile.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    try:
        proof,safety=bind_session(memory,session,3)
        audit=safety['templates'].get('0x19ab11af',{})
        if not audit.get('source_audited_no_intrinsic_stealth'):raise ValueError('Conscript source review unavailable')
        owner=proof['handshake']['player'];native=inspect_player(memory.read,owner)
        thread=window_thread(session['pid']);times=[w.FILETIME()for _ in range(4)]
        if not k.GetProcessTimes(memory.handle,*[c.byref(x)for x in times]):raise c.WinError(c.get_last_error())
        creation=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        start_entries=entry_snapshot(memory,session['game'])
        boot=Bootstrap();boot.binding.session[:]=base.uuid_words(session['session_id']);boot.binding.commander[:]=base.uuid_words(proof['commander_id']);boot.binding.host[:]=base.uuid_words(str(uuid.uuid4()))
        boot.binding.player=3;boot.binding.pid=session['pid'];boot.binding.thread=thread;boot.binding.process_start=creation
        boot.native.logic=memory.u32(0xcd8ce4);boot.native.owner=owner
        boot.native.ai=int(native['ai_player'],0);boot.native.personality=int(native['personality_wrapper'],0);boot.native.personality_id=int(native['instance_id'],0);boot.native.player_template=int(native['player_template'],0)
        boot.native.default_team=memory.u32(owner+0xac);boot.native.script_team=memory.u32(memory.u32(owner+0x8c)+0x10)
        for team in [boot.native.default_team,boot.native.script_team]:
            if memory.u32(memory.u32(team+4)+8)!=owner:raise ValueError('Native team identity changed')
        descriptor=dict(session_id=session['session_id'],pid=session['pid'],creation=creation,thread=thread,player=3,host=list(boot.binding.host),
                        visibility_build=proof['build_id'],mod_sha256=session['mod_sha256'],diagnostic='read_only_no_control')
        boot.binding.binding_hash[:]=struct.unpack('<8I',hashlib.sha256(json.dumps(descriptor,sort_keys=True).encode()).digest())
        boot.duration_ms=round(seconds*1000);boot.policy_schema=2
        boot.mod_path=str(Path(session['mod_big']).resolve());boot.capability_path=str(DEFAULT_CAPABILITY.resolve());boot.safety_path=str(DEFAULT_SAFETY.resolve())
        frozen_boot=bytes(boot)
        token=secrets.randbelow(0x7ffffffe)+1;name=f'Local\\TacticoreReadonly1_{session["pid"]}_{token}'
        mapping=kernel.CreateFileMappingW(c.c_void_p(-1),None,4,0,c.sizeof(Shared),name)
        if not mapping or c.get_last_error()==183:raise ValueError('New private probe mapping unavailable')
        view=kernel.MapViewOfFile(mapping,0xf001f,0,0,c.sizeof(Shared))
        if not view:raise c.WinError(c.get_last_error())
        c.memset(view,0,c.sizeof(Shared));shared=Shared.from_address(view)
        shared.magic_word=MAGIC;shared.protocol=1;shared.structure_size=c.sizeof(Shared);shared.token=token;shared.bootstrap=boot
        durable(output/'preflight.json',dict(descriptor=descriptor,session_sha256=hashlib.sha256(raw_session).hexdigest(),build_manifest_sha256=sha(build/'manifest.json'),
                bootstrap_sha256=hashlib.sha256(frozen_boot).hexdigest(),layout=native_layout,visibility_handshake=proof,conscript_source_review=audit,entry_bytes=start_entries,
                probe_source_sha256=sha(Path(__file__)),module_game_sdk_calls=0,model_requests=0,model_eligible=False,control_admission=False))
        process=subprocess.Popen([str(build/'readonly_probe_host.exe'),str(session['pid']),str(token)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        durable(output/'attach-start.json',dict(helper_pid=process.pid,game_pid=session['pid'],game_start_filetime=creation,session_id=session['session_id'],token=token,
                                             started_at=datetime.now().astimezone().isoformat(),seconds=seconds))
        print(json.dumps({'helper_pid':process.pid,'game_pid':session['pid'],'output':str(output),'read_only':True}),flush=True)
        try:stdout,stderr=process.communicate(timeout=seconds+15)
        except subprocess.TimeoutExpired:
            shared.stop=1
            try:stdout,stderr=process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                durable(output/'observation-timeout.json',dict(helper_pid=process.pid,helper_still_live=process.poll()is None,state=shared.state,active=shared.active,
                                                             no_restart_authorized=True,module_game_sdk_calls=0));raise
        (output/'helper-stdout.txt').write_text(stdout,encoding='utf-8');(output/'helper-stderr.txt').write_text(stderr,encoding='utf-8')
        final=c.string_at(view,c.sizeof(Shared));(output/'native-shared.bin').write_bytes(final);captured=Shared.from_buffer_copy(final)
        if bytes(captured.bootstrap)!=frozen_boot:raise ValueError('Read-only bootstrap changed')
        rows=[]
        for i in range(min(max(captured.count,0),CAPACITY)):
            row=captured.rows[i]
            if row.ticket!=i+1:raise ValueError('Read-only record publication incomplete')
            rows.append(dict(ticket=row.ticket,kind=row.kind,frame=row.frame,thread=row.thread,monotonic_ms=row.monotonic_ms,
                             words=list(row.words),xyz=[row.xyz.x,row.xyz.y,row.xyz.z],hp=row.hp))
        end_entries=entry_snapshot(memory,session['game'])
        verify_session_package(session)
        if session_path.read_bytes()!=raw_session:raise ValueError('Session was edited during readonly sampling')
        own=[x for x in rows if x['kind']==1];ready=[x for x in own if x['words'][31]==1];visible=[x for x in rows if x['kind']==2];lost=[x for x in rows if x['kind']==3]
        checks=dict(closed=captured.state==3 and captured.active==0,helper_exit=process.returncode==0,no_error=captured.error==0,no_overflow=captured.overflow==0,
                    native_thread=captured.callback_thread==thread and bool(rows) and all(x['thread']==thread for x in rows),original_entry_bytes=end_entries==start_entries,
                    own_pair_observed=bool(own),own_ready_state_observed=bool(ready),visible_contact_observed=bool(visible),
                    visible_only_player3=all(x['words'][10]==1 and x['words'][11]==3 and x['words'][9]==x['frame'] and x['hp']>0 for x in visible),
                    unavailable_has_no_current_position=all(x['hp']==0 and x['xyz']==[0,0,0]for x in lost))
        summary=dict(kind='near_native_readonly_field',created_at=datetime.now().astimezone().isoformat(),session_id=session['session_id'],game_pid=session['pid'],helper_pid=process.pid,
                     state=captured.state,error=captured.error,active=captured.active,rows=len(rows),own_rows=len(own),ready_rows=len(ready),visible_rows=len(visible),unavailable_rows=len(lost),
                     own_rejected=captured.own_rejected,registry_refusals=captured.registry_refusals,max_step_ms=captured.max_step_ms,checks=checks,
                     raw_sha256=hashlib.sha256(final).hexdigest(),model_eligible=False,control_admission=False,paid_birth_verified=False,game_entry_detours=0,module_game_sdk_calls=0,
                     model_requests=0,attack_verified=False,capability_granted=False,full_goal_complete=False)
        durable(output/'observations.json',dict(summary=summary,rows=rows));durable(output/'assessment.json',summary)
        print(json.dumps(summary,ensure_ascii=True),flush=True)
        return summary
    finally:
        if view:kernel.UnmapViewOfFile(view)
        if mapping:kernel.CloseHandle(mapping)
        memory.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',type=Path);parser.add_argument('--build',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--seconds',type=float,default=60);parser.add_argument('--layout',action='store_true');args=parser.parse_args()
    if args.layout:print(json.dumps(local_layout()))
    else:
        if not all([args.session,args.build,args.output]):parser.error('--session --build --output required')
        run(args.session.resolve(),args.build.resolve(),args.output.resolve(),args.seconds)
