"""Offline availability audit. Outputs research only, never a runtime allowlist."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as E

ROOT=Path(__file__).resolve().parents[2]
SDK=Path('E:/RA3Modding/SDK')
NS='{uri:ea.com:eala:asset}'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_role(template,type_hash,kinds,already_audited):
    """Proposed narrow functional classification, not applied to the collector."""
    if already_audited is True and template=='SovietRefinery' and type_hash=='0xc45aaeab' and {'REFINERY','SUPPLY_GATHERING_CENTER'}.issubset(kinds):return 'economy'
    return None


def inspect_sources(name,auditor):
    paths={
        'SovietRefinery':SDK/'Mods/TriadFront/data/objects/SovietRefinery.xml',
        'SovietMiner':SDK/'SAGEXML/Soviet/Units/SovietMiner.xml',
    }
    chain=[];key=name;seen=set();kinds=set()
    while key:
        if key in seen:raise ValueError('Source inheritance cycle')
        seen.add(key);path=paths.get(key,SDK/'SAGEXML/BaseObjects'/(key+'.xml'))
        objects=[node for node in E.parse(path).getroot() if node.tag==NS+'GameObject' and node.get('id')==key]
        if len(objects)!=1:raise ValueError('Source identity ambiguous')
        node=objects[0];chain.append((path,node));key=node.get('inheritFrom') or node.get('inheritsFrom')
    for _,node in reversed(chain):
        tokens=node.get('KindOf','').split()
        if tokens and not any(token.startswith(('+','-')) for token in tokens):kinds=set(tokens)
        else:
            for token in tokens:
                if token.startswith('-'):kinds.discard(token[1:])
                else:kinds.add(token.lstrip('+'))
    evidence=[]
    for path,node in chain:
        for item in node.iter():
            tag=item.tag.split('}')[-1]
            if tag in {'OreMinerBehavior','SpawnBehavior','SpawnTemplate','SkirmishAIInformation','AIUpdate'}:evidence.append(dict(tag=tag,attributes=dict(item.attrib),text=(item.text or '').strip(),source=str(path)))
    return dict(source_chain=[dict(path=str(path),sha256=sha(path),audit_risks=auditor.audit_node(node)) for path,node in chain],effective_kinds=sorted(kinds),functional_evidence=evidence,source_risk_rules_only=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path(__file__).with_name('economy-evidence.json'));args=parser.parse_args()
    sys.path.insert(0,'E:/RA3Modding/Analysis/Remix037');from manifest import parse
    spec=importlib.util.spec_from_file_location('offline_economy_auditor',ROOT/'visibility/audit_templates.py');auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    safety_path=ROOT/'visibility/template-safety-2d7873e1.json';safety=json.loads(safety_path.read_text(encoding='utf-8-sig'))
    manifest=ROOT/'native-ai/staging/compiled-commanders-20261024-182027-17286524/package/data/mod.manifest'
    if sha(manifest)!=safety['compiled_manifest_sha256']:raise ValueError('Frozen manifest digest mismatch')
    names={row['name'] for row in parse(manifest)};templates=safety['templates'];records={}
    for name in ('SovietRefinery','SovietMiner'):
        allowed=[(key,value) for key,value in templates.items() if value['template']==name]
        record=inspect_sources(name,auditor)
        record.update(compiled_manifest_present='GameObject:'+name in names,frozen_allowed=bool(allowed),frozen_role=allowed[0][1]['role'] if allowed else None,frozen_rejection=safety.get('rejected',{}).get(name),runtime_exposure_authorized=False)
        if allowed:
            key,safe=allowed[0];record.update(type_hash=key,physical_role='structure',proposed_functional_role=candidate_role(name,key,set(record['effective_kinds']),safe.get('source_audited_no_intrinsic_stealth')))
        records[name]=record
    # Regression guards for the proposal: no blanket structure promotion, no
    # unaudited miner exposure, no same-name/different-hash substitution.
    tags={'REFINERY','SUPPLY_GATHERING_CENTER','STRUCTURE'}
    assert candidate_role('SovietRefinery','0xc45aaeab',tags,True)=='economy'
    for row in [('SovietBarracks','0xc45aaeab',tags,True),('SovietRefinery','0xdeadbeef',tags,True),('SovietRefinery','0xc45aaeab',{'STRUCTURE'},True),('SovietRefinery','0xc45aaeab',tags,False),('SovietMiner','0xc45aaeab',{'HARVESTER'},False)]:assert candidate_role(*row) is None
    economy=[value['template'] for value in templates.values() if value['role']=='economy']
    result=dict(schema_version=1,mode='offline_research_not_capability',commands_issued=0,gui_or_api_used=False,safety_sha256=sha(safety_path),package_sha256=safety['package_sha256'],compiled_manifest=str(manifest),compiled_manifest_sha256=sha(manifest),frozen_allowed_count=len(templates),frozen_economy_templates=economy,economy_contacts_representable=bool(economy),purpose_execution_requires_separate_evidence=True,templates=records,rebuild_required=['safety/catalog hash','classification implementation hash','build capability proof','current session proof'],visibility_algorithm_change_required=False)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(output=str(args.output),allowed=result['frozen_allowed_count'],economy_contacts_possible=bool(result['frozen_economy_templates']),runtime_allowlist_changed=False)))


if __name__=='__main__':main()
