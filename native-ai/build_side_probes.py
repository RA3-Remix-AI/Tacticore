"""Build isolated, UNDEPLOYED Side-binding A/B packages with the stock SDK.

No game processes, injection, installation files or TriadFront sources touched.
The output directory is new on each run so stale metadata cannot contaminate A.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from lxml import etree as E

ROOT = Path(__file__).resolve().parent
SDK = Path(r'E:\RA3Modding\SDK')
MOD = 'CommanderSideProbe'
NS = 'uri:ea.com:eala:asset'
def q(name): return '{' + NS + '}' + name
sys.path.insert(0, str(ROOT.parent))
from frontend_metadata import build_subset
from validate_side_imports import audit


def sources():
    out = SDK / 'Mods' / MOD / 'data'
    out.mkdir(parents=True, exist_ok=True)
    root = E.Element(q('AssetDeclaration'), nsmap={None: NS})
    E.SubElement(root, q('Tags'))
    inc = E.SubElement(root, q('Includes'))
    for name in ['static.xml', 'global.xml', 'audio.xml']:
        E.SubElement(inc, q('Include'), type='reference', source='DATA:' + name)
    for side in ['Allied', 'Soviet', 'Japan']:
        E.SubElement(inc, q('Include'), type='instance',
                     source='DATA:SkirmishAI/Personalities/' + side + 'Balanced.xml')
        E.SubElement(root, q('AIPersonalityDefinition'),
                     id='4TFLLM' + side, PersonalityType='4TFLLM' + side,
                     inheritFrom='1' + side + 'Balanced',
                     SkirmishPersonality='true', PersonalityUIName='Personality:TFLLMSideProbe')
        # Inherit exactly one Side. Adding Side here appends, it does not replace.
    vanilla = E.parse(str(SDK / 'SAGEXML/SkirmishAI/Personalities/RandomPersonalities.xml'))
    random = copy.deepcopy(vanilla.getroot().find(q('AIPersonalityDefinition')))
    random.set('id', '4TFLLMRandom')
    random.set('PersonalityType', '4TFLLMRandom')
    random.set('PersonalityUIName', 'Personality:TFLLMSideProbe')
    for entry in random.findall(q('PersonalityMap')):
        side = entry.get('Side')
        entry.set('Personality', '4TFLLM' + ('Allied' if side == 'Allies' else side))
    root.append(random)
    E.ElementTree(root).write(str(out / 'Mod.xml'), encoding='utf-8',
                              xml_declaration=True, pretty_print=True)
    (out / 'mod.str').write_text('Personality:TFLLMSideProbe\n"SIDE BINDING PROBE"\nEND\n', encoding='ascii')
    sys.path.insert(0, str(ROOT.parent.parent / 'TriadFront/tools'))
    from localization import load_vanilla, write_csf
    strings, _ = load_vanilla()
    strings['personality:tfllmsideprobe'] = 'SIDE BINDING PROBE'
    write_csf(strings, out / 'gamestrings.csf')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    output = a.output or ROOT / 'side-probes' / time.strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    source = sources()
    with (output / 'sdk-build.log').open('w', encoding='utf-8') as log:
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(SDK.parent / 'Build-Mod.ps1'), '-ModName', MOD, '-NoDeploy'],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    compiled = SDK / 'BuiltMods/mods' / MOD / 'data'
    report = dict(source=str(source), output=str(output.resolve()),
                  deployed=False, runtime_verified=False, variants=[])
    # Every variant has identical normal streams and strings. The only variable
    # is an additional copy in one, and only one, metadata location.
    specs = [
        ('A_normal_only', None, False),
        ('B_root_metadata_three', 'AdditionalMaps', False),
        ('C_data_metadata_three', 'data/AdditionalMaps', False),
        ('D_root_metadata_four', 'AdditionalMaps', True),
    ]
    for label, metadata_path, include_random in specs:
        variant = output / label
        package = variant / 'package'
        (package / 'data').mkdir(parents=True)
        for pattern in ['mod.*', 'mod_M.*', 'mod_L.*']:
            for file in compiled.glob(pattern):
                if file.is_file():
                    shutil.copy2(file, package / 'data' / file.name)
        shutil.copy2(source / 'gamestrings.csf', package / 'data/gamestrings.csf')
        item = dict(variant=label, metadata_path=metadata_path,
                    normal_audit=audit(package / 'data/mod.manifest', '4TFLLM'))
        if metadata_path:
            dest = package / metadata_path / 'mapmetadata_commander.manifest'
            item['metadata'] = build_subset(package / 'data/mod.manifest', dest,
                                             include_random=include_random)
            item['metadata_audit'] = audit(dest, '4TFLLM')
        for row in item['normal_audit']['records']:
            if row['side_count'] != 1 or not all(s['valid'] for s in row['sides']):
                raise ValueError('Probe Side must be a single valid import: ' + row['name'])
        big = variant / (label + '.big')
        with (variant / 'makebig.log').open('w', encoding='utf-8') as log:
            subprocess.run([str(SDK / 'Tools/MakeBig.exe'), '-f', str(package),
                            '-x:*.asset', '-o:' + str(big)],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        item['big'] = str(big.resolve())
        item['big_sha256'] = hashlib.sha256(big.read_bytes()).hexdigest()
        (variant / (label + '_1.0.skudef')).write_text(
            'mod-game 1.12\nadd-big ' + big.name + '\n', encoding='ascii')
        item['physical_metadata_required'] = 'Unconfirmed: do not add extra physical copies during the first path-isolation runs.'
        report['variants'].append(item)
    (output / 'side-probes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output.resolve())


if __name__ == '__main__':
    main()
