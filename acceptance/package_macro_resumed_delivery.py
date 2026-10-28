"""Copy an explicit hash-frozen public artifact specification into a new bundle.

No directory of inputs is scanned. No connection library, credential decryption,
game, provider or RPC is used. Packaging never declares the G0-G8 goal complete.
The independent resumed-goal evaluator must inspect the result afterwards.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_resumed_goal import REPORT_SPECS,TRUSTED_FROZEN_REPORTS,safe_child,render_timeline_html

KINDS={'diagnostics','public_profile','execution_record','native_release','assessment','timeline_html',
    'timeline_data','timeline_review','screenshot','native_replay','restoration_proof','regression_evidence','test_log','artifact_manifest'}
JSON_KINDS=KINDS-{'timeline_html','screenshot','native_replay','test_log'}
SINGLES={'current_diagnostics':'diagnostics','current_export':'diagnostics','current_profile':'public_profile',
    'executed_client':'execution_record','native_release':'native_release','original_profile':'public_profile',
    'restored_profile':'public_profile','restoration':'restoration_proof','current_screenshot':'screenshot',
    'G6':'assessment','G7':'assessment','G8':'assessment','G7_manifest':'artifact_manifest','regression':'regression_evidence'}
LISTS={'role_assessments':'assessment','timeline_reviews':'timeline_review'}
G7_FILES={'settlement':('settlement.png','screenshot'),'diagnostics':('diagnostics.json','diagnostics'),
    'profile':('commander-config.json','public_profile'),'replay':('natural.RA3Replay','native_replay'),
    'timeline':('macro-timeline.html','timeline_html')}
# Independently mirror the journal's normalized named-secret contract, adding
# storage wrappers that must never enter a public artifact.
SECRET_KEYS={'key','apikey','apitoken','secret','secretkey','password','authorization','accesstoken','refreshtoken',
    'credential','credentials','encryptedkey','encryptedapikey','protectedkey','dpapiblob','clientsecret','token',
    'privatekey','credentialvalue','connectionstring'}
REDACTION_FIELDS={'credentials','free_text_traits','private_native_addresses','provider_payloads',
    'raw_log_contents','unknown_event_payloads'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


@dataclass(frozen=True)
class Artifact:
    name:str
    source:Path
    kind:str
    sha256:str
    size:int
    value:object=None


def protected_path(path):
    names={p.lower() for p in path.parts};name=path.name.lower()
    return ('.codex' in names or name in ('library.json','library.v2.json','desktop-runtime-config.json','auth.json')
        or any(word in name for word in ('credential','password','dpapi','api-key','api_key','token-secret')))


def source_path(value,kind):
    path=Path(value)
    if not path.is_absolute() or protected_path(path):raise ValueError('explicit_public_source_required')
    if path.is_symlink():raise ValueError('source_symlink_rejected')
    path=path.resolve(strict=True)
    if protected_path(path) or not path.is_file():raise ValueError('protected_source_rejected')
    public_roots=[(ROOT/p).resolve() for p in ('acceptance/runs','reports','delivery','Replays')]
    external=[Path.home()/'Downloads']
    local=os.environ.get('LOCALAPPDATA')
    if local:external.append(Path(local)/'Tacticore/desktop-runtime/exports')
    if not any(path.is_relative_to(p) for p in public_roots):
        if kind!='diagnostics' or not any(path.is_relative_to(p.resolve()) for p in external):
            raise ValueError('source_outside_public_roots')
    expected='.json' if kind in JSON_KINDS else '.html' if kind=='timeline_html' else '.log' if kind=='test_log' else '.ra3replay' if kind=='native_replay' else None
    if expected and path.suffix.lower()!=expected:raise ValueError('public_artifact_suffix_mismatch')
    if kind=='screenshot' and path.suffix.lower() not in ('.png','.jpg','.jpeg'):raise ValueError('public_screenshot_suffix')
    if kind=='public_profile' and not ('profile' in path.stem.lower() or path.name=='commander-config.json'):
        raise ValueError('public_profile_snapshot_name_required')
    if kind=='diagnostics' and not ('diagnostic' in path.stem.lower() or path.parent.name=='exports'):
        raise ValueError('public_diagnostics_name_required')
    return path


def no_private_payload(value):
    if isinstance(value,dict):
        if {'connections','commanders'}<=set(value):raise ValueError('raw_library_not_public')
        for key,item in value.items():
            normalized=''.join(c.lower() for c in key if c.isalnum())
            if normalized in SECRET_KEYS and item not in (None,False,'',[],{}):raise ValueError('private_payload_rejected')
            no_private_payload(item)
    elif isinstance(value,list):
        for item in value:no_private_payload(item)


def validate_payload(path,kind):
    if kind in JSON_KINDS:
        value=load(path)
        if not isinstance(value,dict):raise ValueError('public_json_object_required')
        no_private_payload(value)
        if kind=='diagnostics' and (value.get('kind')!='tacticore_redacted_diagnostics' or value.get('redacted') is not True
                or not value.get('run_id') or not isinstance(value.get('binding'),dict)
                or not isinstance(value.get('redaction'),dict) or any(value['redaction'].get(k) is not False for k in REDACTION_FIELDS)):
            raise ValueError('redacted_diagnostics_required')
        if kind=='public_profile' and not ({'profile_id','revision','draft','effective'}<=set(value)
                or (path.name=='commander-config.json' and {'profile_id','revision','effective_hash'}<=set(value)
                    and value.get('credential_material_included') is False)):
            raise ValueError('public_profile_shape')
        if kind=='execution_record' and not {'executable_sha256','frontend','profile_revision'}<=set(value):raise ValueError('executed_client_shape')
        if kind=='native_release' and (value.get('kind')!='macro_policy_native_release' or not {'binding','run_id','native_release_verified'}<=set(value)):
            raise ValueError('native_release_shape')
        if kind=='assessment' and value.get('kind') not in {s[0] for s in REPORT_SPECS.values()}:raise ValueError('public_assessment_kind')
        if kind=='timeline_data' and (value.get('kind')!='recorded_macro_timeline' or not isinstance(value.get('events'),list)):
            raise ValueError('public_timeline_data_shape')
        if kind=='timeline_review' and (not str(value.get('kind','')).startswith('actual_') or not isinstance(value.get('files'),dict)):
            raise ValueError('actual_timeline_review_shape')
        if kind=='restoration_proof' and not {'restore_required','original_revision','original_effective_hash'}<=set(value):
            raise ValueError('restoration_proof_shape')
        if kind=='regression_evidence' and (value.get('kind')!='macro_regression_evidence' or value.get('schema_version')!=1
                or not isinstance(value.get('sources'),dict) or set(value.get('logs',{}))!={'macro','host','strategy','ui'}):
            raise ValueError('regression_evidence_shape')
        if kind=='artifact_manifest' and not isinstance(value.get('files'),dict):raise ValueError('public_artifact_manifest_shape')
        return value
    if kind=='screenshot':
        with path.open('rb') as stream:signature=stream.read(12)
        if not (signature.startswith(b'\x89PNG\r\n\x1a\n') or signature.startswith(b'\xff\xd8\xff')):raise ValueError('screenshot_signature')
    elif kind=='timeline_html':
        html=path.read_text(encoding='utf8')
        if '<script id="timeline-data" type="application/json">' not in html or '<button' not in html or 'requestAnimationFrame' not in html:
            raise ValueError('playable_timeline_html_required')
    elif kind=='test_log':
        text=path.read_text(encoding='utf-8-sig')
        if not ((re.search(r'Ran\s+\d+\s+tests?\s+in\s+',text) and text.rstrip().endswith('OK') and 'FAILED (' not in text)
                or re.search(r'(?m)^[ \t]*(?:ℹ|#)?[ \t]*fail[ \t]+0[ \t]*$',text)):
            raise ValueError('passed_test_log_required')
    return None


def flat_name(name):
    if (type(name) is not str or not 1<=len(name)<=160 or name.startswith('.') or name[-1:] in (' ','.')
            or any(ord(c)<32 or c in '/\\:' for c in name) or Path(name).name!=name
            or name.casefold() in ('manifest.json','readme.txt')
            or name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}):
        raise ValueError('flat_public_artifact_name_required')
    return name


def preflight(spec_path):
    spec_path=Path(spec_path).resolve(strict=True)
    if protected_path(spec_path) or not spec_path.is_relative_to((ROOT/'reports').resolve()):raise ValueError('public_spec_in_reports_required')
    before=digest(spec_path);spec=load(spec_path)
    if (set(spec)!={'schema_version','kind','current_run_id','current_session_id','artifacts','required'}
            or spec['schema_version']!=1 or spec['kind']!='macro_public_delivery_spec'
            or type(spec['current_run_id']) is not str or not spec['current_run_id']
            or type(spec['current_session_id']) is not str or not spec['current_session_id']
            or not isinstance(spec['artifacts'],list) or not 1<=len(spec['artifacts'])<=256):
        raise ValueError('public_delivery_spec_schema')
    artifacts={};names=set();total=0
    # Validate location and type before reading or hashing each source. Do not
    # inspect a protected library to decide whether its contents look public.
    for row in spec['artifacts']:
        if set(row)!={'name','source','type','sha256','bytes'} or row['type'] not in KINDS:raise ValueError('public_artifact_fields')
        name=flat_name(row['name'])
        if name.casefold() in names:raise ValueError('duplicate_artifact_name')
        names.add(name.casefold());source=source_path(row['source'],row['type'])
        if (type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',row['sha256'])
                or type(row['bytes']) is not int or not 0<row['bytes']<=64*1024*1024):
            raise ValueError('public_artifact_hash_and_size_required')
        if source.stat().st_size!=row['bytes'] or digest(source)!=row['sha256']:raise ValueError('public_source_changed')
        value=validate_payload(source,row['type']);total+=row['bytes']
        artifacts[name]=Artifact(name,source,row['type'],row['sha256'],row['bytes'],value)
    if total>256*1024*1024:raise ValueError('public_delivery_size_limit')
    required=spec['required']
    if not isinstance(required,dict) or set(required)!=set(SINGLES)|set(LISTS)|{'G7_artifacts'}:raise ValueError('required_delivery_bindings')
    def entry(name,kind):
        if type(name) is not str or name not in artifacts or artifacts[name].kind!=kind:raise ValueError('required_public_artifact_missing')
        return artifacts[name]
    for key,kind in SINGLES.items():entry(required[key],kind)
    for key in ('current_profile','original_profile','restored_profile'):
        if not {'profile_id','revision','draft','effective'}<=set(entry(required[key],'public_profile').value):
            raise ValueError('current_public_profile_snapshot_required')
    for key,kind in LISTS.items():
        if not isinstance(required[key],list) or not 1<=len(required[key])<=3 or len(set(required[key]))!=len(required[key]):
            raise ValueError('required_public_artifact_list')
        for name in required[key]:entry(name,kind)
    for stage in ('G6','G7','G8'):
        a=entry(required[stage],'assessment')
        if a.value.get('kind')!=REPORT_SPECS[stage][0] or a.sha256!=TRUSTED_FROZEN_REPORTS[stage]:
            raise ValueError('approved_frozen_stage_artifact_required')
    current=entry(required['current_diagnostics'],'diagnostics');export=entry(required['current_export'],'diagnostics')
    if (current.sha256!=export.sha256 or current.value['run_id']!=spec['current_run_id']
            or current.value['binding'].get('session_id')!=spec['current_session_id']):raise ValueError('actual_download_export_binding')
    release=entry(required['native_release'],'native_release').value
    if release['run_id']!=spec['current_run_id'] or release['binding'].get('session_id')!=spec['current_session_id']:
        raise ValueError('current_release_binding')
    sources={(a.source,a.sha256):a for a in artifacts.values()}
    role_pairs=set()
    for name in required['role_assessments']:
        a=entry(name,'assessment')
        if a.value.get('kind')!=REPORT_SPECS['role'][0] or not a.value.get('run_id') or not a.value.get('session_id'):
            raise ValueError('schema9_role_assessment_required')
        diagnostics=[r for r in artifacts.values() if r.kind=='diagnostics'
            and a.value.get('evidence',{}).get(str(r.source))==r.sha256
            and r.value.get('run_id')==a.value['run_id']
            and r.value.get('binding',{}).get('session_id')==a.value['session_id']]
        if len({r.source for r in diagnostics})<2 or len({r.sha256 for r in diagnostics})!=1:
            raise ValueError('role_actual_download_export_pair_missing')
        role_pairs.add((a.value['session_id'],a.value['run_id']))
    for name in required['timeline_reviews']:
        a=entry(name,'timeline_review');review=a.value;folder=a.source.parent
        for referenced,description in review['files'].items():
            source=safe_child(folder,referenced);expected=description if type(description) is str else description['sha256']
            if (source,expected) not in sources:raise ValueError('timeline_review_artifact_missing')
        html=next((r for r in artifacts.values() if r.source==folder/'macro-timeline.html' and r.kind=='timeline_html'),None)
        data=next((r for r in artifacts.values() if r.source==folder/'macro-timeline.json' and r.kind=='timeline_data'),None)
        if html is None or data is None or (data.value.get('session_id'),data.value.get('run_id')) not in role_pairs:
            raise ValueError('role_timeline_binding')
        if html.source.read_text(encoding='utf8')!=render_timeline_html(data.value):raise ValueError('role_timeline_player_changed')
    g7=entry(required['G7'],'assessment').value;historical=entry(required['G7_manifest'],'artifact_manifest')
    if g7['evidence'].get(str(historical.source))!=historical.sha256:raise ValueError('G7_manifest_not_bound')
    if not isinstance(required['G7_artifacts'],dict) or set(required['G7_artifacts'])!=set(G7_FILES):raise ValueError('G7_public_artifact_bindings')
    for key,(old_name,kind) in G7_FILES.items():
        a=entry(required['G7_artifacts'][key],kind);proof=historical.value['files'].get(old_name,{})
        if proof.get('sha256')!=a.sha256 or proof.get('bytes')!=a.size:raise ValueError('G7_same_match_artifact_changed')
    regression=entry(required['regression'],'regression_evidence').value
    for name,row in regression['logs'].items():
        source=source_path(row['path'],'test_log');a=sources.get((source,row['sha256']))
        if a is None or a.kind!='test_log':raise ValueError('regression_test_log_missing')
    if digest(spec_path)!=before:raise ValueError('delivery_spec_changed_during_preflight')
    return spec,artifacts,before


def package(spec_path,out):
    out=Path(out).resolve()
    if out.exists() or not out.is_relative_to((ROOT/'delivery').resolve()) or out==(ROOT/'delivery').resolve():
        raise ValueError('fresh_delivery_child_required')
    spec,artifacts,spec_sha=preflight(spec_path)
    out.mkdir(parents=True)
    for a in artifacts.values():
        if digest(a.source)!=a.sha256 or a.source.stat().st_size!=a.size:raise ValueError('public_source_changed_before_copy')
        target=out/a.name;shutil.copy2(a.source,target)
        if digest(target)!=a.sha256 or digest(a.source)!=a.sha256 or target.stat().st_size!=a.size:
            raise ValueError('public_source_changed_during_copy')
    timelines=[a.name for a in artifacts.values() if a.kind=='timeline_html']
    readme=('弈核宏观指挥 · 本机公开证据交付\n\n'
        '本包只复制显式列出的公开文件；manifest.json列出逐文件SHA256与大小。打包成功不等于全部G0–G8验收完成。'
        '请以另行生成的独立整体评估报告核对最终结论；本清单不自行授予执行能力。\n\n'
        '可离线打开的过程时间线：\n'+''.join('- '+name+'\n' for name in timelines)+'\n'
        '模型负责宏观意图，原生AI继续负责选兵、寻路、阵型、局部目标、开火和技能。'
        '建造/生产证据有队列、期限和未达标边界；任务激活、推进及回执不保证任务成功。'
        '范围为本机固定RA3 1.12、TemplePrime、P3苏军及逐项授予的接口，不授予任意地图、选兵或坐标。\n\n'
        '研究延续run不代表新的独立完整对局，也不能计作新的胜率样本。'
        '完整自然对局与描述性比较使用已审冻结G7/G8材料，胜负及样本限制以报告为准，不证明胜率提升。\n\n'
        '原生录像不保证重现外部宏观指令；原生录像保真仍未验证。时间线不播放单位动画。'
        '客户端的独立安装及跨机器便携性未验收，不作为本机目标的新增门槛。'
        '本包不复制连接Library、API密钥或DPAPI凭据；脱敏诊断与公开配置单独列出。\n')
    (out/'README.txt').write_text(readme,encoding='utf8')
    files={p.name:dict(sha256=digest(p),bytes=p.stat().st_size) for p in sorted(out.iterdir()) if p.is_file()}
    manifest=dict(schema_version=1,kind='macro_local_public_evidence_delivery',current_run_id=spec['current_run_id'],
        current_session_id=spec['current_session_id'],formal_goal_complete=False,
        completion_status='requires_independent_G0_G8_assessment',native_replay_fidelity_verified=False,
        client_cross_machine_portability_verified=False,credential_material_included=False,unit_micro_control=False,
        specification_sha256=spec_sha,required=spec['required'],
        artifacts={a.name:dict(type=a.kind,source_name=a.source.name,source_sha256=a.sha256) for a in artifacts.values()},files=files)
    if digest(spec_path)!=spec_sha or any(digest(out/a.name)!=a.sha256 for a in artifacts.values()):
        raise ValueError('delivery_changed_before_publication')
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return dict(output=str(out),files=len(files),bytes=sum(r['bytes'] for r in files.values()),
        manifest_sha256=digest(out/'manifest.json'),formal_goal_complete=False,credentials_read=False,game_access=False,model_calls=0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(a.spec,a.output)));return 0


if __name__=='__main__':raise SystemExit(main())
