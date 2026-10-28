"""Observe natural AI calls in one fresh owned model-disabled fixture.

Three passive game-entry detours, no SDK calls or unit-control interface.
An ended observation is not a task-attribution or attack capability grant.
"""
import argparse,ctypes as c,hashlib,json,os,secrets,shutil,struct,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'integration')]
from tactical.runtime import run_near_readonly_probe as old
from tactical.runtime import layout as base
from live_state import own_candidates,load_catalog
from observe_production import Memory,k,w
from read_selected_personality import inspect_player
from capability import bind_session,DEFAULT_CAPABILITY,DEFAULT_SAFETY
from session_package import verify_session_package
from tactical.reusable.lease import window_thread

U,I,Q=base.U,base.I,base.Q
MAGIC=0x54535031;CAPACITY=4096;Bootstrap=old.Bootstrap
class Row(c.Structure):
    _fields_=[('ticket',I),('kind',U),('frame',U),('thread',U),('monotonic_ms',Q),('call_id',Q),('parent_id',Q),('words',U*96)]
class Shared(c.Structure):
    _fields_=[(name,U)for name in ['magic_word','protocol','structure_size','token']]+[('bootstrap',Bootstrap)]+[(name,I)for name in ['state','error','active','stop','count','overflow']]+[
        ('callback_thread',U),('pulse_requested',I),('pulse_acknowledged',I),('started_ms',Q),('last_ms',Q)]+[(name,U)for name in ['hooks_restored','installed_count','rejected','skipped_damage','max_callback_ms']]+[('rows',Row*CAPACITY)]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
durable=old.durable
ENTRIES=old.ENTRIES+(0x790d80,0x764e20,0x7ba770,0x70f440,0x849220,0x73e390,0x789bf0,0x723f50)

def inventory():return dict(bootstrap=c.sizeof(Bootstrap),row=c.sizeof(Row),shared=c.sizeof(Shared),rows_offset=Shared.rows.offset,capacity=CAPACITY,bootstrap_offset=Shared.bootstrap.offset,restore_mask=7)
def entry_snapshot(memory,game):
    raw=Path(game).read_bytes();image,_,sections=old.parse_pe(raw);result={}
    for address in ENTRIES:
        start=old.rva_to_off(address-image,sections);expected=raw[start:start+24].hex();actual=memory.read(address,24).hex()
        if actual!=expected:raise ValueError('Original entry missing:'+hex(address))
        result[hex(address)]=actual
    return result
def closed(s):return not s.active and ((s.state==3 and s.hooks_restored==7)or(s.state==4 and s.hooks_restored==1 and not s.installed_count))
def verify_build(build,pin):
    if not build.is_relative_to(ROOT/'reports')or sha(build/'manifest.json')!=pin:raise ValueError('Explicit isolated shot build pin required')
    manifest=load(build/'manifest.json')
    if manifest['kind']!='isolated_native_passive_shot_probe'or manifest['layout']!=inventory():raise ValueError('Passive shot layout mismatch')
    for row in manifest['sources']:
        path=build/'source'/row['file']
        if not path.resolve().is_relative_to(build/'source')or sha(path)!=row['sha256']:raise ValueError('Frozen shot source changed')
    for row in manifest['outputs']:
        path=build/row['file']
        if path.parent!=build or sha(path)!=row['sha256']:raise ValueError('Passive shot artifact changed')
    if json.loads(subprocess.check_output([str(build/'shot_probe_host.exe'),'--layout'],text=True,timeout=5))!=inventory():raise ValueError('Actual passive shot ABI mismatch')
    return manifest
def freeze(output,build,manifest):
    folder=output/'pre-execution-source';folder.mkdir()
    paths={Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).suffix=='.py'
        and Path(m.__file__).resolve().is_relative_to(ROOT)and '.venv'not in Path(m.__file__).parts}
    paths.add(Path(__file__).resolve());paths.update([build/'manifest.json',ROOT/'tactical/runtime/bin/atomic_publish.dll',ROOT/'tactical/runtime/bin/build-manifest.json'])
    paths.update(build/'source'/row['file']for row in manifest['sources']);paths.update(build/row['file']for row in manifest['outputs'])
    rows=[]
    for path in sorted(paths):
        relative=path.relative_to(ROOT);dest=folder/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        if sha(path)!=sha(dest):raise ValueError('Passive shot source freeze changed')
        rows.append(dict(file=relative.as_posix(),sha256=sha(dest)))
    durable(folder/'sources.json',dict(files=rows,game_sdk_calls=0,control_supported=False));return dict(files=len(rows),sha256=sha(folder/'sources.json'))

def run(session_path,build,output,pin,seconds,min_frame,wait_seconds):
    session_path=session_path.resolve();build=build.resolve();output=output.resolve();session_bytes=session_path.read_bytes();session=load(session_path);scenario=session['scenario'];run_directory=Path(session['run_directory']).resolve()
    if output.exists()or output.parent!=run_directory or not run_directory.is_relative_to(ROOT/'acceptance/runs'):raise ValueError('Fresh owned shot output required')
    if scenario.get('trial_kind')!='near_passive_native_shot_diagnostic'or scenario.get('model_requests_enabled')is not False or scenario.get('diagnostic_only')is not True or scenario.get('full_match_acceptance')is not False or scenario.get('lobby_verified')is not True:raise ValueError('Explicit passive shot fixture required')
    if not 1<=seconds<=90 or not 0<=min_frame<=10000 or not 1<=wait_seconds<=300:raise ValueError('Passive observation/wait bounds')
    verify_session_package(session);manifest=verify_build(build,pin);output.mkdir();snapshot=freeze(output,build,manifest)
    durable(output/'pre-execution.json',dict(session_id=session['session_id'],source_snapshot=snapshot,build_sha256=pin,seconds=seconds,min_frame=min_frame,wait_seconds=wait_seconds,model_requests=0,module_sdk_calls=0,unit_control=False))
    memory=Memory(session['pid'],session);mapping=view=process=None;shared=None;kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];kernel.CreateFileMappingW.restype=w.HANDLE
    kernel.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];kernel.MapViewOfFile.restype=c.c_void_p
    kernel.UnmapViewOfFile.argtypes=[c.c_void_p];kernel.CloseHandle.argtypes=[w.HANDLE]
    atomic_path=ROOT/'tactical/runtime/bin/atomic_publish.dll'
    if sha(atomic_path)!='7133a505593bd77de82c58a32f8e94ed29a12230003ce3f33d4acf7e578706c2':raise ValueError('Original atomic stop bridge changed')
    atomic=c.WinDLL(str(atomic_path));atomic.runtime_exchange.argtypes=[c.POINTER(I),I];atomic.runtime_exchange.restype=I
    try:
        print(json.dumps(dict(stage='waiting_natural_conscript',game_pid=session['pid'],min_frame=min_frame)),flush=True)
        deadline=time.monotonic()+wait_seconds;catalog=load_catalog();ready=None
        while time.monotonic()<deadline:
            if session_path.read_bytes()!=session_bytes:raise ValueError('Passive session changed before attach')
            logic=memory.u32(0xcd8ce4);frame=memory.u32(logic+0x50)
            if memory.u32(logic)!=0xbeb630 or memory.u32(logic+0x15c):raise ValueError('Passive game root or pause changed')
            own=own_candidates(memory,3,catalog);conscript=[row for row in own['candidates']if row['type_hash']=='0x19ab11af'and not memory.u32(int(row['address'],0)+0x238)]
            ready=dict(frame=frame,own_conscripts=len(conscript),game_pid=session['pid']);(output/'wait-status.json').write_text(json.dumps(ready)+'\n',encoding='utf-8')
            if frame>=min_frame and conscript:break
            time.sleep(.5)
        else:raise TimeoutError('Natural Conscript/frame prerequisite not reached; no hook attach')
        durable(output/'natural-readiness.json',ready)
        proof,safety=bind_session(memory,session,3);owner=proof['handshake']['player'];native=inspect_player(memory.read,owner);thread=window_thread(session['pid']);times=[w.FILETIME()for _ in range(4)]
        if not k.GetProcessTimes(memory.handle,*[c.byref(x)for x in times]):raise c.WinError(c.get_last_error())
        created=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime;entries=entry_snapshot(memory,session['game']);boot=Bootstrap()
        boot.binding.session[:]=base.uuid_words(session['session_id']);boot.binding.commander[:]=base.uuid_words(proof['commander_id']);boot.binding.host[:]=base.uuid_words(str(uuid.uuid4()))
        boot.binding.player=3;boot.binding.pid=session['pid'];boot.binding.thread=thread;boot.binding.process_start=created
        boot.native.logic=memory.u32(0xcd8ce4);boot.native.owner=owner
        for name,key in [('ai','ai_player'),('personality','personality_wrapper'),('personality_id','instance_id'),('player_template','player_template')]:setattr(boot.native,name,int(native[key],0))
        boot.native.default_team=memory.u32(owner+0xac);boot.native.script_team=memory.u32(memory.u32(owner+0x8c)+0x10)
        descriptor=dict(session_id=session['session_id'],pid=session['pid'],creation=created,thread=thread,player=3,host=list(boot.binding.host),visibility_build=proof['build_id'],mod_sha256=session['mod_sha256'],diagnostic='passive_natural_ai_no_commands')
        boot.binding.binding_hash[:]=struct.unpack('<8I',hashlib.sha256(json.dumps(descriptor,sort_keys=True).encode()).digest());boot.duration_ms=round(seconds*1000);boot.policy_schema=2
        boot.mod_path=str(Path(session['mod_big']).resolve());boot.capability_path=str(DEFAULT_CAPABILITY.resolve());boot.safety_path=str(DEFAULT_SAFETY.resolve());boot_bytes=bytes(boot)
        token=secrets.randbelow(0x7ffffffe)+1;mapping=kernel.CreateFileMappingW(c.c_void_p(-1),None,4,0,c.sizeof(Shared),f'Local\\TacticoreShot1_{session["pid"]}_{token}')
        if not mapping or c.get_last_error()==183:raise ValueError('Passive shot mapping collision')
        view=kernel.MapViewOfFile(mapping,0xf001f,0,0,c.sizeof(Shared))
        if not view:raise c.WinError(c.get_last_error())
        c.memset(view,0,c.sizeof(Shared));shared=Shared.from_address(view);shared.magic_word=MAGIC;shared.protocol=1;shared.structure_size=c.sizeof(Shared);shared.token=token;shared.bootstrap=boot
        durable(output/'preflight.json',dict(descriptor=descriptor,session_sha256=hashlib.sha256(session_bytes).hexdigest(),build_manifest_sha256=pin,bootstrap_sha256=hashlib.sha256(boot_bytes).hexdigest(),bootstrap_hex=boot_bytes.hex(),layout=inventory(),visibility_handshake=proof,entry_bytes=entries))
        if any(sha(ROOT/r['file'])!=r['sha256']for r in load(output/'pre-execution-source/sources.json')['files']):raise ValueError('Passive source changed before attach')
        process=subprocess.Popen([str(build/'shot_probe_host.exe'),str(session['pid']),str(token)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        durable(output/'attach-start.json',dict(helper_pid=process.pid,game_pid=session['pid'],game_start_filetime=created,session_id=session['session_id'],token=token,seconds=seconds))
        print(json.dumps(dict(stage='passive_shot_observing',helper_pid=process.pid,game_pid=session['pid'],output=str(output))),flush=True)
        try:stdout,stderr=process.communicate(timeout=seconds+20)
        except subprocess.TimeoutExpired:
            atomic.runtime_exchange(c.cast(view+Shared.stop.offset,c.POINTER(I)),1)
            try:stdout,stderr=process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                durable(output/'observation-timeout.json',dict(helper_pid=process.pid,helper_still_live=process.poll()is None,state=shared.state,active=shared.active,hooks_restored=shared.hooks_restored,no_restart_authorized=True));raise
        (output/'helper-stdout.txt').write_text(stdout,encoding='utf-8');(output/'helper-stderr.txt').write_text(stderr,encoding='utf-8')
        raw=c.string_at(view,c.sizeof(Shared));(output/'native-shared.bin').write_bytes(raw);s=Shared.from_buffer_copy(raw)
        if bytes(s.bootstrap)!=boot_bytes:raise ValueError('Passive bootstrap changed')
        rows=[]
        for i in range(min(max(s.count,0),CAPACITY)):
            r=s.rows[i]
            if r.ticket!=i+1:raise ValueError('Passive shot row publication incomplete')
            rows.append(dict(ticket=r.ticket,kind=r.kind,frame=r.frame,thread=r.thread,monotonic_ms=r.monotonic_ms,call_id=r.call_id,parent_id=r.parent_id,words=list(r.words)))
        final_entries=entry_snapshot(memory,session['game']);verify_session_package(session)
        checks=dict(closed=closed(s),normal_terminal=s.state==3 and not s.error,restore_mask=s.hooks_restored==7,all_three_installed=s.installed_count==3,helper_exit=process.returncode==0,
            no_overflow=not s.overflow and 0<=s.count<=CAPACITY,native_thread=s.callback_thread==thread and all(r['thread']==thread for r in rows),original_entries=entries==final_entries,
            immutable_session=session_path.read_bytes()==session_bytes,frozen_sources=all(sha(output/'pre-execution-source'/r['file'])==sha(ROOT/r['file'])==r['sha256']for r in load(output/'pre-execution-source/sources.json')['files']))
        summary=dict(kind='passive_natural_ai_shot_observation',session_id=session['session_id'],game_pid=session['pid'],helper_pid=process.pid,state=s.state,error=s.error,active=s.active,
            rows=len(rows),kinds={str(kind):sum(row['kind']==kind for row in rows)for kind in range(1,9)},hooks_restored=s.hooks_restored,installed_count=s.installed_count,rejected=s.rejected,skipped_damage=s.skipped_damage,max_callback_ms=s.max_callback_ms,
            checks=checks,cleanup_verified=all(checks.values()),raw_sha256=hashlib.sha256(raw).hexdigest(),entry_bytes=final_entries,game_entry_detours=3,module_sdk_calls=0,model_requests=0,
            unit_control=False,task_attribution_verified=False,attack_granted=False,full_goal_complete=False)
        durable(output/'observations.json',dict(summary=summary,rows=rows));durable(output/'assessment.json',summary);print(json.dumps(summary),flush=True)
        return 0 if all(checks.values())else 1
    except BaseException as error:
        if not(output/'driver-failure.json').exists():durable(output/'driver-failure.json',dict(reason=str(error),helper_pid=process.pid if process else None,helper_still_live=process.poll()is None if process else False,state=shared.state if shared else None,active=shared.active if shared else None,hooks_restored=shared.hooks_restored if shared else None,no_restart_authorized=True))
        raise
    finally:
        if view:kernel.UnmapViewOfFile(view)
        if mapping:kernel.CloseHandle(mapping)
        memory.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',type=Path);parser.add_argument('--build',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--build-sha256');parser.add_argument('--seconds',type=float,default=90);parser.add_argument('--min-frame',type=int,default=3000);parser.add_argument('--wait-seconds',type=float,default=300);parser.add_argument('--layout',action='store_true');args=parser.parse_args()
    if args.layout:print(json.dumps(inventory()))
    else:raise SystemExit(run(args.session,args.build,args.output,args.build_sha256,args.seconds,args.min_frame,args.wait_seconds))
