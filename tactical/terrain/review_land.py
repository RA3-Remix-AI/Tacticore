"""Independent offline raw-value consistency review; no process attachment."""
import argparse,hashlib,json,math,struct
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]

def review(source,session_path,archive,parameter_source):
    r=json.loads(source.read_text());s=json.loads(session_path.read_text(encoding='utf-8-sig'))
    p=json.loads(parameter_source.read_text());checks={};raw_ok=True;terrain_ok=True;raster_ok=True;positives=0;codes=set()
    checks['session_and_lobby']=(r['session_id']==s['session_id'] and r['pid']==s['pid'] and r['process_start']==s['start_time']
        and s['scenario']['trial_kind']=='read_only_terrain_geometry_research' and s['scenario']['model_requests_enabled'] is False
        and s['scenario']['lobby_verified'] is True and sha(Path(s['scenario']['lobby_screenshot']))==s['scenario']['lobby_screenshot_sha256'])
    checks['archived_sources']=all(sha(archive/x['file'])==x['sha256'] for x in r['source_files'])
    checks['no_execution_or_target_grant']=(r['native_calls']==r['game_writes']==r['leases']==r['model_requests']==0
        and all(r[x] is False for x in ('walkability_verified','ground_target_permission_granted','ordinary_execution_granted')))
    mask_witnesses=[]
    for witness in p['samples']:
        w=struct.unpack('<39I',bytes.fromhex(witness['params_raw_hex']))
        if (p['session_id']==s['session_id'] and p['pid']==s['pid'] and w[0]==0xc18ca0 and w[1]==0xc1893c
                and w[3]==witness['object_id'] and w[5]==int(witness['update'],0)+0x1fc
                and witness['settings_raw_hex']):
            config=struct.unpack('<8I',bytes.fromhex(witness['settings_raw_hex']))
            if config[0]==0xc37620 and config[5]==witness['surface_mask']==1:mask_witnesses.append(witness['object_id'])
    checks['typed_native_path_to_actual_surface_mask']=bool(mask_witnesses)
    surface_reference_count=0
    for entry in r['samples']:
        q=entry['land'];a=q['actor'];w=a['identity_words'];own=entry['own_census_row'];width=a['footprint_width']
        radius,override=(struct.unpack('<f',struct.pack('<I',v))[0] for v in w[12:14]);diameter=f32(radius*2)
        if 20<diameter<40:diameter=40.
        if override>0:diameter=override
        n=int(f32(f32(diameter*f32(.05))+f32(.3))) or 1
        cx,cy=(int(f32(f32(f32(v)*f32(.05))+(0 if n&1 else f32(.5)))) for v in q['xy'])
        raw_ok &= (len(w)==16 and w[0]==0xc4db60 and w[1]==a['object_id']==own['object_id'] and w[3]==int(own['type_hash'],0)
            and a['thing']==own['address'] and w[4]==int(own['owner_address'],0) and w[5]==int(own['ai_address'],0)
            and w[6:9]==[0xc48670,0xc48528,int(a['thing'],0)] and w[14]==0xc37620 and w[15]==a['mask']==1
            and int(a['mask_address'],0)==w[5]+0x210 and int(a['locomotor_set'],0)==w[5]+0x1fc
            and radius==a['radius'] and override==a['geometry_override'] and n==width==1
            and a['ignored_object_words']==w[9:11] and q['frame']==a['frame'] and q['center_cell']==[cx,cy]
            and entry['actor_borrow_qualified'] is False)
        reasons=set()
        for cell in q['footprint_cells']:
            words=struct.unpack('<12I',bytes.fromhex(cell['cell_raw_hex']));flags=words[3];code=flags&15;codes.add(code)
            expected_mask=[9,10,12,24,40,72,72,136,8,520,1032]
            if code>=11 or expected_mask[code]&1==0:reasons.add('native_terrain_mask_reject5')
            if code!=0:reasons.add('terrain_code_outside_plain_land0_scope')
            if (flags>>4)&63!=1:reasons.add('primary_layer_outside_ground1_scope')
            if flags&0x40000:reasons.add('native_flag18_rejected_conservatively')
            if words[0]:reasons.add('native_object_record_present')
            raw_ok &= (list(words)==cell['cell_words'] and int(cell['cell'],0)==int(cell['column_pointer'],0)+48*cell['row']
                and cell['column']==cx and cell['row']==cy and cell['frame']==q['frame'] and cell['layer']==1)
        terrain_ok &= (len(q['footprint_cells'])==width*width and sorted(reasons)==q['rejection_reasons']
            and q['restricted_empty_land_preconditions']==(not reasons))
        height=q['base_height'];v=[struct.unpack('<H',bytes.fromhex(x))[0] for x in height['vertex_raw_hex']];fx,fy=height['fractions']
        value=((1-fy)*v[0]+(fy-fx)*v[2]+fx*v[3] if fy>fx else (1-fx)*v[0]+(fx-fy)*v[1]+fy*v[3])/25.6
        raster_ok &= (height['frame']==q['frame'] and height['xy']==q['xy'] and abs(value-height['base_height'])<=.0001
            and q['native_calls']==q['game_writes']==0 and all(q[k] is False for k in ('walkability_verified','ground_target_permission_granted','ordinary_execution_granted')))
        positives+=not reasons
        surface_reference_count+=bool(entry['native_reference'] and not entry['surface_reference_refusal'] and entry['native_reference']['height_agrees'])
    checks.update(raw_actor_footprint_and_cell=bool(r['samples']) and raw_ok,independent_rejection_predicates=terrain_ok,
        independent_base_height=raster_ok,positive_and_negative_cells=positives>=6 and len(r['samples'])-positives>=6)
    return dict(schema_version=1,kind='offline_land_cell_precondition_review',status='passed' if all(checks.values()) else 'not_passed',checks=checks,
        source_sha256=sha(source),parameter_source_sha256=sha(parameter_source),typed_mask_witness_object_ids=mask_witnesses,
        samples=len(r['samples']),positive_cell_preconditions=positives,rejected_samples=len(r['samples'])-positives,
        actors=len({x['land']['actor']['object_id'] for x in r['samples']}),frames=len({x['land']['frame'] for x in r['samples']}),raw_terrain_codes=sorted(codes),
        valid_native_surface_references=surface_reference_count,actor_borrow_qualified=False,walkability_verified=False,
        ground_target_permission_granted=False,ordinary_execution_granted=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','session','archive','parameters','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();r=review(a.source.resolve(),a.session.resolve(),a.archive.resolve(),a.parameters.resolve())
    with a.output.open('x',encoding='utf-8') as out:json.dump(r,out,indent=2)
    print(json.dumps(r));raise SystemExit(0 if r['status']=='passed' else 1)
