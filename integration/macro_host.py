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
from host_runtime.macro_bundle import digest
from host_runtime.macro_infrastructure import observe_infrastructure
from host_runtime.macro_forces import observe_forces
from host_runtime.macro_production_feedback import frames as native_pair_frames
from host_runtime.macro_scouting import ScoutingScope,MacroScoutingController
from host_runtime.macro_region_scope import RegionalScope
from host_runtime.macro_regions import MacroRegionalController
from engine import Binding,StrategyEngine,ContractError as StrategyContractError
from battle_agent import BattleAgent
from http_adapter import load_profile

LIMITS=dict(production_queue_observed=False,idle_producers_observed=False,
    queue_and_idle_numbers='unobserved_lower_bounds',own_roles_coverage='audited_templates_only',
    power_observed=False,payment_verified=False)


def request_telemetry_ready(audited,snapshot,event):
    if not audited.fresh_for_game_seconds(snapshot['game_time_seconds']):
        event('macro_decision_deferred',reason_code='macro_telemetry_frame_mismatch')
        return False
    return True


class MacroHost:
    def __init__(self,args):
        self.args=args;self.binding=SessionBinding.from_dict(json.loads(args.binding.read_text(encoding='utf8')))
        self.run_id=args.run_id;self.started=time.monotonic();self.host_pid=os.getpid()
        self.host_start=NativeHostSpawner.identity(self.host_pid)
        self.session=json.loads(args.session.read_text(encoding='utf-8-sig'))
        if (self.session['session_id']!=self.binding.session_id or self.session['pid']!=self.binding.game_process_id
                or self.session['start_time']!=self.binding.game_process_start or self.session['mod_sha256']!=self.binding.mod_sha256
                or digest(self.session['game'])!=self.binding.game_sha256):raise ContractError('session_mismatch')
        self.output=Path(self.session['run_directory'])/'battle-host'
        if self.output.exists() and any(self.output.iterdir()):raise ContractError('run_state_conflict')
        self.output.mkdir(exist_ok=True);self.store=ProfileStore(args.library,args.profile_state_dir)
        self.journal=CommandJournal(args.ledger)
        self.journal.register_run(self.run_id,self.binding.public())
        self.profile=self.store.get_profile(self.binding.commander_id)['profile']
        self.draft=load_commander_draft(args.commander_draft)
        self.expected_hash=self.profile['effective']['effective_hash'];self.expected_revision=self.profile['revision']
        self.phase='starting';self.reason='macro_preparing';self.latest=None;self.backend=None;self.agent=None
        self.sampler=None;self.transport=None;self.controller=None;self.pending=None;self.application=None
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
        value=dict(session_id=self.binding.session_id,player_id=3,commander_id=self.binding.commander_id,
            wall_seconds=round(time.monotonic()-self.started,3),**facts)
        self.journal.append_event(self.run_id,kind,value,
            game_frame=int(self.latest['game_time_seconds']*15) if self.latest else None,monotonic_ns=time.monotonic_ns())
        with (self.output/'host-events.jsonl').open('a',encoding='utf8') as stream:
            stream.write(json.dumps(dict(kind=kind,**value),ensure_ascii=False,allow_nan=False)+'\n')

    def publish(self):
        status=dict(schema_version=1,kind='native_macro_host_v1',session_id=self.binding.session_id,pid=self.session['pid'],
            process_start=self.session['start_time'],host_pid=self.host_pid,host_start_time=self.host_start,
            state=self.phase,reason_code=self.reason,runtime_macro=dict(run_id=self.run_id,binding_hash=self.binding.binding_hash),
            execution=dict(enabled=self.phase=='running',dry_run=False,executor_connected=self.transport is not None,
                control_mode='macro_native',unit_operation_policy='native_ai',remaining_budget=0),
            jobs=[],current_plan=getattr(self,'last_plan',None) or (self.agent.engine.current.public() if self.agent and self.agent.engine.current else None),
            macro_feedback=getattr(self,'last_feedback',None),
            macro_production_feedback=getattr(self,'last_production_feedback',None),
            macro_construction_feedback=getattr(self,'last_construction_feedback',None),
            macro_scouting_feedback=getattr(self,'last_scouting_feedback',None),
            macro_regional_feedback=getattr(self,'last_regional_feedback',None),
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
        for index,path in enumerate(files):
            target=source/(str(index)+'-'+path.name);shutil.copy2(path,target)
            rows.append(dict(path=str(path.resolve()),copy=target.name,sha256=digest(target)))
        _atomic(self.output/'sources.json',dict(kind='pre_execution_macro_host_sources',sources=rows))
        _atomic(self.output/'profile.json',self.profile)

    def production_tick(self,native):
        if not isinstance(self.controller,MacroProductionController):return True
        if 'observation' not in native or 'build_observation' not in native:
            self.event('macro_sample_deferred',reason_code='macro_native_pair_unavailable');return False
        try:pair_frames=native_pair_frames(native['build_observation'],native['observation']['construction_feedback'])
        except ContractError as error:
            if error.code!='macro_production_observations_too_far_apart':raise
            self.event('macro_sample_deferred',reason_code=error.code);return False
        native_seconds=max(self.latest['game_time_seconds'],max(pair_frames)/15)
        # A slow native read can cross expiry after the lawful view was read.
        # Release expired intents before a later autonomous queue is observed.
        self.controller.tick(native_seconds)
        if isinstance(self.controller,MacroScoutingController):self.controller.observe_snapshot(self.latest)
        self.controller.refresh(native)
        if 'observation' in native and 'build_observation' in native:
            self.last_infrastructure=observe_infrastructure(native['build_observation'],native['observation']['construction_feedback'])
        self.controller.tick(native_seconds)
        actions=self.controller.available_actions(native_seconds) if native_seconds>=MIN_MACRO_MODEL_GAME_SECONDS else ()
        self.latest['macro_control']=dict(mode='macro_native',available_actions=list(actions),
            production_counts={action:list(counts) for action,counts in self.sampler.scope.production_counts.items() if action in actions})
        if isinstance(self.controller,MacroRegionalController):
            self.latest['macro_control']['region_targets']={action:region for action,region in self.sampler.scope.regional_action_regions.items()
                if action in actions}
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
        return True

    def observe_current(self):
        # Seed memory with the first lawful snapshot before native attach and
        # provider setup can turn a visible contact into last-seen history.
        with (self.output/'macro-snapshots.jsonl').open('a',encoding='utf8') as stream:
            stream.write(json.dumps(self.latest,ensure_ascii=False,allow_nan=False)+'\n')
        self.agent.observe(self.latest)

    def consume_observation(self,native):
        coherent=self.production_tick(native)
        # VisibilityProjection has already retained this lawful view. Feed it
        # to agent memory even when native builder telemetry is discarded;
        # otherwise a later last-seen contact appears to change while hidden.
        self.observe_current()
        return coherent

    def dispatch_plan(self,plan):
        if self.latest['paused'] or plan.expires_at_game_seconds<=self.latest['game_time_seconds']:
            self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code='expired_or_paused')
            return False
        try:
            self.controller.dispatch(plan,self.latest['game_time_seconds'],effective_hash=self.expected_hash,paused=False)
        except ContractError as error:
            if error.code not in {'macro_production_not_currently_available','macro_production_goal_active','macro_construction_not_currently_available','macro_scout_not_currently_available','macro_region_not_currently_available'}:raise
            # A newly occupied/lost producer revokes the old response. No
            # native delivery was attempted; the next decision uses new facts.
            self.event('macro_plan_not_dispatched',plan_id=plan.plan_id,reason_code=error.code)
            return False
        self.last_plan=plan.public()
        self.event('plan_applied',plan_id=plan.plan_id,snapshot_id=plan.snapshot_id,plan=plan.public())
        return True

    def finish_transport(self):
        if self.transport is None:return
        stop=self.journal.reserve_command(self.run_id,'macro-stop','macro_policy_stop',dict(binding_hash=self.binding.binding_hash))
        if not stop['created']:raise ContractError('macro_stop_already_claimed')
        self.journal.mark_dispatching(self.run_id,'macro-stop')
        try:
            self.controller.stop() if self.controller else self.transport.close()
            if isinstance(self.controller,MacroProductionController):
                self.last_production_feedback=self.controller.production_feedback()
                self.last_construction_feedback=self.controller.construction_feedback()
            if isinstance(self.controller,MacroScoutingController):self.last_scouting_feedback=self.controller.scouting_feedback()
            if isinstance(self.controller,MacroRegionalController):self.last_regional_feedback=self.controller.regional_feedback()
            path=ROOT/'reports'/('macro-desktop-'+self.run_id)/'final-state.json'
            final=json.loads(path.read_text(encoding='utf8'))
            required=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0)
            verified=(final['session_id']==self.binding.session_id and final['pid']==self.binding.game_process_id
                and final['process_creation_filetime']==self.session['process_creation_filetime']
                and final['mod_sha256']==self.binding.mod_sha256 and final['cleanup_verified'] is True
                and final['host_returncode']==0 and final['unknown_command_ids']==[]
                and all(final['native'].get(key)==value for key,value in required.items())
                and len(final['independent_flags']['flags'])==13
                and all(not row['present'] or row['value'] is False for row in final['independent_flags']['flags']))
            proof=dict(kind='macro_policy_native_release',binding=self.binding.public(),run_id=self.run_id,
                host_pid=self.host_pid,host_start_time=self.host_start,native_release_verified=verified,final_state_sha256=digest(path))
            _atomic(self.output/'macro-release.json',proof)
            self.journal.record_outcome(self.run_id,'macro-stop','released' if verified else 'uncertain',dict(
                binding_hash=self.binding.binding_hash,host_pid=self.host_pid,host_start_time=self.host_start,
                native_release_verified=verified,final_state_sha256=digest(path),release_sha256=digest(self.output/'macro-release.json')))
            if not verified:raise ContractError('macro_stop_unverified')
        except BaseException:
            if self.journal.get_command(self.run_id,'macro-stop')['status']=='dispatching':
                self.journal.record_outcome(self.run_id,'macro-stop','uncertain',dict(native_release_verified=False))
            raise

    async def run(self):
        last_request=-100.;failures=0
        try:
            self.freeze();self.sampler=MacroSampler(self.args.session,self.args.macro_bundle)
            self.latest=self.sampler.collect();self.check_profile()
            self.last_forces=observe_forces(self.sampler.latest_census,self.sampler.safety)
            _atomic(self.output/'visibility-proof.json',self.sampler.proof)
            _atomic(self.output/'participants.json',self.sampler.participants)
            self.application=apply_commander_draft(load_profile(self.args.library,self.binding.commander_id),self.draft)
            if self.application.effective.effective_hash!=self.expected_hash:raise ContractError('effective_profile_changed')
            self.backend=create_applied_backend(self.application,event_sink=lambda kind,payload:self.event(kind,**payload),
                backend='pydantic',timeout=28,max_tokens=1536,max_input_bytes=16384,max_inflight=1)
            engine=StrategyEngine(Binding(self.binding.session_id,3,self.binding.commander_id,self.profile['name'],self.profile['connection_id']),
                timeout_seconds=30,max_response_age_seconds=30,min_hold_game_seconds=15,
                audit_path=self.output/'plans.jsonl',status_path=self.output/'strategy-status.json')
            self.agent=BattleAgent(engine,memory_path=self.output/'agent-state.json',jobs_path=self.output/'jobs.json')
            self.observe_current()
            transport_name=getattr(self.sampler.scope,'native_transport_client',
                'client_area_defense.py' if hasattr(self.sampler.scope,'model_catalog_overrides') else 'client.py')
            if transport_name not in ('client.py','client_area_defense.py','client_group_roles.py'):
                raise ContractError('macro_native_transport_not_qualified')
            spec=importlib.util.spec_from_file_location('desktop_macro_native_transport',ROOT/'native-ai/macro-policy-runtime'/transport_name)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            self.transport=module.MacroPolicyProbe(self.args.session,self.sampler.owner,Path(self.sampler.bundle['build']),
                ROOT/'reports'/('macro-desktop-'+self.run_id),build_feedback=isinstance(self.sampler.scope,ProductionPreferenceScope))
            controller_type=(MacroRegionalController if isinstance(self.sampler.scope,RegionalScope) else
                MacroScoutingController if isinstance(self.sampler.scope,ScoutingScope) else
                MacroProductionController if isinstance(self.sampler.scope,ProductionPreferenceScope) else BudgetController)
            self.controller=controller_type(DurableMacroTransport(self.transport,self.journal,self.run_id),self.sampler.scope,
                self.binding.session_id,self.expected_hash,self.event)
            audited=MacroRequestAudit(self.backend,self.event,feedback_supplier=lambda:getattr(self,'last_feedback',None),
                production_supplier=lambda:getattr(self,'last_production_feedback',None),
                construction_supplier=lambda:getattr(self,'last_construction_feedback',None),
                infrastructure_supplier=lambda:getattr(self,'last_infrastructure',None),
                scouting_supplier=lambda:getattr(self,'last_scouting_feedback',None),
                regional_supplier=lambda:getattr(self,'last_regional_feedback',None),
                forces_supplier=lambda:getattr(self,'last_forces',None),
                catalog_supplier=self.sampler.scope.model_catalog_overrides if hasattr(self.sampler.scope,'model_catalog_overrides') else None)
            self.event('host_started',execution_requested=True,control_mode='macro_native')
            self.event('commander_profile_applied',**self.application.public())
            while time.monotonic()-self.started<self.args.max_wall_seconds:
                if self.stopping():self.reason='user_stop';break
                self.check_profile()
                try:
                    self.latest=self.sampler.collect();failures=0
                    self.last_forces=observe_forces(self.sampler.latest_census,self.sampler.safety)
                except ContractError as error:
                    if error.code in ('macro_match_ended','macro_native_result_candidate'):
                        _atomic(self.output/'result-native-state.json',self.sampler.state)
                        self.phase='result_candidate';self.reason='native_result_requires_visual_confirmation';break
                    raise
                except (ValueError,RuntimeError):
                    failures+=1
                    if failures>5:raise ContractError('macro_observation_unstable') from None
                    await asyncio.sleep(.2);continue
                native=self.transport.observe('desktop_macro_tick')
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
                    if request_telemetry_ready(audited,self.latest,self.event):
                        self.pending=asyncio.create_task(self.agent.decide(self.latest,audited));last_request=time.monotonic()
                self.publish();await asyncio.sleep(.5)
            else:self.reason='host_time_limit'
        except BaseException as error:
            self.phase='fault';self.reason=error.code if isinstance(error,ContractError) else 'macro_host_failed'
            if isinstance(error,StrategyContractError) and re.fullmatch(r'[a-z][a-z0-9_]{0,79}',str(error)):
                self.reason=str(error)
            self.event('host_fault',reason_code=self.reason,error_type=type(error).__name__,source_frames=[
                dict(file=str(Path(frame.filename).relative_to(ROOT)) if Path(frame.filename).is_relative_to(ROOT) else Path(frame.filename).name,
                     line=frame.lineno,function=frame.name) for frame in traceback.extract_tb(error.__traceback__)[-12:]])
        finally:
            self.event('macro_host_stop_started',reason_code=self.reason)
            if self.pending:
                if not self.pending.done():self.pending.cancel()
                await asyncio.gather(self.pending,return_exceptions=True)
            if self.agent:self.agent.stop()
            try:self.finish_transport()
            except BaseException:self.phase='fault';self.reason='macro_stop_unverified'
            if self.sampler:self.sampler.close()
            if self.phase not in ('fault','result_candidate'):self.phase='stopped'
            self.publish();self.event('host_stopped',reason_code=self.reason)
            self.store.close();self.journal.close()
        return dict(state=self.phase,reason_code=self.reason,runtime=str(self.output))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('session','macro-bundle','library','commander-draft','profile-state-dir','binding','ledger'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--max-wall-seconds',type=int,default=1500)
    args=parser.parse_args()
    if not 10<=args.max_wall_seconds<=1500:raise ValueError('macro_host_wall_bound')
    try:
        host=MacroHost(args);print(json.dumps(asyncio.run(host.run())));return 0 if host.phase!='fault' else 1
    except Exception as error:
        print(json.dumps(dict(state='fault',reason_code=error.code if isinstance(error,ContractError) else 'macro_host_start_failed')));return 1


if __name__=='__main__':raise SystemExit(main())
