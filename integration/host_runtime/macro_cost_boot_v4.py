"""Production v4 readers borrowing the already verified MacroSampler handle.

Only the Host calls this module. It opens no process, attaches no runtime and
never reads a model/RPC supplied identity, price, qualification or path.
"""
from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
import time

from .resource_settlement_adapter import SettlementSession

ROOT=Path(__file__).resolve().parents[2]
COVERAGE=ROOT/'reports/macro-sickle-prioritized-cost-independent-89844-20261029-v1/review.json'
COVERAGE_SHA='428106c877445a1e719e2799c4bd6d6d303b1e3e90a0c88a833c72679e6288ec'
ATTRIBUTE=ROOT/'reports/macro-native-attribute-upper-field-68180-independent-20261029-v1.json'
ATTRIBUTE_SHA='47102fef4b06f68a61334595bbc0585cb34d40b0fcee2dad5f6ed7b876b87f64'
EXE_SHA='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PACKAGE_SHA='d516540d3d51a48a2d385dd1534e329bd5139bc67a6a0bde3e59a3ea5b9690a5'
EXTRA_PINS={
    'native-ai/macro_guarded_cost_supplier_v2.py':'3b1a27aa592d8ec53b143acfe33eafb4cbef6508219b3d53bbc7d491593c5928',
    'native-ai/macro_profiled_admission_cost_supplier.py':'5231a331163dc84fe80560047bcde5dc2dadb6ebab00bc9c861f475c9d5d4629',
    'native-ai/macro_quoteless_financial_observation.py':'4727c041c9cc73f21fa8d58e1367e14a768d1c12ffff1bce14484d01d49b3ebe',
    'native-ai/read_selected_personality.py':'1dabea75085645420b2bcc7387e4557f410d85bc66a1a57c4b18115981924187',
    'integration/host_runtime/macro_cost_factory_v2.py':'858693d2d6bea07d63d395120f41d7864ab597eb3e27cdec80f0f545941a6ab5',
    'integration/host_runtime/macro_admission_factory_v4.py':'72df650c8b2d1479c801d1d0001eac015b6839ecfa4c7f7e07e15b63e54fbedd'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def word(read,at):return struct.unpack('<I',read(at,4))[0]

@dataclass(frozen=True)
class MacroCostBootV4:
    session:SettlementSession|None
    cost_supplier:object|None
    financial_supplier:object|None
    enabled:bool
    reason:str
    output:str

def _dependencies():
    # Canonical module identity is important: the factory rejects a second
    # import of these dataclasses through integration.host_runtime.
    folder=str(ROOT/'native-ai')
    if folder not in sys.path:sys.path.insert(0,folder)
    from . import macro_cost_factory_v2 as shared
    pins={**shared.COVERAGE_PINS,**EXTRA_PINS}
    for name,wanted in pins.items():
        if sha(ROOT/name)!=wanted:raise ValueError('macro_cost_v4_frozen_source_changed')
    names=('macro_cost_supplier','macro_cost_identity_guard','macro_profiled_admission_cost_supplier',
        'macro_quoteless_financial_observation','read_selected_personality','readiness_dependency_contract')
    modules={name:importlib.import_module(name) for name in names}
    if any(Path(module.__file__).resolve()!=ROOT/'native-ai'/(name+'.py') for name,module in modules.items()):
        raise ValueError('macro_cost_v4_import_source_mismatch')
    from .macro_live import MacroSampler
    from .macro_expansion_scope import ExpansionScope
    from .macro_cost_factory import read_existing_handle_identity
    from .macro_admission_factory_v4 import QualifiedAdmissionCostSupplierV4
    return dict(shared=shared,pins=pins,sampler_type=MacroSampler,scope_type=ExpansionScope,
        dependency_type=modules['readiness_dependency_contract'].DependencyObserver,
        identity_reader=read_existing_handle_identity,binding_type=modules['macro_cost_supplier'].CostSessionBinding,
        universe_type=modules['macro_cost_supplier'].CompiledCostUniverse,
        guard_type=modules['macro_cost_identity_guard'].TrustedCostGuard,
        profile=modules['read_selected_personality'].inspect_player,
        admission_reader=modules['macro_profiled_admission_cost_supplier'].ProfiledAdmissionCostSupplier,
        admission_scope=modules['macro_profiled_admission_cost_supplier'].RESEARCH_SCOPE,
        finance_reader=modules['macro_quoteless_financial_observation'].QuotelessFinancialObserver,
        admission_provider=QualifiedAdmissionCostSupplierV4,
        finance_provider=shared.QualifiedQuotelessFinancialSupplierV4)

class _BorrowedContext:
    """Every guard rechecks this same handle and immutable files; errors latch."""
    def __init__(self,sampler,deps):
        if type(sampler) is not deps['sampler_type'] or not isinstance(sampler.scope,deps['scope_type']):
            raise ValueError('macro_cost_v4_verified_expansion_sampler_required')
        observer=sampler.expansion_dependency
        if type(observer) is not deps['dependency_type']:raise ValueError('macro_cost_v4_dependency_observer_required')
        self.sampler=sampler;self.deps=deps;self.memory=sampler.memory;self.handle=self.memory.handle
        self.owner=sampler.owner;self.game=observer.base.game;self.factory=observer.factory
        self.invalidated=False;self.frame_floor=0;self.session=dict(sampler.session);self.settlement=None
        if (observer.owner!=self.owner or observer.base.owner!=self.owner or observer.base.owner_index!=3
                or sampler.proof['handshake']['player']!=self.owner
                or sampler.proof['handshake']['game_logic']!=self.game):
            raise ValueError('macro_cost_v4_sampler_native_proof_mismatch')
        if (type(self.session.get('pid')) is not int or self.session['pid']<=0
                or type(self.session.get('process_creation_filetime')) is not int
                or self.session['process_creation_filetime']<=0 or self.session.get('mod_sha256')!=PACKAGE_SHA
                or sampler.scope.package_sha256!=PACKAGE_SHA):raise ValueError('macro_cost_v4_exact_session_required')
        self.game_path=Path(self.session['game']).resolve()
        self.frozen={Path(sampler.path).resolve():hashlib.sha256(sampler.raw).hexdigest(),
            Path(sampler.bundle_path).resolve():hashlib.sha256(sampler.bundle_raw).hexdigest(),
            Path(sampler.registry_path).resolve():hashlib.sha256(sampler.registry_raw).hexdigest(),
            self.game_path:EXE_SHA,Path(__file__).resolve():sha(__file__)}
        self.frozen.update({ROOT/name:wanted for name,wanted in deps['pins'].items()})
        manifest_path=(Path(sampler.bundle['build'])/'build-manifest.json').resolve()
        manifest_raw=manifest_path.read_bytes();manifest=json.loads(manifest_raw.decode('utf-8-sig'))
        report_path=Path(manifest['package_report']).resolve();report_raw=report_path.read_bytes()
        if (manifest.get('protocol_version')!=2 or manifest.get('package_sha256')!=PACKAGE_SHA
                or hashlib.sha256(report_raw).hexdigest()!=manifest.get('package_report_sha256')):
            raise ValueError('macro_cost_v4_native_package_manifest_changed')
        report=json.loads(report_raw.decode('utf-8-sig'));self.package=report_path.parent/'TFMacroProbe.big'
        if (report.get('variant')!='expanded_macro_policy_v2' or report.get('compiled') is not True
                or report.get('big_sha256')!=PACKAGE_SHA):raise ValueError('macro_cost_v4_compiled_package_required')
        self.frozen.update({manifest_path:hashlib.sha256(manifest_raw).hexdigest(),
            report_path:hashlib.sha256(report_raw).hexdigest(),self.package:PACKAGE_SHA})
        self.files();self.binding=self.live()
        profile=deps['profile'](self.memory.read,self.owner)
        if (profile['player_index']!=3 or profile['instance_id']!='0x799613e0'
                or int(profile['ai_player'],0)!=sampler.proof['handshake']['ai_player']):
            raise ValueError('macro_cost_v4_wrong_profile')
        self.settlement=SettlementSession(self.binding.session_id,self.binding.pid,self.binding.process_creation_filetime,
            self.binding.executable_sha256,self.binding.package_sha256,self.binding.game_identity,
            profile['ai_player'],profile['personality_wrapper'],profile['player_template'])
        self.settlement.validate()
        # The profile is still reread inside every complete financial window.
        # A later change is not accepted just because boot saw a valid profile.
        if self.live()!=self.binding:raise ValueError('macro_cost_v4_boot_identity_changed')

    def files(self):
        if self.invalidated:raise ValueError('macro_cost_v4_session_epoch_invalidated')
        try:
            result={}
            for path,wanted in self.frozen.items():
                actual=sha(path)
                if actual!=wanted:raise ValueError('macro_cost_v4_source_or_session_file_changed')
                result[str(path)]=actual
            return result
        except Exception:self.invalidated=True;raise

    def live(self):
        if self.invalidated:raise ValueError('macro_cost_v4_session_epoch_invalidated')
        try:
            s=self.sampler;m=self.memory;read=m.read
            if s.memory is not m or m.handle!=self.handle or s.owner!=self.owner:
                raise ValueError('macro_cost_v4_borrowed_handle_changed')
            if s.session!=self.session:raise ValueError('macro_cost_v4_sampler_session_changed')
            actual=self.deps['identity_reader'](m)
            if (actual['pid']!=self.session['pid'] or actual['pid']!=m.pid
                    or actual['process_creation_filetime']!=self.session['process_creation_filetime']
                    or str(Path(actual['image_path']).resolve()).casefold()!=str(self.game_path).casefold()):
                raise ValueError('macro_cost_v4_pid_creation_or_image_changed')
            if (word(read,0xcd8ce4)!=self.game or word(read,self.game)!=0xbeb630
                    or word(read,self.owner)!=0xc5bce0 or word(read,self.owner+0x20)!=3
                    or word(read,0xce6c58)!=self.factory):raise ValueError('macro_cost_v4_native_identity_changed')
            ai=word(read,self.owner+0x90)
            if (not 0x10000<=ai<=0x7ffe0000 or word(read,ai)!=0xc60f60 or word(read,ai+8)!=self.owner
                    or word(read,ai+0x8a8)!=self.owner):raise ValueError('macro_cost_v4_owned_ai_changed')
            if self.settlement is not None and (ai!=int(self.settlement.ai_player,0)
                    or word(read,ai+0x8b0)!=int(self.settlement.personality_wrapper,0)
                    or word(read,self.owner+0x10)!=int(self.settlement.player_template,0)):
                raise ValueError('macro_cost_v4_owned_profile_changed')
            profile=self.deps['profile'](read,self.owner)
            if (profile.get('player_index')!=3 or profile.get('instance_id')!='0x799613e0'
                    or int(profile['ai_player'],0)!=ai
                    or self.settlement is not None and any(profile.get(key)!=wanted for key,wanted in
                        dict(ai_player=self.settlement.ai_player,personality_wrapper=self.settlement.personality_wrapper,
                            player_template=self.settlement.player_template).items())):
                raise ValueError('macro_cost_v4_owned_profile_changed')
            frame=word(read,self.game+0x50)
            if not frame or frame<self.frame_floor:raise ValueError('macro_cost_v4_native_epoch_regressed')
            self.frame_floor=frame
            return self.deps['binding_type'](self.session['session_id'],actual['pid'],actual['process_creation_filetime'],
                EXE_SHA,PACKAGE_SHA,3,(hex(self.game),hex(self.owner),hex(self.factory)))
        except Exception:self.invalidated=True;raise

    def add_review_inputs(self,path,wanted):
        path=Path(path).resolve()
        if not path.is_relative_to(ROOT/'reports') or sha(path)!=wanted:raise ValueError('macro_cost_v4_review_changed')
        self.frozen[path]=wanted
        for row in json.loads(path.read_text(encoding='utf-8-sig'))['inputs']:
            source=Path(row['path']);source=(source if source.is_absolute() else ROOT/source).resolve()
            if not source.is_relative_to(ROOT/'reports') or sha(source)!=row['sha256']:
                raise ValueError('macro_cost_v4_review_input_changed')
            self.frozen[source]=row['sha256']

def boot_macro_cost_v4(sampler,*,output,event=None):
    """Fresh, diagnosed boot; only explicit qualified suppliers authorize work."""
    output=Path(output).resolve();created=False;began=time.monotonic_ns()
    session=None;cost=None;finance=None;errors={};context=None
    try:
        if not output.is_relative_to(ROOT/'reports') or output.exists():raise ValueError('macro_cost_v4_fresh_output_required')
        output.mkdir(parents=True);created=True;deps=_dependencies();context=_BorrowedContext(sampler,deps)
        session=context.settlement
        # Qualification input artifacts and current sources are hashed in both
        # full file phases of every window. No old cash/queue data is read as a
        # current value, including this evidence's source game.
        context.add_review_inputs(COVERAGE,COVERAGE_SHA)
        shared=deps['shared']
        try:
            qualification=shared.load_current_financial_coverage_qualification(coverage_review=COVERAGE,coverage_sha256=COVERAGE_SHA)
            guard=deps['guard_type'](session=context.binding,file_check=context.files,live_check=context.live)
            reader=deps['finance_reader'](context.memory.read,session=context.binding,guard=guard)
            finance=deps['finance_provider'](reader,qualification=qualification,session=session,output=output/'financial-evidence')
            context.frozen.update({Path(path):wanted for path,wanted in finance.required_guard_files.items()})
        except Exception as error:errors['finance']=getattr(error,'code',None) or str(error) or type(error).__name__
        try:
            context.add_review_inputs(ATTRIBUTE,ATTRIBUTE_SHA)
            qualification=shared.load_current_queue_cost_qualification(coverage_review=COVERAGE,coverage_sha256=COVERAGE_SHA,
                attribute_review=ATTRIBUTE,attribute_sha256=ATTRIBUTE_SHA)
            universe=deps['universe_type'].recompute(package=context.package,game_root=context.game_path.parent.parent,
                output=output/'compiled-universe')
            guard=deps['guard_type'](session=context.binding,file_check=context.files,live_check=context.live)
            reader=deps['admission_reader'](context.memory.read,session=context.binding,guard=guard,universe=universe,
                product_scope=deps['admission_scope'])
            cost=deps['admission_provider'](reader,qualification=qualification,session=session,output=output/'admission-evidence')
            context.frozen.update({Path(path):wanted for path,wanted in cost.required_guard_files.items()})
        except Exception as error:errors['admission']=getattr(error,'code',None) or str(error) or type(error).__name__
        context.files()
        if context.live()!=context.binding:raise ValueError('macro_cost_v4_post_boot_identity_changed')
        archive=output/'source';archive.mkdir();records=[]
        for index,(path,wanted) in enumerate(context.frozen.items()):
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=wanted:raise ValueError('macro_cost_v4_archive_changed')
            target=archive/(str(index)+'-'+path.name);target.write_bytes(raw)
            records.append(dict(path=str(path),sha256=wanted,copy=target.name))
        (output/'source-manifest.json').write_text(json.dumps(dict(schema_version=1,sources=records),indent=2)+'\n',encoding='utf8')
        context.files();context.live()
    except Exception as error:
        errors['boot']=getattr(error,'code',None) or str(error) or type(error).__name__
        cost=None;finance=None
        if context is None or context.invalidated:session=None
    enabled=cost is not None and finance is not None
    reason='qualified_current_admission_and_financial_v4' if enabled else 'macro_cost_v4_unavailable'
    status=dict(kind='macro_cost_production_boot_v4',schema_version=1,enabled=enabled,reason=reason,errors=errors,
        canonical_session_bound=session is not None,admission_ready=cost is not None,financial_ready=finance is not None,
        source_field_qualification_inherited=cost is not None or finance is not None,current_financial_fact_observed=False,
        handle_borrowed=True,new_handles_opened=0,native_calls=0,process_writes=0,model_calls=0,reservations_created=0,
        began_monotonic_ns=began,ended_monotonic_ns=time.monotonic_ns())
    if created:
        try:
            with (output/'boot.json').open('x',encoding='utf8') as stream:json.dump(status,stream,indent=2);stream.write('\n')
        except OSError:
            cost=None;finance=None;enabled=False;reason='macro_cost_v4_boot_evidence_unavailable'
            errors['boot_evidence']='macro_cost_v4_boot_evidence_unavailable'
            status.update(enabled=False,reason=reason,admission_ready=False,financial_ready=False,
                source_field_qualification_inherited=False)
    if event is not None:
        try:event('macro_cost_production_boot_v4',**{key:value for key,value in status.items() if key not in ('kind','errors')},
            failure_domains=sorted(errors))
        except Exception:pass
    return MacroCostBootV4(session,cost,finance,enabled,reason,str(output))
