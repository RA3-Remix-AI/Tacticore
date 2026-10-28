"""Compile AI-only macro policy consumers, preserving original unit-operation assets.

This expands the isolated probe, not the installed product. Every consumer is
field-unqualified until its native adoption and effects are independently seen.
"""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as E

from stage_macro_probe import generate,compile_probe,digest
from stage_commanders import SDK,q,safe_output,manifest_rows,sage_hash


def generate_policy(commander_id,slot,baselines):
    xml,report=generate(commander_id,slot,baselines)
    root=E.fromstring(xml);personality=root.find(q('AIPersonalityDefinition'))
    prefix=report['personality'].removesuffix('_Soviet')
    keys={(r['type_id'],r['instance_id']) for r in baselines}
    keys.update((int(r['type_id'],0),int(r['instance_id'],0)) for r in report['assets'])
    consumers=[]

    def asset(kind,suffix,domain):
        name=prefix+'_'+suffix;key=sage_hash(kind),sage_hash(name.lower())
        if key in keys:raise ValueError('macro_policy_asset_collision')
        keys.add(key);report['assets'].append(dict(name=kind+':'+name,type_id=hex(key[0]),instance_id=hex(key[1])))
        flag='/'+prefix+'_'+suffix.lower();report['flags'][suffix.lower()]=flag
        node=E.Element(q(kind),id=name);root.insert(list(root).index(personality),node)
        tag={'construction':'BuildState','production':'BuildState','budget':'BudgetState','strategic':'StrategicState'}[domain]
        E.SubElement(personality,q(tag),id=name,State=name)
        heuristic=E.SubElement(node,q('Heuristic'))
        E.SubElement(heuristic,q('ScriptedFlagHeuristic'),FlagName=flag)
        E.SubElement(heuristic,q('OpeningMoveHeuristic'),Complete='true')
        E.SubElement(heuristic,q('ConstantHeuristic'),Weight='100')
        consumers.append(dict(action=suffix.lower(),flag=flag,state=kind+':'+name,domain=domain,
            field_verified=False,capability_granted=False))
        return node,heuristic

    def exists(heuristic,thing,present):
        condition=E.SubElement(heuristic,q('ObjectOfTypeExistsHeuristic'),PassIfExists=str(present).lower())
        filt=E.SubElement(condition,q('ObjectFilter'),Relationship='SAME_PLAYER',Rule='ANY')
        E.SubElement(filt,q('IncludeThing')).text=thing

    airport=root.find(q('AIBuildStateDefinition'));heuristic=airport.find(q('Heuristic'))
    E.SubElement(heuristic,q('ConstantHeuristic'),Weight='100')
    exists(heuristic,'SovietPowerPlantAdvanced',True)
    consumers.append(dict(action='build_airfield',flag=report['flags']['build_airfield'],state=report['assets'][0]['name'],
        domain='construction',required_own_template='SovietPowerPlantAdvanced',field_verified=False,capability_granted=False))
    consumers.append(dict(action='scout',flag=report['flags']['scout'],state=report['assets'][1]['name'],
        domain='strategic',target_policy='original_native_scout_target_selection',field_verified=False,capability_granted=False))
    for suffix,thing,prerequisite in [('BuildReactor','SovietPowerPlantAdvanced',None),
            ('BuildTech','SovietTechStructure','SovietPowerPlantAdvanced')]:
        node,heuristic=asset('AIBuildStateDefinition',suffix,'construction')
        exists(heuristic,thing,False)
        if prerequisite:exists(heuristic,prerequisite,True)
        E.SubElement(heuristic,q('IsBuildingHeuristic'),KindOf='STRUCTURE',PassIfBuilding='false')
        E.SubElement(node,q('BuildEntry'),Build=thing,Heuristic='CONSTANT',Score='100')
    node,heuristic=asset('AIBuildStateDefinition','EconomyRefinery','construction')
    E.SubElement(heuristic,q('OpenNodeHeuristic'),Exists='true')
    E.SubElement(node,q('BuildEntry'),Build='SovietRefinery',Heuristic='REFINERY')
    for suffix,thing in [('ProduceConscript','SovietAntiInfantryInfantry'),('ProduceFlak','SovietAntiVehicleInfantry'),
            ('ProduceTank','SovietAntiVehicleVehicleTech1')]:
        node,heuristic=asset('AIBuildStateDefinition',suffix,'production')
        E.SubElement(node,q('BuildEntry'),Build=thing,Heuristic='CONSTANT',Score='100')
        consumers[-1].update(native_factory_and_payment_required=True,
            desired_count_requires_host_observation=True,bounded_expiry_required=True)
    budgets={
        'BudgetEconomy':dict(INVESTMENT=40,SPECIAL_OPERATIONS=0,PRODUCTION=25,DEFENSE=10,TECHNOLOGY=15,SLUSH_FUND=10),
        'BudgetArmy':dict(INVESTMENT=10,SPECIAL_OPERATIONS=0,PRODUCTION=70,DEFENSE=10,TECHNOLOGY=5,SLUSH_FUND=5),
        'BudgetTech':dict(INVESTMENT=15,SPECIAL_OPERATIONS=0,PRODUCTION=25,DEFENSE=10,TECHNOLOGY=40,SLUSH_FUND=10)}
    for suffix,shares in budgets.items():
        if sum(shares.values())!=100:raise ValueError('macro_native_budget_total')
        node,_=asset('AIBudgetStateDefinition',suffix,'budget');budget=E.SubElement(node,q('Budget'))
        for account,percent in shares.items():E.SubElement(budget,q('AccountShare'),Account=account,Percent=str(percent)+'%')
        consumers[-1].update(account_shares=shares,exclusive_group='budget_policy')
    source=SDK/'SAGEXML/SkirmishAI/States/BalancedStates.xml';tree=E.parse(source).getroot()
    for suffix,stock in [('DeployAttack','GrowingAttacks_Land_MEDIUM'),('DeployDefense','BalancedDefense')]:
        original=tree.find(q('AIStrategicStateDefinition')+"[@id='"+stock+"']")
        if original is None:raise ValueError('macro_stock_deployment_state_missing')
        node,heuristic=asset('AIStrategicStateDefinition',suffix,'strategic')
        for key,value in original.attrib.items():
            if key!='id':node.set(key,value)
        node.set('MaxTargets','1');node.set('MaxRunningCopies','1')
        for child in original:
            if child.tag!=q('Heuristic'):node.append(copy.deepcopy(child))
        for tactic in node.findall(q('Tactic')):
            tactic.set('EndIfStateTurnsOff','true');tactic.set('EndBehavior','DISBAND')
        consumers[-1].update(stock_source_state=stock,target_policy='original_native_state_target_selection',
            arbitrary_region_selection_supported=False,exclusive_group='deployment_policy')
    E.indent(root,space='  ')
    report.update(variant='expanded_macro_policy_v1',consumers=consumers,
        policy_source=str(source),policy_source_sha256=digest(source),
        product_capability_granted=False,
        policy_limits=['No arbitrary unit commands or native target pointers.',
            'Counts, budgets, technology and expiry must be enforced by the future host.',
            'Native default state behavior remains; macro preference is not exclusive ownership.',
            'Every new consumer requires field qualification; compilation grants none.'])
    return E.tostring(root,encoding='utf-8',xml_declaration=True),report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--commander-id',required=True)
    p.add_argument('--slot',required=True,type=int);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--baseline',type=Path,action='append',default=[]);p.add_argument('--compile-base-big',type=Path)
    args=p.parse_args();out=safe_output(args.output)
    paths=[SDK/'BuiltMods/sagexml'/(name+'.manifest') for name in ['static','global','audio']]+args.baseline
    rows=[r for path in paths for r in manifest_rows(path)]
    xml,report=generate_policy(args.commander_id,args.slot,rows)
    report.update(compiled=False,output=str(out),source_sha256=digest(__file__),
        collision_baselines=[dict(path=str(path),sha256=digest(path)) for path in paths])
    out.mkdir(parents=True);(out/'MacroProbe.xml').write_bytes(xml);report['macro_xml_sha256']=digest(out/'MacroProbe.xml')
    (out/'generation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.compile_base_big:compile_probe(out,report,args.compile_base_big)
    (out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),compiled=report['compiled'],assets=len(report['assets']),
        consumers=len(report['consumers']),field_verified=False,capability_granted=False)))


if __name__=='__main__':main()
