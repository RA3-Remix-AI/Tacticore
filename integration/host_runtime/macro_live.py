"""Current native-AI identity and legal player-perspective macro observations."""
import hashlib
import re
import json
from pathlib import Path,PureWindowsPath
import sys
import time

from .contracts import ContractError
from .macro_policy_runtime import COMMANDER,MIN_MACRO_MODEL_GAME_SECONDS
from .macro_bundle import load_bundle
from .macro_expansion_scope import ExpansionScope,EXTRA_ACTIONS

ROOT=Path(__file__).resolve().parents[2]
EXPANSION_OBSERVER_PINS={
    'macro_readiness_observation.py':'d9abb6c26e218f5a719a22bed1279a8b468ae0611ebbc506ad0f2678b5704989',
    'macro_readiness_observation_v2.py':'70acbba640012b9ebb391994d8834e13a4c71f6a58a33025bfde6c5e7ab2e9a7',
    'readiness_dependency_contract.py':'7b80c594283631fa3cf31f616f63c4a38da32c1e8f29ee32e95fde988a3dee4b',
    'macro_component_diagnostic.py':'a0c0059cba9353abb2198a4087a1aae38e5d6d29a2359478db64923cf69aedcf'}


def expansion_component_frames(native):
    try:
        frames=(native['observation']['frame'],native['observation']['construction_feedback']['frame'],
            native['build_observation']['frame'],native['readiness']['frame'],native['dependency']['frame'])
    except (KeyError,TypeError):raise ContractError('macro_expansion_components_unavailable') from None
    if any(type(frame) is not int or not 0<frame<=0xffffffff for frame in frames) or max(frames)-min(frames)>15:
        raise ContractError('macro_expansion_component_frames_mismatch')
    return frames


def require_base_origin(census,required_origin):
    yards=[r for r in census['own_objects'] if r['type_hash']=='0xc16ff13f']
    if not yards:raise ContractError('session_not_ready')
    if (len(yards)!=1 or 'region_'+str(int(yards[0]['xyz'][0]//512))+'_'+str(int(yards[0]['xyz'][1]//512))!=required_origin):
        raise ContractError('macro_base_defense_origin_outside_qualified_scope')


class MacroSampler:
    def __init__(self,session_path,bundle_path,*,strategic_only=False):
        for folder in ('integration','strategy','production','native-ai','visibility'):
            path=str(ROOT/folder)
            if path not in sys.path:sys.path.insert(0,path)
        from observe_production import Memory
        from projection import VisibilityProjection
        from collector import VisibilityCollector
        self.path=Path(session_path);self.raw=self.path.read_bytes();self.session=json.loads(self.raw.decode('utf-8-sig'))
        self.bundle_path=Path(bundle_path);self.bundle_raw=self.bundle_path.read_bytes()
        self.bundle,self.scope=load_bundle(bundle_path,self.session)
        scenario=self.session.get('scenario',{})
        if (scenario.get('commander_id')!=COMMANDER or scenario.get('computer_player_index')!=3
                or scenario.get('participant_count')!=2 or scenario.get('opponent_player_index')!=4
                or scenario.get('observer_player_index',2)!=2):raise ContractError('session_mismatch')
        self.registry_path=Path(self.session['registry']);self.registry_raw=self.registry_path.read_bytes()
        self.registry=json.loads(self.registry_raw.decode('utf-8-sig'))
        if getattr(self.scope,'native_transport_protocol',None)==6:
            from .native6_transport import native_module
            _,sdk=native_module();Memory=sdk.Memory
        self.memory=Memory(self.session['pid'],self.session)
        try:
            folder=Path(self.bundle['visibility'])
            if getattr(self.scope,'native_transport_protocol',None)==6:
                from .native6_visibility import bind_session as bind_native6
                self.proof,self.safety=bind_native6(self.memory,self.session,3)
            else:
                from capability import bind_session
                self.proof,self.safety=bind_session(self.memory,self.session,3,folder/'build-capability.json',folder/'template-safety.json')
            if self.proof['commander_id']!=COMMANDER:raise ContractError('session_mismatch')
            self.owner=self.proof['handshake']['player'];self.sequence=0;self.previous=0;self.state=None
            self.collector=VisibilityCollector(self.memory,self.session,3,VisibilityProjection(
                self.session['session_id'],3,self.session['mod_sha256'],self.proof,self.safety))
            if isinstance(self.scope,ExpansionScope) and not strategic_only:self.enable_expansion_observers()
        except BaseException:self.memory.close();raise

    def enable_expansion_observers(self):
        for name,expected in EXPANSION_OBSERVER_PINS.items():
            if hashlib.sha256((ROOT/'native-ai'/name).read_bytes()).hexdigest()!=expected:
                raise ContractError('macro_expansion_observer_source_changed')
        from macro_readiness_observation import TEMPLATES
        from macro_readiness_observation_v2 import ReadinessObserverV2
        from readiness_dependency_contract import DependencyObserver,ConstructionLifecycleTracker
        from macro_component_diagnostic import ComponentReadTrace
        executable_sha=hashlib.sha256(Path(self.session['game']).read_bytes()).hexdigest()
        # Both observers borrow this sampler's existing read-only Memory.
        self.expansion_read_trace=ComponentReadTrace(self.memory.read,maximum_records=1024,maximum_raw_bytes=262144)
        self.expansion_readiness=ReadinessObserverV2(self.expansion_read_trace,self.owner,
            executable_sha256=executable_sha,expected_owner_index=3)
        self.expansion_dependency=DependencyObserver(self.expansion_read_trace,self.owner,
            executable_sha256=executable_sha,expected_owner_index=3)
        self.expansion_lifecycle=ConstructionLifecycleTracker();self.expansion_templates=set(TEMPLATES)

    def collect_expansion(self,native):
        if not isinstance(self.scope,ExpansionScope):return native
        result=dict(native);errors={};timings={};error_details={}
        result.update(readiness=None,dependency=None,lifecycle=None,expansion_sample_coherent=False)
        if not all(hasattr(self,name) for name in ('expansion_readiness','expansion_dependency','expansion_lifecycle','expansion_templates')):
            result['expansion_sample_reason']='macro_expansion_components_unavailable'
            return result
        def measure(name,operation):
            started=time.monotonic_ns()
            try:
                trace=getattr(self,'expansion_read_trace',None)
                result[name]=trace.run(name,operation) if trace is not None else operation()
            except (ValueError,RuntimeError,KeyError,TypeError) as error:
                errors[name]='native_read_only_component_unavailable'
                code=str(error)
                error_details[name]=dict(error_type=type(error).__name__,
                    reason_code=code if re.fullmatch(r'[a-z][a-z0-9_]{0,79}',code) else errors[name])
            finally:
                timings[name]=dict(started_monotonic_ns=started,ended_monotonic_ns=time.monotonic_ns(),
                    original_frame=(result.get(name) or {}).get('frame'))
        def readiness():
            objects=result['observation']['construction_feedback']['own_objects']
            ids=[row['thing_id'] for row in objects if int(row['type_hash'],0) in self.expansion_templates]
            if len(ids)>128 or len(ids)!=len(set(ids)):raise ValueError('named_readiness_bounds')
            return self.expansion_readiness.sample(ids)
        measure('readiness',readiness)
        measure('dependency',lambda:self.expansion_dependency.sample(list(EXTRA_ACTIONS)))
        try:
            expansion_component_frames(result)
            measure('lifecycle',lambda:self.expansion_lifecycle.observe(result['dependency'],session_token=self.session['session_id']))
            if errors:raise ContractError('macro_expansion_components_unavailable')
            if type(result['lifecycle']) is not dict or result['lifecycle'].get('frame')!=result['dependency']['frame']:
                raise ContractError('macro_expansion_component_frames_mismatch')
            result['expansion_sample_coherent']=True
        except ContractError as error:result['expansion_sample_reason']=error.code
        result['expansion_sample_errors']=errors;result['expansion_sample_error_details']=error_details
        result['expansion_component_timings']=timings
        if errors and getattr(self,'expansion_read_trace',None) is not None and getattr(self,'expansion_error_trace_count',0)<4:
            result['expansion_private_read_trace']=self.expansion_read_trace.private_report()
            self.expansion_error_trace_count=getattr(self,'expansion_error_trace_count',0)+1
        return result

    def collect(self):
        from read_match_state import snapshot
        from macro_observation import own_census
        from match_participants import verify_two_ai
        from read_selected_personality import inspect_player,resolve_registry
        from engine import Snapshot
        if (self.path.read_bytes()!=self.raw or self.bundle_path.read_bytes()!=self.bundle_raw
                or self.registry_path.read_bytes()!=self.registry_raw):raise ContractError('session_changed')
        state=snapshot(self.memory.read);self.state=state
        if not state['simulation_frame']:raise ContractError('macro_match_ended')
        logic=self.memory.u32(0xcd8ce4)
        if logic!=self.proof['handshake']['game_logic']:raise ContractError('session_changed')
        native=inspect_player(self.memory.read,self.owner)
        identity=resolve_registry(native,self.registry,self.session)
        if identity['commander_id']!=COMMANDER or native['player_index']!=3 or not identity['personality_binding_verified']:
            raise ContractError('session_mismatch')
        pointer=self.memory.u32(logic+0x98)
        path=PureWindowsPath(self.memory.read(pointer,260).split(b'\0',1)[0].decode('ascii'))
        expected=self.session['scenario']['map_id']
        if path.suffix.lower()!='.map' or path.stem.lower()!=expected.lower() or path.parent.name.lower()!=expected.lower():
            raise ContractError('macro_scenario_map_mismatch')
        self.participants=verify_two_ai(self.memory,state,self.registry,3,4,2)
        if any(row.get('victory_frame') or row.get('defeat_frame') for row in state['result_records']):
            raise ContractError('macro_native_result_candidate')
        census=own_census(self.memory,self.owner);frame=census['frame']
        required_origin=getattr(self.scope,'required_origin_region',None)
        if self.sequence==0 and required_origin is not None:
            require_base_origin(census,required_origin)
        if frame<self.previous:raise ContractError('macro_frame_regression')
        self.previous=frame;at=frame/15;field=self.collector.collect(at);roles={}
        for row in census['own_objects']:
            safe=self.safety['templates'].get(row['type_hash'])
            if safe:roles[safe['role']]=roles.get(safe['role'],0)+1
        resources=census['resources']
        if resources.get('resource_available') is not True:raise ContractError('macro_credit_observation_unavailable')
        self.sequence+=1
        raw=dict(schema_version=1,session_id=self.session['session_id'],player_id=3,snapshot_id=self.sequence,
            game_time_seconds=at,source='game_bridge',paused=bool(state['pause_flag_candidate']),
            resources=dict(credits=resources['display_sum'],power_balance=None),
            capabilities=dict(production_focus=['native_baseline'],regions=[row['region_id'] for row in field['regions']]),
            production=dict(queued_count=0,idle_producers=0,own_roles=roles),enemy_observations=[],events=[],battlefield=field,
            # Production requires paired private builder/own-census samples.
            # The live controller may add it after refresh; sampler alone cannot.
            macro_control=dict(mode='macro_native',available_actions=[action for action in self.scope.available_actions
                if action.startswith('budget')] if at>=MIN_MACRO_MODEL_GAME_SECONDS else []))
        if hasattr(self.scope,'regional_action_regions'):
            # Public map navigation locations carry no enemy presence claim.
            raw['capabilities']['regions']=sorted(set(raw['capabilities']['regions'])|set(self.scope.regional_action_regions.values()))
        self.latest_census=census
        return Snapshot.from_dict(raw).to_dict()

    def close(self):self.memory.close()

    def footprint(self):
        # Stable admission identity excludes changing frame/resources/own roster.
        return dict(session_sha256=hashlib.sha256(self.raw).hexdigest(),registry_sha256=hashlib.sha256(self.registry_raw).hexdigest(),
            bundle_sha256=hashlib.sha256(self.bundle_raw).hexdigest(),owner=self.owner,
            ai=self.proof['handshake']['ai_player'],game_logic=self.proof['handshake']['game_logic'],
            participants=self.participants,visibility_build=self.proof['build_id'])
