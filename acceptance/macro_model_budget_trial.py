"""Bounded real-provider macro-budget field trial; no unit orders or product grant.

Uses the current desktop profile API and normal protected backend factory.
The game's own AI consumes only independently qualified budget presets.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'strategy'),str(ROOT/'production'),
              str(ROOT/'native-ai'),str(ROOT/'visibility')]
from integration.host_runtime.application import apply_commander_draft,create_applied_backend
from integration.host_runtime.profile_store import ProfileStore
from integration.host_runtime.macro_policy_runtime import BudgetController,MacroRequestAudit,verify_budget_scope,COMMANDER
from integration.host_runtime.contracts import ContractError
from engine import Binding,Snapshot,StrategyEngine
from battle_agent import BattleAgent
from http_adapter import load_profile
from observe_production import Memory
from read_match_state import snapshot as match_state
from macro_observation import own_census,MacroObserver
from capability import bind_session
from projection import VisibilityProjection
from collector import VisibilityCollector

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,allow_nan=False,indent=2)


def public_snapshot(session,ident,at,paused,census,battlefield,safety,actions):
    """Explicit projection: no raw object IDs, positions, hashes, HP or pointers."""
    roles={}
    for row in census['own_objects']:
        safe=safety['templates'].get(row['type_hash'])
        if safe:
            role=safe['role'];roles[role]=roles.get(role,0)+1
    resources=census['resources']
    if resources.get('resource_available') is not True:raise ContractError('macro_credit_observation_unavailable')
    result=dict(schema_version=1,session_id=session['session_id'],player_id=3,snapshot_id=ident,
        game_time_seconds=at,source='game_bridge',paused=paused,
        resources=dict(credits=resources['display_sum'],power_balance=None),
        capabilities=dict(production_focus=['native_baseline'],regions=[r['region_id'] for r in battlefield['regions']]),
        # These are lower bounds, explicitly marked unobserved in every macro
        # feedback entry. This experiment never allocates production jobs.
        production=dict(queued_count=0,idle_producers=0,own_roles=roles),
        enemy_observations=[],events=[],battlefield=battlefield,
        macro_control=dict(mode='macro_native',available_actions=list(actions)))
    return Snapshot.from_dict(result).to_dict()


OBSERVATION_LIMITS=dict(production_queue_observed=False,idle_producers_observed=False,
    queue_and_idle_numbers='unobserved_lower_bounds',own_roles_coverage='audited_templates_only',
    power_observed=False,payment_verified=False)


async def run(args):
    session=load(args.session);build=Path(args.build).resolve();out=Path(args.output).resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ContractError('fresh_macro_model_output_required')
    scope=verify_budget_scope(ROOT/'reports/macro-policy-budget-73924-20261028-v3',
        ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',
        ROOT/'reports/macro-policy-expiry-71320-20261028-v1',build)
    runtime_config=Path(os.environ['LOCALAPPDATA'])/'Tacticore/desktop-runtime-config.json'
    config=load(runtime_config);library=Path(config['library_path'])
    store=ProfileStore(library,Path(os.environ['LOCALAPPDATA'])/'Tacticore/desktop-runtime')
    record=store.get_profile(COMMANDER)['profile']
    if (record['library_hash']!=config['library_sha256'] or record['validation']['ok'] is not True
            or record['library_changed'] or record['revision']!=4):
        store.close();raise ContractError('current_desktop_profile_not_bound')
    expected_hash=record['effective']['effective_hash']
    def check_profile():
        current=store.get_profile(COMMANDER)['profile']
        if (load(runtime_config)!=config or current['library_hash']!=config['library_sha256']
                or current['effective']['effective_hash']!=expected_hash or current['revision']!=record['revision']):
            raise ContractError('macro_profile_revision_changed')

    out.mkdir(parents=True)
    journal=(out/'model-macro-events.jsonl').open('x',encoding='utf-8')
    def event(kind,**facts):
        journal.write(json.dumps(dict(kind=kind,session_id=session['session_id'],
            monotonic_ns=time.monotonic_ns(),**facts),ensure_ascii=False,allow_nan=False)+'\n')
        journal.flush();os.fsync(journal.fileno())
    transport=None;controller=None;agent=None;backend=None;memory=None;pending=None
    failure=None;rounds=[];observations=0;read_errors=0;real_model_calls=0
    try:
        save(out/'profile.json',record);save(out/'scope.json',scope.public())
        save(out/'registration.json',dict(registration_id=config['registration_id'],
            library_sha256=config['library_sha256'],profile_id=COMMANDER,revision=record['revision'],effective_hash=expected_hash))
        registry=dict(identity_revision=1,registry_revision=record['revision'],compiled_ids_verified=True,
            package_sha256=session['mod_sha256'],research_only=True,commanders=[dict(id=COMMANDER,
            name=record['name'],connection_id=record['connection_id'],assets=[dict(
            asset_id='5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_Soviet',instance_id='0x799613e0',side='Soviet')])])
        save(out/'registry.json',registry)
        model_session=dict(session,registry=str(out/'registry.json'),registry_revision=record['revision'],research_only=True)
        save(out/'model-session.json',model_session)
        # Freeze the code before any model call or native policy attachment.
        source=out/'source';source.mkdir();sources=[]
        paths=[Path(__file__),runtime_config,Path(args.session),build/'build-manifest.json',
            ROOT/'integration/host_runtime/macro_policy_runtime.py',ROOT/'integration/host_runtime/application.py',
            ROOT/'integration/host_runtime/profiles.py',ROOT/'integration/host_runtime/profile_store.py',
            *sorted((ROOT/'strategy').glob('*.py')),
            *sorted((ROOT/'agent_runtime/src/tacticore_agent_runtime').glob('*.py')),
            *[ROOT/'visibility'/n for n in ['capability.py','native_read.py','collector.py','projection.py','audit_templates.py']]]
        for i,path in enumerate(paths):
            target=source/(str(i)+'-'+path.name);shutil.copy2(path,target)
            sources.append(dict(path=str(path.resolve()),copy=target.name,sha256=sha(target)))
        save(out/'sources.json',sources)
        memory=Memory(session['pid'],session)
        proof,safety=bind_session(memory,model_session,3,Path(args.visibility)/'build-capability.json',Path(args.visibility)/'template-safety.json')
        save(out/'session-visibility-proof.json',proof)
        collector=VisibilityCollector(memory,model_session,3,VisibilityProjection(session['session_id'],3,session['mod_sha256'],proof,safety))
        owner=proof['handshake']['player']
        spec=importlib.util.spec_from_file_location('macro_policy_field_transport',ROOT/'native-ai/macro-policy-runtime/client.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        transport=module.MacroPolicyProbe(Path(args.session),owner,build,out/'transport')
        controller=BudgetController(transport,scope,session['session_id'],expected_hash,event)
        binding=Binding(session['session_id'],3,COMMANDER,record['name'],record['connection_id'])
        engine=StrategyEngine(binding,timeout_seconds=30,max_response_age_seconds=30,min_hold_game_seconds=10,
            audit_path=out/'strategy-audit.jsonl',status_path=out/'strategy-status.json')
        agent=BattleAgent(engine,memory_path=out/'agent-memory.json',jobs_path=out/'agent-jobs.json')
        sequence=0
        def observe():
            nonlocal sequence,observations
            state=match_state(memory.read)
            if not state['simulation_frame']:raise ContractError('macro_match_no_longer_running')
            census=own_census(memory,owner)
            frame=memory.u32(memory.u32(0xcd8ce4)+0x50);at=frame/15
            battlefield=collector.collect(at)
            sequence+=1
            raw=public_snapshot(session,sequence,at,bool(state['pause_flag_candidate']),census,battlefield,safety,scope.available_actions)
            agent.observe(raw);observations+=1
            return raw
        # Native budget states are gated by OpeningMoveComplete (~120s).
        while True:
            raw=observe()
            if raw['game_time_seconds']>=125 and not raw['paused']:break
            await asyncio.sleep(.5)
        check_profile()
        # This is the normal existing protected loader, used only because the
        # following operation starts real provider requests. Never serialize it.
        application=apply_commander_draft(load_profile(library,COMMANDER),record['draft'])
        if application.effective.effective_hash!=expected_hash:raise ContractError('macro_application_hash_mismatch')
        save(out/'application.json',application.public())
        backend=create_applied_backend(application,event_sink=lambda kind,payload:event(kind,**payload),
            backend='pydantic',timeout=28,max_tokens=1536,max_input_bytes=16384,max_inflight=1)
        audited_backend=MacroRequestAudit(backend,event)
        for index in range(args.rounds):
            check_profile();raw=observe()
            feedback=controller.feedback(transport.observer.sample());feedback.update(OBSERVATION_LIMITS)
            agent.feedback.append(feedback)
            event('macro_feedback_for_model',round=index,**feedback)
            pending=asyncio.create_task(agent.decide(raw,audited_backend))
            while not pending.done():
                await asyncio.sleep(.25)
                try:observe()
                except (ValueError,RuntimeError):
                    read_errors+=1
                    # A failed refresh cannot authorize dispatch. The next fresh
                    # snapshot plus engine response-age checks remain required.
                    if read_errors>8:raise ContractError('macro_observation_unstable') from None
            decision=await pending;pending=None;check_profile();latest=observe()
            provider=backend.observation();real_model_calls=provider['responses_returned']
            row=dict(round=index,status=decision.status,reason_code=decision.reason_code,
                plan=decision.plan.public() if decision.plan else None,provider=provider)
            event('model_macro_decision',**row)
            if decision.status=='accepted' and provider['real_network_verified']:
                row['dispatch']=controller.dispatch(decision.plan,latest['game_time_seconds'],
                    effective_hash=expected_hash,paused=latest['paused'])
            rounds.append(row)
            deadline=time.monotonic()+args.hold_seconds
            while time.monotonic()<deadline:
                await asyncio.sleep(.5);check_profile();observe()
                sample=transport.observe('model_round_'+str(index))
                if 'observation' in sample:
                    feedback=controller.feedback(sample['observation']);feedback.update(OBSERVATION_LIMITS)
                    agent.feedback.append(feedback);event('model_macro_native_feedback',round=index,**feedback)
        event('macro_model_trial_stop_requested',real_model_calls=real_model_calls)
    except BaseException as error:
        # Fixed failure marker only; never emit provider text or protected data.
        failure='cancelled' if isinstance(error,asyncio.CancelledError) else 'macro_model_trial_failed'
        event('macro_model_trial_failed',reason_code=failure,error_type=type(error).__name__)
    finally:
        if pending is not None and not pending.done():
            pending.cancel();await asyncio.gather(pending,return_exceptions=True)
        if agent:agent.stop()
        try:
            if controller:controller.stop()
            elif transport:transport.close()
        except Exception:
            failure='macro_stop_unverified';event('macro_stop_unverified')
        if memory and transport:
            try:
                await asyncio.sleep(1.5)
                after=MacroObserver(memory,owner,transport.manifest['flags']).sample()
                save(out/'post-stop-native-budget.json',dict(frame=after['frame'],
                    budget_feedback=after['budget_feedback'],process_writes=0,native_calls=0))
                event('macro_post_stop_budget_observed',frame=after['frame'],
                    native_macro_policy_selected=after['budget_feedback']['selected_macro_flag'] is not None,
                    account_shares=after['budget_feedback']['account_shares'])
            except (ValueError,RuntimeError):event('macro_post_stop_budget_unavailable')
        if memory:memory.close()
        store.close()
        final=load(out/'transport/final-state.json') if (out/'transport/final-state.json').exists() else None
        summary=dict(kind='real_model_macro_budget_research',session_id=session['session_id'],
            profile_revision=record['revision'],effective_hash=expected_hash,rounds=rounds,
            observations=observations,read_errors=read_errors,real_model_responses=real_model_calls,
            cleanup_verified=bool(final and final['cleanup_verified']),failure=failure,
            provider=backend.observation() if backend else None,
            product_integration_verified=False,full_match_verified=False,formal_goal_complete=False)
        save(out/'summary.json',summary);journal.close()
    print(json.dumps(dict(output=str(out),real_model_responses=real_model_calls,
        accepted=sum(r['status']=='accepted' for r in rounds),cleanup_verified=summary['cleanup_verified'],failure=failure)))
    return 1 if failure else 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','visibility','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--rounds',type=int,default=3);p.add_argument('--hold-seconds',type=int,default=12)
    args=p.parse_args()
    if not 1<=args.rounds<=5 or not 5<=args.hold_seconds<=30:raise ValueError('bounded_macro_model_trial')
    return asyncio.run(run(args))

if __name__=='__main__':raise SystemExit(main())
