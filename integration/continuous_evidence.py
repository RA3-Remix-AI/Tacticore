"""Read only the bound native mission record; never dispatch or grant itself."""
import hashlib
import importlib.util
import json
import re
import struct
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parent
EXPECTED='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
CONTROLLER_FAMILIES={'mission-formation-v13':(0x4d463133,13),'mission-formation-v14':(0x4d463134,14),'mission-formation-v15':(0x4d463135,15),'mission-formation-v16':(0x4d463136,16),'mission-formation-v17':(0x4d463137,17)}


def _load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    return value

def _executor_filename(directory,key,default):
    schema=_load(ROOT.parent/'tactical/evidence.py','continuous_trusted_reader_schema').executor_schema(directory)
    name=schema.get(key,default)
    if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid trusted executor reader filename')
    return name


def _same_uuid13(a,b):
    return type(a) is str and type(b) is str and uuid.UUID(a).int!=0 and uuid.UUID(a)==uuid.UUID(b)


def _bound_report13(host,receipt,entry,*,terminal=False):
    """The outer controller lease is older than this parent mission command."""
    results=receipt.get('unit_results',[])
    if results and len(results)!=1:raise ValueError('Continuous13 ambiguous native report')
    source=results[0].get('report') if results else receipt.get('active_report')
    if not source:
        if terminal:raise ValueError('Continuous13 terminal raw missing')
        return None
    path=Path(source).resolve();run=Path(host.session['run_directory']).resolve()
    if not path.is_relative_to(run):raise ValueError('Continuous13 raw outside current match')
    try:data=path.read_bytes();report=json.loads(data.decode('utf-8-sig'))
    except (FileNotFoundError,json.JSONDecodeError):
        if terminal:raise
        return None
    pre=report.get('preflight',{});n=report.get('native',{});outer=report.get('request',{});mr=report.get('mission_request')
    if report.get('session_id')!=host.binding.session_id or pre.get('pid')!=host.session['pid'] or pre.get('commander_id')!=host.binding.commander_id or pre.get('player_id')!=host.binding.player_id:
        raise ValueError('Continuous13 foreign game binding')
    if not isinstance(mr,dict):raise ValueError('Continuous13 original model publication missing')
    expected=entry.get('object_ids')
    if entry.get('module')!='combined_arms' or not isinstance(expected,list) or len(expected)!=2 or expected[0]==expected[1] or any(type(x) is not int or x<=0 for x in expected):raise ValueError('Continuous13 exact paid pair missing')
    if receipt.get('object_ids')!=expected or results and results[0].get('object_ids')!=expected:raise ValueError('Continuous13 receipt pair changed')
    if report.get('package_sha256')!=host.session['mod_sha256'] or report.get('executable_sha256')!=EXPECTED:raise ValueError('Continuous13 package changed')
    family=entry['executor_directory'];qualifier=_qualifier(family,'continuous_controller_binding')
    if not qualifier.source_pins(report):raise ValueError('Continuous13 source bundle changed')
    if (n.get('magic'),n.get('version'))!=CONTROLLER_FAMILIES[family] or n.get('pid')!=pre['pid'] or n.get('thread')!=pre.get('window_thread') or n.get('session_id')!=host.binding.session_id or n.get('commander_id')!=host.binding.commander_id:
        raise ValueError('Continuous13 native namespace changed')
    if any(outer.get(k)!=n.get(k) for k in ('command_id','task_id','seq','token')) or type(outer.get('seq')) is not int or outer['seq']<=0 or type(outer.get('token')) is not int or outer['token']<=0:
        raise ValueError('Continuous13 outer controller envelope changed')
    for key,target in (('controller_id','command_id'),('lease_id','task_id')):
        if key in entry and not _same_uuid13(entry[key],outer[target]):raise ValueError('Continuous13 another controller lease')
    if not _same_uuid13(entry['command_id'],mr.get('parent_command_id')) or not _same_uuid13(entry['task_id'],mr.get('parent_task_id')) or type(mr.get('seq')) is not int or mr['seq']!=entry['seq']:
        raise ValueError('Continuous13 parent command mapping changed')
    child_command=str(uuid.uuid5(uuid.UUID(entry['command_id']),'formation'));child_task=str(uuid.uuid5(uuid.UUID(entry['task_id']),'formation'))
    if not _same_uuid13(mr.get('child_command_id'),child_command) or not _same_uuid13(mr.get('child_task_id'),child_task):raise ValueError('Continuous13 deterministic child mapping changed')
    commit=n.get('mission_commit',{});body=commit.get('body',{});ctl=n.get('controller',{})
    if not terminal and commit.get('generation') in (0,2) and commit.get('status')==0:
        if receipt.get('started') is True:raise ValueError('Continuous13 pending body falsely started')
        return None
    raw=bytes.fromhex(mr['commit_body_hex']);prefix=bytes.fromhex(mr['commit_prefix_hex'])
    if len(raw)!=284 or len(prefix)!=252:raise ValueError('Continuous13 commit body size changed')
    typed=qualifier.controller.plain(qualifier.controller.L.MissionCommitBody13.from_buffer_copy(raw));digest=hashlib.sha256(prefix).digest()
    if raw[:252]!=prefix or typed!=body or list(struct.unpack('<8I',digest))!=body.get('digest_sha256') or mr['digest_sha256']!=digest.hex():raise ValueError('Continuous13 original binary commit seal changed')
    if qualifier.controller.ident(body['controller'])!=outer['command_id'] or qualifier.controller.ident(body['lease'])!=outer['task_id'] or qualifier.controller.ident(body['command'])!=child_command or qualifier.controller.ident(body['task'])!=child_task or not _same_uuid13(qualifier.controller.ident(body['parent_command']),entry['command_id']) or not _same_uuid13(qualifier.controller.ident(body['parent_task']),entry['task_id']) or body['seq']!=entry['seq']:
        raise ValueError('Continuous13 original typed commit identity changed')
    actors=[qualifier.actor(report,role) for role in (0,1)]
    if [a['object_id'] for a in actors]!=expected or [body['front_id'],body['support_id']]!=expected:raise ValueError('Continuous13 actual paid-slot actors changed')
    if not qualifier.controller.parent_request_audit(report)['verified']:raise ValueError('Continuous13 original public parent request changed')
    if 'public_command_path' in entry and Path(entry['public_command_path']).resolve()!=Path(mr['public_command_path']).resolve():raise ValueError('Continuous13 original parent file changed')
    if 'public_command_sha256' in entry and entry['public_command_sha256']!=mr['public_command_sha256']:raise ValueError('Continuous13 original parent digest changed')
    public=mr['public_command'];versions=dict(public['formation_versions'])
    if versions!=entry.get('formation_versions') or public.get('target_contact_id')!=entry.get('target_contact_id') or not entry.get('target_contact_id'):raise ValueError('Continuous13 formation or contact changed')
    target=report.get('private_target',{})
    if entry.get('target_object_id') is not None:
        if target.get('object_id')!=entry['target_object_id'] or body.get('target_id')!=entry['target_object_id'] or commit.get('status')==1 and n.get('target_id')!=entry['target_object_id'] or target.get('type_hash')!=entry.get('target_type_hash') or target.get('owner_player_id')!=entry.get('target_owner_player_id'):raise ValueError('Continuous13 target identity changed')
    records=[qualifier.controller.reserve_record(e) for e in report.get('events',[]) if e.get('kind') in qualifier.controller.RS_KINDS]
    audits=[(qualifier.controller.input_audit,(report,)),(qualifier.controller.producer_arm_audit,(report,)),(qualifier.controller.producer_audit,(report,)),(qualifier.controller.clock_audit,(report,records)),(qualifier.controller.cohort_audit,(report,records)),(qualifier.controller.borrow_audit,(report,)),(qualifier.controller.ready_audit,(report,records)),(qualifier.controller.stop_audit,(report,records)),(qualifier.controller.origin_audit,(report,records)),(qualifier.controller.precommit_audit,(report,))]
    if CONTROLLER_FAMILIES[family][1]>=15:audits.append((qualifier.controller.spawn_wait_audit,(report,records)))
    if not all(fn(*args)['verified'] is True for fn,args in audits):
        raise ValueError('Continuous13 original actual lease admission missing')
    issued=n.get('issued_frame');hard=entry['expires_frame']
    if type(issued) is not int or issued<=0 or issued!=ctl.get('lease_issued_frame') or issued!=ctl.get('reserve_start_frame') or hard!=issued+4500 or ctl.get('hard_deadline_frame')!=hard or n.get('mission_deadline_frame')!=hard or body.get('hard_deadline_frame')!=hard or public.get('expires_frame')!=hard:
        raise ValueError('Continuous13 original lease deadline renewed')
    accepted=[e for e in report['events'] if e.get('kind')==153];rejected=[e for e in report['events'] if e.get('kind')==154]
    started=commit.get('generation')==2 and commit.get('status')==1
    denial=commit.get('generation')==2 and commit.get('status')==2
    if started:
        frame=ctl.get('mission_commit_frame')
        valid=type(frame) is int and frame>0 and len(accepted)==1 and not rejected and accepted[0]['frame']==commit.get('ack_frame')==ctl.get('approach_frame')==frame
        if not valid:
            if terminal:raise ValueError('Continuous13 acceptance lacks original153')
            return None
        if not entry['dispatch_frame']<=frame<hard or frame<issued or frame>=ctl['reserve_deadline_frame']:raise ValueError('Continuous13 model issue clock changed')
        if receipt.get('started') is False or receipt.get('issued_frame',frame)!=frame or receipt.get('execution',{}).get('issued_frame',frame)!=frame:raise ValueError('Continuous13 receipt confused lease and mission issue')
        if not qualifier.controller.commit_audit(report,records)['verified'] or not qualifier.controller.target_proof_audit(report,records)['verified']:
            if terminal:raise ValueError('Continuous13 actual committed scope or target proof missing')
            return None
    elif denial:
        frame=commit.get('ack_frame')
        if len(rejected)!=1 or accepted or type(frame) is not int or rejected[0]['frame']!=frame or not entry['dispatch_frame']<=frame<ctl['reserve_deadline_frame'] or ctl.get('mission_commit_frame')!=0 or ctl.get('approach_frame')!=0:raise ValueError('Continuous13 rejection lacks original154')
        if receipt.get('started') is not False or receipt.get('issued_frame',0)!=0 or receipt.get('execution',{}).get('issued_frame',0)!=0:raise ValueError('Continuous13 rejected mission falsely started')
    else:
        if terminal:raise ValueError('Continuous13 terminal commit not acknowledged')
        return None
    if terminal and (report.get('status')!='finished' or type(report.get('host_exit')) is not int or n.get('phase') not in (3,4) or n.get('active')!=0):raise ValueError('Continuous13 native terminal unproven')
    return dict(report=report,path=path,sha256=hashlib.sha256(data).hexdigest(),model_started=bool(started),model_accept_seq=accepted[0]['seq'] if started else None,model_issued_frame=ctl['mission_commit_frame'] if started else 0,lease_issued_frame=issued,model_commit_rejected=bool(denial))


def _terminal_facts13(host,receipt,entry):
    bound=_bound_report13(host,receipt,entry,terminal=True);q=_qualifier(entry['executor_directory'],'continuous_controller_terminal')
    scene=_scene_release17(bound,receipt,entry)
    if scene is not None:
        if receipt.get('status')=='completed' or any(receipt.get(k) is True for k in ('completed','goal_observed','restoration_verified')):
            raise ValueError('Continuous17 scene release is not mission completion or restoration')
        result=q.qualify(bound['report'])
        # The original raw and its failed qualification are retained unchanged.
        facts=dict(bound,qualification=result,control_release=scene,scene_release=scene)
        verify_formation_release(facts,entry,q)
        return facts
    release=q.control_release(bound['report'])
    if release.get('control_release_verified') is not True:raise ValueError('Continuous13 controller control release unproven')
    result=q.qualify(bound['report'])
    if receipt.get('status')=='completed':
        if bound['report'].get('host_exit')!=0 or not bound['model_started'] or release.get('restoration_verified') is not True or release.get('return_verified') is not True or result.get('combined_arms_verified') is not True or not result.get('checks') or not all(x is True for x in result['checks'].values()) or any(result.get(k) is not True for k in ('effect_verified','approach_verified','retreat_verified','restoration_verified')):
            raise ValueError('Continuous13 completion lacks actual effect home stance and Return')
    facts=dict(bound,qualification=result,control_release=release)
    verify_formation_release(facts,entry,q)
    return facts


def _scene_release17(bound,receipt,entry):
    """Reverify a saved certificate; booleans in a receipt confer no release."""
    results=receipt.get('unit_results',[])
    claimed=results[0].get('scene_release') if len(results)==1 else None
    if claimed is None:return None
    if entry.get('executor_directory')!='mission-formation-v17':raise ValueError('Continuous scene release executor changed')
    path=Path(claimed['sidecar_path']).resolve()
    if not path.is_relative_to(bound['path'].parent):raise ValueError('Continuous17 scene sidecar outside bound run')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=claimed.get('sidecar_sha256'):raise ValueError('Continuous17 scene sidecar digest changed')
    reader=_load(ROOT.parent/'tactical/mission-formation-v17/scene_terminal_release.py','continuous_exact_scene_release17')
    proof=reader.verify_path(path,bound['path'])
    if proof.get('source_sha256')!=bound['sha256'] or proof.get('control_release_verified') is not True or proof.get('scene_disposed_control_release') is not True:
        raise ValueError('Continuous17 scene closure unproven')
    if any(proof.get(k) is not False for k in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')):
        raise ValueError('Continuous17 scene closure has physical outcome claim')
    actors=proof.get('actors',[])
    if len(actors)!=2 or [a.get('role') for a in actors]!=[0,1] or [a.get('object_id') for a in actors]!=entry['object_ids'] or any(a.get('released') is not True or a.get('returned') is not False or a.get('disposed') is not False for a in actors):
        raise ValueError('Continuous17 scene actor release changed')
    return proof


def _model_rejection_facts13(host,receipt,entry):
    facts=_terminal_facts13(host,receipt,entry);r=facts['report'];n=r['native'];commit=n['mission_commit']
    if facts['model_started'] or not facts['model_commit_rejected'] or receipt.get('started') is not False or receipt.get('status')=='completed':raise ValueError('Continuous13 model rejection falsely accepted')
    forbidden=(12,13,34,35,37,39,40,41,42,43,64,76,80,81,85,86,89,92,95)
    for role in (0,1):
        begin=next((e['seq'] for e in r['events'] if e.get('kind')==14 and e.get('tag')==1 and e.get('role')==role),None)
        if begin is None or any(e.get('role')==role and e['seq']>=begin and e.get('kind') in forbidden for e in r['events']):raise ValueError('Continuous13 rejected model has controlled combat or core navigation')
    if any(n.get(k)!=0 for k in ('attack_calls','attack_facade_calls','attack_private_calls','toggle_calls','toggle_hook_calls','damage_count','commit_own_calls')):raise ValueError('Continuous13 rejected model has combat counters')
    held=all((n if role==0 else n['support']).get('detach_calls')==1 for role in (0,1))
    if not held:raise ValueError('Continuous13 model rejection must retain real controller lease history')
    family=CONTROLLER_FAMILIES[entry['executor_directory']][1]
    proof=dict(protocol=f'mf{family}_model_rejection_after_actual_reserve_v1',model_mission_never_started=True,no_dispatch_verified=True,exclusive_control_never_held=False,controller_lease_was_held=True,control_release_verified=True,restoration_verified=facts['control_release']['restoration_verified'],return_verified=facts['control_release']['return_verified'],completion_claim=False,model_combat_sdk_calls=0,model_issued_frame=0,lease_issued_frame=facts['lease_issued_frame'],actual_reject_frame=commit['ack_frame'],reason=commit['reason'])
    return dict(sha256=facts['sha256'],path=facts['path'],proof=proof,control_release=facts['control_release'])


def _qualifier(directory,namespace):
    if directory in CONTROLLER_FAMILIES:
        filename=_executor_filename(directory,'qualifier_filename','formation_mission_qualification.py')
        return _load(ROOT.parent/'tactical'/directory/filename,namespace+'_'+directory.replace('-','_'))
    tactical=ROOT.parent/'tactical'
    if str(tactical) not in sys.path:sys.path.insert(0,str(tactical))
    files={'mission-combat':'mission_combat_qualification.py','mission-combat-v2':'mission_combat_v2_qualification.py','mission-combat-v3':'mission_combat_v3_qualification.py','mission-combat-v4':'mission_combat_v4_qualification.py','mission-combat-v5':'mission_combat_v5_qualification_v2.py','mission-combat-v6':'mission_combat_v6_runtime_qualification.py','mission-combat-v7':'mission_combat_v7_runtime_qualification.py','mission-formation':'mission-formation/formation_mission_qualification.py','mission-formation-v2':'mission-formation-v2/formation_mission_qualification.py','mission-formation-v3':'mission-formation-v3/formation_mission_qualification_v4.py','mission-formation-v4':'mission-formation-v4/formation_mission_qualification_traffic_v2.py','mission-formation-v5':'mission-formation-v5/formation_mission_qualification.py','mission-formation-v6':'mission-formation-v6/formation_mission_qualification.py','mission-formation-v7':'mission-formation-v7/formation_mission_qualification.py','mission-formation-v8':'mission-formation-v8/formation_mission_qualification.py','mission-formation-v9':'mission-formation-v9/formation_mission_qualification.py','mission-formation-v10':'mission-formation-v10/formation_mission_qualification.py','mission-formation-v12':'mission-formation-v12/formation_mission_qualification.py'}
    if directory not in files:raise ValueError('Unknown continuous mission executor')
    path=tactical/files[directory]
    schema=_load(tactical/'evidence.py','continuous_trusted_qualifier_schema').executor_schema(directory)
    if schema.get('kind')=='formation' and schema.get('qualifier_filename'):
        name=schema['qualifier_filename']
        if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid trusted formation qualifier filename')
        path=tactical/directory/name
    return _load(path,namespace+'_'+directory.replace('-','_'))


def bound_report(host,receipt,entry,*,terminal=False):
    if entry.get('executor_directory') in CONTROLLER_FAMILIES:
        return _bound_report13(host,receipt,entry,terminal=terminal)
    results=receipt.get('unit_results',[])
    if results:
        if len(results)!=1:raise ValueError('Continuous mission must have one bound native report')
        source=results[0].get('report')
    else:source=receipt.get('active_report')
    if not source:
        if terminal:raise ValueError('Continuous mission terminal raw missing')
        return None
    path=Path(source).resolve();run=Path(host.session['run_directory']).resolve()
    if not path.is_relative_to(run):raise ValueError('Continuous mission raw outside current match')
    try:
        data=path.read_bytes();report=json.loads(data.decode('utf-8-sig'))
    except (FileNotFoundError,json.JSONDecodeError):
        if terminal:raise
        return None
    pre=report.get('preflight',{});native=report.get('native',{});request=report.get('request',{})
    if report.get('session_id')!=host.binding.session_id or pre.get('pid')!=host.session['pid'] or pre.get('commander_id')!=host.binding.commander_id or pre.get('player_id')!=host.binding.player_id:
        raise ValueError('Continuous mission foreign native binding')
    expected=entry.get('object_ids')
    if not expected:raise ValueError('Continuous mission allocation missing')
    if entry['module']=='combined_arms':
        if len(expected)!=2 or request.get('front_id')!=expected[0] or request.get('support_id')!=expected[1]:raise ValueError('Continuous formation allocation changed')
        if pre.get('selected',{}).get('object_id')!=expected[0] or pre.get('support',{}).get('object_id')!=expected[1] or native.get('object_id')!=expected[0] or native.get('support',{}).get('id')!=expected[1]:raise ValueError('Continuous formation native actor changed')
        suffix='formation'
    else:
        if len(expected)!=1 or pre.get('selected',{}).get('object_id')!=expected[0]:raise ValueError('Continuous actor allocation changed')
        suffix=str(expected[0])
    command=str(uuid.uuid5(uuid.UUID(entry['command_id']),suffix));task=str(uuid.uuid5(uuid.UUID(entry['task_id']),suffix))
    if any(section.get('command_id')!=command or section.get('task_id')!=task for section in (request,native)):
        raise ValueError('Continuous mission child command identity changed')
    if native.get('session_id')!=host.binding.session_id or native.get('commander_id')!=host.binding.commander_id:
        raise ValueError('Continuous mission native session changed')
    if type(native.get('seq')) is not int or native['seq']<=0 or native['seq']!=request.get('seq'):
        raise ValueError('Continuous mission native sequence changed')
    if request.get('target_contact_id')!=entry.get('target_contact_id') or not entry.get('target_contact_id'):
        raise ValueError('Continuous mission target changed')
    if entry.get('target_object_id') is not None:
        target=report.get('private_target',{})
        if target.get('object_id')!=entry['target_object_id'] or request.get('target_object_id')!=entry['target_object_id'] or native.get('target_id')!=entry['target_object_id'] or target.get('type_hash')!=entry['target_type_hash'] or target.get('owner_player_id')!=entry['target_owner_player_id']:raise ValueError('Continuous mission native target identity changed')
    if report.get('package_sha256')!=host.session['mod_sha256'] or report.get('executable_sha256')!=EXPECTED:
        raise ValueError('Continuous mission package changed')
    issued=native.get('issued_frame',0)
    if issued and (type(issued) is not int or not entry['dispatch_frame']<=issued<=entry['expires_frame']):
        raise ValueError('Continuous mission issue clock changed')
    deadline=native.get('mission_deadline_frame',native.get('deadline_frame'))
    if deadline!=entry['expires_frame']:raise ValueError('Continuous mission native deadline changed')
    directory=entry['executor_directory']
    schema=_load(ROOT.parent/'tactical/evidence.py','continuous_evidence_registry').executor_schema(directory)
    dll=ROOT.parent/'tactical'/directory/'bin'/schema['dll'];binary_host=dll.parent/'tactical_host.exe'
    for key,file in (('native_binary_sha256',dll),('native_host_sha256',binary_host),('wrapper_sha256',dll.parent.parent/schema.get('wrapper_filename','lease.py')),('native_source_sha256',dll.parent.parent/'lease.cpp'),('native_shared_sha256',dll.parent.parent/'shared.h')):
        if report.get(key)!=hashlib.sha256(file.read_bytes()).hexdigest():raise ValueError('Continuous mission native revision changed')
    if terminal:
        returned=native.get('returned_frame')
        if type(returned) is not int or not issued or not issued<=returned<=entry['expires_frame']:
            raise ValueError('Continuous mission returned outside committed window')
    return dict(report=report,path=path,sha256=hashlib.sha256(data).hexdigest())


def terminal_facts(host,receipt,entry):
    if entry.get('executor_directory') in CONTROLLER_FAMILIES:
        return _terminal_facts13(host,receipt,entry)
    bound=bound_report(host,receipt,entry,terminal=True)
    directory=entry['executor_directory']
    qualifier=_qualifier(directory,'continuous_terminal')
    result=qualifier.qualify(bound['report'])
    if directory in ('mission-combat-v5','mission-combat-v6','mission-combat-v7'):result=dict(result,remembered_navigation_evidence=_load(ROOT.parent/'tactical/remembered_approach.py','continuous_memory_displacement').qualify(bound['report']))
    release=qualifier.control_release(bound['report'])
    if release.get('restoration_verified') is not True:raise ValueError('Continuous mission restoration unproven')
    if receipt.get('status')=='completed':
        if result.get('restoration_verified') is not True or not result.get('checks') or not all(value is True for value in result['checks'].values()) or any(result.get(key) is not True for key in ('effect_verified','approach_verified','retreat_verified')):
            raise ValueError('Continuous mission result lacks actual effect and retreat')
        if entry['module']=='combined_arms' and result.get('combined_arms_verified') is not True:
            raise ValueError('Continuous mission lacks paired role effect')
    else:result=dict(result,restoration_verified=True)
    facts=dict(bound,qualification=result,control_release=release)
    if directory in ('mission-formation','mission-formation-v2','mission-formation-v3','mission-formation-v4','mission-formation-v5','mission-formation-v6','mission-formation-v7','mission-formation-v8','mission-formation-v9','mission-formation-v10','mission-formation-v12'):verify_formation_release(facts,entry,qualifier)
    return facts


def verify_formation_release(facts,entry,qualifier=None):
    """Bind role releases and every entry in the trusted executor's hook set."""
    if facts.get('scene_release') is not None:
        _scene_release17(facts,dict(unit_results=[dict(scene_release=facts['scene_release'])]),entry)
        return
    report=facts['report'];pre=report['preflight'];request=report['request'];native=report['native'];terminal=report.get('terminal_readonly',{})
    directory=entry['executor_directory']
    schema=_load(ROOT.parent/'tactical/evidence.py','continuous_formation_release_schema').executor_schema(directory)
    hooks=schema.get('hook_count',13);mask=schema.get('restore_mask')
    if schema.get('kind')!='formation' or type(hooks) is not int or hooks not in (13,16,17) or mask!=(1<<hooks)-1:
        raise ValueError('Unknown trusted formation restoration contract')
    expected=dict(pid=pre['pid'],session_id=report['session_id'],commander_id=pre['commander_id'],command_id=request['command_id'],task_id=request['task_id'],seq=request['seq'],token=request['token'],owner=pre['owner'],logic=pre['logic'],native_binary_sha256=report['native_binary_sha256'])
    if any(terminal.get(key)!=value or type(terminal.get(key)) is not type(value) for key,value in expected.items()) or terminal.get('mutations') is not False or terminal.get('timer')!=0 or terminal.get('active')!=0 or terminal.get('restore_mask')!=mask:
        raise ValueError('Continuous formation terminal identity changed')
    if directory not in ('mission-formation','mission-formation-v2','mission-formation-v3','mission-formation-v4','mission-formation-v5','mission-formation-v6','mission-formation-v7','mission-formation-v8','mission-formation-v9','mission-formation-v10','mission-formation-v12','mission-formation-v13','mission-formation-v14','mission-formation-v15','mission-formation-v16','mission-formation-v17'):raise ValueError('Unknown formation release executor')
    folder=ROOT.parent/'tactical'/directory
    layout=json.loads((folder/'inert-layout.json').read_text())
    if terminal.get('layout')!=layout or layout.get('dll_sha256')!=report['native_binary_sha256']:raise ValueError('Continuous formation terminal layout changed')
    block=(folder/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
    signatures=re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block)
    trusted={int(address,0):bytes.fromhex(escaped.replace('\\x','')).hex() for address,escaped,size in signatures}
    rows=terminal.get('entries',[])
    if len(trusted)!=hooks or len(rows)!=hooks or len({row.get('address') for row in rows})!=hooks:raise ValueError('Continuous formation terminal entry set incomplete')
    for row in rows:
        address=int(row['address'],0)
        if address not in trusted or row.get('expected')!=trusted[address] or row.get('actual')!=trusted[address]:raise ValueError('Continuous formation original entry bytes not restored')
    actors=facts['control_release'].get('actors',[])
    if len(actors)!=2 or [a.get('role') for a in actors]!=[0,1] or [a.get('object_id') for a in actors]!=entry['object_ids'] or any(a.get('released') is not True for a in actors):raise ValueError('Continuous formation role release incomplete')
    if qualifier is None:qualifier=_qualifier(directory,'continuous_mixed_release')
    for actor in actors:
        if actor.get('disposed'):
            disposition=report.get('disposal_readonly',{}).get(str(actor['role']),{})
            if not qualifier.disposal_binding_verified(disposition,report,actor['role']):raise ValueError('Continuous formation role disposal unproven')


def progress_evidence(host,receipt,entry,progress):
    """Reconstruct the published revision even if the active report advanced."""
    bound=bound_report(host,receipt,entry)
    if bound is None:return None
    if entry.get('executor_directory') in CONTROLLER_FAMILIES:
        if not bound['model_started']:raise ValueError('Continuous13 progress before actual model acceptance')
        if type(progress.get('revision')) is not int or progress['revision']<bound['model_accept_seq']:raise ValueError('Continuous13 progress before original153')
    report=bound['report'];revision=progress['revision']
    history=[event for event in report.get('events',[]) if event.get('seq',0)<=revision]
    if not history or history[-1].get('seq')!=revision or history[-1].get('frame')!=progress['observed_frame']:
        raise ValueError('Continuous progress lacks its native event')
    directory=entry['executor_directory']
    qualifier=_qualifier(directory,'continuous_progress')
    snapshot=dict(report,events=history)
    expected=qualifier.progress(snapshot,str(uuid.UUID(entry['task_id'])))
    if expected!=progress:raise ValueError('Continuous progress differs from bound native history')
    return bound


def pre_dispatch_facts(host,receipt,entry):
    """Recheck a child wrapper refusal; exit text alone is never an attestation."""
    if entry.get('executor_directory') in CONTROLLER_FAMILIES:
        return _model_rejection_facts13(host,receipt,entry)
    results=receipt.get('unit_results',[])
    if not results:
        if receipt.get('wrapper_attempted') is not False or receipt.get('no_dispatch_verified') is not True or receipt.get('dispatch_attempted') is not False:
            raise ValueError('Continuous refusal lacks a verified pre-dispatch boundary')
        certificate=receipt.get('pre_dispatch',{})
        expected=dict(command_id=entry['command_id'],task_id=entry['task_id'],seq=entry['seq'],session_id=host.binding.session_id,commander_id=host.binding.commander_id,player_id=host.binding.player_id,object_ids=entry['object_ids'])
        if certificate.get('protocol')!='executor_queue_rejection_v1' or certificate.get('stage')!='queued_before_wrapper' or any(certificate.get(key)!=value or type(certificate.get(key)) is not type(value) for key,value in expected.items()):raise ValueError('Continuous queue refusal identity changed')
        if certificate.get('wrapper_attempted') is not False or certificate.get('dispatch_attempted') is not False or certificate.get('native_launch_intent_persisted') is not False or certificate.get('active_report') is not None or receipt.get('active_report') or receipt.get('started') is not False or receipt.get('issued_frame',0)!=0:raise ValueError('Continuous queue refusal may have launched a wrapper')
        if certificate.get('client_sha256')!=hashlib.sha256((ROOT.parent/'tactical/client.py').read_bytes()).hexdigest():raise ValueError('Continuous queue refusal executor revision changed')
        return dict(sha256=hashlib.sha256(json.dumps(receipt,sort_keys=True,allow_nan=False).encode()).hexdigest())
    if len(results)!=1:raise ValueError('Continuous refusal has ambiguous child results')
    child=results[0];path=Path(child['report']).resolve()
    if not path.is_relative_to(Path(host.session['run_directory']).resolve()):raise ValueError('Continuous refusal outside current match')
    raw=path.read_bytes();report=json.loads(raw.decode('utf-8-sig'))
    gate=child.get('native_gate_no_lease',{})
    if gate.get('no_actor_lease_verified') is True:
        # The native host DID launch. This is a different boundary from exit64:
        # exact passive header snapshots and restored entry bytes prove no lease.
        gate_readers={'mission-combat-v3':'mission_v3_gate_no_lease.py','mission-combat-v4':'mission_v4_gate_no_lease.py','mission-combat-v5':'mission_v5_gate_no_lease.py','mission-combat-v6':'mission_v6_gate_no_lease.py','mission-combat-v7':'mission_v7_gate_no_lease.py','mission-formation-v2':'mission_formation_v3_gate_no_lease.py','mission-formation-v3':'mission_formation_v3_admission_v4_gate_no_lease.py','mission-formation-v4':'mission_formation_v4_traffic_v2_gate_no_lease.py','mission-formation-v5':'mission_formation_v5_gate_no_lease.py','mission-formation-v6':'mission_formation_v6_gate_no_lease.py','mission-formation-v7':'mission_formation_v7_gate_no_lease.py','mission-formation-v8':'mission_formation_v8_gate_no_lease.py','mission-formation-v9':'mission_formation_v9_gate_no_lease.py','mission-formation-v10':'mission_formation_v10_gate_no_lease.py','mission-formation-v12':'mission_formation_v12_gate_no_lease.py'}
        if entry['executor_directory'] not in gate_readers:raise ValueError('Unknown native gate verifier')
        bound=bound_report(host,receipt,entry)
        evidence_path=Path(gate['evidence_path']).resolve()
        if not evidence_path.is_relative_to(Path(host.session['run_directory']).resolve()):raise ValueError('Native gate proof outside current match')
        if str(ROOT.parent/'tactical') not in sys.path:sys.path.insert(0,str(ROOT.parent/'tactical'))
        gate_name=_executor_filename(entry['executor_directory'],'gate_reader',gate_readers[entry['executor_directory']])
        verifier=_load(ROOT.parent/'tactical'/gate_name,'continuous_native_gate_'+entry['executor_directory'].replace('-','_'))
        verified=verifier.verify_path(evidence_path,path)
        if verified.get('no_actor_lease_verified') is not True or verified.get('exclusive_control_never_held') is not True or verified.get('completion_claim') is not False or verified.get('return_verified') is not False or receipt.get('started') is not False or receipt.get('issued_frame',0)!=0:
            raise ValueError('Native zero-lease refusal unproven')
        return dict(sha256=bound['sha256'],path=path,proof=verified)
    suffix='formation' if entry['module']=='combined_arms' else str(entry['object_ids'][0])
    command=str(uuid.uuid5(uuid.UUID(entry['command_id']),suffix));task=str(uuid.uuid5(uuid.UUID(entry['task_id']),suffix))
    helper={'mission-combat-v2':'pre_dispatch_v2_contract.py','mission-combat-v3':'pre_dispatch_v3_contract.py','mission-combat-v4':'pre_dispatch_v4_contract.py','mission-combat-v5':'pre_dispatch_v5_contract.py','mission-combat-v6':'pre_dispatch_v6_contract.py','mission-combat-v7':'pre_dispatch_v7_contract.py','mission-formation-v2':'pre_dispatch_formation_v2_contract.py','mission-formation-v3':'pre_dispatch_formation_v3_admission_v4_contract.py','mission-formation-v4':'pre_dispatch_formation_v4_traffic_v2_contract.py','mission-formation-v5':'pre_dispatch_formation_v5_contract.py','mission-formation-v6':'pre_dispatch_formation_v6_contract.py','mission-formation-v7':'pre_dispatch_formation_v7_contract.py','mission-formation-v8':'pre_dispatch_formation_v8_contract.py','mission-formation-v9':'pre_dispatch_formation_v9_contract.py','mission-formation-v10':'pre_dispatch_formation_v10_contract.py','mission-formation-v12':'pre_dispatch_formation_v12_contract.py'}.get(entry['executor_directory'],'pre_dispatch_contract.py')
    helper=_executor_filename(entry['executor_directory'],'pre_dispatch_helper',helper)
    verifier=_load(ROOT.parent/'tactical'/helper,'continuous_pre_dispatch_verifier_'+entry['executor_directory'].replace('-','_'))
    seq=report.get('request',{}).get('seq')
    if type(seq) is not int or seq<=0:raise ValueError('Continuous refusal native sequence invalid')
    verified=verifier.verify_no_dispatch(report,child_exit_code=child.get('child_exit_code'),session=host.session,commander_id=host.binding.commander_id,command_id=command,task_id=task,seq=seq,object_ids=entry['object_ids'],directory=entry['executor_directory'],target_contact_id=entry['target_contact_id'])
    if verified.get('no_dispatch_verified') is not True or verified.get('exclusive_control_never_held') is not True or verified.get('completion_claim') is not False:
        raise ValueError('Continuous refusal raw attestation rejected')
    return dict(sha256=hashlib.sha256(raw).hexdigest(),path=path,proof=verified)
