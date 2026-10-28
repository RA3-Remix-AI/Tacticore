"""Bounded read-only own-actor/empty-land precondition study; no executor."""
import argparse,collections,hashlib,json,math,shutil,sys,time
from pathlib import Path
from compare_native import native_reference
from land_surface import EmptyLandReader


def collect(session_path,output):
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'integration'))
    from live_state import Memory,own_candidates,verify_session_package
    original=session_path.read_bytes();s=json.loads(original.decode('utf-8-sig'));run=Path(s['run_directory']).resolve()
    if (output.parent!=run or output.exists() or s['scenario']['model_requests_enabled'] is not False
            or s['scenario']['trial_kind']!='read_only_terrain_geometry_research' or not s['scenario']['lobby_verified']):
        raise ValueError('owned_readonly_research_session_required')
    verify_session_package(s);archive=run/(output.stem+'-code');archive.mkdir();sources=[]
    for name in ('heightmap.py','pathgrid.py','compare_native.py','land_surface.py','compare_land.py'):
        target=archive/name;shutil.copyfile(Path(__file__).with_name(name),target)
        sources.append(dict(file=name,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    m=Memory(s['pid'],s);reader=EmptyLandReader(m);samples=[];errors=collections.Counter();seen=set();start=time.monotonic()
    try:
        while time.monotonic()-start<60 and len(samples)<128:
            if session_path.read_bytes()!=original:raise ValueError('research_session_changed')
            try:
                census=own_candidates(m,s['scenario']['computer_player_index'],{})
                if not census['frame_start'] or census['frame_start']!=census['frame_end']:raise ValueError('census_cross_frame')
                for row in census['candidates']:
                    if int(row['type_hash'],0) not in (0x19ab11af,0x2c358c61):continue
                    actor=reader.actor(int(row['address'],0))
                    if actor['frame']!=census['frame_start']:continue
                    # This study reads cell predicates and actor dimensions;
                    # it never qualifies an actor for Borrow. Preserve a failed
                    # native surface cache as missing evidence, rather than
                    # letting it suppress unrelated static cell observations.
                    reference=None;surface_refusal=None
                    try:
                        reference=native_reference(m,row,actor['frame'],reader.height)
                        if not reference['height_agrees']:surface_refusal='own_surface_raster_mismatch'
                    except (ValueError,OSError,RuntimeError) as error:surface_refusal=str(error)
                    x,y=row['xyz'][:2]
                    points=[(x,y),(x+40,y),(x-40,y),(x,y+40),(x,y-40),(x+80,y+80),(x+100,y),(x,y+100),
                        (100.,100.),(300.,300.),(4500.,4500.),(2500.,2500.)]
                    for px,py in points:
                        try:
                            value=reader.sample(actor,px,py)
                            key=(row['object_id'],tuple(value['center_cell']),bool(value['rejection_reasons']))
                            if key in seen:continue
                            seen.add(key);samples.append(dict(native_reference=reference,surface_reference_refusal=surface_refusal,
                                own_census_row=row,land=value,actor_borrow_qualified=False))
                            if len(samples)>=128:break
                        except (ValueError,OSError,RuntimeError) as error:errors[str(error)]+=1
                    if len(samples)>=128:break
            except (ValueError,OSError,RuntimeError) as error:errors[str(error)]+=1
            good=[x for x in samples if x['land']['restricted_empty_land_preconditions']]
            bad=[x for x in samples if x['land']['rejection_reasons']]
            if (len(good)>=6 and len(bad)>=6 and len({x['land']['frame'] for x in samples})>=3
                    and len({x['land']['actor']['object_id'] for x in samples})>=2):break
            time.sleep(.15)
    finally:m.close()
    assert session_path.read_bytes()==original
    for source in sources:
        if hashlib.sha256(Path(__file__).with_name(source['file']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('land_research_sources_changed')
    good=sum(x['land']['restricted_empty_land_preconditions'] for x in samples)
    sufficient=(good>=6 and len(samples)-good>=6 and len({x['land']['frame'] for x in samples})>=3
        and len({x['land']['actor']['object_id'] for x in samples})>=2)
    result=dict(schema_version=1,kind='own_actor_land_precondition_readonly_study',session_id=s['session_id'],pid=s['pid'],
        process_start=s['start_time'],source_files=sources,samples=samples,rejections=dict(errors),elapsed_seconds=time.monotonic()-start,
        status='cell_preconditions_observed' if sufficient else 'insufficient_cell_observations',
        native_calls=0,game_writes=0,leases=0,model_requests=0,walkability_verified=False,
        ground_target_permission_granted=False,ordinary_execution_granted=False)
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=collect(a.session.resolve(),a.output.resolve())
    print(json.dumps(dict(status=r['status'],samples=len(r['samples']),positive_preconditions=sum(x['land']['restricted_empty_land_preconditions'] for x in r['samples']),
        actors=len({x['land']['actor']['object_id'] for x in r['samples']}),frames=len({x['land']['frame'] for x in r['samples']}),
        mask_values=sorted({x['land']['actor']['mask'] for x in r['samples']}),
        rejection_reasons=dict(collections.Counter(v for x in r['samples'] for v in x['land']['rejection_reasons'])),read_rejections=r['rejections'])))
    raise SystemExit(0 if r['status']=='cell_preconditions_observed' else 1)
