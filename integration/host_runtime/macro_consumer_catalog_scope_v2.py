"""Explicit v2 inheritance of five independently replayed consumer queues.

Old schema11 and the original single-sickle scope stay unchanged. A future
versioned trusted bundle must explicitly call this entry point and pin it.
"""
from dataclasses import dataclass,fields,replace
from pathlib import Path
from .contracts import ContractError
from .macro_expansion_scope import ExpansionScope,EXTRA_ACTIONS,runtime_build
from .macro_consumer_catalog_review_v2 import ACTIONS,CONTRACT,ConsumerCatalogReviewV2,review_candidate_v2,sha

def reject(code):raise ContractError('macro_consumer_catalog_v2_'+code)

@dataclass(frozen=True)
class ConsumerCatalogScopeV2(ExpansionScope):
    consumer_catalog_revision:int=2
    def public(self):
        value=super().public();value['consumer_catalog_revision']=2
        value['fixed_consumer_qualification_contracts']={action:dict(schema_version=2 if kind==CONTRACT else 1,
            kind=kind,qualification='fixed_consumer_queue_acceptance_only') for action,kind in self.fixed_consumer_qualifications}
        return value

def extend_fixed_consumer_catalog_v2(scope,*,build,contracts):
    if not isinstance(scope,ExpansionScope):reject('expansion_scope_required')
    if type(contracts) is not list or not 1<=len(contracts)<=len(ACTIONS):reject('contract_set')
    manifest,_,_,build_evidence=runtime_build(build)
    if (scope.package_sha256!=manifest['package_sha256'] or list(scope.budget.flags)!=manifest['flags']
            or scope.budget.native_sources!=manifest['sources']):reject('runtime_mismatch')
    choices=set(scope.expansion_choices);granted=dict(scope.expansion_evidence);qualified=dict(scope.fixed_consumer_qualifications)
    evidence=dict(scope.evidence);new_evidence=dict(build_evidence);directories=set()
    # Validate the entire descriptor set before replay or construction.
    actions=set();prepared=[]
    for entry in contracts:
        if (type(entry) is not dict or set(entry)!={'schema_version','kind','action','directory'}
                or type(entry.get('schema_version')) is not int or entry['schema_version']!=2 or entry.get('kind')!=CONTRACT
                or entry.get('action') not in ACTIONS or type(entry.get('directory')) is not str):reject('contract_schema')
        action=entry['action'];folder=Path(entry['directory'])
        if (not folder.is_absolute() or str(folder).startswith('\\\\') or not folder.is_dir()
                or folder.resolve() in directories or action in choices or action in actions):reject('duplicate_or_path')
        directories.add(folder.resolve());actions.add(action);prepared.append((action,folder.resolve()))
    for action,folder in prepared:
        reviewed,pins=review_candidate_v2(folder,expected_manifest=manifest,expected_action=action)
        if (type(reviewed) is not ConsumerCatalogReviewV2 or reviewed.action!=action or reviewed.contract!=CONTRACT
                or reviewed.schema_version!=2 or reviewed.underlying_raw_contract!='fixed_consumer_primed_v1'
                or reviewed.queue_acceptance_supported is not True or type(reviewed.first_observed_queue_batch_count) is not int
                or reviewed.first_observed_queue_batch_count<1
                or any(getattr(reviewed,key) is not False for key in ('product_capability_granted','field_qualification_granted',
                    'model_loop_verified','completion_verified','operational_verified','technology_unlock_verified',
                    'payment_verified','exclusive_attribution_verified','hard_native_queue_cap'))):reject('candidate_not_qualified')
        matches=[row for row in manifest['consumers'] if row.get('action')==action]
        if len(matches)!=1:reject('manifest_action')
        choices.add(action);granted[action]=matches[0]['flag'];qualified[action]=CONTRACT
        for path,digest in pins.items():
            if path in new_evidence and new_evidence[path]!=digest:reject('evidence_conflict')
            new_evidence[path]=digest
    own=Path(__file__).resolve();new_evidence[str(own)]=sha(own)
    for path,digest in new_evidence.items():
        if path in evidence and evidence[path]!=digest:reject('evidence_conflict')
        evidence[path]=digest
    values={field.name:getattr(scope,field.name) for field in fields(ExpansionScope)}
    values.update(budget=replace(scope.budget,evidence=evidence),evidence=evidence,
        expansion_choices=tuple(action for action in EXTRA_ACTIONS if action in choices),
        expansion_evidence=tuple((action,granted[action]) for action in EXTRA_ACTIONS if action in granted),
        fixed_consumer_qualifications=tuple((action,qualified[action]) for action in EXTRA_ACTIONS if action in qualified))
    return ConsumerCatalogScopeV2(**values)
