"""Generate additive selectable personalities; original AI remains fallback."""
from pathlib import Path
from lxml import etree as E
import json
import sys
NS='uri:ea.com:eala:asset'
def q(x): return '{'+NS+'}'+x
SDK=Path(r'E:\RA3Modding\SDK')
ROOT=Path(__file__).resolve().parent

def create(out):
    out.mkdir(parents=True,exist_ok=True)
    root=E.Element(q('AssetDeclaration'),nsmap={None:NS})
    E.SubElement(root,q('Tags'));inc=E.SubElement(root,q('Includes'))
    for side in ['Allied','Soviet','Japan']:
        E.SubElement(inc,q('Include'),type='instance',source='DATA:SkirmishAI/Personalities/'+side+'Balanced.xml')
        n=E.SubElement(root,q('AIPersonalityDefinition'),id='4TFLLM'+side,PersonalityType='4TFLLM'+side,
                       inheritFrom='1'+side+'Balanced',SkirmishPersonality='true',PersonalityUIName='Personality:TFLLM')
        # Side is inherited as an array. An explicit Side here appends a second
        # entry; it does not replace or repair an unresolved inherited import.
    # Generic random-side choice follows the vanilla RandomPersonalities pattern.
    vanilla=E.parse(str(SDK/'SAGEXML/SkirmishAI/Personalities/RandomPersonalities.xml'))
    n=vanilla.getroot().find(q('AIPersonalityDefinition'))
    n.set('id','4TFLLMRandom');n.set('PersonalityType','4TFLLMRandom');n.set('PersonalityUIName','Personality:TFLLM')
    for item in n.findall(q('PersonalityMap')):
        side=item.get('Side');item.set('Personality','4TFLLM'+('Allied' if side=='Allies' else side))
    root.append(n)
    E.ElementTree(root).write(str(out/'AICommander.xml'),encoding='utf-8',xml_declaration=True,pretty_print=True)
    return {'Personality:TFLLM':'AI 指挥官'}

def lab():
    out=SDK/'Mods/CommanderLab/data';strings=create(out)
    root=E.Element(q('AssetDeclaration'),nsmap={None:NS});E.SubElement(root,q('Tags'));inc=E.SubElement(root,q('Includes'))
    for name in ['static.xml','global.xml','audio.xml']:
        E.SubElement(inc,q('Include'),type='reference',source='DATA:'+name)
    E.SubElement(inc,q('Include'),type='all',source='DATA:CommanderLab/data/AICommander.xml')
    E.ElementTree(root).write(str(out/'Mod.xml'),encoding='utf-8',xml_declaration=True,pretty_print=True)
    sys.path.insert(0,str(ROOT.parent/'TriadFront/tools'))
    from localization import load_vanilla,write_csf
    base,_=load_vanilla();base.update({k.lower():v for k,v in strings.items()})
    # Additive lab assets only: menu discovery and Side binding remain unverified.
    # No stock commander slots are replaced, and registration is not LLM control.
    write_csf(base,out/'gamestrings.csf')
    (out/'mod.str').write_text('Personality:TFLLM\n"AI COMMANDER"\nEND\n',encoding='ascii')
    menu=SDK/'Mods/CommanderMenu/data';menu.mkdir(parents=True,exist_ok=True)
    r=E.Element(q('AssetDeclaration'),nsmap={None:NS});E.SubElement(r,q('Tags'));inc=E.SubElement(r,q('Includes'))
    for name in ['static.xml','global.xml','audio.xml']:E.SubElement(inc,q('Include'),type='reference',source='DATA:'+name)
    for side,template,portrait in [('Allied','Allies','Warren'),('Soviet','Soviet','Oleg'),('Japan','Japan','Shinzo')]:
        n=E.SubElement(r,q('AIPersonalityDefinition'),id='4TFLLM'+side,PersonalityType='4TFLLM'+side,SkirmishPersonality='true',PersonalityUIName='Personality:TFLLM',CommanderPortrait=portrait)
        E.SubElement(n,q('Side')).text=template;E.SubElement(n,q('CountAsStructureForBuildPurposesFilter'))
    E.ElementTree(r).write(str(menu/'Mod.xml'),encoding='utf-8',xml_declaration=True,pretty_print=True)
    (ROOT/'reports/commander-personalities.json').write_text(json.dumps({'ids':['4TFLLMAllied','4TFLLMSoviet','4TFLLMJapan','4TFLLMRandom'],'display':'AI 指挥官','fallback':'vanilla balanced personalities','side_binding_verified':False,'runtime_model_control':False},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':lab()
