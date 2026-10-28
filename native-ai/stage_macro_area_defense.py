"""Isolated native area-defense candidate; original AI performs all combat.

The qualified two-waypoint generator is unchanged. This candidate replaces
only its east-side custom tactic with the SDK's original StaticDefense tactic.
Compilation grants no field or product capability.
"""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as E

from stage_macro_regions import generate_regions
from stage_macro_probe import compile_probe,digest
from stage_commanders import SDK,q,safe_output,manifest_rows


def generate_area_defense(commander,slot,baselines,map_raw):
    xml,report=generate_regions(commander,slot,baselines,map_raw);root=E.fromstring(xml)
    stock=SDK/'SAGEXML/SkirmishAI/States/BalancedStates.xml'
    source=E.parse(stock).getroot().find(q('AIStrategicStateDefinition')+"[@id='BalancedDefense']")
    tactic=copy.deepcopy(source.find(q('Tactic')))
    if (tactic.get('Tactic')!='StaticDefense' or tactic.get('Distance')!='500'
            or tactic.find(q('TeamTemplate')).get('MicroManager')!='DefenseMicroManager'):
        raise ValueError('original_native_area_defense_required')
    team=tactic.find(q('TeamTemplate'));team.set('Priority','HIGH')
    if team.findall(q('CreateUnits')):raise ValueError('native_existing_force_pool_required')
    consumer=next(r for r in report['consumers'] if r['action']=='deploydefense')
    state=root.find(q('AIStrategicStateDefinition')+"[@id='"+consumer['state'].split(':',1)[1]+"']")
    old=state.find(q('Tactic'));state.remove(old);state.append(tactic)
    consumer.update(native_tactic='StaticDefense',native_micro_manager='DefenseMicroManager',
        stock_source_state='BalancedDefense',goal='original_native_area_defense_at_fixed_public_point',
        native_defense_radius=500,legacy_action_name_is_not_mission_purpose=False,
        native_recruitment_allows_units_in_combat=team.get('AllowRecruitUnitsInCombat')=='true',
        field_verified=False,capability_granted=False)
    report.update(area_defense_candidate_revision=1,area_defense_stock_source=str(stock),
        area_defense_stock_sha256=digest(stock),area_defense_field_verified=False,
        area_defense_product_capability_granted=False)
    E.indent(root,space='  ')
    return E.tostring(root,encoding='utf-8',xml_declaration=True),report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decoded-map',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',type=Path,action='append',default=[])
    p.add_argument('--compile-base-big',type=Path);a=p.parse_args();out=safe_output(a.output)
    paths=[SDK/'BuiltMods/sagexml'/(n+'.manifest') for n in ('static','global','audio')]+a.baseline
    rows=[r for path in paths for r in manifest_rows(path)]
    xml,report=generate_area_defense('57e668b4-4d89-43bd-bc92-0dd436f046ef',3,rows,a.decoded_map.read_bytes())
    report.update(compiled=False,output=str(out),source_sha256=digest(__file__),regional_map_source=str(a.decoded_map.resolve()),
        regional_map_parser_sha256=digest(Path(__file__).with_name('read_map_waypoints.py')),
        collision_baselines=[dict(path=str(path),sha256=digest(path)) for path in paths])
    out.mkdir(parents=True);(out/'MacroProbe.xml').write_bytes(xml);report['macro_xml_sha256']=digest(out/'MacroProbe.xml')
    (out/'generation-report.json').write_text(json.dumps(report,indent=2)+'\n')
    if a.compile_base_big:compile_probe(out,report,a.compile_base_big)
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),compiled=report['compiled'],assets=len(report['assets']),
        field_verified=False,product_capability_granted=False)))


if __name__=='__main__':main()
