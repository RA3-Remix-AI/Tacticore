"""Qualified current-queue facts; active attributes require a new field review.

No process opening, native call, write, reservation or dispatch. A trusted
backend supplies the guarded active-attribute reader and complete file guards.
Old queue/cash observations are never promoted into current facts.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

from .contracts import ContractError
from .resource_reservations import CurrentQueueBudgetFact,CURRENT_QUEUE_BUDGET_SOURCE

ROOT=Path(__file__).resolve().parents[2]
SOURCE='native_coherent_active_attribute_current_upper_research_observation_v5'
COVERAGE_ALGORITHM='prioritized_registry_live_union_complete_double_collect_v1'
COVERAGE_PINS={
    'native-ai/macro_registered_queue_observation.py':'2cf467746a61b7c25f4ccb3ad2a8313d8fa1de5e06d26ca599cfc44bb0dead11',
    'native-ai/macro_payment_observation_v2.py':'52418796f4e80133bc2543edda4088afece132f92ef551cf8d078fcdd23bd149',
    'native-ai/macro_prioritized_financial_window.py':'5e91b66c48b05b71fbcecd9a6433aa60afdba528db91fcc81f3b13baf142656e',
    'native-ai/macro_attribute_cost_bound.py':'1c92938e89aa87e1a430175536040474309ec43fbd992ff5531edf117f73f3c4',
    'native-ai/macro_active_attribute_cost_supplier.py':'e7a05ab822c05fb2afe175a27c65d251a8e879557dbcf9b8e18976ab69cd6480'}
COVERAGE_PINS.update({
    'native-ai/macro_coherent_registered_cost_supplier.py':'3efc2de16860b44253ab89013a66053f9206152751a7cfcc557c50aa6492e20d',
    'native-ai/macro_cost_supplier.py':'353a35cbecb4b9229b19a5c060eef482a8edb8782d8124f75e639177ef26ddaf',
    'native-ai/macro_cost_observation.py':'726e87805bd50acd68dc2c5237d1ab7b64317f710f5483502e228876ab9904f7',
    'native-ai/macro_cost_observation_v2.py':'d7e32f224b8419255eae0d9adcfe2fc3d4bae0de128bc4a08fd7ee3a3c514e6b',
    'native-ai/macro_cost_upper_contract.py':'40b4f68edf8ea13a9522d51212493e5f30c5f94e81f7eb53d770f08949b92aa6',
    'native-ai/macro_cost_asset_audit.py':'ad500ea45396045167051be1318965d643c03b69232131f93daf7bce54a57370',
    'native-ai/macro_payment_observation.py':'f8bc8ae911a452cf19acc3b53a76cbf404bf29b8cca09933da500b45239d442a',
    'native-ai/macro_readiness_observation.py':'d9abb6c26e218f5a719a22bed1279a8b468ae0611ebbc506ad0f2678b5704989',
    'native-ai/readiness_dependency_contract.py':'7b80c594283631fa3cf31f616f63c4a38da32c1e8f29ee32e95fde988a3dee4b',
    'native-ai/macro_cost_identity_guard.py':'0a593d4548f63a2b3aa3a15315c4a266e6557ceb59e8ec433ff846e07d03f2c6',
    'native-ai/macro_guarded_cost_supplier.py':'fa6da32c07d19584cccfd1b1f26fcb62fd1586fe0ed8e9a8d104d906b79ecfcf',
    'native-ai/macro_prioritized_cost_supplier.py':'d0e3c916cc15b8e9a75ef2d6ae90e69702f69dc1372f04c8b234c3d0bf48ce17',
    'native-ai/macro_queue_owner_coverage_contract.py':'c2380f5d3a6a597f2fa593ef2aabc00bd8247c9d2a3dfdb27025f71200885a5d',
    'integration/host_runtime/macro_cost_factory.py':'dce7bc31c2b07f141a6fcaebaf0a718ce1cd7886d787ba78dabd7fdb33636b37'})
SOURCE_PINS2=COVERAGE_PINS
_SEAL=object()

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fail(code):raise ContractError(code)
def _review_inputs(value):
    inputs=value.get('inputs')
    if type(inputs) is not list or not inputs:fail('blocked_cost_v2_review_raw_missing')
    for row in inputs:
        source=Path(row['path']);source=source if source.is_absolute() else ROOT/source
        if not source.resolve().is_relative_to(ROOT/'reports') or sha(source)!=row['sha256']:
            fail('blocked_cost_v2_review_raw_changed')

def _review(path,digest,kind,*,validate_inputs=True):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT/'reports') or sha(path)!=digest:fail('blocked_cost_v2_review_binding')
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if value.get('kind')!=kind or value.get('schema_version')!=1:fail('blocked_cost_v2_review_schema')
    if validate_inputs:_review_inputs(value)
    return path,value

@dataclass(frozen=True)
class CurrentQueueCostQualification:
    coverage_review:Path
    coverage_sha256:str
    attribute_review:Path
    attribute_sha256:str
    executable_sha256:str
    package_sha256:str
    attribute_source_scope:str
    seal:object


def load_current_queue_cost_qualification(*,coverage_review,coverage_sha256,attribute_review,attribute_sha256):
    # The active-attribute review deliberately does not exist until an
    # independent reviewer has a NEW real entry/definition trace. The older
    # active-vector header cannot satisfy this missing proof.
    if attribute_review is None or attribute_sha256 is None:fail('blocked_cost_v2_active_attribute_field_review_missing')
    cp,c=_review(coverage_review,coverage_sha256,'independent_current_queue_coverage_and_cash_field_review')
    q=c.get('qualification',{})
    if (q.get('source_algorithm')!=COVERAGE_ALGORITHM
            or q.get('current_owned_production_upgrade_queue_coverage_supported') is not True
            or q.get('current_player_resource_zero_cash_balance_supported') is not True
            or q.get('old_cash_or_queue_snapshot_reuse_allowed') is not False
            or c.get('all_reads_consumed_in_original_order') is not True):fail('blocked_cost_v2_coverage_review_scope')
    ap,a=_review(attribute_review,attribute_sha256,'independent_native_attribute_cost_upper_review',validate_inputs=False)
    source_scope=a.get('source_scope')
    if (a.get('static_supported') is not True or a.get('field_supported') is not True
            or a.get('upper_bound_scope')!='current_native_attribute14_nonincreasing_divisor_context'
            or source_scope not in ('empty_attribute_vector_only','active_nonincreasing')
            or a.get('executable_sha256')!=c['executable_sha256'] or a.get('package_sha256')!=c['package_sha256']
            or a.get('exact_enqueue_quote_asserted') is not False
            or a.get('source_pins')!={name:COVERAGE_PINS[name] for name in ('native-ai/macro_attribute_cost_bound.py','native-ai/macro_active_attribute_cost_supplier.py')}):
        fail('blocked_cost_v2_active_attribute_review_scope')
    _review_inputs(a)
    for name,expected in COVERAGE_PINS.items():
        if sha(ROOT/name)!=expected:fail('blocked_cost_v2_frozen_algorithm_changed')
    return CurrentQueueCostQualification(cp,coverage_sha256,ap,attribute_sha256,
        c['executable_sha256'],c['package_sha256'],source_scope,_SEAL)


class QualifiedCurrentQueueCostSupplierV2:
    def __init__(self,reader,*,qualification):
        from macro_active_attribute_cost_supplier import ActiveAttributeCostSupplier
        if type(reader) is not ActiveAttributeCostSupplier:fail('blocked_cost_v2_trusted_reader_required')
        if type(qualification) is not CurrentQueueCostQualification or qualification.seal is not _SEAL:
            fail('blocked_cost_v2_explicit_qualification_required')
        if (reader.session.executable_sha256!=qualification.executable_sha256
                or reader.session.package_sha256!=qualification.package_sha256
                or reader.core.delegate.universe._archives_verified is not True):
            fail('blocked_cost_v2_binding_or_compiled_universe')
        self.reader=reader;self.qualification=qualification;self.last_observation=None;self.last_fact=None
        self.required_guard_files={str(ROOT/name):digest for name,digest in SOURCE_PINS2.items()}
        self.required_guard_files.update({str(qualification.coverage_review):qualification.coverage_sha256,
            str(qualification.attribute_review):qualification.attribute_sha256,
            str(Path(__file__).resolve()):sha(__file__)})
    def _fact(self,value):
        if value is not self.reader.last_observation or value.get('source')!=SOURCE:
            fail('blocked_cost_v2_fresh_typed_observation_required')
        q=self.qualification;session=self.reader.session
        if (value.get('session_id')!=session.session_id or value.get('pid')!=session.pid
                or value.get('process_creation_filetime')!=session.process_creation_filetime
                or tuple(value.get('game_identity',()))!=session.game_identity):fail('blocked_cost_v2_native_binding')
        files=value.get('file_guard',{}).get('files',{})
        if (value.get('file_guard',{}).get('complete_file_guards_equal') is not True
                or any(files.get(path)!=digest for path,digest in self.required_guard_files.items())):
            fail('blocked_cost_v2_review_and_factory_not_in_complete_file_guards')
        collect=value.get('financial_collection',{});queues=value.get('queue_commitments',{})
        if (value.get('cross_stage_necessary_bytes_revalidated') is not True or collect.get('phase')!='finished'
                or collect.get('exact_first_range_set_equals_final_range_set') is not True
                or collect.get('final_collect_all_ranges_verified') is not True
                or queues.get('roster_union_scan_complete') is not True or queues.get('queue_scan_complete') is not True
                or queues.get('necessary_fields_stable') is not True
                or queues.get('registry_scan',{}).get('deletion_batch_active') is not False
                or queues.get('registry_scan',{}).get('complete_bucket_scan') is not True
                or queues.get('registry_scan',{}).get('live_list_complete') is not True
                or value.get('owner_lifecycle_contract',{}).get('static_normal_lifecycle_support') is not True):
            fail('blocked_cost_v2_complete_current_queues_required')
        quote=value['quote'];upper=value['single_native_queue_conditional_upper_cost'];attrs=value['native_attribute_upper_context']
        if self.qualification.attribute_source_scope=='empty_attribute_vector_only':
            attribute_evidence=quote.get('producer_attribute_evidence',{})
            if attribute_evidence.get('cost_adjustment_absent') is not True or attribute_evidence.get('entry_count',0)!=0:
                fail('blocked_cost_v2_active_attribute_outside_reviewed_empty_scope')
        if (quote.get('native_getter_quote_verified') is not True
                or type(quote.get('native_getter_quote')) is not int
                or type(upper) is not int or not 0<upper<=0xffffffff
                or not 0<=quote['native_getter_quote']<=upper
                or quote.get('producer_multiplier',{}).get('modifier_count')!=0
                or attrs.get('native_attribute_upper_context_verified') is not True
                or attrs.get('all_active_entries_examined') is not True
                or type(attrs.get('native_attribute_divisor_lower_bound')) is not int
                or attrs.get('native_attribute_divisor_lower_bound')!=1
                or value.get('loaded_target_binding',{}).get('loaded_target_cost_fields_match_audited_asset') is not True
                or value.get('producer_definition_binding',{}).get('producer_definition_verified') is not True):
            fail('blocked_cost_v2_current_conditional_upper_unverified')
        cash=value['credits'];debt=value['production_queue_payment_commitment_upper_bound']
        if (value.get('credits_verified') is not True or any(type(v) is not int or not 0<=v<=0xffffffff for v in (cash,debt))):
            fail('blocked_cost_v2_current_cash_or_queue_amount_unknown')
        self.reader.guard.live_check()
        import struct
        current=struct.unpack('<I',self.reader.raw(self.reader.core.game+0x50,4))[0]
        if current<value['financial_window_frame']:
            self.reader.guard.invalidated=True;fail('blocked_cost_v2_financial_epoch_regressed')
        if current-value['financial_window_frame']>15:fail('blocked_cost_v2_financial_fact_expired')
        # Insufficient cash remains a known observation; the resource store
        # independently rejects admission. Never falsify or clamp its amounts.
        return CurrentQueueBudgetFact(session_id=session.session_id,player_id=3,action=value['action'],
            template_hash=value['template_hash'],source=CURRENT_QUEUE_BUDGET_SOURCE,
            frame=value['financial_window_frame_after'],upper_cost=upper,credits=cash,
            production_upgrade_queue_payment_commitment_upper_bound=debt,game_identity=session.game_identity,
            producer_thing_id=quote['producer_thing_id'],
            producer_type_hash=hex(__import__('macro_cost_observation').PRODUCERS[value['action']]),
            upper_cost_verified=True,credits_verified=True,
            production_upgrade_queue_payment_commitment_upper_bound_verified=True,
            all_owned_production_updates_observed=True,all_production_and_upgrade_nodes_observed=True,
            loaded_target_schema_verified=True,native_quote_context_verified=True,producer_definition_verified=True,
            single_new_request_hard_limit_verified=False,native_ai_autonomous_spending_covered=False,
            repair_and_ability_spending_covered=False,additional_count=1)
    def __call__(self,action,sample,game_seconds):
        self.last_fact=None;self.last_observation=None
        if type(sample) is not dict:fail('blocked_cost_v2_host_sample_required')
        frames=tuple(sample[k]['frame'] for k in ('observation','build_observation','dependency','readiness')
            if type(sample.get(k)) is dict and 'frame' in sample[k])
        self.last_observation=self.reader.observe(action,game_seconds=game_seconds,component_frames=frames)
        self.last_fact=self._fact(self.last_observation);return self.last_fact


def make_current_queue_cost_supplier_v2(reader,*,qualification):
    return QualifiedCurrentQueueCostSupplierV2(reader,qualification=qualification)

@dataclass(frozen=True)
class CostFactoryBootV2:
    supplier:object|None
    enabled:bool
    reason:str
    required_guard_files:dict


def boot_current_queue_cost_supplier_v2(reader,*,coverage_review,coverage_sha256,
        attribute_review=None,attribute_sha256=None):
    """Safe disabled boot leaves the legacy lane independent.

The reader must already borrow the trusted sampler's held read-only handle,
actual recomputed CompiledCostUniverse and explicit TrustedCostGuard. Append
returned required_guard_files to that guard before its first observation.
"""
    try:
        qualification=load_current_queue_cost_qualification(coverage_review=coverage_review,
            coverage_sha256=coverage_sha256,attribute_review=attribute_review,attribute_sha256=attribute_sha256)
        supplier=make_current_queue_cost_supplier_v2(reader,qualification=qualification)
        return CostFactoryBootV2(supplier,True,'qualified_current_queue_upper_reader',dict(supplier.required_guard_files))
    except Exception as error:
        return CostFactoryBootV2(None,False,getattr(error,'code',None) or str(error) or type(error).__name__,{})


@dataclass(frozen=True)
class CurrentFinancialCoverageQualification:
    review_path:Path
    review_sha256:str
    executable_sha256:str
    package_sha256:str
    seal:object


FINANCIAL_SOURCE_PINS={name:value for name,value in COVERAGE_PINS.items()
    if name not in ('native-ai/macro_attribute_cost_bound.py','native-ai/macro_active_attribute_cost_supplier.py',
        'native-ai/macro_cost_upper_contract.py','native-ai/macro_cost_asset_audit.py',
        'native-ai/macro_cost_observation_v2.py','native-ai/macro_prioritized_cost_supplier.py')}
FINANCIAL_SOURCE_PINS.update({'native-ai/macro_quoteless_financial_observation.py': '4727c041c9cc73f21fa8d58e1367e14a768d1c12ffff1bce14484d01d49b3ebe', 'native-ai/read_selected_personality.py': '1dabea75085645420b2bcc7387e4557f410d85bc66a1a57c4b18115981924187'})


def load_current_financial_coverage_qualification(*,coverage_review,coverage_sha256):
    path,review=_review(coverage_review,coverage_sha256,'independent_current_queue_coverage_and_cash_field_review')
    q=review.get('qualification',{})
    if (q.get('source_algorithm')!=COVERAGE_ALGORITHM
            or q.get('current_owned_production_upgrade_queue_coverage_supported') is not True
            or q.get('current_player_resource_zero_cash_balance_supported') is not True
            or q.get('old_cash_or_queue_snapshot_reuse_allowed') is not False
            or review.get('all_reads_consumed_in_original_order') is not True):
        fail('blocked_financial_v4_coverage_review_scope')
    for name,expected in FINANCIAL_SOURCE_PINS.items():
        if sha(ROOT/name)!=expected:fail('blocked_financial_v4_frozen_algorithm_changed')
    return CurrentFinancialCoverageQualification(path,coverage_sha256,
        review['executable_sha256'],review['package_sha256'],_SEAL)


class QualifiedQuotelessFinancialSupplierV4:
    def __init__(self,reader,*,qualification,session,output):
        from macro_quoteless_financial_observation import QuotelessFinancialObserver
        if type(reader) is not QuotelessFinancialObserver:fail('blocked_financial_v4_trusted_reader_required')
        if type(qualification) is not CurrentFinancialCoverageQualification or qualification.seal is not _SEAL:
            fail('blocked_financial_v4_explicit_coverage_qualification_required')
        if (reader.session.executable_sha256!=qualification.executable_sha256
                or reader.session.package_sha256!=qualification.package_sha256):fail('blocked_financial_v4_binary_binding')
        from host_runtime.resource_settlement_adapter import SettlementSession
        if type(session) is not SettlementSession:fail('blocked_financial_v4_canonical_controller_session_required')
        session.validate();binding=reader.session
        if (session.session_id,session.pid,session.process_creation_filetime,session.executable_sha256,
                session.package_sha256,session.game_identity)!=(binding.session_id,binding.pid,binding.process_creation_filetime,
                binding.executable_sha256,binding.package_sha256,binding.game_identity):
            fail('blocked_financial_v4_controller_binding_mismatch')
        self.session=session
        output=Path(output).resolve()
        if not output.is_relative_to(ROOT/'reports') or output.exists():fail('blocked_financial_v4_fresh_output_required')
        output.mkdir(parents=True)
        self.reader=reader;self.qualification=qualification;self.output=output;self.counter=0
        self.last_observation=None;self.last_fact=None
        self.required_guard_files={str(ROOT/name):value for name,value in FINANCIAL_SOURCE_PINS.items()}
        self.required_guard_files.update({str(qualification.review_path):qualification.review_sha256,
            str(Path(__file__).resolve()):sha(__file__)})
    def observe(self):
        import time
        from host_runtime.resource_admission_reservations_v4 import FinancialStateV4,validate_financial
        from host_runtime.resource_settlement_adapter import SettlementSession,digest
        from macro_quoteless_financial_observation import SOURCE
        self.last_observation=None;self.last_fact=None;value=self.reader.observe()
        self.last_observation=value;guardfiles=value.get('file_guard',{}).get('files',{})
        if (value is not self.reader.last_observation or value.get('source')!=SOURCE
                or value.get('file_guard',{}).get('complete_file_guards_equal') is not True
                or any(guardfiles.get(path)!=wanted for path,wanted in self.required_guard_files.items())):
            fail('blocked_financial_v4_complete_files_or_fresh_observation')
        collect=value['financial_collection'];queues=value['queue_commitments'];contract=value['owner_lifecycle_contract']
        if (collect.get('phase')!='finished' or collect.get('exact_first_range_set_equals_final_range_set') is not True
                or collect.get('final_collect_all_ranges_verified') is not True
                or queues.get('roster_union_scan_complete') is not True or queues.get('queue_scan_complete') is not True
                or queues.get('necessary_fields_stable') is not True
                or queues.get('registry_scan',{}).get('deletion_batch_active') is not False
                or contract.get('static_normal_lifecycle_support') is not True
                or value.get('payment_balance',{}).get('credits_verified') is not True):
            fail('blocked_financial_v4_complete_window_required')
        profile=value['native_profile'];binding=self.reader.session
        session=SettlementSession(binding.session_id,binding.pid,binding.process_creation_filetime,
            binding.executable_sha256,binding.package_sha256,binding.game_identity,
            profile['ai_player'],profile['personality_wrapper'],profile['player_template']);session.validate()
        if session!=self.session:fail('blocked_financial_v4_current_profile_differs_from_controller')
        # A new durable artifact binds this actual byte range set and values;
        # no archived old queue/cash amounts enter the returned fact.
        self.counter+=1;artifact=dict(kind='qualified_quoteless_financial_current_evidence_v4',
            observation=value,necessary_ranges=self.reader.last_raw_manifest,
            field_coverage_review_sha256=self.qualification.review_sha256)
        raw=json.dumps(artifact,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        target=self.output/('financial-'+str(self.counter).zfill(6)+'.json')
        with target.open('xb') as stream:stream.write(raw)
        evidence=hashlib.sha256(raw).hexdigest()
        qualification_digest=digest(dict(static_lifecycle_contract=contract,
            field_coverage_review_sha256=self.qualification.review_sha256,frozen_sources=FINANCIAL_SOURCE_PINS))
        fact=FinancialStateV4(session=session,frame=value['frame'],frame_after=value['frame_after'],
            component_frames=tuple(value['component_frames']),started_monotonic_ns=value['started_monotonic_ns'],
            ended_monotonic_ns=value['ended_monotonic_ns'],credits=value['credits'],
            production_upgrade_commitment_upper_bound=value['production_upgrade_commitment_upper_bound'],
            coverage_contract_sha256=qualification_digest,source_evidence_sha256=evidence,
            complete_registered_live_union_coverage_verified=True,all_production_upgrade_modules_and_nodes_verified=True,
            same_financial_window_stable=True,native_payment_balance_currency_verified=True,
            owner_lifecycle_contract_verified=True,field_complete_queue_coverage_qualified=True,
            held_handle_identity_before_after_verified=True,gc_inactive_verified=True,
            future_unaccepted_spending_covered=False,prior_preference_latent_work_covered=False,
            actual_payment_attribution_verified=False,exclusive_enqueue_causality_verified=False,
            hard_total_spending_limit_verified=False)
        self.reader.guard.live_check();current=self.reader._frame()
        validate_financial(fact,session,current_game_frame=current,now_monotonic_ns=time.monotonic_ns())
        self.last_fact=fact;return fact
    def __call__(self):return self.observe()


def boot_quoteless_financial_supplier_v4(reader,*,coverage_review,coverage_sha256,session,output):
    try:
        qualification=load_current_financial_coverage_qualification(coverage_review=coverage_review,coverage_sha256=coverage_sha256)
        supplier=QualifiedQuotelessFinancialSupplierV4(reader,qualification=qualification,session=session,output=output)
        return CostFactoryBootV2(supplier,True,'qualified_quoteless_current_financial_v4',dict(supplier.required_guard_files))
    except Exception as error:
        return CostFactoryBootV2(None,False,getattr(error,'code',None) or str(error) or type(error).__name__,{})
