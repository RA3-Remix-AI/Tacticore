"""Isolated high-level group-role candidates using unchanged native micro assets.

Three unused/unqualified building gates become research group goals. Existing
qualified consumers are preserved; compilation grants no product capability.
"""
import argparse
import copy
import json
import xml.etree.ElementTree as E
from pathlib import Path

from stage_macro_base_defense import generate_area_defense
from stage_macro_probe import compile_probe,digest
from stage_commanders import SDK,q,safe_output,manifest_rows,sage_hash

REPLACEMENTS=(('build_airfield','regroup','RegroupHome'),
    ('buildtech','withdraw','WithdrawHome'),('economyrefinery','reinforce','ReinforceBase'))


def generate_group_roles(commander,slot,baselines,map_raw):
    xml,report=generate_area_defense(commander,slot,baselines,map_raw);root=E.fromstring(xml)
    personality=root.find(q('AIPersonalityDefinition'));prefix=report['personality'].removesuffix('_Soviet')
    attack=next(s for s in root.findall(q('AIStrategicStateDefinition')) if s.get('id').endswith('_DeployAttack'))
    defense=next(s for s in root.findall(q('AIStrategicStateDefinition')) if s.get('id').endswith('_DeployDefense'))
    home=next(p for p in report['regional_waypoints'] if p['name']=='Player_2_Start')
    target_name=prefix+'_Waypoint_'+home['name'];roles=[]
    reactive_path=SDK/'SAGEXML/SkirmishAI/States/AlliedPCGDemoStates.xml'
    reactive=E.parse(reactive_path).getroot().find(q('AIStrategicStateDefinition')+"[@id='PCGDemo_ReactiveDefense']").find(q('Tactic'))
    if reactive.get('Tactic')!='ReactiveDefense' or reactive.find(q('TeamTemplate')).get('MicroManager')!='ReactiveDefenseMicroManager':
        raise ValueError('native_reactive_defense_source_changed')
    for old_action,action,suffix in REPLACEMENTS:
        old=next(c for c in report['consumers'] if c['action']==old_action)
        if old['field_verified'] or old['capability_granted']:raise ValueError('cannot_replace_qualified_consumer')
        old_kind,old_name=old['state'].split(':',1);node=root.find(q(old_kind)+"[@id='"+old_name+"']")
        if old_kind!='AIBuildStateDefinition' or node is None:raise ValueError('unqualified_build_gate_required')
        entry=personality.find(q('BuildState')+"[@State='"+old_name+"']")
        if entry is None:raise ValueError('old_personality_state_missing')
        new_name=prefix+'_'+suffix
        state=E.Element(q('AIStrategicStateDefinition'),id=new_name,MaxTargets='1',MaxRunningCopies='1')
        heuristic=copy.deepcopy(attack.find(q('Heuristic')))
        heuristic.find(q('ScriptedFlagHeuristic')).set('FlagName',old['flag']);state.append(heuristic)
        if action=='reinforce':
            tactic=copy.deepcopy(reactive);tactic.set('EndIfStateTurnsOff','true');tactic.set('EndBehavior','DISBAND')
            tactic.remove(tactic.find(q('TeamTemplate')))
            E.SubElement(tactic,q('TargetBaseCriteria'),PreferredNotBaseTypes='CAPTURED',SortOrder='PREFER_MOST_RECENTLY_ATTACKED')
            team=copy.deepcopy(defense.find(q('Tactic')).find(q('TeamTemplate')))
            team.set('MicroManager','ReactiveDefenseMicroManager');tactic.append(team)
            target_policy='original_native_most_recently_attacked_own_base'
            goal='reinforce_own_base_through_original_reactive_defense'
        else:
            E.SubElement(state,q('TargetHeuristic'),TargetHeuristic=target_name,Priority='20')
            tactic=copy.deepcopy(attack.find(q('Tactic')));tactic.set('GatherWaypoint',home['name'])
            tactic.set('EndBehavior','RETURN_HOME_AND_DISBAND' if action=='withdraw' else 'DISBAND')
            if action=='withdraw':
                # The high-level withdrawal must be able to recruit an existing
                # forward combat team. Unit operation still uses the unchanged
                # original GrowingAttacks micro manager and native gather path.
                team=tactic.find(q('TeamTemplate'))
                team.set('Priority','COOP');team.set('AllowRecruitUnitsInCombat','true')
                E.SubElement(tactic,q('HomeBaseCriteria'),PreferredNotBaseTypes='CAPTURED',SortOrder='PREFER_OLDEST')
                # Sequence requires HomeBaseCriteria before TeamTemplate.
                home_criteria=tactic.find(q('HomeBaseCriteria'));tactic.remove(home_criteria);tactic.insert(0,home_criteria)
            target_policy='fixed_public_own_home_start_waypoint'
            goal='withdraw_native_group_to_own_home_region' if action=='withdraw' else 'regroup_native_force_at_own_home_waypoint'
        state.append(tactic);root.insert(list(root).index(node),state);root.remove(node)
        replacement=E.Element(q('StrategicState'),id=new_name,State=new_name)
        personality.insert(list(personality).index(entry),replacement);personality.remove(entry)
        asset=next(a for a in report['assets'] if a['name']==old['state'])
        asset.update(name='AIStrategicStateDefinition:'+new_name,type_id=hex(sage_hash('AIStrategicStateDefinition')),
            instance_id=hex(sage_hash(new_name.lower())))
        consumer=dict(action=action,flag=old['flag'],state=asset['name'],domain='deployment_policy',exclusive_group='deployment_policy',
            goal=goal,target_policy=target_policy,native_tactic=tactic.get('Tactic'),
            native_micro_manager=tactic.find(q('TeamTemplate')).get('MicroManager'),
            native_ai_selects_and_operates_group=True,unit_orders_exposed=False,
            field_verified=False,capability_granted=False,legacy_transport_flag_alias=old_action,
            required_own_origin_region='region_8_3')
        if action!='reinforce':consumer.update(region_id='region_8_3',waypoint_name=home['name'],waypoint_xyz=home['xyz'])
        report['consumers'][report['consumers'].index(old)]=consumer;roles.append(consumer)
    report.update(group_roles_candidate_revision=2,group_role_candidates=roles,
        group_role_native_source=str(reactive_path),group_role_native_source_sha256=digest(reactive_path),
        group_role_product_capability_granted=False,scope='isolated original-native high-level group-role qualification candidate')
    # The existing compiler verifies feedback offsets on the first strategic
    # asset in this ledger. Keep its intended, unchanged Scout asset first.
    report['assets'].sort(key=lambda a:not (a['name'].startswith('AIStrategicStateDefinition:') and a['name'].endswith('_Scout')))
    E.indent(root,space='  ')
    return E.tostring(root,encoding='utf-8',xml_declaration=True),report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--decoded-map',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--baseline',type=Path,action='append',default=[]);p.add_argument('--compile-base-big',type=Path)
    a=p.parse_args();out=safe_output(a.output)
    paths=[SDK/'BuiltMods/sagexml'/(n+'.manifest') for n in ('static','global','audio')]+a.baseline
    rows=[r for path in paths for r in manifest_rows(path)]
    xml,report=generate_group_roles('57e668b4-4d89-43bd-bc92-0dd436f046ef',3,rows,a.decoded_map.read_bytes())
    report.update(compiled=False,output=str(out),source_sha256=digest(__file__),regional_map_source=str(a.decoded_map.resolve()),
        regional_map_parser_sha256=digest(Path(__file__).with_name('read_map_waypoints.py')),
        collision_baselines=[dict(path=str(path),sha256=digest(path)) for path in paths])
    out.mkdir(parents=True);(out/'MacroProbe.xml').write_bytes(xml);report['macro_xml_sha256']=digest(out/'MacroProbe.xml')
    (out/'generation-report.json').write_text(json.dumps(report,indent=2)+'\n')
    if a.compile_base_big:compile_probe(out,report,a.compile_base_big)
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),compiled=report['compiled'],assets=len(report['assets']),
        group_roles_candidate_revision=1,field_verified=False,product_capability_granted=False)))


if __name__=='__main__':main()
