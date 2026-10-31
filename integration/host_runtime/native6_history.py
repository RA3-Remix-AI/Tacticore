"""Passive replay of explicitly recognized Native6 return evidence.

Historical manifests are data, never import roots or execution grants. Only
current installed verifier bytecode runs. Nothing here attaches, collects a
fresh proof, changes a ledger, or qualifies another use of an old Game.
"""
import builtins
from pathlib import Path
from types import FunctionType,SimpleNamespace

from .contracts import ContractError
from .native6_runtime_contract import read,sha
from .native6_qualification import trusted_pin

# Installed rc06: two startup failures, both independently returned. This
# recognizes its software identity, not a claimed pass or an acceptance count.
PRIOR={
    '66a966191d56c5d6d31750c0a90288e458d6a0567590fd031ddb3e9258664a25':
    'c1df3f59cf08ee332263230ea61d46e39a959b2abd9b6a1a96cf0d992b7d0da2',
}


def _review(row):
    from . import native6_lifecycle as live
    value=read(Path(row['output_path'])/'native6-context.json')
    pin=value['runtime_manifest_sha256']
    if pin==trusted_pin():return live.context,None
    if pin not in PRIOR:raise ContractError('native6_history_version_unrecognized')
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
        if manifest['source_closure_sha256']!=PRIOR[pin]:raise ContractError('native6_history_version_unrecognized')
        # Do not reinterpret old proof formats with changed verifier files.
        for name in ('native6_lifecycle.py','native6_release.py','native6_no_attachment.py',
                     'native6_orphan_return.py','native5_orphan_return_v1.py','strategic_unified_unknown_return_v5.py'):
            if sha(Path(__file__).with_name(name))!=inventory['files'].get('app/integration/host_runtime/'+name):
                raise ContractError('native6_history_verifier_changed')
    return result


def verified_return(backend,row,binding,receipt):
    try:
        from . import native6_lifecycle as live,native6_orphan_return as orphan
        session=read(Path(row['session_path']))
        context(row,session,binding)
        _,values=_review(row)
        if values is None:return live.verified_return(backend,row,binding,receipt)
        # Clone only pure review functions. In particular capture, finish and
        # recover_after_stop are never rebound or exposed by this adapter.
        passive=dict(vars(orphan),context=context)
        for name in ('inputs','verified_capture','verified_return'):
            function=getattr(orphan,name)
            passive[name]=FunctionType(function.__code__,passive,name,function.__defaults__,function.__closure__)
        original_import=builtins.__import__
        def review_import(name,globals=None,locals=None,fromlist=(),level=0):
            if level==1 and name=='native6_orphan_return':
                return SimpleNamespace(verified_return=passive['verified_return'])
            return original_import(name,globals,locals,fromlist,level)
        values.update(context=context,__builtins__=dict(vars(builtins),__import__=review_import))
        verify=FunctionType(live.verified_return.__code__,values,live.verified_return.__name__)
        return verify(backend,row,binding,receipt)
    except (OSError,ValueError,KeyError,TypeError,OverflowError,ContractError):return False
