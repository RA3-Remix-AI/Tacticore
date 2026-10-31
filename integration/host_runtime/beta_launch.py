"""Read-only qualification of the ordinary client's fixed game entry point."""
from pathlib import Path
from .contracts import ContractError
from .native6_paths import plain_local
from .native6_runtime_contract import sha

ENTRY='RA3_chinese_t_1.12.SkuDef'
# Exact base configuration chain used by the original qualified 1.12 games.
# Neither arbitrary SKU commands nor WebView/environment launch arguments run.
BASE_PINS={
 'RA3_chinese_t_1.0.SkuDef':'2ead0a0797731516f2b867001a27163a548576eeb0bb2c622d347ff93950e33c',
 'RA3_chinese_t_1.1.SkuDef':'9f4e154ed7be8719636d48836d5404041fe3af23da3efb7615233871ac9edc8b',
 'RA3_chinese_t_1.2.SkuDef':'c0b63978469c14eb9257d076a248a42fede52f6c8e58bd0dbf698ad28575da0e',
 'RA3_chinese_t_1.3.SkuDef':'94bc7397433f796ac2ab12725bda01a566b1cdd2a5ededd21c4dadd347f09dd9',
 'RA3_chinese_t_1.4.SkuDef':'22ed4e33437c185efaabcdb43c95a47a19d8c41209c9447c8c16f0d3f0f70920',
 'RA3_chinese_t_1.5.SkuDef':'a561218777b8093918cc4c286bf9335686b23f9b5c4ae741777ce3a2d3b7301b',
 'RA3_chinese_t_1.6.SkuDef':'75f018370a6829233f6891df81b2f0c1394ca05f2cedcf0b91c113b4a615876c',
 'RA3_chinese_t_1.7.SkuDef':'52115b1e255ddb88e931f9c42b43e6cd86336d0e397557c40769bf817fc05dea',
 'RA3_chinese_t_1.8.SkuDef':'814a1bfbe088cbc3a55ebaa87c3d7ac37cf8c0f654812228eec232cbc2163749',
 'RA3_chinese_t_1.9.SkuDef':'26beb06ea5ed0ab59088246929ab0903924b8f5fd11b99e09695b419888a1d1b',
 'RA3_chinese_t_1.10.SkuDef':'6c3038e9640c58768496096e1f8d65a7885f57739fcd3c201aeee5eb464985d0',
 'RA3_chinese_t_1.11.SkuDef':'34b461ded8e7e494b29ab01072230392500009b37f60d8c36dbd2a450ec85194',
 'RA3_chinese_t_1.12.SkuDef':'309cb47b57456c88bd7bc924c8e77f68b3b949171b0598c04c7ea1e4b9839250',
}

def base_config(game):
    root=Path(game).parent.parent
    try:
        for name,pin in BASE_PINS.items():
            path=plain_local(root/name)
            if sha(path)!=pin:raise ValueError('base_changed')
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if not line.strip().lower().startswith('add-big '):continue
                relative=Path(line.strip().split(None,1)[1].replace('\\','/'))
                if relative.is_absolute() or '..' in relative.parts or ':' in str(relative):raise ValueError('base_path')
                plain_local(root/relative)
        return plain_local(root/ENTRY)
    except (OSError,ValueError,IndexError):raise ContractError('beta_base_game_config_unsupported') from None

def record(game,mod_config,pin,policy_id):
    base=base_config(game)
    return dict(schema_version=2,kind='qualified_game_image_launch',runtime_manifest_sha256=pin,policy_id=policy_id,
        game=str(game),game_sha256=sha(game),mod_config=str(mod_config),mod_config_sha256=sha(mod_config),
        base_config=str(base),base_config_sha256=sha(base))

def arguments(game,mod_config,base):
    return [str(game),'-ui','-win','-modConfig',str(mod_config),'-config',str(base)]
