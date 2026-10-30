"""Explicit same-window AdmissionCostV4; never converts a v3 cost fact."""
import hashlib
import json
from pathlib import Path
import time
from .contracts import ContractError
from . import macro_cost_factory_v2 as shared
from .resource_settlement_adapter import SettlementSession,digest
from .resource_admission_reservations_v4 import FinancialStateV4,AdmissionCostV4,validate_financial

PROFILED_READER_SHA256='5231a331163dc84fe80560047bcde5dc2dadb6ebab00bc9c861f475c9d5d4629'
PERSONALITY_INSPECTOR_SHA256='1dabea75085645420b2bcc7387e4557f410d85bc66a1a57c4b18115981924187'
ROOT=shared.ROOT

def fail(code):raise ContractError(code)

class QualifiedAdmissionCostSupplierV4:
    def __init__(self,reader,*,qualification,session,output):
        from macro_profiled_admission_cost_supplier import ProfiledAdmissionCostSupplier
        if type(reader) is not ProfiledAdmissionCostSupplier:fail('admission_v4_trusted_same_window_reader_required')
        if type(qualification) is not shared.CurrentQueueCostQualification or qualification.seal is not shared._SEAL:
            fail('admission_v4_explicit_price_and_coverage_qualification_required')
        if type(session) is not SettlementSession:fail('admission_v4_canonical_session_required')
        session.validate();binding=reader.session
        if (session.session_id,session.pid,session.process_creation_filetime,session.executable_sha256,
                session.package_sha256,session.game_identity)!=(binding.session_id,binding.pid,
                binding.process_creation_filetime,binding.executable_sha256,binding.package_sha256,binding.game_identity):
            fail('admission_v4_exact_session_binding_required')
        if (binding.executable_sha256!=qualification.executable_sha256 or binding.package_sha256!=qualification.package_sha256
                or reader.core.delegate.universe._archives_verified is not True):fail('admission_v4_compiled_universe_binding')
        if shared.sha(ROOT/'native-ai/macro_profiled_admission_cost_supplier.py')!=PROFILED_READER_SHA256:
            fail('admission_v4_profiled_reader_changed')
        if shared.sha(ROOT/'native-ai/read_selected_personality.py')!=PERSONALITY_INSPECTOR_SHA256:
            fail('admission_v4_personality_inspector_changed')
        output=Path(output).resolve()
        if not output.is_relative_to(ROOT/'reports') or output.exists():fail('admission_v4_fresh_output_required')
        output.mkdir(parents=True);self.reader=reader;self.qualification=qualification;self.session=session;self.output=output
        self.counter=0;self.last_fact=None;self.last_observation=None
        self.required_guard_files={str(ROOT/name):value for name,value in shared.SOURCE_PINS2.items()}
        self.required_guard_files.update({str(qualification.coverage_review):qualification.coverage_sha256,
            str(qualification.attribute_review):qualification.attribute_sha256,
            str(Path(shared.__file__).resolve()):shared.sha(shared.__file__),
            str(Path(__file__).resolve()):shared.sha(__file__),
            str(ROOT/'native-ai/macro_profiled_admission_cost_supplier.py'):PROFILED_READER_SHA256,
            str(ROOT/'native-ai/read_selected_personality.py'):PERSONALITY_INSPECTOR_SHA256})
    def __call__(self,action,sample,game_seconds):
        from macro_profiled_admission_cost_supplier import SOURCE
        self.last_fact=None;self.last_observation=None
        if type(sample) is not dict:fail('admission_v4_current_host_sample_required')
        component_frames=tuple(sample[k]['frame'] for k in ('observation','build_observation','dependency','readiness')
            if type(sample.get(k)) is dict and 'frame' in sample[k])
        value=self.reader.observe(action,game_seconds=game_seconds,component_frames=component_frames)
        self.last_observation=value;files=value.get('file_guard',{}).get('files',{})
        if (value is not self.reader.last_observation or value.get('source')!=SOURCE
                or value.get('file_guard',{}).get('complete_file_guards_equal') is not True
                or any(files.get(path)!=wanted for path,wanted in self.required_guard_files.items())):
            fail('admission_v4_source_or_complete_files_unverified')
        profile=value['native_profile'];binding=self.reader.session
        actual=SettlementSession(binding.session_id,binding.pid,binding.process_creation_filetime,
            binding.executable_sha256,binding.package_sha256,binding.game_identity,
            profile['ai_player'],profile['personality_wrapper'],profile['player_template'])
        actual.validate()
        if actual!=self.session:fail('admission_v4_current_owned_profile_differs_from_controller')
        collect=value['financial_collection'];queues=value['queue_commitments'];contract=value['owner_lifecycle_contract']
        if (collect.get('phase')!='finished' or collect.get('exact_first_range_set_equals_final_range_set') is not True
                or collect.get('final_collect_all_ranges_verified') is not True
                or value.get('cross_stage_necessary_bytes_revalidated') is not True
                or queues.get('roster_union_scan_complete') is not True or queues.get('queue_scan_complete') is not True
                or queues.get('necessary_fields_stable') is not True
                or queues.get('registry_scan',{}).get('deletion_batch_active') is not False
                or contract.get('static_normal_lifecycle_support') is not True):
            fail('admission_v4_complete_same_financial_window_required')
        quote=value['quote'];attrs=value['native_attribute_upper_context'];upper=value['single_native_queue_conditional_upper_cost']
        if self.qualification.attribute_source_scope=='empty_attribute_vector_only':
            evidence=quote.get('producer_attribute_evidence',{})
            if evidence.get('cost_adjustment_absent') is not True or evidence.get('entry_count',0)!=0:
                fail('admission_v4_active_attribute_outside_reviewed_empty_scope')
        if (value['action']!=action or quote.get('native_getter_quote_verified') is not True
                or type(quote.get('native_getter_quote')) is not int or type(upper) is not int or not 0<upper<=0xffffffff
                or not 0<=quote['native_getter_quote']<=upper or quote.get('producer_multiplier',{}).get('modifier_count')!=0
                or attrs.get('native_attribute_upper_context_verified') is not True or attrs.get('all_active_entries_examined') is not True
                or type(attrs.get('native_attribute_divisor_lower_bound')) is not int or attrs['native_attribute_divisor_lower_bound']!=1
                or value['loaded_target_binding'].get('loaded_target_cost_fields_match_audited_asset') is not True
                or value['producer_definition_binding'].get('producer_definition_verified') is not True
                or value.get('credits_verified') is not True):fail('admission_v4_current_price_upper_unverified')
        self.counter+=1;artifact=dict(kind='same_window_current_financial_admission_cost_evidence_v4',
            observation=value,necessary_ranges=self.reader.last_raw_manifest,
            coverage_review_sha256=self.qualification.coverage_sha256,attribute_review_sha256=self.qualification.attribute_sha256)
        raw=json.dumps(artifact,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        with (self.output/('admission-'+str(self.counter).zfill(6)+'.json')).open('xb') as stream:stream.write(raw)
        evidence=hashlib.sha256(raw).hexdigest();timing=value['financial_core_timing']
        finance=FinancialStateV4(session=actual,frame=value['financial_window_frame'],frame_after=value['financial_window_frame_after'],
            component_frames=tuple(value['internal_financial_component_frames']),started_monotonic_ns=timing['started_monotonic_ns'],
            ended_monotonic_ns=timing['ended_monotonic_ns'],credits=value['credits'],
            production_upgrade_commitment_upper_bound=value['production_queue_payment_commitment_upper_bound'],
            coverage_contract_sha256=digest(dict(static_lifecycle_contract=contract,
                field_coverage_review_sha256=self.qualification.coverage_sha256,frozen_sources=shared.FINANCIAL_SOURCE_PINS)),
            source_evidence_sha256=evidence,complete_registered_live_union_coverage_verified=True,
            all_production_upgrade_modules_and_nodes_verified=True,same_financial_window_stable=True,
            native_payment_balance_currency_verified=True,owner_lifecycle_contract_verified=True,
            field_complete_queue_coverage_qualified=True,held_handle_identity_before_after_verified=True,gc_inactive_verified=True,
            future_unaccepted_spending_covered=False,prior_preference_latent_work_covered=False,
            actual_payment_attribution_verified=False,exclusive_enqueue_causality_verified=False,hard_total_spending_limit_verified=False)
        self.reader.guard.live_check();current=self.reader.core._frame()
        validate_financial(finance,actual,current_game_frame=current,now_monotonic_ns=time.monotonic_ns())
        fact=AdmissionCostV4(financial=finance,action=action,template_hash=value['template_hash'],
            producer_thing_id=quote['producer_thing_id'],producer_type_hash=hex(__import__('macro_cost_observation').PRODUCERS[action]),
            quote_frame=quote['frame_after'],upper_cost=upper,source_evidence_sha256=evidence,
            native_upper_cost_verified=True,loaded_target_schema_verified=True,current_quote_and_producer_verified=True)
        self.last_fact=fact;return fact


def boot_admission_cost_supplier_v4(reader,*,coverage_review,coverage_sha256,attribute_review,attribute_sha256,session,output):
    try:
        qualification=shared.load_current_queue_cost_qualification(coverage_review=coverage_review,
            coverage_sha256=coverage_sha256,attribute_review=attribute_review,attribute_sha256=attribute_sha256)
        supplier=QualifiedAdmissionCostSupplierV4(reader,qualification=qualification,session=session,output=output)
        return shared.CostFactoryBootV2(supplier,True,'qualified_same_window_current_admission_v4',dict(supplier.required_guard_files))
    except Exception as error:
        return shared.CostFactoryBootV2(None,False,getattr(error,'code',None) or str(error) or type(error).__name__,{})
