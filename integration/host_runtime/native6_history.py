"""Passive replay of explicitly recognized Native6 return evidence.

Historical manifests are data, never import roots or execution grants. Only
current installed verifier bytecode runs. Nothing here attaches, collects a
fresh proof, changes a ledger, or qualifies another use of an old Game.
"""
from pathlib import Path
from types import FunctionType

from .contracts import ContractError
from .native6_runtime_contract import read,sha
from .native6_qualification import trusted_pin

# Recognized installed software identities, never field passes or acceptance
# counts. rc07's normal STOP routing failure and unselected orphan files remain
# original evidence; only their committed complete proof is passively reviewed.
PRIOR={
    '2b169834d047be5252fceaf5dcf2d1a985b6e502d15ca826746c87acc76cf02f':
    'e6bc60a173972f28c82623ca5ade393d214ca4c1b24cf71822f36e275ee15824',
    '3da3125060350f4dd0a0f27cc002fc7ab1b42526bc27f1a0bf3ffd92f69d4304':
    'b2a73cc69f5185f1f34af0e28505d7681a4afa3b594189c744f38743022c48ea',
    '3ca984304899a58c2c8bf8e5c8b4669937f839a05078b11ba5807c236cd00911':
    'ad69412b47e390c765c24ece14a235776af23d3bbb15f074cf444c8c2561ddc0',
    'a6fc0e473dd3d348d07a2e7661dd874eaf88c8f2fde32d89a4c8b2b65cf6c27e':
    '8ca54eb34d9c98470d5387a8f0cba90912459ce09e6170c3172c46812660e642',
    'a43ab48b1daaf58f8e21091f609b6a7d669d3493e4d7f14946469e74210c1388':
    '177cd3feac2707eaa2679956817fee616127f391d4dbc1d160c3e4960835deae',
    '66a966191d56c5d6d31750c0a90288e458d6a0567590fd031ddb3e9258664a25':
    'c1df3f59cf08ee332263230ea61d46e39a959b2abd9b6a1a96cf0d992b7d0da2',
    '5eb167dd9a507d15b6ba0df7079f7d55045dc50209107ff99c19ad891de5772e':
    'a5ed8b94e5e283233b118ce90ed1e7cbc5a6658979f1e6fe6e8f3d82de261391',
    '4179628c6ff2618803ad824ba27cfcec0633a87aabe799172698c02ad0038625':
    '0595471ba91279a272064dd2b575cbddcd134ceb0fac5722345b7ad30ea83e34',
}


def _review(row):
    from . import native6_lifecycle as live
    value=read(Path(row['output_path'])/'native6-context.json')
    pin=value['runtime_manifest_sha256']
    current=trusted_pin()
    if pin==current and Path(value['runtime_root'])==live.runtime_root():return live.context,None
    if pin!=current and pin not in PRIOR:raise ContractError('native6_history_version_unrecognized')
    # The original context still validates every frozen source, identity,
    # descriptor, session and report location. Only its expected software pin
    # and comparison-only installation root differ in this passive replay.
    values=dict(vars(live),trusted_pin=lambda:pin,runtime_root=lambda:Path(value['runtime_root']))
    context=FunctionType(live.context.__code__,values,live.context.__name__)
    values['context']=context
    return context,values


def context(row,session,binding):
    verify,values=_review(row)
    result=verify(row,session,binding)
    if values is not None:
        _,manifest,inventory=result
        pin=result[0]['runtime_manifest_sha256']
        if pin!=trusted_pin() and manifest['source_closure_sha256']!=PRIOR[pin]:
            raise ContractError('native6_history_version_unrecognized')
        # Do not reinterpret old proof formats with changed verifier files.
        for name in ('native6_lifecycle.py','native6_release.py','native6_no_attachment.py',
                     'native6_orphan_return.py','native5_orphan_return_v1.py','strategic_unified_unknown_return_v5.py'):
            if sha(Path(__file__).with_name(name))!=inventory['files'].get('app/integration/host_runtime/'+name):
                raise ContractError('native6_history_verifier_changed')
    return result


def verified_return(backend,row,binding,receipt):
    try:
        from .native6_release import KIND as NORMAL
        from .native6_no_attachment import KIND as NO_ATTACH
        from . import native6_orphan_return as orphan
        stop=backend.journal.get_command(row['run_id'],'macro-stop')
        if stop['status']!='released':return False
        contract=(stop['receipt'] or {}).get('native_release_contract')
        if contract in (NORMAL,NO_ATTACH):
            from .native6_normal_return_v1 import verified_return as normal_verified
            return normal_verified(backend,row,binding,receipt,context=context)
        if contract!=orphan.KIND:return False
        # Clone only pure review functions. In particular capture, finish and
        # recover_after_stop are never rebound or exposed by this adapter.
        passive=dict(vars(orphan),context=context)
        for name in ('inputs','verified_capture','verified_return'):
            function=getattr(orphan,name)
            passive[name]=FunctionType(function.__code__,passive,name,function.__defaults__,function.__closure__)
        return passive['verified_return'](backend,row,binding,receipt)
    except (OSError,ValueError,KeyError,TypeError,OverflowError,AttributeError,ContractError):return False
