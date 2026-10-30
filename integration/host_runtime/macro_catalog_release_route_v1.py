"""Explicit schema12/V5 routing signals; signals require proof, never grant it."""
import hashlib
import json
from pathlib import Path

from .contracts import ContractError,SessionBinding
from . import macro_release_review_v5 as review

def fail():raise ContractError('macro_catalog_release_v5_required_or_unverified')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def requires_v5(output,*,journal=None,run_id=None,release=None,receipt=None,bundle=None,selected=False):
    """No absent/broken V5 evidence may select the older scalar/V4 grammar."""
    if selected is True:return True
    if type(bundle) is dict and (bundle.get('schema_version')==12 or bundle.get('kind')=='verified_macro_consumer_catalog_bootstrap_v12'):return True
    for value in (release,receipt):
        if value is not None and type(value) is not dict:fail()
        if type(value) is dict and (value.get('native_release_contract')==review.KIND
                or any(type(key) is str and key.startswith('publication_v5_') for key in value)):return True
    return review.publication_v5_was_selected(output,journal=journal,run_id=run_id)

def extension(proof,contract_path,review_path):
    """Metadata from an already recomputed proof; does not authorize cleanup."""
    if (type(proof) is not dict or proof.get('kind')!='macro_publication_v5_release_projection'
            or proof.get('native_release_verified') is not True or sha(contract_path)!=proof.get('contract_sha256')):fail()
    raw=Path(review_path).read_bytes()
    if json.loads(raw.decode('utf-8-sig'))!=proof:fail()
    value=dict(native_release_contract=review.KIND,publication_v5_contract_sha256=proof['contract_sha256'],
        publication_v5_release_review_sha256=hashlib.sha256(raw).hexdigest(),publication_v5_outer_bundle_sha256=proof['outer_bundle_sha256'],
        publication_v5_base_bundle_sha256=proof['base_bundle_sha256'])
    if Path(review_path).read_bytes()!=raw or sha(contract_path)!=proof['contract_sha256']:fail()
    return value

def reviewed_v5_trial(directory,*,output,release,receipt=None,journal=None,expected=None,expected_binding=None,expected_run_id=None):
    """Recompute completed durable history, selector, raw proof and sidecar.

    File-only readers possess only release; desktop also supplies the actual
    durable receipt. File-only callers use the pre-execution journal location
    to read the actual receipt, never an invented or exported scalar receipt.
    """
    output=Path(output);contract=output/'publication-v5-contract.json';sidecar=output/'publication-v5-release-review.json'
    from .macro_catalog_release_history_v1 import historical_projection_v1
    # This is an explicit completed-history grammar, never a fallback after a
    # failed first release. Host first release calls strict frozen V5 directly.
    proof,result=historical_projection_v1(directory,output=output,release=release,receipt=receipt,journal=journal,
        expected=expected,expected_binding=expected_binding,expected_run_id=expected_run_id)
    raw=sidecar.read_bytes()
    if json.loads(raw.decode('utf-8-sig'))!=proof:fail()
    wanted=extension(proof,contract,sidecar)
    marker=load(contract)
    if type(release) is not dict:fail()
    binding=SessionBinding.from_dict(release.get('binding'))
    if (release.get('kind')!='macro_policy_native_release' or release.get('run_id')!=marker['run_id']
            or binding.binding_hash!=marker['binding_hash']
            or release.get('final_state_sha256')!=sha(Path(directory)/'final-state.json')):fail()
    if receipt is not None and (type(receipt) is not dict or receipt.get('binding_hash')!=marker['binding_hash']):fail()
    values=[release] if receipt is None else [release,receipt]
    for value in values:
        if (type(value) is not dict or value.get('native_release_verified') is not True
                or any(value.get(key)!=entry for key,entry in wanted.items())):fail()
    if sidecar.read_bytes()!=raw:fail()
    return result
