"""Project an existing MF13 controller into parent mission receipts.

Projection is telemetry. Continuous evidence readers independently bind raw
events, source pins, release and effects before the host can accept an outcome.
No executor or controller is started here.
"""
import copy,uuid

DIRECTORIES=('mission-formation-v13','mission-formation-v14','mission-formation-v15','mission-formation-v16','mission-formation-v17')

def receipt_for(controller,entry,binding):
    directory=entry.get('executor_directory')
    if directory not in DIRECTORIES:raise ValueError('held_receipt_untrusted_executor')
    runtime=controller.runtime
    if runtime is None:raise ValueError('held_receipt_missing_runtime')
    report=runtime.report or {};native=report.get('native',{});mission=report.get('mission_request') or {}
    if mission.get('parent_command_id')!=str(uuid.UUID(entry['command_id'])) or mission.get('parent_task_id')!=str(uuid.UUID(entry['task_id'])) or mission.get('seq')!=entry['seq']:
        raise ValueError('held_receipt_parent_mapping_changed')
    request=mission.get('public_command',{})
    if request.get('expires_frame')!=entry['expires_frame'] or request.get('target_contact_id')!=entry['target_contact_id']:
        raise ValueError('held_receipt_request_changed')
    acknowledged=native.get('mission_commit',{}).get('status')==1
    issued=native.get('controller',{}).get('mission_commit_frame',0) if acknowledged else 0
    if acknowledged and (type(issued) is not int or not entry['dispatch_frame']<=issued<entry['expires_frame']):
        raise ValueError('held_receipt_commit_clock_changed')
    terminal=report.get('status')=='finished' and report.get('host_exit') is not None
    assessment=report.get('assessment',{}) if terminal else {}
    release=assessment.get('restoration',{})
    completed=bool(terminal and acknowledged and assessment.get('combined_arms_verified') is True and assessment.get('checks') and all(v is True for v in assessment['checks'].values()))
    restored=bool(terminal and release.get('restoration_verified') is True)
    receipt=dict(command_id=entry['command_id'],task_id=entry['task_id'],seq=entry['seq'],session_id=binding.session_id,commander_id=binding.commander_id,player_id=binding.player_id,module=entry['module'],purpose=entry['purpose'],executor_directory=directory,object_ids=list(entry['object_ids']),formation_versions=dict(entry['formation_versions']),active_report=str(runtime.output),accepted=True,started=bool(issued),issued_frame=issued,expires_frame=entry['expires_frame'],status='completed' if completed else 'failed' if terminal else 'started' if issued else 'queued',completed=completed,goal_observed=completed,restoration_verified=restored,command_source='game_thread_bridge',interference='none' if completed else 'unknown',dispatch_attempted=True,wrapper_attempted=False,no_dispatch_verified=False,mission=copy.deepcopy(report.get('progress')) if acknowledged else None,unit_results=[])
    if terminal:
        receipt['unit_results']=[dict(report=str(runtime.output),object_ids=list(entry['object_ids']),assessment=copy.deepcopy(assessment),batch_restoration=copy.deepcopy(release),expected_restore_mask=131071)]
        scene=(getattr(controller,'record',None) or {}).get('scene_release') if directory=='mission-formation-v17' else None
        if scene is not None:
            if scene.get('scene_disposed_control_release') is not True or any(scene.get(k) is not False for k in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')):raise ValueError('held_scene_release_cannot_claim_return_or_effect')
            receipt.update(status='failed',completed=False,goal_observed=False,restoration_verified=False,scene_disposed_control_release_verified=True)
            receipt['unit_results'][0]['scene_release']=copy.deepcopy(scene)
    receipt['execution']={key:copy.deepcopy(receipt[key]) for key in ('formation_versions','issued_frame','expires_frame','command_source','interference','goal_observed','restoration_verified')}
    return receipt
