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
    '09e0749b7373ebba6e26f668d3bd48979a07e105475d778eaf876b47b965683e':
    '1f8b9a821d27f935d698e9e6a9203ec226114fde910073f10c574405c4cdc5d6',
    'c2dd57b66d7b7c8098e720d6eedee6fb0428a8b7d03d39fddff870f15189182c':
    '690204d4325faef14c5940406666c14303c314b3680530404b60c562f839e5b1',
    'ab9296652b97fe6839242dbc1a4f3f49f2a85da66dbef9cef2ea846a9104970f':
    '5156551c16b22ff7020f49b3680b704743ff28fea7ac4daec45aed49d0416209',
    '679c17e1954f3ffca0ef08150569a66369197223fee5f4a49e13ab989c03b1ea':
    '107535fd5992caf266dc0455ac80130af8a11d1996ea8a788489f45154f344e2',
    'fe028ba2b3eaf3a0004df7fec52efd4b614fc713da03341d5a8f3461a64d25c4':
    '6ca6d533509a163fc902610ad7e2aa5a323e223a7dd5e32b7e52b7bcdbf788ba',
    '7a855ec67ca241c72e79ec1b640e6a6219d3fa1d986d98f8cf43790717ff7b08':
    'dde92bb9a8fc9633a04255f6c0b431ff906d3490ae4f09684965fca01707124a',
    'b7a4bfca0a341c1ee72d9d4457d3036e2355278dd1a28eac06f4055641adf8f7':
    'deaf9cbf1b4bafeac87a012920a38168b4d0b3da3fc2d754affd457c5c55311a',
    'b9a74c41e1fa48b05e4c55beb1b26868031702e1b6dfe99719fb5e5539aed9b0':
    '2ac3d42b0041ebe20931da2b29a1577fd735d17274f62037ab3f7e86777d3053',
    '2f0e8ca3758fca080dba326d62fcf80eba450ca8ccec398cef14f4007f851e15':
    '687f9e6abdcc037ec2fbe9c360bbff644f82f88d619cb0f048115f3d65f3fc9d',
    'a1322dd30c6ff63c8d70c644c9d3796f87df53a30c3f6bb9ac7f67004120a539':
    'f25f9a8273bd7bf957e2e14648e2c0328d877c71bdc40aa85bf53b99075d222b',
    '171a0f5b21bd97028331ebade2b454c499919f3c2695be48d33ab60df9b1ca4a':
    '060c8e7345366e2db9adb452646755533167a72d12bb26a2dcb715fc331efe09',
    '71cec70c2e9c96afc3e50c8457e73bf5a926e5d3775a13dc1034362ab78e5044':
    'f00bd19eeb8c622217e90014ea69470156d2a41794df1e3e5cb3b118d7ee86f4',
    '6a30677351cf9b1422202e11c90632f8301dc65769c3697b8d1e62c26adbca6e':
    '37f0f0080091c2be88f62f8582a140a9240ac97d96e27af9d8bbcc466437ef83',
    'f6b44593f084246c73cc055dcd8878de0efb8b36cfa35e9407be5d0f87c304b4':
    '5d02ee26bbf53a248dccd994c223937a80a2e9f3c173274d5f9cb58da00c0b67',
    'b0b522d907281acf6277308ac1564bf290422d447c4ca2e46d73a0283a778d5d':
    '5f9b1e90380d2621158660524bdda0f9f301928c0521f58e32aa4398189c2bdb',
    'e1ba4370aba50421f88ebc8f79e5e22c24db91d3a276cd1b699a2b646bfdba29':
    'e66d9f1130d0f3f58a9a787bed4f4d918f1b8994a7932a7a598dcd44a829bfec',
    '56331fd3116baa27141c190bcb3885a9b6f75d903103aabc55ebbb8bc8aa3b8a':
    '00a76e5b7f017c2bc0669811a820dac2af9d1b121d47914ea0f521ad65818f82',
    '02ee6cbfb7c29f37ceced12d21ea87919f15297aca48496f69e2557c32f23b7a':
    '0402854e31c89cb8fa2373cb254b51a6e985ee1d92ddae02836bde9d9716aed6',
    'b008a6e63642e32d2a69d4a4d2935ac794811c2b7a7958040ef567fd12aa83db':
    'a1686fbce043b50f60927aa350aceeb0d757e8faea2b99898ff7cf8c524a8c90',
    '6a322c8bc4a217e91b85b13ab177344dd0c751a565acd7ac1483276a3f492865':
    '7bcfa7d9396537ad8dd89957ca748aa4e673ab12ee44ff0691c0af5bd787663b',
    '233163615096c6151f9f7ee6338d2abbd91ef5f4d5f8f8d507c60b8676e726de':
    '32948ecf20341ed7e8d9069e188e5f9e2226c531dc5f9ffdf7c366903b546470',
    '669e3a75f03a2d28762e4a768a066d0ec75438ba0da8a5b176fccb7c549352d8':
    '9122d6142eb3a7e60e38b9fe0eae32e4b6aa792d2b844ef876bd36254596ed4b',
    '771f08fe3ddc1df9b2a794cc099124c96e164ba7a8c763c3088d3a9698affdd2':
    'c82dd181e5f9daa6985a342793e40c102726101de6d9f64ab9db9a9dc5728d87',
    '926f8de946d383e9a8c8c2aa9549bd1a9d071dc7277556654bafad97d482d94d':
    '65f73cd1c59b39a01f77865e78d6dfbed45ba7666e18bde73a11fb6d0ad3b4d0',
    '08e20663e21e35f78b1bec3418063932980549dbfe22907678206e0f7127e3f1':
    '0e305f5b9c6ba82bea76abd72fa5470ba51a9d3c11ad9135ac430fde52357900',
    'e328808cdb23001170e6daa426ad1bd162869f454f0f7a4c4f4778d4261c2373':
    '7298450060f9886ced8890d725e116601a3ef10bf5dd1066784d4efa3ea0c7f9',
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
    # context verifies this build-manifest against the recognized historical
    # inventory pin before returning any passive proof.
    package=read(Path(row['output_path'])/'source/6-build-manifest.json')['package_sha256']
    values=dict(vars(live),trusted_pin=lambda:pin,runtime_root=lambda:Path(value['runtime_root']),PACKAGE_SHA=package)
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
