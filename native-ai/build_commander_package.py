"""Compile UUID commander staging and merge into an untouched BIG copy.

Only dedicated SDK Mods/TFUUIDProbe and a new native-ai/staging directory are
written. No deployment, game operations or TriadFront post-compile scripts.
"""
import argparse,hashlib,json,shutil,struct,subprocess,sys,time,uuid
from pathlib import Path
import xml.etree.ElementTree as E
from stage_commanders import ROOT,SDK,TYPE,q,safe_output
from validate_side_imports import read_stream
sys.path.insert(0,r'E:\RA3Modding\Reference')
from inspect_data import big_entries,csf
sys.path.insert(0,str(ROOT.parent.parent/'TriadFront/tools'))
from read_remix_meshes import unpack_refpack
from localization import load_vanilla,write_csf

MOD='TFUUIDProbe'
def digest(data):return hashlib.sha256(data).hexdigest()

def mrefs(raw):
    rows=[];p=0
    while p<len(raw):
        end=raw.index(0,p+1);rows.append(raw[p:end+1]);p=end+1
    return rows

def payload(stream,row,ext):
    off,size={'bin':('binary_offset','binary_size'),'imp':('imp_offset','imp_size'),'relo':('relo_offset','relo_size')}[ext]
    return stream['files'][ext][row[off]:row[off]+row[size]]

def merge_stream(base_path,new_path,destination,expected_names):
    base,new=read_stream(base_path),read_stream(new_path)
    if base['header'][0]!=new['header'][0] or base['header'][2]!=new['header'][2]:
        raise ValueError('Stream version/type layout mismatch')
    added=[r for r in new['rows'] if r['name'] in expected_names]
    if {r['name'] for r in added}!=expected_names:raise ValueError('Compiled commander records missing')
    keys={(r['type_id'],r['instance_id']) for r in base['rows']}
    for row in added:
        key=row['type_id'],row['instance_id']
        if key in keys:raise ValueError('Cannot replace existing asset '+row['name'])
        keys.add(key)
    specs=[(r,base) for r in base['rows']]+[(r,new) for r in added]
    h=list(base['header']);refs,names,sources=bytearray(),bytearray(),bytearray();records=[]
    blobs={ext:bytearray(struct.pack('<I',h[1])) for ext in ['bin','imp','relo']}
    external=mrefs(base['manifest_refs'])
    for item in mrefs(new['manifest_refs']):
        if item not in external:external.append(item)
    external=b''.join(external)
    for row,source in specs:
        ro,no,so=len(refs),len(names),len(sources)
        for ref in row['refs']:refs.extend(struct.pack('<II',*ref))
        names.extend(row['name'].encode()+b'\0');sources.extend(row['source'].encode()+b'\0')
        records.append(struct.pack('<12I',row['type_id'],row['instance_id'],row['type_hash'],row['instance_hash'],ro,len(row['refs']),no,so,row['binary_size'],row['relo_size'],row['imp_size'],row['flags']))
        for ext in blobs:blobs[ext].extend(payload(source,row,ext))
    h[3]=len(specs);h[4]=len(blobs['bin'])-4
    h[5:8]=[max(r[key] for r,_ in specs) for key in ['binary_size','relo_size','imp_size']]
    h[8:12]=[len(refs),len(external),len(names),len(sources)]
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(struct.pack('<12I',*h)+b''.join(records)+refs+external+names+sources)
    for ext,blob in blobs.items():destination.with_suffix('.'+ext).write_bytes(blob)
    merged=read_stream(destination)
    for original,current in zip(base['rows'],merged['rows']):
        for field in ['name','source','type_id','instance_id','type_hash','instance_hash','refs','flags']:
            if original[field]!=current[field]:raise ValueError('Baseline metadata changed: '+field)
        for ext in blobs:
            if payload(base,original,ext)!=payload(merged,current,ext):raise ValueError('Baseline asset payload changed')
    if not merged['manifest_refs'].startswith(base['manifest_refs']):raise ValueError('Baseline stream dependencies changed')
    return dict(baseline_assets=len(base['rows']),added_assets=len(added),all_baseline_payloads_and_refs_preserved=True,
                external_manifest_refs_hex=external.hex(),manifest_sha256=digest(destination.read_bytes()))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--staging',required=True,type=Path)
    ap.add_argument('--base-big',type=Path,help='Read-only base package, e.g. deployed TriadFront.big')
    ap.add_argument('--output',type=Path);a=ap.parse_args()
    output=safe_output(a.output or ROOT/'staging'/('compiled-commanders-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]))
    registry=json.loads((a.staging/'commander-registry.json').read_text(encoding='utf-8-sig'))
    strings=json.loads((a.staging/'localization.json').read_text(encoding='utf-8-sig'))
    expected={TYPE+':'+asset['asset_id'] for row in registry['commanders'] for asset in row['assets']}
    source=SDK/'Mods'/MOD/'data';source.mkdir(parents=True,exist_ok=True)
    shutil.copy2(a.staging/'LLMCommanders.xml',source/'LLMCommanders.xml')
    root=E.Element(q('AssetDeclaration'));E.SubElement(root,q('Tags'));inc=E.SubElement(root,q('Includes'))
    for name in ['static','global','audio']:E.SubElement(inc,q('Include'),type='reference',source='DATA:'+name+'.xml')
    E.SubElement(inc,q('Include'),type='all',source='DATA:'+MOD+'/data/LLMCommanders.xml')
    E.ElementTree(root).write(source/'Mod.xml',encoding='utf-8',xml_declaration=True)
    output.mkdir(parents=True,exist_ok=False)
    with (output/'sdk-build.log').open('w',encoding='utf-8') as log:
        subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(SDK.parent/'Build-Mod.ps1'),'-ModName',MOD,'-NoDeploy'],stdout=log,stderr=subprocess.STDOUT,check=True)
    compiled=SDK/'BuiltMods/mods'/MOD/'data';package=output/'package';package.mkdir()
    baseline_entries={};base_sha=None
    if a.base_big:
        base_sha=digest(a.base_big.read_bytes())
        for name,raw in big_entries(a.base_big):
            name=name.replace('\\','/');target=(package/name).resolve()
            if not target.is_relative_to(package.resolve()) or name.lower() in baseline_entries:raise ValueError('Unsafe/duplicate base archive path')
            target.parent.mkdir(parents=True,exist_ok=True);data=unpack_refpack(raw);target.write_bytes(data)
            baseline_entries[name.lower()]=digest(data)
        if any('/additionalmaps/' in '/'+name or name.startswith('additionalmaps/') for name in baseline_entries):
            raise ValueError('Base contains AdditionalMaps; normal-flow experiment requires a clean base')
    streams=[]
    for stem in ['mod','mod_M','mod_L']:
        target=package/'data'/(stem+'.manifest');new=compiled/(stem+'.manifest')
        if a.base_big:
            # Source files are snapshotted separately before the append; merged
            # files never become the baseline for preservation assertions.
            before=output/'baseline'/'data'/(stem+'.manifest');before.parent.mkdir(parents=True,exist_ok=True)
            for ext in ['manifest','bin','imp','relo']:shutil.copy2(target.with_suffix('.'+ext),before.with_suffix('.'+ext))
            streams.append(dict(stem=stem,**merge_stream(before,new,target,expected)))
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            for ext in ['manifest','bin','imp','relo']:shutil.copy2(new.with_suffix('.'+ext),target.with_suffix('.'+ext))
            streams.append(dict(stem=stem,added_assets=len(expected),stock_only=True))
        actual={r['name']:r for r in read_stream(target)['rows']}
        for row in registry['commanders']:
            for asset in row['assets']:
                record=actual[TYPE+':'+asset['asset_id']]
                if record['instance_id']!=int(asset['instance_id'],0) or record['type_id']!=int(asset['type_id'],0):
                    raise ValueError('Predicted and compiled native ID differ')
    csf_path=package/'data/gamestrings.csf'
    original=csf(csf_path.read_bytes()) if csf_path.exists() else load_vanilla()[0]
    localized=dict(original)
    for key,value in strings.items():
        if key.lower() in localized:raise ValueError('Localization key collision')
        localized[key.lower()]=value
    write_csf(localized,csf_path)
    checked=csf(csf_path.read_bytes())
    if any(checked.get(key)!=value for key,value in original.items()):raise ValueError('Original localization changed')
    allowed={'data/gamestrings.csf'}|{'data/'+stem.lower()+'.'+ext for stem in ['mod','mod_M','mod_L'] for ext in ['manifest','bin','imp','relo']}
    preserved=0
    for name,old_sha in baseline_entries.items():
        if name not in allowed:
            if digest((package/name).read_bytes())!=old_sha:raise ValueError('Other base archive content changed: '+name)
            preserved+=1
    big=output/'TFNames.big'
    with (output/'makebig.log').open('w',encoding='utf-8') as log:
        subprocess.run([str(SDK/'Tools/MakeBig.exe'),'-f',str(package),'-x:*.asset','-o:'+str(big)],stdout=log,stderr=subprocess.STDOUT,check=True)
    # Verify the archive actually contains what was validated on disk.
    actual_big={name.replace('\\','/').lower():digest(unpack_refpack(raw)) for name,raw in big_entries(big)}
    for file in package.rglob('*'):
        if file.is_file() and actual_big.get(file.relative_to(package).as_posix().lower())!=digest(file.read_bytes()):raise ValueError('BIG roundtrip mismatch')
    if a.base_big and digest(a.base_big.read_bytes())!=base_sha:raise ValueError('Original base package changed')
    registry.update(compiled_ids_verified=True,package_sha256=digest(big.read_bytes()),game_sync_verified=False,side_binding_verified=False,deployed=False)
    (output/'commander-registry.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'TFNames_1.0.skudef').write_text('mod-game 1.12\nadd-big TFNames.big\n',encoding='ascii')
    report=dict(source_staging=str(a.staging.resolve()),base_big=str(a.base_big.resolve()) if a.base_big else None,
                baseline_big_sha256=base_sha,output=str(output),big_sha256=registry['package_sha256'],
                generated_assets=len(expected),streams=streams,unchanged_other_base_entries=preserved,
                all_original_localization_preserved=True,big_roundtrip_verified=True,
                no_additionalmaps=True,compiled=True,deployed=False,game_sync_verified=False)
    (output/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
