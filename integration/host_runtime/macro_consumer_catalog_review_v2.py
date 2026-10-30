"""Explicit multi-consumer candidate contract over unchanged primed raw trials.

This is an offline reviewer. Only the separate v2 scope extender may inherit
its queue qualification; no report, action string or model request grants it.
"""
from dataclasses import asdict,dataclass
import hashlib
import json
from pathlib import Path
import sys

from .contracts import ContractError
from . import macro_consumer_candidate_review as original
from .macro_expansion_scope import ROOT,TARGETS

CONTRACT='fixed_consumer_primed_catalog_v2'
ACTIONS=('buildbarracks','buildfactory','buildbattlelab','producesickle','producebullfrog')
PINS={
    'integration/host_runtime/macro_consumer_candidate_review.py':'6e7312b5d48df272f8d06cf77a9d45a11f0b5053b48b4a77166ec0daa77fc332',
    'integration/host_runtime/macro_expansion_scope.py':'2c5bb72d463f9e1d1bdfd6391df2aae3aba021d78b506578d0735e28216542af',
    'acceptance/macro_consumer_primed_trial.py':'0857000722d6b08b788082cfef313453d8ba503efd90e99d2aab516cbe6a340d',
    'acceptance/assess_macro_consumer_primed_field.py':'b3156faf745057625a3d8974e645410411e001c3aded38cf9828a0e40364c8e7',
    'acceptance/macro_expansion_primed_trial.py':'e11bd43e78f636aa29ed21c0989eab68fa5507971c0994c1e018688c4813b7b4',
    'acceptance/assess_macro_expansion_primed_field.py':'678a0b215dfa48364fff08a267440cb5db450db63bd5eac4bd6c8c91b83a5cdb'}
SPECS={
    'buildbarracks':('SovietBarracks','SovietConstructionYard',True,(), 'budgeteconomy'),
    'buildfactory':('SovietWarFactory','SovietConstructionYard',True,('SovietRefinery',),'budgeteconomy'),
    'buildbattlelab':('SovietTechStructure','SovietConstructionYard',True,('SovietPowerPlantAdvanced',),'budgeteconomy'),
    'producesickle':('SovietAntiInfantryVehicle','SovietWarFactory',False,('SovietWarFactory',),'budgetarmy'),
    'producebullfrog':('SovietAntiAirShip_Ground','SovietWarFactory',False,('SovietWarFactory',),'budgetarmy')}

def reject(code='macro_consumer_catalog_v2_not_qualified'):raise ContractError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

@dataclass(frozen=True)
class ConsumerCatalogReviewV2:
    action:str
    first_observed_queue_batch_count:int
    queue_acceptance_supported:bool=True
    underlying_raw_contract:str=original.CONTRACT
    contract:str=CONTRACT
    schema_version:int=2
    kind:str='macro_consumer_catalog_candidate_review'
    product_capability_granted:bool=False
    model_loop_verified:bool=False
    completion_verified:bool=False
    operational_verified:bool=False
    technology_unlock_verified:bool=False
    payment_verified:bool=False
    exclusive_attribution_verified:bool=False
    hard_native_queue_cap:bool=False
    field_qualification_granted:bool=False
    def public(self):return asdict(self)

def _unique_manifest_consumer(manifest,action):
    if action not in ACTIONS:reject('macro_consumer_catalog_v2_distinct_driver_required')
    rows=manifest.get('consumers');flags=manifest.get('flags')
    if (type(rows) is not list or len(rows)!=20 or type(flags) is not list or len(flags)!=20
            or any(type(row) is not dict for row in rows) or [row.get('flag') for row in rows]!=flags
            or any(type(flag) is not str or not flag for flag in flags) or len(set(flags))!=20
            or any(type(row.get('action')) is not str for row in rows) or len({row['action'] for row in rows})!=20):reject()
    matches=[row for row in rows if row['action']==action]
    if len(matches)!=1:reject()
    row=matches[0];template,producer,absent,required,budget=SPECS[action]
    if (row.get('template')!=template or row.get('producer')!=producer or row.get('domain')!=TARGETS[action][2]
            or row.get('heuristic')!='CONSTANT' or type(row.get('only_if_target_absent')) is not bool
            or row['only_if_target_absent'] is not absent or row.get('required_own_templates')!=list(required)
            or len([r for r in rows if r['action']==budget and r.get('domain')=='budget'])!=1):reject()
    return row

def review_data_v2(pre,events,final,result,assessment,expected_manifest,*,expected_action):
    _unique_manifest_consumer(expected_manifest,expected_action)
    if pre.get('config',{}).get('action')!=expected_action:reject('macro_consumer_catalog_v2_action_binding')
    # These 28 original checks include coherent samples, two actual prime
    # budget frames, a fresh legal idle baseline, exact raw ACKs/first new
    # target queue, immediate clear and all 20 flags/hook/lease cleanup.
    reviewed=original.review_data(pre,events,final,result,assessment,expected_manifest)
    if type(reviewed) is not original.ConsumerCandidateReview or reviewed.action!=expected_action:reject()
    return ConsumerCatalogReviewV2(expected_action,reviewed.first_observed_queue_batch_count)

def verify_sources():
    for name,wanted in PINS.items():
        if sha(ROOT/name)!=wanted:reject('macro_consumer_catalog_v2_frozen_algorithm_changed')

def review_candidate_v2(folder,*,expected_manifest,expected_action):
    """Replay original raw files, never trust a saved assessment's green bit."""
    verify_sources();_unique_manifest_consumer(expected_manifest,expected_action)
    folder=Path(folder).resolve()
    if not folder.is_relative_to(ROOT/'reports') or not folder.is_dir():reject('macro_consumer_catalog_v2_reports_required')
    path=folder/'driver-preflight.json';pre_raw=path.read_bytes();pre=json.loads(pre_raw.decode('utf-8-sig'))
    if pre.get('config',{}).get('action')!=expected_action:reject('macro_consumer_catalog_v2_action_binding')
    # The frozen reviewer independently reassesses the raw driver and v2
    # transport, including source and original/session SHA checks.
    reviewed,evidence=original.review_candidate(folder,expected_manifest=expected_manifest)
    if (type(reviewed) is not original.ConsumerCandidateReview or reviewed.action!=expected_action
            or reviewed.contract!=original.CONTRACT or reviewed.queue_acceptance_supported is not True
            or type(reviewed.first_observed_queue_batch_count) is not int or reviewed.first_observed_queue_batch_count<1
            or any(getattr(reviewed,key) is not False for key in ('product_capability_granted','field_qualification_granted',
                'model_loop_verified','completion_verified','operational_verified','technology_unlock_verified',
                'payment_verified','exclusive_attribution_verified','hard_native_queue_cap'))):reject()
    if pre_raw!=path.read_bytes():reject('macro_consumer_catalog_v2_input_changed')
    verify_sources()
    for name,wanted in PINS.items():
        key=str((ROOT/name).resolve())
        if key in evidence and evidence[key]!=wanted:reject('macro_consumer_catalog_v2_evidence_conflict')
        evidence[key]=wanted
    evidence[str(Path(__file__).resolve())]=sha(__file__)
    return ConsumerCatalogReviewV2(expected_action,reviewed.first_observed_queue_batch_count),evidence
