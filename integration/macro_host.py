"""Desktop-launched macro host; native AI retains all unit operations."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration'),str(ROOT/'strategy')]
from host_runtime.application import apply_commander_draft,load_commander_draft,create_applied_backend
from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.desktop_backend import NativeHostSpawner,_atomic
from host_runtime.journal import CommandJournal
from host_runtime.profile_store import ProfileStore
from host_runtime.macro_live import MacroSampler
from host_runtime.macro_policy_runtime import BudgetController,MacroRequestAudit,MIN_MACRO_MODEL_GAME_SECONDS
from host_runtime.macro_production_runtime import ProductionPreferenceScope,MacroProductionController
from host_runtime.macro_durable import DurableMacroTransport
from host_runtime.macro_bundle import digest,load_bundle
from host_runtime.macro_infrastructure import observe_infrastructure
from host_runtime.macro_forces import observe_forces
from host_runtime.macro_production_feedback import frames as native_pair_frames
from host_runtime.macro_scouting import ScoutingScope,MacroScoutingController
from host_runtime.macro_region_scope import RegionalScope
from host_runtime.macro_regions import MacroRegionalController
from engine import Binding,StrategyEngine,ContractError as StrategyContractError
from battle_agent import BattleAgent
from http_adapter import load_profile
from macro_strategy import MacroStrategyMemory
from host_runtime.macro_strategy_runtime import MacroStrategyRuntime
from host_runtime.macro_expansion_scope import ExpansionScope
from host_runtime.macro_expansion_runtime import MacroExpansionController
from host_runtime.macro_expansion_feedback import compact_expansion_feedback
from host_runtime.resource_reservations import ResourceReservationStore,compact_reservation
from host_runtime.macro_expansion_runtime_v4 import MacroExpansionControllerV4
from host_runtime.macro_expansion_factory_v4 import create_expansion_controller_v4
from host_runtime.macro_admission_feedback_v4 import MacroRequestAuditV4,compact_admission_feedback_v4
from host_runtime.strategic_unified_bundle_v5 import UnifiedStrategicScopeV5
from host_runtime.strategic_unified_controller_v5 import UnifiedStrategicControllerV5
from host_runtime.strategic_unified_feedback_v5 import UnifiedRequestAuditV5,UnifiedStrategyRuntimeV5

LIMITS=dict(production_queue_observed=False,idle_producers_observed=False,
    queue_and_idle_numbers='unobserved_lower_bounds',own_roles_coverage='audited_templates_only',
    power_observed=False,payment_verified=False)


def native_transport_config(scope,manifest,max_wall_seconds=None):
    """Pure admission before attach; an absolute native guard is only backup."""
    protocol=getattr(scope,'native_transport_protocol',1)
    if type(protocol) is int and protocol==5:
        if (type(scope) is not UnifiedStrategicScopeV5 or manifest.get('protocol_version')!=5
                or manifest.get('kind')!='strategic_unified_transport_v5_candidate'
                or manifest.get('package_sha256')!=scope.package_sha256 or manifest.get('admission_ready') is not True
                or manifest.get('compile_only') is not False or tuple(manifest.get('flags',()))!=tuple(scope.action_flags.values())):
            raise ContractError('macro_native_transport_protocol_mismatch')
        wall=3540 if max_wall_seconds is None else max_wall_seconds
        if type(wall) is not int or not 10<=wall<=3540:raise ContractError('macro_host_wall_bound')
        return dict(protocol_version=5,client_path=str(ROOT/'integration/host_runtime/strategic_unified_transport_v5.py'),
            max_wall_seconds=wall,maximum_host_wall_seconds=3540,heartbeat_loss_ms=5000,
            absolute_native_wall_ms=3600000,native_wall_guard_is_backup_only=True)
    if type(protocol) is not int or protocol not in (1,2):raise ContractError('macro_native_transport_not_qualified')
    client=getattr(scope,'native_transport_client',
        'client_area_defense.py' if hasattr(scope,'model_catalog_overrides') else 'client.py')
    kind='native_macro_policy_transport_v2_candidate' if protocol==2 else 'native_macro_policy_transport_candidate'
    if (type(manifest) is not dict or manifest.get('kind')!=kind
            or manifest.get('package_sha256')!=scope.package_sha256
            or type(manifest.get('flags')) is not list or len(manifest['flags'])!=(20 if protocol==2 else 13)
            or any(type(flag) is not str or not flag for flag in manifest['flags'])
            or len(set(manifest['flags']))!=len(manifest['flags'])):
        raise ContractError('macro_native_transport_protocol_mismatch')
    maximum=3540 if protocol==2 else 1500
    if protocol==2:
        if (not isinstance(scope,ExpansionScope) or client!='client.py' or type(manifest.get('protocol_version')) is not int
                or manifest['protocol_version']!=2 or any(type(manifest.get(key)) is not int or manifest[key]!=value
                    for key,value in dict(maximum_host_wall_seconds=3540,absolute_native_wall_ms=3600000,heartbeat_loss_ms=5000).items())
                or manifest.get('same_process_reattach_supported') is not False):
            raise ContractError('macro_native_transport_protocol_mismatch')
    elif (client not in ('client.py','client_area_defense.py','client_group_roles.py')
            or type(manifest.get('protocol_version',1)) is not int or manifest.get('protocol_version',1)!=1
            or type(manifest.get('maximum_host_wall_seconds',1500)) is not int or manifest.get('maximum_host_wall_seconds',1500)!=1500):
        raise ContractError('macro_native_transport_protocol_mismatch')
    wall=maximum if max_wall_seconds is None else max_wall_seconds
    if type(wall) is not int or not 10<=wall<=maximum:raise ContractError('macro_host_wall_bound')
    directory=ROOT/'native-ai'/('macro-policy-runtime-v2' if protocol==2 else 'macro-policy-runtime')
    return dict(protocol_version=protocol,client_path=str(directory/client),max_wall_seconds=wall,
        maximum_host_wall_seconds=maximum,heartbeat_loss_ms=5000,
        absolute_native_wall_ms=3600000 if protocol==2 else None,native_wall_guard_is_backup_only=True)


def request_telemetry_ready(audited,snapshot,event):
    if not audited.fresh_for_game_seconds(snapshot['game_time_seconds']):
        event('macro_decision_deferred',reason_code='macro_telemetry_frame_mismatch')
        return False
    return True


def native_release_matches(final,session,binding,expected_flags):
    """Exact current transport flags and scalar state, never an ACK-only release."""
    try:
        required=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0)
        rows=final['independent_flags']['flags']
        return (type(expected_flags) in (list,tuple) and 1<=len(expected_flags)<=31
            and len(set(expected_flags))==len(expected_flags)
            and final['session_id']==binding.session_id and final['pid']==binding.game_process_id
            and type(final['process_creation_filetime']) is int
            and final['process_creation_filetime']==session['process_creation_filetime']
            and final['mod_sha256']==binding.mod_sha256 and final['cleanup_verified'] is True
            and type(final['host_returncode']) is int and final['host_returncode']==0 and final['unknown_command_ids']==[]
            and all(type(final['native'].get(key)) is int and final['native'][key]==value for key,value in required.items())
            and type(rows) is list and len(rows)==len(expected_flags)
            and {row['name'] for row in rows}==set(expected_flags)
            and all(type(row['present']) is bool and (not row['present'] or row['value'] is False) for row in rows))
    except (KeyError,TypeError,ValueError):return False


class MacroHost:
    def __init__(self,args):
        self.strategic_only=True
        self.args=args;self.binding=SessionBinding.from_dict(json.loads(args.binding.read_text(encoding='utf8')))
        self.run_id=args.run_id;self.started=time.monotonic();self.host_pid=os.getpid()
        self.host_start=NativeHostSpawner.identity(self.host_pid)
        self.session=json.loads(args.session.read_text(encoding='utf-8-sig'))
        if (self.session['session_id']!=self.binding.session_id or self.session['pid']!=self.binding.game_process_id
                or self.session['start_time']!=self.binding.game_process_start or self.session['mod_sha256']!=self.binding.mod_sha256
                or digest(self.session['game'])!=self.binding.game_sha256):raise ContractError('session_mismatch')
        self.output=Path(self.session['run_directory'])/'battle-host'
        if self.output.exists() and any(self.output.iterdir()):
            names={p.name for p in self.output.iterdir()};stop=self.output/'stop.json'
            allowed={'stop.json','strategic-admission.jsonl'}
            if not names<=allowed or not stop.is_file():raise ContractError('run_state_conflict')
            value=json.loads(stop.read_bytes())
            if (value.get('session_id')!=self.binding.session_id or value.get('run_id')!=self.run_id
                    or value.get('binding_hash')!=self.binding.binding_hash
                    or value.get('source')!='strategic_stop_admission_barrier_v1'):
                raise ContractError('run_state_conflict')
        self.output.mkdir(exist_ok=True);self.store=ProfileStore(args.library,args.profile_state_dir)
        self.journal=CommandJournal(args.ledger)
        self.journal.register_run(self.run_id,self.binding.public())
        self.profile=self.store.get_profile(self.binding.commander_id)['profile']
        self.draft=load_commander_draft(args.commander_draft)
        self.expected_hash=self.profile['effective']['effective_hash'];self.expected_revision=self.profile['revision']
        self.phase='starting';self.reason='macro_preparing';self.latest=None;self.backend=None;self.agent=None
        self.startup_lawful_snapshots=[]
        self.sampler=None;self.transport=None;self.controller=None;self.pending=None;self.application=None
        self.strategy_runtime=None;self.strategy_audit=None;self.prepared_macro_commands={}
        self.publication_v4_selected=False
        self.publication_v5_selected=False
        self.native_transport_attached=False
        starts=self.journal.commands_for_run(self.run_id,operation='host_start')
        if (len(starts)!=1 or starts[0]['payload'].get('profile_revision')!=self.expected_revision
                or starts[0]['payload'].get('effective_hash')!=self.expected_hash
                or starts[0]['payload'].get('capabilities',{}).get('native_macro') is not True):
            raise ContractError('macro_host_launch_binding')
        self.check_profile()

    def check_profile(self):
        current=self.store.get_profile(self.binding.commander_id)['profile']
        if (current['validation']['ok'] is not True or current['library_changed']
                or current['revision']!=self.expected_revision or current['library_hash']!=self.profile['library_hash']
                or current['effective']['effective_hash']!=self.expected_hash):raise ContractError('effective_profile_changed')

    def stopping(self):
        path=self.output/'stop.json'
        if path.exists():
            try:
                if json.loads(path.read_text(encoding='utf8')).get('session_id')==self.binding.session_id:return True
            except (ValueError,OSError):raise ContractError('macro_stop_file_invalid') from None
        return False

    def event(self,kind,**facts):
        if kind.endswith('_prepared') and facts.get('plan_id') and facts.get('command_id'):
            self.prepared_macro_commands[facts['plan_id']]=facts['command_id']
        value=dict(session_id=self.binding.session_id,player_id=3,commander_id=self.binding.commander_id,
            wall_seconds=round(time.monotonic()-self.started,3),**facts)
        self.journal.append_event(self.run_id,kind,value,
            game_frame=int(self.latest['game_time_seconds']*15) if self.latest else None,monotonic_ns=time.monotonic_ns())
        with (self.output/'host-events.jsonl').open('a',encoding='utf8') as stream:
            stream.write(json.dumps(dict(kind=kind,**value),ensure_ascii=False,allow_nan=False)+'\n')

    def publish(self):
        if getattr(self,'strategy_runtime',None) is not None:
            strategic_state=self.strategy_runtime.memory.public_state()
            _atomic(self.output/'macro-strategy-state.json',strategic_state)
        else:strategic_state=None
        status=dict(schema_version=1,kind='native_macro_host_v1',session_id=self.binding.session_id,pid=self.session['pid'],
            process_start=self.session['start_time'],host_pid=self.host_pid,host_start_time=self.host_start,
            state=self.phase,reason_code=self.reason,runtime_macro=dict(run_id=self.run_id,binding_hash=self.binding.binding_hash),
            native_transport_protocol=getattr(self,'transport_config',{}).get('protocol_version',1),
            execution=dict(enabled=self.phase=='running',dry_run=False,executor_connected=self.transport is not None,
                control_mode='macro_native',unit_operation_policy='native_ai',remaining_budget=0,
                commander_boundary='native_ai_details_v1' if getattr(self,'strategic_only',False) else 'historical_precision'),
            jobs=[],current_plan=getattr(self,'last_plan',None) or (self.agent.engine.current.public() if self.agent and self.agent.engine.current else None),
            macro_strategy=strategic_state,
            macro_feedback=getattr(self,'last_feedback',None),
            macro_unified_feedback=getattr(self,'last_unified_feedback',None),
            macro_production_feedback=getattr(self,'last_production_feedback',None),
            macro_construction_feedback=getattr(self,'last_construction_feedback',None),
            macro_scouting_feedback=getattr(self,'last_scouting_feedback',None),
            macro_regional_feedback=getattr(self,'last_regional_feedback',None),
            macro_expansion_feedback=getattr(self,'last_expansion_feedback',None),
            macro_resource_feedback=self.current_resource_feedback(),
            macro_expansion_blocked=getattr(self.controller,'expansion_blocked',{}) if self.controller else {},
            metrics=dict(self.agent.engine.metrics) if self.agent else {},
            task_counters=dict(dispatches=len(self.controller.sent) if self.controller else 0,started=0,completed=0,failed=0,blocked=0),
            profile_application=self.application.public() if self.application else None,
            profile_consumption=self.backend.observation() if self.backend else None,
            latest_snapshot={key:self.latest[key] for key in ('snapshot_id','game_time_seconds','paused','resources')} if self.latest else None)
        _atomic(self.output/'host-status.json',status)

    def freeze(self):
        source=self.output/'source';source.mkdir();rows=[]
        files=[Path(__file__),self.args.session,self.args.macro_bundle,self.args.commander_draft,self.args.binding,
            *sorted((ROOT/'integration/host_runtime').glob('*.py')),*sorted((ROOT/'strategy').glob('*.py')),
            *sorted((ROOT/'visibility').glob('*.py')),*sorted((ROOT/'agent_runtime/src/tacticore_agent_runtime').glob('*.py'))]
        files += [*sorted((ROOT/'native-ai').glob('*.py')),*sorted((ROOT/'production').glob('*.py'))]
        frozen_bundle=getattr(getattr(self,'sampler',None),'bundle',{})
        if type(frozen_bundle.get('schema_version')) is int and frozen_bundle['schema_version']==12:
            from host_runtime.macro_catalog_bundle_v12 import load_catalog_bundle_v12
            outer,_=load_catalog_bundle_v12(self.args.macro_bundle,self.session)
            # Append after the unchanged rows0..4 and existing source list.
            # V5 binds the original schema11 bytes and this separate archive.
            files.append(Path(outer['base_bundle']))
            from host_runtime.macro_catalog_release_history_v1 import is_software,JOURNAL_KIND,executed_algorithm_paths
            location=self.output/'publication-v5-history-journal.json'
            _atomic(location,dict(kind=JOURNAL_KIND,schema_version=1,ledger_path=str(Path(self.args.ledger).resolve()),
                run_id=self.run_id,binding_hash=self.binding.binding_hash))
            files.append(location)
            # Archive every software pin, including UI TypeScript. Later
            # cleanup-only history must not depend on mutable installed UI.
            files.extend(Path(name) for name in sorted(outer['pins']) if is_software(name))
            # Includes the actual external compiled manifest parser. Stable
            # executable dependencies require matching pre-attach archives.
            files.extend(executed_algorithm_paths())
        for name in ('macro-policy-runtime','macro-policy-runtime-v2','strategic-unified-runtime-v5'):
            directory=ROOT/'native-ai'/name
            files += [*sorted(directory.glob('*.py')),directory/'shared.h',directory/'native.cpp',directory/'host.cpp']
            if name=='strategic-unified-runtime-v5':files.extend((directory/'flags.h',directory/'flag_api.h'))
        files=list(dict.fromkeys(path.resolve() for path in files))
        for index,path in enumerate(files):
            target=source/(str(index)+'-'+path.name);shutil.copy2(path,target)
            rows.append(dict(path=str(path.resolve()),copy=target.name,sha256=digest(target)))
        _atomic(self.output/'sources.json',dict(kind='pre_execution_macro_host_sources',sources=rows))
        _atomic(self.output/'profile.json',self.profile)

    def update_macro_control(self,game_seconds):
        available=(lambda at:MacroRegionalController.available_actions(self.controller,at)) if (
            getattr(self,'strategic_only',False) and isinstance(self.controller,MacroExpansionController)) else self.controller.available_actions
        actions=available(game_seconds) if (game_seconds>=MIN_MACRO_MODEL_GAME_SECONDS
            and not (getattr(self,'strategic_only',False) and self.latest['paused'])) else ()
        if getattr(self,'strategic_only',False):
            from host_runtime.macro_delegation_boundary_v1 import strategic_actions
            actions=strategic_actions(actions)
        self.latest['macro_control']=dict(mode='macro_native',available_actions=list(actions),
            production_counts={action:list(counts) for action,counts in self.sampler.scope.production_counts.items() if action in actions})
        if isinstance(self.controller,(MacroRegionalController,UnifiedStrategicControllerV5)):
            self.latest['macro_control']['region_targets']={action:region for action,region in self.sampler.scope.regional_action_regions.items()
                if action in actions}

    def production_tick(self,native,*,update_capabilities=True):
        if isinstance(self.controller,UnifiedStrategicControllerV5):
            return self.unified_tick(native,update_capabilities=update_capabilities)
        if getattr(self,'strategic_only',False) and isinstance(self.controller,MacroProductionController):
            return self.strategic_tick(native,update_capabilities=update_capabilities)
        if not isinstance(self.controller,MacroProductionController):return True
        if 'observation' not in native or 'build_observation' not in native:
            self.event('macro_sample_deferred',reason_code='macro_native_pair_unavailable');return False
        try:pair_frames=native_pair_frames(native['build_observation'],native['observation']['construction_feedback'])
        except ContractError as error:
            if error.code!='macro_production_observations_too_far_apart':raise
            self.event('macro_sample_deferred',reason_code=error.code);return False
        native_seconds=max(self.latest['game_time_seconds'],max(pair_frames)/15)
        if isinstance(self.controller,MacroExpansionController):
            native_seconds=max([native_seconds,*[row['frame']/15 for key in ('readiness','dependency','lifecycle')
                if type(row:=native.get(key)) is dict and type(row.get('frame')) is int and 0<row['frame']<=0xffffffff]])
        # A slow native read can cross expiry after the lawful view was read.
        # Release expired intents before a later autonomous queue is observed.
        self.controller.tick(native_seconds)
        if isinstance(self.controller,MacroScoutingController):self.controller.observe_snapshot(self.latest)
        self.controller.refresh(native)
        self.capability_sample_frames=tuple(pair_frames)
        if getattr(self,'strategy_runtime',None) is not None:
            # Capture this still-active, independently bounded sample before a
            # first-queue goal immediately clears its gate below.
            self.strategy_runtime.observe(self.controller,self.transport.native_status(),native_seconds)
        if 'observation' in native and 'build_observation' in native:
            self.last_infrastructure=observe_infrastructure(native['build_observation'],native['observation']['construction_feedback'])
        self.controller.tick(native_seconds)
        if update_capabilities:self.update_macro_control(native_seconds)
        feedback=self.controller.production_feedback()
        if feedback:
            self.last_production_feedback=feedback
            self.event('macro_production_feedback',**feedback)
        construction=self.controller.construction_feedback()
        if construction:
            self.last_construction_feedback=construction
            self.event('macro_construction_feedback',**construction)
        if isinstance(self.controller,MacroScoutingController):
            scouting=self.controller.scouting_feedback()
            if scouting:
                self.last_scouting_feedback=scouting
                self.event('macro_scouting_feedback',**scouting)
        if isinstance(self.controller,MacroRegionalController):
            regional=self.controller.regional_feedback()
            if regional:
                self.last_regional_feedback=regional
                self.event('macro_regional_feedback',**regional)
        if isinstance(self.controller,MacroExpansionController):
            expansion=self.controller.expansion_feedback()
            if expansion and native.get('expansion_sample_coherent') is not False:
                self.last_expansion_feedback=compact_expansion_feedback(expansion,native_seconds)
                self.event('macro_expansion_feedback',**self.last_expansion_feedback)
            else:self.last_expansion_feedback=None
            self.refresh_resource_feedback()
            if self.last_resource_feedback:self.event('macro_resource_feedback',**self.last_resource_feedback)
            if native.get('expansion_sample_coherent') is False:
                self.event('macro_expansion_sample_deferred',reason_code=native.get('expansion_sample_reason','macro_expansion_components_unavailable'))
        return True

    def unified_tick(self,native,*,update_capabilities=True):
        from host_runtime.strategic_unified_observation_v5 import validate_sample
        frames=validate_sample(native,self.latest,self.transport,self.strategic_transport_binding)
        if frames is None:
            self.event('macro_sample_deferred',reason_code='unified_native_sample_out_of_phase');return False
        state=native['unified_native'];observation=native['observation']
        if not self.controller.observe(observation,state,native['independent_controls']):return False
        self.capability_sample_frames=frames;self.capability_sample_kind='rooted_strategy_v5'
        self.last_unified_feedback=self.controller.unified_feedback()
        if update_capabilities or self.latest['paused']:self.update_macro_control(self.latest['game_time_seconds'])
        self.event('macro_unified_feedback',**self.last_unified_feedback)
        return True

    def strategic_tick(self,native,*,update_capabilities=True):
        """Use real strategic observations without requesting precise queues."""
        from host_runtime.macro_strategic_observation_v1 import validate_strategic_observation_v1,KIND
        from read_script_flags import inspect_flags
        controller=self.controller
        # These are existing controller state, never caller assertions. Fine
        # goals and unresolved delivery cannot migrate into strategic mode.
        if type(controller) not in (MacroProductionController,MacroScoutingController,MacroRegionalController,
                                    MacroExpansionController,MacroExpansionControllerV4):
            raise ContractError('macro_strategic_controller_unknown')
        trackers=[controller.tracker,controller.construction_tracker]
        if isinstance(controller,MacroExpansionController):
            trackers.append(controller.expansion_tracker)
            store=controller.reservation_store
            if store is not None and store.unresolved:raise ContractError('macro_strategic_reservation_unresolved')
        if isinstance(controller,MacroExpansionControllerV4) and controller.reconciliation_blocked is not None:
            raise ContractError('macro_strategic_reconciliation_required')
        if controller.stopped or any(t is not None and not t.policy_released for t in trackers):
            raise ContractError('macro_strategic_precision_active')
        if self.strategy_runtime is not None and any(row.unknown for row in self.strategy_runtime.commands.values()):
            raise ContractError('macro_strategic_delivery_unknown')
        rows=self.journal.commands_for_run(self.run_id)
        if any(row['status']=='uncertain' or row['operation']=='macro_policy' and row['status']!='completed' for row in rows):
            raise ContractError('macro_strategic_delivery_unknown')
        if self.transport.pending is not False or any(row['status']!='acknowledged' for row in self.transport.ledger.values()):
            raise ContractError('macro_strategic_delivery_unknown')
        state=self.transport.native_status()
        flags=inspect_flags(self.transport.memory.read,list(self.strategic_transport_binding.flags))
        after=self.transport.native_status()
        # Native changes during the independent flag read need another normal
        # observation, never a replay of the preceding command.
        stable=('request','ack','phase','active','error','applied_mask','deadline_frame','cleanup_verified')
        if any(state[key]!=after[key] for key in stable):
            self.event('macro_sample_deferred',reason_code='macro_strategic_flags_changed');return False
        frames=validate_strategic_observation_v1(native,self.latest,after,flags,self.strategic_transport_binding)
        if frames is None:
            self.event('macro_sample_deferred',reason_code='macro_strategic_observation_out_of_phase');return False
        seconds=max(self.latest['game_time_seconds'],max(frames)/15)
        # Native kind1 (including an empty-mask release) is rejected while
        # paused. Keep observing automatic native cleanup, but wait for resume
        # before ticking the original, unchanged intent deadline. STOP kind2
        # remains the independent shutdown path.
        paused=self.latest['paused']
        if not paused:controller.tick(seconds)
        if isinstance(controller,MacroScoutingController):controller.observe_snapshot(self.latest)
        if isinstance(controller,MacroExpansionController):MacroRegionalController.refresh(controller,native)
        else:controller.refresh(native)
        controller.construction_candidate=None
        self.last_infrastructure=None;self.last_production_feedback=None;self.last_construction_feedback=None
        self.last_expansion_feedback=None;self.last_resource_feedback=None
        self.capability_sample_frames=frames;self.capability_sample_kind=KIND
        if self.strategy_runtime is not None:self.strategy_runtime.observe(controller,after,seconds)
        if not paused:controller.tick(seconds)
        if update_capabilities or paused:self.update_macro_control(seconds)
        for cls,method,attribute,event in (
            (MacroScoutingController,'scouting_feedback','last_scouting_feedback','macro_scouting_feedback'),
            (MacroRegionalController,'regional_feedback','last_regional_feedback','macro_regional_feedback')):
            if isinstance(controller,cls):
                feedback=getattr(controller,method)();setattr(self,attribute,feedback)
                if feedback:self.event(event,**feedback)
        self.event('macro_strategic_observation',sample_kind=KIND,builder_status='not_requested',
            observed_frames=list(frames),queue_effect_verified=False,detailed_action_granted=False)
        return True

    def archive_expansion_sample(self,native):
        if getattr(self,'expansion_archive_truncated',False):return
        value=dict(schema_version=1,kind='private_macro_expansion_component_sample',
            session_id=self.binding.session_id,monotonic_ns=time.monotonic_ns(),
            game_time_seconds=self.latest['game_time_seconds'],
            transport_native=self.transport.native_status(),
            original_transport_frames=dict(observation=native.get('observation',{}).get('frame'),
                builder=native.get('build_observation',{}).get('frame')),
            components={key:native.get(key) for key in ('readiness','dependency','lifecycle',
                'expansion_sample_coherent','expansion_sample_reason','expansion_sample_errors',
                'expansion_sample_error_details','expansion_component_timings','expansion_private_read_trace')})
        encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n'
        used=getattr(self,'expansion_archive_bytes',0)+len(encoded.encode('utf8'))
        if used>128*1024*1024:
            self.expansion_archive_truncated=True
            self.event('macro_expansion_component_archive_truncated',reason_code='private_archive_size_bound')
            return
        with (self.output/'macro-expansion-samples.jsonl').open('a',encoding='utf8') as stream:stream.write(encoded)
        self.expansion_archive_bytes=used

    def observe_current(self):
        if getattr(self,'strategic_only',False):
            from host_runtime.macro_delegation_boundary_v1 import restrict_snapshot
            self.latest=restrict_snapshot(self.latest)
        # Archive every successful lawful startup view immediately. Cost boot
        # may outlast visibility before the agent exists, so retain an isolated
        # copy to prime it later with the real original IDs and timestamps.
        encoded=json.dumps(self.latest,ensure_ascii=False,allow_nan=False)
        with (self.output/'macro-snapshots.jsonl').open('a',encoding='utf8') as stream:
            stream.write(encoded+'\n')
        snapshot=json.loads(encoded)
        if getattr(self,'agent',None) is None:
            pending=getattr(self,'startup_lawful_snapshots',[])
            if len(pending)>=8:raise ContractError('macro_startup_snapshot_bound')
            pending.append(snapshot);self.startup_lawful_snapshots=pending
        else:self.agent.observe(snapshot)

    def prime_startup_snapshots(self):
        if getattr(self,'agent',None) is None:raise ContractError('macro_startup_agent_missing')
        # Acquisition order is authoritative; BattleAgent enforces monotonic
        # snapshots and the existing unseen/hidden-contact guards unchanged.
        pending=getattr(self,'startup_lawful_snapshots',[])
        for snapshot in pending:self.agent.observe(snapshot)
        self.event('macro_startup_history_primed',snapshot_count=len(pending),
            first_snapshot_id=pending[0]['snapshot_id'] if pending else None,
            last_snapshot_id=pending[-1]['snapshot_id'] if pending else None,
            transport_constructor_started=False,attach_started=False)
        self.startup_lawful_snapshots=[]

    def consume_observation(self,native):
        coherent=self.production_tick(native)
        # VisibilityProjection has already retained this lawful view. Feed it
        # to agent memory even when native builder telemetry is discarded;
        # otherwise a later last-seen contact appears to change while hidden.
        self.observe_current()
        return coherent

    def refresh_dispatch_observation(self,plan):
        collect=getattr(getattr(self,'sampler',None),'collect',None)
        if not callable(collect):return True
        self.latest=collect();self.last_forces=observe_forces(self.sampler.latest_census,self.sampler.safety)
        # Feed the real pre-view to history even if subsequent native sampling
        # fails. VisibilityProjection has already retained this observation.
        self.observe_current()
        if (self.latest['paused'] or plan.expires_at_game_seconds<=self.latest['game_time_seconds']
                or not isinstance(self.controller,(MacroProductionController,UnifiedStrategicControllerV5))):return True
        native=self.transport.observe('desktop_macro_dispatch_revalidation')
        if isinstance(self.sampler.scope,ExpansionScope) and not getattr(self,'strategic_only',False):
            native=self.sampler.collect_expansion(native);self.archive_expansion_sample(native)
        # Refresh actual native predicates and bounded effects first. Do not
        # spend a duplicate cost scan to decorate an already observed ID.
        if not self.production_tick(native,update_capabilities=False):
            self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code='macro_dispatch_native_pair_deferred')
            return False
        return self.observe_post_native_view(plan=plan)

    def observe_post_native_view(self,*,plan=None):
        """Get a true post-view after native memory mutations, without retiming."""
        collect=getattr(getattr(self,'sampler',None),'collect',None)
        if not callable(collect):raise ContractError('macro_post_native_view_unavailable')
        self.latest=collect();self.last_forces=observe_forces(self.sampler.latest_census,self.sampler.safety)
        try:
            if self.latest['paused'] or plan is not None and plan.expires_at_game_seconds<=self.latest['game_time_seconds']:return True
            if isinstance(self.controller,(MacroProductionController,UnifiedStrategicControllerV5)):
                pair=getattr(self,'capability_sample_frames',None);frame=self.latest['game_time_seconds']*15
                if pair is None or any(not -1e-6<=frame-value<=15+1e-6 for value in pair):
                    if plan is None:self.event('macro_decision_deferred',reason_code='macro_request_native_pair_stale')
                    else:self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code='macro_dispatch_native_pair_stale')
                    return False
            else:return True
            # This is a new qualification at the post-view time, never a copy
            # of the request's actions or the sampler's budget-only defaults.
            self.update_macro_control(self.latest['game_time_seconds'])
        finally:self.observe_current()
        return True

    def prepare_model_request(self,audited):
        """Capture one request synchronously before any async scheduling gap."""
        if not self.observe_post_native_view():return None
        if self.latest['paused']:return None
        if not request_telemetry_ready(audited,self.latest,self.event):return None
        from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1
        try:return prepare_macro_request_v1(self.agent,audited,self.agent.latest)
        except (ContractError,StrategyContractError) as error:
            code=getattr(error,'code',None) or str(error)
            if code!='strategy_context_before_memory':raise
            # A new real observation is required; never move the old time or
            # insert a newer memory into an older request to make it pass.
            self.event('macro_decision_deferred',reason_code=code)
            return None

    def dispatch_plan(self,plan):
        if getattr(self,'strategic_only',False):
            from host_runtime.macro_delegation_boundary_v1 import validate_policy
            try:validate_policy(plan)
            except ContractError as error:
                self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code=error.code)
                return False
        if getattr(self,'strategy_runtime',None) is not None:
            if not self.refresh_dispatch_observation(plan):return False
        if self.latest['paused'] or plan.expires_at_game_seconds<=self.latest['game_time_seconds']:
            self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code='expired_or_paused')
            return False
        review=None
        if getattr(self,'strategy_runtime',None) is not None:
            try:
                current=self.agent.context(self.agent.latest.model_context(self.agent.engine.binding),commit=False)
                review=self.strategy_runtime.review(plan,self.strategy_audit,self.strategy_audit.prepare(current))
            except ContractError as error:
                self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code=error.code)
                return False
            if not review.allowed:
                self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code=review.reason_code)
                return False
        try:
            receipt=self.controller.dispatch(plan,self.latest['game_time_seconds'],effective_hash=self.expected_hash,paused=False)
        except ContractError as error:
            self.current_resource_feedback()
            if error.code=='macro_dispatch_outcome_unknown' and getattr(self,'strategy_runtime',None) is not None:
                command_id=self.prepared_macro_commands.get(plan.plan_id)
                if command_id is not None:self.strategy_runtime.dispatched(review,plan,None,self.latest['game_time_seconds'],unknown_command_id=command_id)
            if error.code not in {'macro_production_not_currently_available','macro_production_goal_active','macro_construction_not_currently_available','macro_scout_not_currently_available','macro_region_not_currently_available',
                    'macro_expansion_not_currently_available','macro_expansion_components_unavailable',
                    'blocked_native_cost_reservation_unverified','macro_resource_insufficient_unreserved_credits',
                    'macro_resource_reservation_unresolved','macro_admission_v4_active_buffer_unresolved',
                    'macro_admission_v4_insufficient_current_funds','macro_admission_v4_refused_before_native',
                    'macro_admission_v4_plan_expired_before_native','macro_admission_v4_financial_state_unverified',
                    'macro_admission_v4_cost_unverified'}:raise
            # A newly occupied/lost producer revokes the old response. No
            # native delivery was attempted; the next decision uses new facts.
            self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code=error.code)
            return False
        self.current_resource_feedback()
        if getattr(self,'strategy_runtime',None) is not None:
            if hasattr(self,'journal') and type(receipt) is dict:
                recorded=self.journal.get_command(self.run_id,receipt['command_id'])
                proof=recorded.get('receipt') or {}
                if (recorded['status']!='completed' or recorded['payload'].get('actions')!=list(plan.macro_actions)
                        or proof.get('seq')!=receipt.get('seq')):raise ContractError('strategy_native_receipt_required')
                receipt=dict(receipt,**{key:proof[key] for key in ('native_start_frame','native_deadline_frame') if key in proof})
            self.strategy_runtime.dispatched(review,plan,receipt,self.latest['game_time_seconds'])
        self.last_plan=plan.public()
        self.event('plan_applied',plan_id=plan.plan_id,snapshot_id=plan.snapshot_id,plan=plan.public())
        return True

    def compact_resource_feedback(self,value):
        if value is None:return None
        codec=compact_admission_feedback_v4 if isinstance(self.controller,MacroExpansionControllerV4) else compact_reservation
        return codec(value)

    def refresh_resource_feedback(self):
        if isinstance(self.controller,MacroExpansionControllerV4):
            # Only this canonical store snapshot is current. It needs no
            # native observation and never changes financial sample frames.
            with self.controller.dispatch_lock:
                self.last_resource_feedback=self.compact_resource_feedback(self.controller.resource_feedback())
        elif isinstance(self.controller,MacroExpansionController):
            self.last_resource_feedback=self.compact_resource_feedback(self.controller.resource_feedback())
        return getattr(self,'last_resource_feedback',None)

    def current_resource_feedback(self):
        if getattr(self,'strategic_only',False):return None
        if isinstance(self.controller,MacroExpansionControllerV4):return self.refresh_resource_feedback()
        return getattr(self,'last_resource_feedback',None)

    def create_controller(self):
        scope=self.sampler.scope
        if type(scope) is UnifiedStrategicScopeV5:
            return UnifiedStrategicControllerV5(self.transport,self.journal,self.run_id,scope,self.binding.session_id,self.expected_hash,self.event)
        if isinstance(scope,ExpansionScope):
            boot=getattr(self,'cost_boot',None)
            session=getattr(boot,'session',None)
            if session is not None:
                # The factory borrows the one existing raw probe and creates
                # its sole durable wrapper and shared physical dispatch lock.
                from read_script_flags import inspect_flags
                return create_expansion_controller_v4(self.transport,self.journal,self.run_id,scope,session,
                    self.expected_hash,self.event,read_flags=inspect_flags,
                    cost_supplier=getattr(boot,'cost_supplier',None),
                    financial_supplier=getattr(boot,'financial_supplier',None),
                    persist=lambda value:_atomic(self.output/'active-preference-buffers-v4.json',value))
            # An unverified boot never opens new preferences. The original
            # thirteen retain their previously qualified controller path.
            reservations=ResourceReservationStore(self.binding.session_id,
                persist=lambda value:_atomic(self.output/'resource-reservations.json',value))
            _atomic(self.output/'resource-reservations.json',reservations.snapshot())
            return MacroExpansionController(DurableMacroTransport(self.transport,self.journal,self.run_id),scope,
                self.binding.session_id,self.expected_hash,self.event,cost_supplier=None,reservation_store=reservations)
        controller_type=(MacroRegionalController if isinstance(scope,RegionalScope) else
            MacroScoutingController if isinstance(scope,ScoutingScope) else
            MacroProductionController if isinstance(scope,ProductionPreferenceScope) else BudgetController)
        return controller_type(DurableMacroTransport(self.transport,self.journal,self.run_id),scope,
            self.binding.session_id,self.expected_hash,self.event)

    def freeze_publication_contract(self):
        """Explicit pre-attach selector for the new publication/release grammar."""
        if not isinstance(self.sampler.scope,ExpansionScope):return
        session=getattr(getattr(self,'cost_boot',None),'session',None)
        catalog_v5=type(self.sampler.bundle.get('schema_version')) is int and self.sampler.bundle['schema_version']==12
        if session is None:
            if catalog_v5:raise ContractError('macro_catalog_v5_canonical_session_required')
            return
        from dataclasses import asdict
        from host_runtime.resource_settlement_adapter import SettlementSession
        from host_runtime import raw_admission_publisher_v4 as publisher
        from host_runtime import macro_expansion_factory_v4 as factory
        from host_runtime import macro_admission_delivery_v4 as delivery
        if type(session) is not SettlementSession:raise ContractError('macro_admission_v4_canonical_session_required')
        session.validate()
        if (digest(Path(publisher.__file__))!=publisher.SOURCE_SHA or digest(publisher.CLIENT)!=publisher.CLIENT_SHA
                or digest(Path(factory.__file__))!=factory.GUARDED_SOURCE_SHA256
                or digest(Path(delivery.__file__))!=delivery.DELIVERY_SOURCE_SHA256):
            raise ContractError('macro_admission_v4_publication_source_changed')
        manifest=Path(self.sampler.bundle['build'])/'build-manifest.json'
        value=dict(kind='guarded_admission_publication_contract_v4',schema_version=1,
            session=asdict(session),binding_hash=self.binding.binding_hash,run_id=self.run_id,
            native_build_manifest_path=str(manifest.resolve()),native_build_manifest_sha256=digest(manifest),
            publisher_source_path=str(Path(publisher.__file__).resolve()),publisher_source_sha256=publisher.SOURCE_SHA,
            client_source_path=str(publisher.CLIENT.resolve()),client_source_sha256=publisher.CLIENT_SHA,
            controller_factory_source_sha256=factory.GUARDED_SOURCE_SHA256,
            delivery_adapter_source_sha256=delivery.DELIVERY_SOURCE_SHA256,
            pre_execution_sources_sha256=digest(self.output/'sources.json'),
            created_monotonic_ns=time.monotonic_ns(),native_constructor_started=False)
        if catalog_v5:
            from host_runtime import macro_release_review_v5 as reviewer
            from host_runtime import macro_catalog_bundle_v12 as catalog
            outer,_=catalog.load_catalog_bundle_v12(self.args.macro_bundle,self.session)
            outer_path=Path(self.args.macro_bundle).resolve();base_path=Path(outer['base_bundle']).resolve()
            value.update(kind=reviewer.KIND,outer_bundle_path=str(outer_path),outer_bundle_sha256=digest(outer_path),
                base_bundle_path=str(base_path),base_bundle_sha256=digest(base_path),catalog_loader_source_sha256=digest(Path(catalog.__file__)),
                reviewer_source_sha256=digest(Path(reviewer.__file__)))
            reviewer._frozen_sources(self.output)
            path=self.output/'publication-v5-contract.json';_atomic(path,value)
            # Validate the archive/qualification before constructor entry. The
            # ordered selector event is added next and verified at release.
            self.publication_v5_selected=True
            self.event(reviewer.SELECTOR,contract_sha256=digest(path),publisher_source_sha256=publisher.SOURCE_SHA,
                outer_bundle_sha256=value['outer_bundle_sha256'],base_bundle_sha256=value['base_bundle_sha256'],native_constructor_started=False)
            return
        path=self.output/'publication-v4-contract.json';_atomic(path,value)
        self.event('macro_admission_publication_contract_frozen',contract_sha256=digest(path),
            publisher_source_sha256=publisher.SOURCE_SHA,native_constructor_started=False)
        self.publication_v4_selected=True

    def finish_transport(self):
        if self.transport is None:
            if getattr(self,'transport_config',{}).get('protocol_version')==5:
                from host_runtime.strategic_no_attachment_v5 import capture,KIND
                proof=capture(self.sampler.memory if self.sampler is not None else None,self.session,self.binding,self.run_id)
                path=self.output/'native-no-attachment.json';_atomic(path,proof)
                stop=self.journal.reserve_command(self.run_id,'macro-stop','macro_policy_stop',dict(binding_hash=self.binding.binding_hash))
                if not stop['created']:raise ContractError('macro_stop_already_claimed')
                self.journal.mark_dispatching(self.run_id,'macro-stop')
                release=dict(kind='macro_policy_native_release',binding=self.binding.public(),run_id=self.run_id,
                    host_pid=self.host_pid,host_start_time=self.host_start,native_release_verified=True,
                    native_release_contract=KIND,no_attachment_sha256=digest(path))
                _atomic(self.output/'macro-release.json',release)
                self.journal.record_outcome(self.run_id,'macro-stop','released',dict(binding_hash=self.binding.binding_hash,
                    host_pid=self.host_pid,host_start_time=self.host_start,native_release_verified=True,
                    native_release_contract=KIND,no_attachment_sha256=digest(path),release_sha256=digest(self.output/'macro-release.json')))
            return
        stop=self.journal.reserve_command(self.run_id,'macro-stop','macro_policy_stop',dict(binding_hash=self.binding.binding_hash))
        if not stop['created']:raise ContractError('macro_stop_already_claimed')
        self.journal.mark_dispatching(self.run_id,'macro-stop')
        try:
            if isinstance(self.controller,MacroExpansionControllerV4):
                # macro-stop is already dispatching. It must remain visible
                # to the complete ledger; native release is independent of
                # closing this admission buffer or attributing any payment.
                self.controller.stop(reconcile_before_close=False)
            elif self.controller:self.controller.stop()
            else:self.transport.close()
            if isinstance(self.controller,MacroProductionController):
                self.last_production_feedback=self.controller.production_feedback()
                self.last_construction_feedback=self.controller.construction_feedback()
            if isinstance(self.controller,MacroScoutingController):self.last_scouting_feedback=self.controller.scouting_feedback()
            if isinstance(self.controller,MacroRegionalController):self.last_regional_feedback=self.controller.regional_feedback()
            if isinstance(self.controller,MacroExpansionController):
                expansion=self.controller.expansion_feedback()
                self.last_expansion_feedback=compact_expansion_feedback(expansion,
                    max(expansion['builder_frame'],expansion['own_census_frame'])/15) if expansion else None
                self.refresh_resource_feedback()
                if self.last_expansion_feedback:self.event('macro_expansion_feedback',**self.last_expansion_feedback)
                if self.last_resource_feedback:self.event('macro_resource_feedback',**self.last_resource_feedback)
            path=ROOT/'reports'/('macro-desktop-'+self.run_id)/'final-state.json'
            final=json.loads(path.read_text(encoding='utf8'))
            if self.transport_config['protocol_version']==5:
                from host_runtime.strategic_unified_release_v5 import verified_final
                verified=verified_final(final,path.with_name('independent-release.json'),self.session,self.binding,self.transport.manifest)
            else:verified=native_release_matches(final,self.session,self.binding,self.transport.manifest['flags'])
            publication={}
            from host_runtime.macro_catalog_release_route_v1 import requires_v5,extension
            use_v5=requires_v5(self.output,journal=self.journal,run_id=self.run_id,
                bundle=getattr(getattr(self,'sampler',None),'bundle',None),selected=getattr(self,'publication_v5_selected',False))
            contract=self.output/('publication-v5-contract.json' if use_v5 else 'publication-v4-contract.json')
            if use_v5:
                if not contract.is_file():raise ContractError('macro_release_v5_contract_missing')
                if not verified:raise ContractError('macro_stop_unverified')
                from host_runtime.macro_release_review_v5 import write_release_review_v5
                review,review_sha,result=write_release_review_v5(path.parent,contract_path=contract,
                    expected=self.transport.manifest,expected_binding=self.binding,expected_run_id=self.run_id)
                if (result[1]!=final or review!=contract.with_name('publication-v5-release-review.json')
                        or digest(review)!=review_sha):raise ContractError('macro_release_v5_final_state_changed')
                publication=extension(json.loads(review.read_text(encoding='utf8')),contract,review)
            if (isinstance(self.controller,MacroExpansionControllerV4) or getattr(self,'publication_v4_selected',False)) and not contract.is_file():
                raise ContractError('macro_release_v4_contract_missing')
            if not use_v5 and contract.exists():
                if not verified:raise ContractError('macro_stop_unverified')
                from host_runtime.macro_release_review_v4 import write_release_review_v4
                review,review_sha,result=write_release_review_v4(path.parent,contract_path=contract,
                    expected=self.transport.manifest,expected_binding=self.binding,expected_run_id=self.run_id)
                if (result[1]!=final or review!=contract.with_name('publication-v4-release-review.json')
                        or digest(review)!=review_sha):raise ContractError('macro_release_v4_final_state_changed')
                publication=dict(native_release_contract='guarded_admission_publication_contract_v4',
                    publication_v4_contract_sha256=digest(contract),publication_v4_release_review_sha256=review_sha)
            if self.transport_config['protocol_version']==5:
                publication=dict(native_release_contract='strategic_unified_release_v5',independent_release_sha256=final['independent_release_sha256'])
            proof=dict(kind='macro_policy_native_release',binding=self.binding.public(),run_id=self.run_id,
                host_pid=self.host_pid,host_start_time=self.host_start,native_release_verified=verified,final_state_sha256=digest(path),**publication)
            _atomic(self.output/'macro-release.json',proof)
            self.journal.record_outcome(self.run_id,'macro-stop','released' if verified else 'uncertain',dict(
                binding_hash=self.binding.binding_hash,host_pid=self.host_pid,host_start_time=self.host_start,
                native_release_verified=verified,final_state_sha256=digest(path),release_sha256=digest(self.output/'macro-release.json'),**publication))
            if getattr(self,'strategy_runtime',None) is not None:
                self.strategy_runtime.finish(max(self.latest['game_time_seconds'],final['native']['last_frame']/15),release_verified=verified)
            if not verified:raise ContractError('macro_stop_unverified')
        except BaseException:
            if self.journal.get_command(self.run_id,'macro-stop')['status']=='dispatching':
                self.journal.record_outcome(self.run_id,'macro-stop','uncertain',dict(native_release_verified=False))
            raise

    def record_run_exception(self,error):
        """Classify only a known result signal from a returned constructor.

        This is a candidate, never visual confirmation or a cleanup proof.
        The independent release in run.finally still decides safe termination.
        """
        if isinstance(error,ContractError) and error.code=='strategic_stop_already_committed' and self.stopping():
            self.phase='stopped';self.reason='user_stop'
            self.event('macro_dispatch_cancelled_before_stop_barrier',reason_code='user_stop')
            return
        candidate=(isinstance(error,ContractError) and error.code in ('macro_match_ended','macro_native_result_candidate')
            and getattr(self,'native_transport_attached',False) is True and self.transport is not None)
        if candidate:
            try:_atomic(self.output/'result-native-state.json',self.sampler.state)
            except BaseException as archive_error:
                self.event('macro_result_candidate_archive_failed',native_reason_code=error.code,error_type=type(archive_error).__name__)
                error=archive_error;candidate=False
        self.phase='result_candidate' if candidate else 'fault'
        self.reason='native_result_requires_visual_confirmation' if candidate else error.code if isinstance(error,ContractError) else 'macro_host_failed'
        if not candidate and isinstance(error,StrategyContractError) and re.fullmatch(r'[a-z][a-z0-9_]{0,79}',str(error)):
            self.reason=str(error)
        self.event('macro_result_candidate' if candidate else 'host_fault',reason_code=self.reason,
            native_reason_code=error.code if candidate else None,error_type=type(error).__name__,source_frames=[
                dict(file=str(Path(frame.filename).relative_to(ROOT)) if Path(frame.filename).is_relative_to(ROOT) else Path(frame.filename).name,
                     line=frame.lineno,function=frame.name) for frame in traceback.extract_tb(error.__traceback__)[-12:]])

    async def run(self):
        last_request=-100.;failures=0
        strategic_only=getattr(self,'strategic_only',False)
        self.native_transport_attached=False
        try:
            bundle,scope=load_bundle(self.args.macro_bundle,self.session)
            self.product_source_locks=None
            if type(scope) is UnifiedStrategicScopeV5:
                from host_runtime.strategic_source_locks_v5 import ProductSourceLocksV5
                pins={**bundle['pins'],str(self.args.macro_bundle.resolve()):digest(self.args.macro_bundle),
                    str(self.args.session.resolve()):digest(self.args.session),str(Path(self.session['registry']).resolve()):digest(self.session['registry']),
                    str(Path(self.session['mod_big']).resolve()):self.session['mod_sha256']}
                self.product_source_locks=ProductSourceLocksV5(pins)
            manifest=json.loads((Path(bundle['build'])/'build-manifest.json').read_text(encoding='utf-8-sig'))
            self.transport_config=native_transport_config(scope,manifest,getattr(self.args,'max_wall_seconds',None))
            self.args.max_wall_seconds=self.transport_config['max_wall_seconds']
            bundle_sha=digest(self.args.macro_bundle)
            _atomic(self.output/'native-transport-preflight.json',dict(kind='native_macro_host_preflight',
                schema_version=1,bundle_sha256=bundle_sha,scope=scope.public(),transport=self.transport_config,attach_started=False))
            self.freeze();self.sampler=MacroSampler(self.args.session,self.args.macro_bundle,strategic_only=strategic_only)
            if digest(self.args.macro_bundle)!=bundle_sha:raise ContractError('session_changed')
            selected=native_transport_config(self.sampler.scope,manifest,self.args.max_wall_seconds)
            if selected!=self.transport_config:raise ContractError('macro_native_transport_protocol_mismatch')
            self.latest=self.sampler.collect();self.observe_current();self.check_profile()
            self.last_forces=observe_forces(self.sampler.latest_census,self.sampler.safety)
            _atomic(self.output/'visibility-proof.json',self.sampler.proof)
            _atomic(self.output/'participants.json',self.sampler.participants)
            self.cost_boot=None
            if isinstance(self.sampler.scope,ExpansionScope) and not getattr(self,'strategic_only',False):
                # Offline archive work precedes native hook/lease ownership.
                # Failure only closes the seven new cost-gated preferences.
                from host_runtime.macro_cost_boot_v4 import boot_macro_cost_v4
                self.publish()
                self.cost_boot=boot_macro_cost_v4(self.sampler,
                    output=ROOT/'reports'/('macro-cost-v4-'+self.run_id),event=self.event)
                self.latest=self.sampler.collect();self.observe_current()
                self.last_forces=observe_forces(self.sampler.latest_census,self.sampler.safety)
            self.application=apply_commander_draft(load_profile(self.args.library,self.binding.commander_id),self.draft)
            if self.application.effective.effective_hash!=self.expected_hash:raise ContractError('effective_profile_changed')
            self.stop_gate=None
            if type(self.sampler.scope) is UnifiedStrategicScopeV5:
                from host_runtime.strategic_stop_gate_v1 import StrategicStopGateV1
                self.stop_gate=StrategicStopGateV1(self.run_id,self.binding,self.output)
            self.backend=create_applied_backend(self.application,event_sink=lambda kind,payload:self.event(kind,**payload),
                request_admission=self.stop_gate.admit if self.stop_gate is not None else None,
                backend='pydantic',timeout=28,max_tokens=1536,max_input_bytes=16384,max_inflight=1)
            engine=StrategyEngine(Binding(self.binding.session_id,3,self.binding.commander_id,self.profile['name'],self.profile['connection_id']),
                timeout_seconds=30,max_response_age_seconds=30,min_hold_game_seconds=15,
                audit_path=self.output/'plans.jsonl',status_path=self.output/'strategy-status.json')
            self.agent=BattleAgent(engine,memory_path=self.output/'agent-state.json',jobs_path=self.output/'jobs.json',
                context_budget_bytes=16384 if isinstance(self.sampler.scope,(ExpansionScope,UnifiedStrategicScopeV5)) else 8192)
            if getattr(self.args,'strategy_mode','legacy')=='declared':
                memory=MacroStrategyMemory(session_id=self.binding.session_id,commander_id=self.binding.commander_id,
                    player_id=3,profile_revision=self.expected_revision,effective_hash=self.expected_hash)
                runtime_type=UnifiedStrategyRuntimeV5 if type(self.sampler.scope) is UnifiedStrategicScopeV5 else MacroStrategyRuntime
                self.strategy_runtime=runtime_type(memory,self.event)
            self.prime_startup_snapshots()
            if type(scope) is UnifiedStrategicScopeV5:
                from host_runtime.native5_capacity_preflight_v1 import check_native5_capacity
                from macro_policy import public_descriptions
                provider=self.profile.get('provider')
                if provider not in ('DeepSeek','OpenAI','自定义'):
                    raise ContractError('model_context_capacity_provider_unavailable')
                if provider!=self.application.profile.provider:
                    raise ContractError('effective_profile_changed')
                catalog=public_descriptions(scope.available_actions,region_targets=scope.regional_action_regions.items())
                catalog.update(scope.model_catalog_overrides())
                capacity=check_native5_capacity(self.application.effective,provider,self.latest,catalog)
                self.event('macro_model_capacity_checked',native_constructor_started=False,capacity=capacity)
                if not capacity['fits']:raise ContractError(capacity['reason_code'])
            self.freeze_publication_contract()
            spec=importlib.util.spec_from_file_location('desktop_macro_native_transport',self.transport_config['client_path'])
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            from contextlib import nullcontext
            with self.stop_gate.admit('native_constructor') if self.stop_gate is not None else nullcontext() as admission:
                admitted={'admission_id':admission['admission_id']} if admission is not None else {}
                self.event('macro_native_transport_constructor_begin',constructor_boundary_entered=True,attach_started=None,**admitted)
                self.transport=module.MacroPolicyProbe.__new__(module.MacroPolicyProbe)
                self.transport.__init__(self.args.session,self.sampler.owner,Path(self.sampler.bundle['build']),
                    ROOT/'reports'/('macro-desktop-'+self.run_id),build_feedback=(
                        isinstance(self.sampler.scope,ProductionPreferenceScope) and not strategic_only))
                self.native_transport_attached=True
                if self.stop_gate is not None:self.transport.configure_stop_gate(self.stop_gate)
                self.event('macro_native_transport_constructor_returned',constructor_returned=True,attach_started=None)
            if strategic_only:
                if type(self.sampler.scope) is UnifiedStrategicScopeV5:
                    from host_runtime.strategic_unified_observation_v5 import bind_transport
                    self.strategic_transport_binding=bind_transport(self.transport,self.session)
                else:
                    from host_runtime.macro_strategic_observation_v1 import bind_strategic_transport_v1
                    self.strategic_transport_binding=bind_strategic_transport_v1(self.transport,self.session)
            self.controller=self.create_controller()
            audit_type=UnifiedRequestAuditV5 if type(self.controller) is UnifiedStrategicControllerV5 else MacroRequestAuditV4 if isinstance(self.controller,MacroExpansionControllerV4) else MacroRequestAudit
            audited=audit_type(self.backend,self.event,feedback_supplier=lambda:getattr(self,'last_feedback',None),
                production_supplier=None if strategic_only else lambda:getattr(self,'last_production_feedback',None),
                construction_supplier=None if strategic_only else lambda:getattr(self,'last_construction_feedback',None),
                infrastructure_supplier=None if strategic_only else lambda:getattr(self,'last_infrastructure',None),
                scouting_supplier=lambda:getattr(self,'last_scouting_feedback',None),
                regional_supplier=lambda:getattr(self,'last_regional_feedback',None),
                forces_supplier=lambda:getattr(self,'last_forces',None),
                expansion_supplier=(lambda:getattr(self,'last_expansion_feedback',None)) if not strategic_only and isinstance(self.controller,MacroExpansionController) else None,
                resource_supplier=self.current_resource_feedback if not strategic_only and isinstance(self.controller,MacroExpansionController) else None,
                catalog_supplier=self.sampler.scope.model_catalog_overrides if hasattr(self.sampler.scope,'model_catalog_overrides') else None,
                strategy_supplier=self.strategy_runtime.memory.context if self.strategy_runtime is not None else None,
                strategic_only=getattr(self,'strategic_only',False),**(dict(unified_supplier=lambda:self.last_unified_feedback)
                    if audit_type is UnifiedRequestAuditV5 else {}))
            self.strategy_audit=audited
            self.event('host_started',execution_requested=True,control_mode='macro_native',
                commander_boundary='native_ai_details_v1' if getattr(self,'strategic_only',False) else 'historical_precision')
            self.event('commander_profile_applied',**self.application.public())
            while time.monotonic()-self.started<self.args.max_wall_seconds:
                if self.stopping():self.reason='user_stop';break
                self.check_profile()
                try:
                    self.latest=self.sampler.collect();failures=0
                    self.last_forces=observe_forces(self.sampler.latest_census,self.sampler.safety)
                except ContractError:raise
                except (ValueError,RuntimeError):
                    failures+=1
                    if failures>5:raise ContractError('macro_observation_unstable') from None
                    await asyncio.sleep(.2);continue
                native=self.transport.observe('desktop_macro_tick')
                if isinstance(self.sampler.scope,ExpansionScope) and not strategic_only:
                    native=self.sampler.collect_expansion(native)
                    self.archive_expansion_sample(native)
                if not self.consume_observation(native):
                    self.phase='sampling_wait';self.reason='macro_native_pair_pending';self.publish()
                    await asyncio.sleep(.2);continue
                if 'observation' in native:
                    feedback=self.controller.feedback(native['observation']);feedback.update(LIMITS)
                    self.last_feedback=feedback
                    self.agent.feedback.append(feedback)
                    self.event('macro_native_feedback',**feedback)
                    with (self.output/'macro-feedback.jsonl').open('a',encoding='utf8') as stream:
                        stream.write(json.dumps(feedback)+'\n')
                if getattr(self,'strategy_runtime',None) is not None:
                    strategy_native=self.transport.native_status()
                    self.strategy_runtime.observe(self.controller,strategy_native,
                        max(self.latest['game_time_seconds'],strategy_native['last_frame']/15),
                        budget_feedback=getattr(self,'last_feedback',None))
                if self.pending is not None and self.pending.done():
                    result=await self.pending;self.pending=None
                    self.event('decision',status=result.status,reason_code=result.reason_code)
                    if result.status=='accepted':
                        if self.stopping():self.reason='user_stop';break
                        self.check_profile()
                        if self.backend.observation()['real_network_verified']:
                            self.dispatch_plan(result.plan)
                self.phase='paused' if self.latest['paused'] else 'running';self.reason='observing'
                if (self.pending is None and not self.latest['paused'] and self.latest['game_time_seconds']>=MIN_MACRO_MODEL_GAME_SECONDS
                        and not (isinstance(self.controller,MacroProductionController) and self.controller.busy)
                        and time.monotonic()-last_request>=12):
                    # Live snapshot and native feedback are read sequentially.
                    # If those reads span too many frames, wait for a coherent
                    # next sample instead of counting an unsent provider error.
                    if self.strategy_runtime is not None:
                        prepared=self.prepare_model_request(audited)
                        if prepared is not None:
                            from host_runtime.macro_prepared_request_v1 import decide_prepared_macro_request_v1
                            self.pending=asyncio.create_task(decide_prepared_macro_request_v1(self.agent,self.agent.latest,prepared))
                            last_request=time.monotonic()
                    elif request_telemetry_ready(audited,self.latest,self.event):
                        self.pending=asyncio.create_task(self.agent.decide(self.latest,audited));last_request=time.monotonic()
                self.publish();await asyncio.sleep(.5)
            else:self.reason='host_time_limit'
        except BaseException as error:
            self.record_run_exception(error)
        finally:
            self.event('macro_host_stop_started',reason_code=self.reason)
            if self.pending:
                if not self.pending.done():self.pending.cancel()
                await asyncio.gather(self.pending,return_exceptions=True)
            if self.agent:self.agent.stop()
            try:self.finish_transport()
            except BaseException:self.phase='fault';self.reason='macro_stop_unverified'
            finally:
                if getattr(self,'strategy_runtime',None) is not None:self.strategy_runtime.memory.stop()
            if self.sampler:self.sampler.close()
            if self.phase not in ('fault','result_candidate'):self.phase='stopped'
            self.publish();self.event('host_stopped',reason_code=self.reason)
            locks=getattr(self,'product_source_locks',None)
            if locks is not None:
                # On uncertain Native return retain source handles and the
                # publisher process. Only re-read STOP/return; never reapply.
                probe=getattr(getattr(self,'transport',None),'_probe',None)
                while probe is not None and getattr(probe,'state',None) is not None and getattr(probe,'host',None) is not None:
                    self.phase='fault';self.reason='macro_stop_unverified';self.publish()
                    await asyncio.sleep(1)
                    try:self.transport.close()
                    except BaseException:continue
                locks.close()
            self.store.close();self.journal.close()
        return dict(state=self.phase,reason_code=self.reason,runtime=str(self.output))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('session','macro-bundle','library','commander-draft','profile-state-dir','binding','ledger'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--strategy-mode',choices=('declared','legacy'),default='declared')
    parser.add_argument('--run-id',required=True);parser.add_argument('--max-wall-seconds',type=int,default=None)
    args=parser.parse_args()
    try:
        host=MacroHost(args);print(json.dumps(asyncio.run(host.run())));return 0 if host.phase!='fault' else 1
    except Exception as error:
        print(json.dumps(dict(state='fault',reason_code=error.code if isinstance(error,ContractError) else 'macro_host_start_failed')));return 1


if __name__=='__main__':raise SystemExit(main())
