"""Add installer-only license data without changing a frozen companion."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from locked_python_runtime import plain

ROOT=Path(__file__).resolve().parents[2]
UPSTREAM=ROOT/'desktop-ui/notices/upstream'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def compiler():
    rustc=Path.home()/'.cargo/bin/rustc.exe'
    root=Path(subprocess.check_output([str(rustc),'--print','sysroot'],text=True,encoding='utf-8').strip())
    version=subprocess.check_output([str(rustc),'-V'],text=True,encoding='utf-8').strip()
    return root,dict(version=version,sha256=sha(root/'bin/rustc.exe'))

def create(output,nsis_source):
    output=Path(output).absolute()
    plain(next(p for p in output.parents if p.exists()))
    output.mkdir(parents=True)  # a new immutable supplement
    plain(output)
    def put(name,source):
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        source=plain(source);expected=sha(source);shutil.copyfile(source,target)
        if sha(source)!=expected or sha(target)!=expected:raise ValueError('supplement_source_changed')
        return dict(file=name,sha256=expected)
    root,rust=compiler()
    rows=[dict(name='Rust standard library and its dependencies',version=rust['version'],
        notices=[put('rust-stdlib/COPYRIGHT-library.html',root/'share/doc/rust/COPYRIGHT-library.html')])]
    sources=read(UPSTREAM/'sources.json')
    sdk=sources['webview2-sdk-1.0.3800.47-LICENSE.txt']
    crates=Path.home()/'.cargo/registry/src'
    loaders=list(crates.glob('*/webview2-com-sys-0.39.1/x64/WebView2LoaderStatic.lib'))
    if len(loaders)!=1 or sha(loaders[0])!=sdk['x64_static_loader_sha256']:
        raise ValueError('sdk_static_loader_changed')
    notices=[]
    for name,provenance in sources.items():
        if not (name.startswith('nsis-') or name.startswith('webview2-sdk-')):continue
        if sha(UPSTREAM/name)!=provenance['sha256']:raise ValueError('vendor_notice_changed')
        notices.append(dict(**put('native-vendor/'+name,UPSTREAM/name),origin=provenance))
    rows.append(dict(name='Microsoft WebView2 static loader and NSIS installer components',notices=notices,
        x64_webview2_loader_sha256=sdk['x64_static_loader_sha256']))
    original=read(UPSTREAM/'native-sources.json')['nsis_source']
    if sha(nsis_source)!=original['sha256']:raise ValueError('nsis_original_source_changed')
    rows.append(dict(name='Unmodified NSIS 3.13 source, including LZMA compression module',
        original=original,notices=[put('source-form/nsis-3.13-source.zip',nsis_source)]))
    (output/'README.txt').write_text(
        'Tacticore beta supplemental distribution notices\n\n'
        'Keep these original notices alongside runtime/notices. This directory contains data only; it is not a Python or native execution path.\n'
        'rust-stdlib/ contains the original complete license inventory from the exact Rust compiler standard library used for this build.\n'
        'native-vendor/ contains the Microsoft WebView2 static-loader BSD notice and the original NSIS, UI, downloader and Tauri plugin notices.\n'
        'source-form/ contains the unmodified NSIS 3.13 source archive, including its LZMA module and original licenses/linking exception.\n'
        'No game, Mod, game SDK, compiler executable or user credentials are included.\n',encoding='utf-8',newline='\n')
    files={p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    record=dict(schema_version=1,kind='installer_only_license_supplement',rust_compiler=rust,
        code_or_execution_authority=False,components=rows,files=files)
    (output/'index.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    return verify(output)

def verify(output):
    output=plain(output);record=read(output/'index.json')
    if record['kind']!='installer_only_license_supplement' or record['code_or_execution_authority'] is not False:
        raise ValueError('license_supplement_required')
    _,actual=compiler()
    if actual!=record['rust_compiler']:raise ValueError('license_compiler_changed')
    files=record['files']
    for name,expected in files.items():
        parts=name.split('/')
        if any(p in ('','.','..') for p in parts) or ':' in name or '\\' in name:
            raise ValueError('supplement_plain_relative_required')
        path=plain(output/name)
        if path.suffix not in ('.txt','.html','.zip') or sha(path)!=expected:raise ValueError('supplement_file_changed')
    entries=list(output.rglob('*'))
    if len(entries)>1000:raise ValueError('supplement_inventory_size_limit')
    for path in entries:plain(path)
    found={p.relative_to(output).as_posix() for p in entries if p.is_file() and p!=output/'index.json'}
    if found!=set(files):raise ValueError('supplement_inventory_changed')
    for row in record['components']:
        for entry in row['notices']:
            if files.get(entry['file'])!=entry['sha256']:raise ValueError('supplement_notice_mismatch')
    return dict(kind=record['kind'],files=len(files),index_sha256=sha(output/'index.json'),code_or_execution_authority=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--nsis-source',type=Path)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    if not args.verify and args.nsis_source is None:parser.error('--nsis-source is required when creating')
    print(json.dumps(verify(args.output) if args.verify else create(args.output,args.nsis_source)))
