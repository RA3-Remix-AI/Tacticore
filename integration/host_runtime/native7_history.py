"""Passive review of recognized Native7 releases across candidate upgrades."""
from pathlib import Path
from types import FunctionType

from .contracts import ContractError
from .native7_runtime_contract import read,sha
from .native7_qualification import trusted_pin

PRIOR={
    'cecbb725b3918aef2068d181e103f6a2ce78ccc42fca55856ed30c870a260dc4':
    '1ada857a32bee6bc60971c0fcdf3cc6c68562b06e27280d963e41af597ee84ca',
    '2f8a30bb23a789be69d7630bf87afdd31a42cd47d9be764b4df4c2da162a61dd':
    '66108fcd57dc0707701be41ab32ee9b13d721c313ef71fe56563e484a6b9c8fa',
    '394a4281dd3ef72b281ddd73be96c9773c3729ae4d9268a0ca405fb3114e3366':
    'd7dccd39a4747c8cb0e0a22673c8bf66cf7f3b41a161f2bf53b9d2ed4179be52',
    '18a3a42a74249e06d7a044bf91a9b7c90ae0d0f859bb6cfbc835ae5b94dac450':
    'add5e04cdb1b090243d8af6da9c7681b9c11686fdb950089bfa434d437b542da',
    '6cf7f652140bd81ca03ce292de65699bc712aa0c5714f9bcb4f03bc6b3e90406':
    '6a77b0d9e290f36b47a91234b38240a8a8bed3f5e7795a7fef399d3b4bb2218c',
    'ca49970478efd56051f2e3e5eec2b5df6adb23f5a92667ed84ad878d6d55c213':
    '357fa3ff9d6b0db2c8764e1d75c65bf8a40e69e442cc0c598ef6dd50ea71421a',
    '5d4f5696e87c4cf0d30f8e4368326320e7a8e59986c8cd385ca595d60cbb6fe7':
    '7300d10be130030995045db48a1f72a1685e5e4606adf724a25351ff9a23114b',
}
PRIOR_PACKAGES={
    'cecbb725b3918aef2068d181e103f6a2ce78ccc42fca55856ed30c870a260dc4':
    '4128e1a598e12895fd84db3ce52122c696d9905e57e25497bd949a408466a62c',
    '2f8a30bb23a789be69d7630bf87afdd31a42cd47d9be764b4df4c2da162a61dd':
    '0c1cf8c501aef75b60d5e6b6419c70c659dd8042474eae2df09f57861a5d75e8',
}


def context(row,session,binding):
    from . import native7_lifecycle as live
    value=read(Path(row['output_path'])/'native7-context.json')
    pin=value['runtime_manifest_sha256']
    if pin==trusted_pin():return live.context(row,session,binding)
    if pin not in PRIOR:raise ContractError('native7_history_version_unrecognized')
    # Execute installed verifier bytecode. Historical paths are comparison data.
    historical_package=PRIOR_PACKAGES.get(pin,
        '4811342ec70c153ee8b2328797dc321e62b2770b53d5e6270b7f396c59dff29c')
    if binding.mod_sha256!=historical_package:raise ContractError('native7_history_package_changed')
    values=dict(vars(live),trusted_pin=lambda:pin,runtime_root=lambda:Path(value['runtime_root']),
                PACKAGE_SHA=historical_package)
    verify=FunctionType(live.context.__code__,values,live.context.__name__)
    result=verify(row,session,binding)
    _,manifest,inventory=result
    if manifest['source_closure_sha256']!=PRIOR[pin]:
        raise ContractError('native7_history_version_unrecognized')
    for name in ('native7_lifecycle.py','native7_release.py','native7_no_attachment.py',
                 'native7_journal.py','strategic_unified_unknown_return_v5.py'):
        expected=inventory['files'].get('app/integration/host_runtime/'+name)
        current=sha(Path(__file__).with_name(name))
        compatible=(name=='native7_release.py' and expected==sha(Path(__file__).with_name('native7_release_1v2.py')))
        if current!=expected and not compatible:
            raise ContractError('native7_history_verifier_changed')
    return result


def verified_return(backend,row,binding,receipt):
    from . import native7_lifecycle as live
    values=dict(vars(live),context=context)
    verify=FunctionType(live.verified_return.__code__,values,live.verified_return.__name__)
    return verify(backend,row,binding,receipt)
