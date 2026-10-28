"""Stage two public-map region targets for original native AI task execution.

Reuses the 13-gate protocol. Existing custom construction, budgets, production
and scouting remain byte-identical XML; only two unqualified deployment states
are changed. No baseline micro manager or original asset is replaced.
"""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as E

from stage_macro_policy import generate_policy
from stage_macro_probe import compile_probe,digest
from stage_commanders import SDK,q,safe_output,manifest_rows,sage_hash
from read_map_waypoints import starting_waypoints

MAP_SHA='ec4775f8c2d50ad15576544f00071ed1e409ee70f5a9dc7610282584e6798d66'

def generate_regions(commander,slot,baselines,map_raw):
    import hashlib
    if hashlib.sha256(map_raw).hexdigest()!=MAP_SHA:raise ValueError('reviewed_public_map_required')
    waypoints=starting_waypoints(map_raw)
    xml,report=generate_policy(commander,slot,baselines);root=E.fromstring(xml)
    prefix=report['personality'].removesuffix('_Soviet');keys={(int(r['type_id'],0),int(r['instance_id'],0)) for r in report['assets']}
    keys.update((r['type_id'],r['instance_id']) for r in baselines)
    attack=root.find(q('AIStrategicStateDefinition')+"[@id='"+prefix+"_DeployAttack']")
    native_tactic=copy.deepcopy(attack.find(q('Tactic')))
    if native_tactic.get('Tactic')!='SimpleAttack':raise ValueError('original_native_attack_tactic_required')
    for action,point in zip(('deployattack','deploydefense'),waypoints):
        consumer=next(r for r in report['consumers'] if r['action']==action)
        state=root.find(q('AIStrategicStateDefinition')+"[@id='"+consumer['state'].split(':',1)[1]+"']")
        target_name=prefix+'_Waypoint_'+point['name'];kind='AITargetingHeuristic';key=sage_hash(kind),sage_hash(target_name.lower())
        if key in keys:raise ValueError('regional_target_asset_collision')
        keys.add(key);report['assets'].append(dict(name=kind+':'+target_name,type_id=hex(key[0]),instance_id=hex(key[1])))
        # Match the stock waypoint hotspot example. Native uniqueness rejects a
        # point already present in the AI target manager, even for another task.
        target=E.Element(q(kind),id=target_name,HeuristicType='Waypoint',Name=point['name'],RequireUniqueTarget='false')
        root.insert(list(root).index(state),target)
        for child in list(state):
            if child.tag!=q('Heuristic'):state.remove(child)
        E.SubElement(state,q('TargetHeuristic'),TargetHeuristic=target_name,Priority='20')
        tactic=copy.deepcopy(native_tactic);tactic.set('EndBehavior','DISBAND');tactic.set('EndIfStateTurnsOff','true')
        team=tactic.find(q('TeamTemplate'));team.set('MinUnits','1');team.set('MaxUnits','12')
        # Use the stock priority-based recruiter to request available combat
        # forces ahead of ordinary growing attacks. No unit is commanded here.
        team.set('Priority','HIGH')
        if team.get('MicroManager')!='GrowingAttacksMicroManager_MEDIUM' or team.findall(q('CreateUnits')):
            raise ValueError('native_pool_and_micro_manager_required')
        state.append(tactic)
        consumer.update(target_policy='fixed_public_start_waypoint',waypoint_name=point['name'],waypoint_xyz=point['xyz'],
            region_id='region_'+str(int(point['xyz'][0]//512))+'_'+str(int(point['xyz'][1]//512)),
            bounded_region_selection_supported=True,arbitrary_region_selection_supported=False,
            native_tactic='SimpleAttack',native_micro_manager='GrowingAttacksMicroManager_MEDIUM',
            native_recruitment_min_units=1,native_recruitment_max_units=12,unit_orders_exposed=False,
            native_recruitment_priority='HIGH',native_recruitment_release_type='RELEASE_TO_PRIORITY',
            native_waypoint_require_unique_target=False,
            stock_source_state='GrowingAttacks_Land_MEDIUM',legacy_action_name_is_not_mission_purpose=True)
    report.update(regional_waypoints_revision=3,regional_map_id='map_mp_2_black1b',regional_map_sha256=MAP_SHA,
        regional_waypoints=waypoints,regional_field_verified=False,regional_capability_granted=False,
        scope='13-gate expanded policy plus two fixed public map waypoint consumers; research only')
    E.indent(root,space='  ')
    return E.tostring(root,encoding='utf-8',xml_declaration=True),report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decoded-map',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',type=Path,action='append',default=[])
    p.add_argument('--compile-base-big',type=Path);a=p.parse_args();out=safe_output(a.output)
    paths=[SDK/'BuiltMods/sagexml'/(n+'.manifest') for n in ('static','global','audio')]+a.baseline
    rows=[r for path in paths for r in manifest_rows(path)]
    xml,report=generate_regions('57e668b4-4d89-43bd-bc92-0dd436f046ef',3,rows,a.decoded_map.read_bytes())
    report.update(compiled=False,output=str(out),source_sha256=digest(__file__),regional_map_source=str(a.decoded_map.resolve()),
        regional_map_parser_sha256=digest(Path(__file__).with_name('read_map_waypoints.py')),
        collision_baselines=[dict(path=str(path),sha256=digest(path)) for path in paths])
    out.mkdir(parents=True);(out/'MacroProbe.xml').write_bytes(xml);report['macro_xml_sha256']=digest(out/'MacroProbe.xml')
    (out/'generation-report.json').write_text(json.dumps(report,indent=2)+'\n')
    if a.compile_base_big:compile_probe(out,report,a.compile_base_big)
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),compiled=report['compiled'],assets=len(report['assets']),
        regional_field_verified=False,product_capability_granted=False)))

if __name__=='__main__':main()
