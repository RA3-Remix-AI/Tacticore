"""Read native AI group type tags, only through strictly bound own tasks.

No unknown object's members, position, template or health is read. This is a
diagnostic for rejected native group tags, not an execution grant.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from observe_production import Memory
from session_package import verify_session_package
from read_match_state import snapshot
from macro_area_defense_observation import MacroObserver,registry_lookup,pointer
from read_selected_personality import inspect_player


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--seconds',type=int,default=90);a=p.parse_args()
    session=json.loads(a.session.read_text(encoding='utf-8-sig'));manifest=json.loads((a.build/'build-manifest.json').read_text())
    out=a.output.resolve()
    if (out.exists() or not out.is_relative_to(ROOT/'reports') or not 1<=a.seconds<=120
            or session['mod_sha256']!=manifest['package_sha256']
            or session['mod_sha256']!='c76b3c9492848cdc91b7221cf5247d4ff0d6cf99bebb7f432f5624372d939622'):
        raise ValueError('owned_area_group_diagnostic_scope')
    verify_session_package(session);memory=Memory(session['pid'],session);rows=[];errors=0
    try:
        state=snapshot(memory.read);owners=[int(v['player'],0) for v in state['victory_conditions']['participants'] if v['player_index']==3]
        if len(owners)!=1:raise ValueError('unique_own_area_ai_required')
        owner=owners[0];identity=inspect_player(memory.read,owner)
        if int(identity['instance_id'],0)!=0x799613e0:raise ValueError('own_area_personality_required')
        observer=MacroObserver(memory,owner,manifest['flags']);deadline=time.monotonic()+a.seconds
        while time.monotonic()<deadline:
            try:
                if inspect_player(memory.read,owner)!=identity:raise ValueError('own_area_identity_changed')
                observation=observer.sample();registry=pointer(memory.u32(0xce8ca4),0x34)
                for task in observation['runtimes']:
                    if task['native_tactic_family']!='static_defense' or not task['native_execution_active']:continue
                    for ident in task['native_owned_ids_raw']:
                        group=registry_lookup(memory.read,registry+0x28,ident)
                        if not group:continue
                        tag=memory.u32(group+0x39c);vtable=memory.u32(group)
                        if registry_lookup(memory.read,registry+0x28,ident)!=group or memory.u32(group+0x39c)!=tag:
                            raise ValueError('native_area_group_changed')
                        row=dict(frame=observation['frame'],native_type_tag=tag,native_vtable=hex(vtable),
                            source='strict_own_task_native_id_registry',unknown_object_details_read=False)
                        if len(rows)>=2048:raise ValueError('native_area_diagnostic_bound')
                        rows.append(row)
            except (ValueError,RuntimeError):errors+=1
            time.sleep(.25)
        result=dict(kind='own_area_group_type_diagnostic',session_id=session['session_id'],pid=session['pid'],
            rows=rows,read_errors=errors,model_calls=0,native_calls=0,process_writes=0,
            enemy_details_read=False,execution_capability_granted=False)
        out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(output=str(out),samples=len(rows),read_errors=errors)))
    finally:memory.close()


if __name__=='__main__':main()
