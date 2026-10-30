"""Fixed next-candidate source/input closure. No process or native execution."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import types
import uuid

ROOT=Path(__file__).resolve().parents[1]
KIND='strategic_source_closure_v1'
REPORT_SHA='81ac4d4890ebe8bda7d0541ae8799bca324acd8e9fbffece564a4993fab052da'
PACKAGE_SHA='66025609e788ed18f8eb55b1722e6c197a373f387137b69e6b04118d0a5278f0'
VALIDATOR_SHA='16131f30a9bed96462eddc420790fadd775cb8a170979b1903fb2a0f7a84538c'
ORIGINAL_NATIVE={
    'native.cpp':'f0528ca468f5a24ca63b5b6d630d5e13a4ed68c5c04b6efe3d25d4310902062b',
    'host.cpp':'e509acbc3fbdc2fbb277f2a856b1ef425bd774939c52a622bd2b877526f3efcf',
    'shared.h':'a3f16802163aa5d77f25831cde3f0977a6155b0b68557aa601dc93b82434b0d8'}
RELATIVE_SOURCES=(
    'native-ai/macro-policy-runtime-v2/shared.h','native-ai/macro-policy-runtime-v2/native.cpp',
    'native-ai/macro-policy-runtime-v2/host.cpp','native-ai/macro-policy-runtime-v2/client.py',
    'native-ai/macro_group_role_observation.py','native-ai/macro_observation.py',
    'native-ai/read_script_flags.py','native-ai/read_selected_personality.py',
    'production/session_package.py','production/observe_production.py',
    'native-ai/strategic_transport_profile_v1.py','native-ai/strategic_transport_client_v1.py',
    'native-ai/strategic_expansion_observation_v1.py','native-ai/stage_strategic_expansion_v1.py',
    'native-ai/strategic_source_closure_v1.py','native-ai/compiled_stock_expansion_validator_v1.py',
    'native-ai/strategic_expansion_runtime_reader_v2.py',
    'native-ai/stage_commanders.py','native-ai/stage_macro_group_roles.py','native-ai/stage_macro_probe.py',
    'native-ai/validate_side_imports.py','native-ai/macro-policy-runtime-v2/build.py',
    'reference/Ra3-Copilot/unit-codes/tools/sage_hash.py',
    'native-ai/stage_macro_base_defense.py','native-ai/stage_macro_regions.py','native-ai/stage_macro_policy.py',
    'native-ai/read_map_waypoints.py','native-ai/macro_expansion_contract.py',
    'native-ai/verify_group_role_observer.py','native-ai/verify_area_defense_observer.py','probe.py',
    'native-ai/build_commander_package.py','native-ai/macro_build_observation.py','visibility/native_read.py')
EXTERNAL_SOURCE=Path('E:/RA3Modding/Analysis/Remix037/manifest.py')
LOADED_HELPER_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
UNSPECIFIED=object()


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def plain(path):
    path=Path(path).absolute()
    if path.resolve()!=path or not path.is_file():raise ValueError('strategic_closure_plain_file_required')
    for item in (path,*path.parents):
        if item.is_symlink() or getattr(item.lstat(),'st_file_attributes',0)&0x400:raise ValueError('strategic_closure_reparse_input')
    return path


def source_paths():return [*(ROOT/name for name in RELATIVE_SOURCES),EXTERNAL_SOURCE]


def assert_pins(pins):
    if type(pins) is not dict or any(sha(plain(path))!=expected for path,expected in pins.items()):
        raise ValueError('strategic_closure_input_changed')


def no_shadow_header(directory):
    if any((Path(directory)/name).exists() for name in ('profile.h','profile.h.gch','shared.h.gch','native.cpp.gch','host.cpp.gch')):
        raise ValueError('strategic_closure_shadow_include')


def canonical(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))


def strict_json(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            if key in result:raise ValueError('strategic_closure_duplicate_json_key')
            result[key]=value
        return result
    def constant(_):raise ValueError('strategic_closure_nonfinite_json')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=constant)


class SourceClosure:
    def __init__(self,entry_sha,expected=UNSPECIFIED):
        if expected is not UNSPECIFIED and type(expected) is not dict:raise ValueError('strategic_closure_source_map_required')
        self.raw={str(plain(path)):plain(path).read_bytes() for path in source_paths()}
        self.pins={path:hashlib.sha256(raw).hexdigest() for path,raw in self.raw.items()}
        if expected is not UNSPECIFIED and expected!=self.pins:raise ValueError('strategic_closure_source_set_or_hash')
        if self.pins[str(Path(__file__).resolve())]!=LOADED_HELPER_SHA or self.pins[str(ROOT/'native-ai/strategic_transport_profile_v1.py')]!=entry_sha:
            raise ValueError('strategic_closure_loaded_source_changed')
        for name,expected_hash in ORIGINAL_NATIVE.items():
            if self.pins[str(ROOT/'native-ai/macro-policy-runtime-v2'/name)]!=expected_hash:raise ValueError('strategic_closure_original_native_changed')
        if self.pins[str(ROOT/'native-ai/compiled_stock_expansion_validator_v1.py')]!=VALIDATOR_SHA:
            raise ValueError('strategic_closure_decoder_not_frozen')
        self._check_import_inventory();self.check()

    def _check_import_inventory(self):
        folders=(ROOT/'native-ai',ROOT/'production',ROOT/'visibility',ROOT,
            ROOT/'reference/Ra3-Copilot/unit-codes/tools',EXTERNAL_SOURCE.parent)
        for path,raw in self.raw.items():
            if Path(path).suffix!='.py':continue
            for node in ast.walk(ast.parse(raw,filename=path)):
                names=[row.name.split('.')[0] for row in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
                for name in names:
                    dependency=next((folder/(name+'.py') for folder in folders if (folder/(name+'.py')).is_file()),None)
                    if dependency is not None and str(dependency.resolve()) not in self.pins:
                        raise ValueError('strategic_closure_unlisted_local_import_'+name)

    def check(self):
        no_shadow_header(ROOT/'native-ai/macro-policy-runtime-v2');assert_pins(self.pins)

    def load_current_decoder(self):
        self.check();path=ROOT/'native-ai/compiled_stock_expansion_validator_v1.py'
        name='_current_compiled_strategy_'+uuid.uuid4().hex
        module=types.ModuleType(name);module.__file__=str(path);module.__package__=''
        sys.modules[name]=module
        try:
            # Current original source captured before execution, never a copied
            # archive or cached module. Dataclasses need the temporary module.
            exec(compile(self.raw[str(path)],str(path),'exec'),module.__dict__)
            self.check()
        except BaseException:sys.modules.pop(name,None);raise
        return module


def package_paths(directory):
    paths=[directory/'build-report.json',directory/'TFMacroProbe.big',directory/'package/data/gamestrings.csf']
    for family in ('baseline','package'):
        for stem in ('mod','mod_M','mod_L'):
            for ext in ('manifest','bin','imp','relo'):paths.append(directory/family/'data'/(stem+'.'+ext))
    return paths


class PackageClosure:
    def __init__(self,report_path,sources,expected_inputs=UNSPECIFIED):
        if expected_inputs is not UNSPECIFIED and type(expected_inputs) is not dict:raise ValueError('strategic_closure_input_map_required')
        self.sources=sources;self.report_path=plain(report_path);self.directory=self.report_path.parent
        self.raw_report=self.report_path.read_bytes()
        if hashlib.sha256(self.raw_report).hexdigest()!=REPORT_SHA:raise ValueError('strategic_closure_fixed_report_required')
        self.report=strict_json(self.raw_report)
        self.input_pins={str(plain(path)):sha(path) for path in package_paths(self.directory)}
        self.input_pins[str(self.report_path)]=hashlib.sha256(self.raw_report).hexdigest()
        if self.input_pins[str(self.directory/'TFMacroProbe.big')]!=PACKAGE_SHA:raise ValueError('strategic_closure_fixed_package_required')
        sources.check();assert_pins(self.input_pins)
        self.decoder=sources.load_current_decoder()
        try:
            self.game_root=Path('E:/RedRar3')
            paths,configs=self.decoder.config_archives(self.game_root)
            self.stock_paths=tuple(sorted(set(str(plain(path)) for path in [*paths,*configs])))
            self.input_pins.update({path:sha(path) for path in self.stock_paths})
            compiler=plain(ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe')
            self.compiler=compiler;self.compiler_sha256=sha(compiler);self.input_pins[str(compiler)]=self.compiler_sha256
            if expected_inputs is not UNSPECIFIED and expected_inputs!=self.input_pins:raise ValueError('strategic_closure_input_set_or_hash')
            self.validation=self.recompute()
        except BaseException:self.close();raise

    def check(self):
        self.sources.check();assert_pins(self.input_pins)
        paths,configs=self.decoder.config_archives(self.game_root)
        if tuple(sorted(set(str(plain(path)) for path in [*paths,*configs])))!=self.stock_paths:
            raise ValueError('strategic_closure_stock_inventory_changed')

    def recompute(self):
        self.check();value=self.decoder.validate_package(self.directory,self.game_root,expected_package_sha256=PACKAGE_SHA);self.check()
        if (value.get('kind')!='compiled_stock_expansion_definition_validation_v1' or value.get('package_sha256')!=PACKAGE_SHA
                or value.get('validator_source_sha256')!=VALIDATOR_SHA or value.get('compiled_fields_verified') is not True
                or value.get('compiled_inherited_registrations_verified') is not True):raise ValueError('strategic_closure_actual_compiled_validation')
        if any(self.input_pins.get(str(plain(path)))!=expected for path,expected in value['stock_evidence']['source_pins'].items()):
            raise ValueError('strategic_closure_stock_evidence_changed')
        qualities=value.get('qualities')
        if type(qualities) is not list or [row.get('quality') for row in qualities]!=['high','medium','low']:
            raise ValueError('strategic_closure_compiled_quality_set')
        wanted=self.report['consumers'][-1]['flag']
        for row in qualities:
            flags=[h['fields']['flag'] for h in row['state']['heuristics'] if h['kind']=='scripted_flag']
            if flags!=[wanted] or row['state']['fields']['tactic']['enum']!=8 or row['state']['fields']['tactic']['end_if_state_turns_off'] is not False:
                raise ValueError('strategic_closure_compiled_flag_binding')
        return value

    def finish(self):
        value=self.recompute()
        if canonical(value)!=canonical(self.validation):raise ValueError('strategic_closure_validation_changed')
        return value

    def close(self):
        if hasattr(self,'decoder'):sys.modules.pop(self.decoder.__name__,None)
