"""One owned, model-disabled, paid-birth factory qualification; no unit commands."""
import argparse,ctypes as c,hashlib,importlib.util,json,os,shutil,subprocess,sys,time,traceback,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'integration'),str(ROOT/'production'),str(ROOT/'native-ai')]
from live_state import Memory,own_candidates,load_catalog,atomic_json
from session_package import verify_session_package
from host_runtime.contracts import SessionBinding
from tactical.runtime.near_factory_probe import NearFactoryProbe,verify_build
from tactical.runtime import near_layout as n
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def original_producer():
    name='tacticore_near_factory_original_producer';path=ROOT/'production/persistent/client.py'
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def production_resource_readiness(player,factory):
    """Planning wait only; the original native producer makes final admission."""
    queue=factory.get('queue_candidate');nodes=queue.get('nodes')if isinstance(queue,dict)else None
    if not player.get('resource_available')or not isinstance(nodes,list)or len(nodes)>2:return None
    if any(row.get('kind_raw')!=1 or not 0<row.get('native_cost_plus_30',0)<=10000
           or not 0<=row.get('paid_accumulator_plus_68',-1)<=row['native_cost_plus_30'] for row in nodes):return None
    debt=sum(row['native_cost_plus_30']-row['paid_accumulator_plus_68']for row in nodes)
    cash=player['display_sum'];required=1000+85+debt+500
    return dict(cash=cash,liability=debt,required=required,reserve_floor=1000,readiness_buffer=500,queue_count=len(nodes),ready=cash>=required)


def freeze(run,build,producer):
    target=run/'near-factory-pre-execution-source';target.mkdir(exist_ok=False)
    files={Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)
        and Path(m.__file__).suffix=='.py'and Path(m.__file__).resolve().is_relative_to(ROOT)and '.venv'not in Path(m.__file__).parts}
    files.add(Path(__file__).resolve())
    files.update(ROOT/p for p in ['production/bin/observe_build.exe','production/bin/NativeProductionObserver.dll',
        'production/persistent/bin-v2/persistent_host.exe','production/persistent/bin-v2/ProductionPersistent.dll',
        'production/persistent/shared.h','production/persistent/executor.cpp','production/persistent/host.cpp',
        'tactical/runtime/bin/build-manifest.json','tactical/runtime/bin/atomic_publish.dll'])
    manifest=json.loads((build/'manifest.json').read_text(encoding='utf-8-sig'));files.add(build/'manifest.json')
    for row in manifest['sources']:files.add(build/'source'/row['file'])
    for row in manifest['outputs']:files.add(build/row['file'])
    rows=[]
    for path in sorted(files):
        relative=path.relative_to(ROOT);dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        if sha(path)!=sha(dest):raise ValueError('Qualification source freeze changed')
        rows.append(dict(file=relative.as_posix(),sha256=sha(dest)))
    atomic_json(target/'sources.json',dict(files=rows,model_requests=0,near_module_sdk_calls=0,full_goal_complete=False))
    return dict(directory=str(target),sha256=sha(target/'sources.json'),files=len(rows))


def execute(session_path,output,build,build_pin,seconds):
    session_path=session_path.resolve();output=output.resolve();build=build.resolve()
    raw_session=session_path.read_bytes();session=json.loads(raw_session.decode('utf-8-sig'));scenario=session['scenario'];run=Path(session['run_directory']).resolve()
    if output.parent!=run or output.exists()or not run.is_relative_to(ROOT/'acceptance/runs'):
        raise ValueError('New owned output required')
    if(scenario.get('trial_kind')!='near_factory_channel2_readonly'or scenario.get('model_requests_enabled')is not False
        or scenario.get('diagnostic_only')is not True or scenario.get('lobby_verified')is not True
        or scenario.get('full_match_acceptance')is not False):raise ValueError('Owned factory qualification session required')
    if not 1<=seconds<=30:raise ValueError('Bounded1..30 second qualification observation required')
    verify_session_package(session);verify_build(build,build_pin);production=original_producer()
    binding=SessionBinding(1,session['session_id'],3,scenario['commander_id'],session['pid'],session['start_time'],str(uuid.uuid4()),sha(session['game']),session['mod_sha256'])
    record=dict(kind='near_factory_channel2_qualification',session_id=session['session_id'],binding=binding.public(),
        status='preparing',model_requests=0,near_module_sdk_calls=0,near_commands=[],production_commands=[],
        capability_granted=False,attack_verified=False,full_goal_complete=False,build=str(build),build_sha256=build_pin)
    record['source_freeze']=freeze(run,build,production);atomic_json(output,record)
    memory=producer=probe=observer=None;started=time.monotonic();raw_path=output.with_name(output.stem+'-native.json')
    try:
        memory=Memory(session['pid'],session);factory=None;deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if session_path.read_bytes()!=raw_session:raise ValueError('Session changed')
            logic=memory.u32(0xcd8ce4)
            if memory.u32(logic+0x15c):raise ValueError('Qualification game paused')
            snapshot=own_candidates(memory,3,load_catalog())
            factories=[row for row in snapshot['candidates']if row['type_hash']=='0x80d4ea1e'
                and memory.f32(memory.u32(int(row['address'],0)+0x33c)+4)>0]
            if len(factories)==1:factory=factories[0];break
            time.sleep(.25)
        if factory is None:raise ValueError('No unique own barracks')
        natural=run/'natural-production.json'
        if natural.exists():raise ValueError('Fresh unobserved session required')
        observer=subprocess.Popen([str(ROOT/'production/bin/observe_build.exe'),str(session['pid']),'30'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        record.update(status='observing_native_production_thread',observer_pid=observer.pid);atomic_json(output,record)
        print(json.dumps(dict(stage=record['status'],observer_pid=observer.pid,game_pid=session['pid'])),flush=True)
        observed,errors=observer.communicate(timeout=50)
        (run/'natural-observer-stderr.txt').write_text(errors,encoding='utf-8');natural.write_text(observed,encoding='utf-8')
        if observer.returncode:raise ValueError('Original production observer refused')
        record['status']='waiting_native_production_resource_floor';atomic_json(output,record)
        print(json.dumps(dict(stage=record['status'],game_pid=session['pid'])),flush=True)
        deadline=time.monotonic()+120;owner=int(factory['owner_address'],0);factory_address=int(factory['address'],0)
        while time.monotonic()<deadline:
            if session_path.read_bytes()!=raw_session:raise ValueError('Session changed before production')
            logic=memory.u32(0xcd8ce4)
            if memory.u32(logic+0x15c):raise ValueError('Qualification game paused before production')
            if memory.u32(factory_address+0xdc)!=factory['object_id']or memory.u32(factory_address+0x418)!=owner:
                raise ValueError('Original factory identity changed while waiting')
            player=production.read_owner(memory,owner,3);current_factory=production.read_factory(memory,factory,owner)
            readiness=production_resource_readiness(player,current_factory);record['resource_readiness']=readiness
            atomic_json(output,record)
            if readiness and readiness['ready']:break
            time.sleep(.25)
        else:raise TimeoutError('Native production resource floor never became ready; no submission')
        owned=output.with_name(output.stem+'-owned.json');atomic_json(owned,dict(snapshot,pid=session['pid'],sha256=binding.game_sha256))
        producer=production.ProductionExecutor(session_path,owned,factory['address'],scenario['commander_id'],natural,
            total_budget=85,reserve_floor=1000,min_interval_frames=150)
        producer.start();record.update(status='paid_production_ready',producer_host_pid=producer.host.pid);atomic_json(output,record)
        frame=memory.u32(memory.u32(0xcd8ce4)+0x50)
        command=dict(session_id=session['session_id'],player_id=3,commander_id=scenario['commander_id'],
            command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=1,unit='conscript',budget=85,reserve=1000,expires_frame=frame+450)
        # Seal the immutable intent before the original producer can dispatch.
        intent_path=run/'near-factory-paid-intent.json'
        with intent_path.open('x',encoding='utf-8')as stream:
            json.dump(command,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        record['production_intent_sha256']=sha(intent_path);atomic_json(output,record)
        receipt=producer.submit(command);record['production_commands'].append(dict(command=command,receipt=receipt))
        record['status']='waiting_paid_birth';atomic_json(output,record)
        if receipt.get('accepted')is not True:raise ValueError('Production refused before factory qualification')
        deadline=time.monotonic()+40;born=None
        while time.monotonic()<deadline:
            status=producer.status();record['production_status']=status
            born=next((row for row in status.get('ledger',[])if row.get('command_id')==command['command_id']),None)
            if born and born.get('completed')and born.get('paid_verified')and born.get('paid')==85 and born.get('created'):break
            if born and born.get('status')in ('rejected','failed','unknown'):raise ValueError('Paid birth failed or unknown')
            time.sleep(.1)
        else:raise TimeoutError('Paid birth observation expired; no production retry')
        record['paid_birth']=born;record['status']='attaching_near_factory';atomic_json(output,record)
        probe=NearFactoryProbe(session_path,binding,producer,command['command_id'],raw_path,build=build,build_sha256=build_pin)
        actor=probe.attach();record.update(status='near_factory_observing',native_report=str(raw_path),
            near_host_pid=probe.host.pid,actor_id=actor.identity.object_id,actor_generation=actor.identity.generation)
        atomic_json(output,record);print(json.dumps(dict(stage=record['status'],near_host_pid=probe.host.pid,actor_id=actor.identity.object_id)),flush=True)
        deadline=time.monotonic()+seconds;rows=[]
        while time.monotonic()<deadline:
            probe.poll();rows.append(dict(frame=probe.shared.current_observation.frame,identity=bool(probe.shared.current_observation.identity),
                birth_verified=bool(probe.shared.current_observation.actor_birth_verified),contacts=probe.full.contacts_count,
                readonly_weapon_events=probe.full.combat_written,near_state=probe.shared.state))
            if probe.shared.state!=2:raise ValueError('Near factory stopped or became unknown during observation')
            time.sleep(.1)
        record['observations']=rows;record['status']='factory_observed_requires_independent_review'
    except BaseException as error:
        record.update(status='failed_or_unknown',reason_code=str(error),exception=traceback.format_exc())
    finally:
        if probe is not None:
            try:
                probe.stop();record['near_stopped']=True;record['near_host_exit']=probe.host.poll();probe.close()
            except BaseException as error:record['near_stop_unknown']=str(error)
        if producer is not None:
            try:
                record['production_stopped']=producer.stop()
                if producer.shared is not None:
                    p=c.string_at(producer.view,c.sizeof(production.Persistent));path=run/'near-factory-production-final.bin'
                    with path.open('xb')as stream:stream.write(p);stream.flush();os.fsync(stream.fileno())
                    record['production_final_sha256']=hashlib.sha256(p).hexdigest()
                record['producer_host_exit']=producer.host.poll()if producer.host else None
            except BaseException as error:record['production_stop_unknown']=str(error)
        if observer is not None and observer.poll()is None:
            record['observer_still_live']=True;record['observer_pid']=observer.pid
        if memory is not None:memory.close()
        record['elapsed_wall_seconds']=time.monotonic()-started;atomic_json(output,record)
    print(json.dumps(dict(status=record['status'],report=str(output),near_stopped=record.get('near_stopped',False),field_granted=False)),flush=True)
    return 0 if record['status']=='factory_observed_requires_independent_review'and record.get('near_stopped')else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--build-sha256',required=True);parser.add_argument('--seconds',type=float,default=12);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if args.execute:raise SystemExit(execute(args.session,args.output,args.build,args.build_sha256,args.seconds))
    verify_build(args.build,args.build_sha256);print(json.dumps(dict(preflight=True,commands_dispatched=0,game_opened=False,field_granted=False)))
