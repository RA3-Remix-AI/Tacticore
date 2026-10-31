"""Collect exact installed notices and dependency identities before freezing.

No game/Mod/media is collected. This is a technical distribution inventory,
not a change to upstream licenses or a license grant for Tacticore sources.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
import zipfile

ROOT=Path(__file__).resolve().parents[2]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def collect(runtime,mingw_notice):
    runtime=Path(runtime);output=runtime/'notices'
    output.mkdir()  # only a new stage
    rows=[]
    def put(group,name,source):
        target=output/group/name;target.parent.mkdir(parents=True,exist_ok=True)
        pin=sha(source);shutil.copyfile(source,target)
        if sha(source)!=pin or sha(target)!=pin:raise ValueError('notice_source_changed')
        return dict(file=target.relative_to(runtime).as_posix(),sha256=pin)
    put('python','CPython-LICENSE.txt',runtime/'python/LICENSE.txt')
    with zipfile.ZipFile(runtime/'python/Lib/site-packages.zip') as container:
        for item in read(runtime/'third-party-inventory.json')['dependencies']:
            notices=[]
            for notice_index,locator in enumerate(item['license_locations']):
                if locator['kind']=='zip_member':raw=container.read(locator['member']);name=locator['member']
                else:raw=(runtime/locator['path']).read_bytes();name=locator['path']
                # RECORD can list distinct nested notices with the same base
                # name (OpenAI wheel contains multiple LICENSE files).
                target=output/'python'/item['name']/(str(notice_index).zfill(2)+'-'+Path(name).name)
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                notices.append(dict(file=target.relative_to(runtime).as_posix(),sha256=sha(target)))
            if not notices and item['name']=='logfire-api':
                notices.append(put('python/logfire-api','LICENSE.txt',ROOT/'desktop-ui/notices/upstream/logfire-api-5.3.0-LICENSE.txt'))
            if not notices:raise ValueError('python_dependency_notice_missing:'+item['name'])
            rows.append(dict(ecosystem='python',name=item['name'],version=item['version'],license=item['declared_license'],notices=notices))
    lock=read(ROOT/'desktop-ui/package-lock.json')['packages']
    for name in ('react','react-dom','scheduler','@phosphor-icons/react','@tauri-apps/api'):
        source=ROOT/'desktop-ui/node_modules'/name;metadata=read(source/'package.json')
        if metadata['version']!=lock['node_modules/'+name]['version']:raise ValueError('frontend_dependency_changed')
        paths=[p for p in source.iterdir() if p.is_file() and re.match(r'(?i)^(licen[cs]e|copying|notice)',p.name)]
        if not paths:raise ValueError('frontend_dependency_notice_missing:'+name)
        rows.append(dict(ecosystem='frontend',name=name,version=metadata['version'],license=metadata.get('license'),
            notices=[put('frontend/'+name,p.name,p) for p in paths]))
    cargo=Path.home()/'.cargo/bin/cargo.exe'
    tree=subprocess.run([str(cargo),'tree','--manifest-path',str(ROOT/'desktop-ui/src-tauri/Cargo.toml'),
        '--target','x86_64-pc-windows-msvc','--edges','normal,build','--prefix','none','--format','{p}','--offline','--locked'],
        capture_output=True,text=True,encoding='utf-8',check=True,timeout=60).stdout
    used=set(re.findall(r'(?m)^([A-Za-z0-9_-]+) v([0-9][^\s]*)',tree))
    registries=sorted((Path.home()/'.cargo/registry/src').iterdir())
    cargo_lock=tomllib.loads((ROOT/'desktop-ui/src-tauri/Cargo.lock').read_text(encoding='utf-8'))['package']
    for name,version in sorted(used):
        if name=='tacticore-desktop':continue
        candidates=[p/(name+'-'+version) for p in registries if (p/(name+'-'+version)).is_dir()]
        if len(candidates)!=1:raise ValueError('cargo_notice_source_ambiguous:'+name)
        source=candidates[0];metadata=tomllib.loads((source/'Cargo.toml').read_text(encoding='utf-8'))['package']
        paths=[p for p in source.iterdir() if p.is_file() and re.match(r'(?i)^(licen[cs]e|copying|notice|copyright)',p.name)]
        notices=[put('cargo/'+name+'-'+version,p.name,p) for p in paths]
        if not notices:
            fallback=list((ROOT/'desktop-ui/notices/upstream').glob(name+'-'+version+'-LICENSE*'))
            if name=='selectors':fallback=[ROOT/'desktop-ui/notices/upstream/MPL-2.0.txt']
            if not fallback:raise ValueError('cargo_dependency_notice_missing:'+name)
            notices=[put('cargo/'+name+'-'+version,p.name,p) for p in fallback]
        source_form=None
        if 'MPL-2.0' in metadata.get('license',''):
            archive=Path.home()/'.cargo/registry/cache'/source.parent.name/(name+'-'+version+'.crate')
            entry=next(row for row in cargo_lock if row['name']==name and row['version']==version)
            if sha(archive)!=entry['checksum']:raise ValueError('mpl_source_archive_changed')
            source_form=put('source-form',archive.name,archive)
        rows.append(dict(ecosystem='cargo_windows_normal_and_build',name=name,version=version,license=metadata.get('license'),
            notices=notices,unmodified_source_archive=source_form))
    put('native-runtime','COPYING.MinGW-w64-runtime.txt',mingw_notice)
    upstream=ROOT/'desktop-ui/notices/upstream'
    for name,item in read(upstream/'sources.json').items():
        if sha(upstream/name)!=item['sha256']:raise ValueError('upstream_notice_pin_changed')
        put('upstream',name,upstream/name)
    notice_names=set()
    for row in rows:
        for notice in row['notices']:
            if notice['file'] in notice_names or sha(runtime/notice['file'])!=notice['sha256']:
                raise ValueError('distribution_notice_collision_or_mismatch')
            notice_names.add(notice['file'])
    (output/'index.json').write_text(json.dumps(dict(schema_version=1,kind='exact_beta_distribution_notices',
        dependencies=rows,game_or_mod_assets_included=False,redistributed_sources_unmodified=True,
        source_locks=dict(python=sha(ROOT/'agent_runtime/requirements-pydantic.lock'),npm=sha(ROOT/'desktop-ui/package-lock.json'),
                          cargo=sha(ROOT/'desktop-ui/src-tauri/Cargo.lock')),upstream=read(upstream/'sources.json')),indent=2)+'\n',encoding='utf-8')
    (output/'README.txt').write_text('Tacticore v0.1.0-beta.1 third-party notices\n\n'
        'Original notices and license texts are preserved in these directories; index.json records exact versions and hashes.\n'
        'CPython notice is in python/CPython-LICENSE.txt. Unmodified Python dependency sources are also included in the runtime, '
        'as filesystem packages or members of python/Lib/site-packages.zip. This includes the unmodified certifi sources (MPL-2.0).\n'
        'Cargo notices cover Windows normal/build dependencies. Build-tool inventory is not a claim that every tool is shipped.\n'
        'GCC 16.2 runtime licensing and Runtime Library Exception are in upstream/. MinGW-w64 notices are in native-runtime/.\n'
        'The app icon uses Phosphor (MIT). Native-only beta builds do not package the browser demo faction art or media.\n'
        'No Electronic Arts game, complete Mod, SDK or compiler is included. Game/Mod files are supplied locally by the user.\n',encoding='utf-8')
    # Full companion inventory is resealed before qualification/build. Notices
    # are data, not an extra executable input or a source-lock limit expansion.
    files={p.relative_to(runtime).as_posix():sha(p) for p in sorted(runtime.rglob('*')) if p.is_file() and p!=runtime/'manifest.json'}
    (runtime/'manifest.json').write_text(json.dumps(dict(schema_version=1,python='python/python.exe',working_directory='app/integration',files=files),sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    return dict(dependencies=len(rows),notice_files=sum(1 for p in output.rglob('*') if p.is_file()),game_assets=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--mingw-notice',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(collect(args.runtime,args.mingw_notice)))
