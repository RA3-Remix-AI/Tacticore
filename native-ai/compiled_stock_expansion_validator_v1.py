"""Exact-file compiled stock expansion validator, no XML trust or game calls.

Raw BIG/RefPack/manifest algorithms follow the repository's existing offline
asset readers. This bounded implementation retains import/relocation evidence
and can be pinned as one small source for later candidate admission.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import struct

ROOT=Path(__file__).resolve().parents[1]
PACKAGE_SHA='66025609e788ed18f8eb55b1722e6c197a373f387137b69e6b04118d0a5278f0'
STOCK_STATE='AIStrategicStateDefinition:SovietExpansion_MEDIUM'
STOCK_PROFILE='AIPersonalityDefinition:1SovietBalanced'
PREFIX='5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3'
NEW_STATE='AIStrategicStateDefinition:'+PREFIX+'_StockExpansionPreference'
NEW_PROFILE='AIPersonalityDefinition:'+PREFIX+'_Soviet'
FLAG='/'+PREFIX+'_expand'
STOCK_PAYLOAD_SHA='311b783b143ad0056ec60cf37b7ce2d7992fcfa1fcfa4dbc52eea913f08fda97'
STOCK_PROFILE_SHA='be811fc50549527075cae9d984894848cd6c18db2a658cf7ad35c60c9bccd685'
EXE_SHA='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
LAYOUT_PINS={
    0x8d3555:'8b47108b503c8bcec1e10403ce8b448a0483f80e',
    0x8d3e68:'8b46548b4e508b51108bf8c1e70403f88b423c807cb841007428',
    0x8d3e92:'e8f906fbff',
    0x8d3ea5:'e86681feff',
    0x889bf0:'8bc18b40048b5008518bcc52e80f2dc4ff',
}
STOCK_KEY=(0x242ff6d4,0x7b9eee56)
NEW_KEY=(0x242ff6d4,0x0e48be4d)
TARGET_KEY=(0x373e10fa,0x5a92f90e)
MICRO_KEY=(0x9077f377,0x1cdf61ab)
HEURISTICS={0x809071b7:('scripted_flag',None),0x7ee4c9b4:('opening_complete',8),
    0xe40ebc24:('time_since_last_expansion',12),0x45c8cca2:('not_building',44),
    0x67b985a7:('enemy_nearby',20),0x38b3fd56:('all_nearby_nodes_full',4),
    0x874a6e09:('resource_node_share',12),0x51fb6d92:('constant',8)}
CORE_ORDER=['opening_complete','time_since_last_expansion','not_building','enemy_nearby',
            'all_nearby_nodes_full','resource_node_share']


def reject(reason):raise ValueError('compiled_expansion_'+reason)
def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):digest.update(data)
    return digest.hexdigest()
def u32(raw,at):
    if type(at) is not int or at<0 or at+4>len(raw):reject('word_extent')
    return struct.unpack_from('<I',raw,at)[0]
def f32(raw,at):
    value=struct.unpack('<f',struct.pack('<I',u32(raw,at)))[0]
    if not math.isfinite(value):reject('nonfinite_field')
    return value
def boolean(raw,at):
    if not 0<=at<len(raw) or raw[at] not in (0,1):reject('boolean_field')
    return bool(raw[at])
def extent(raw,at,size):
    if type(at) is not int or at%4 or at<0 or size<0 or at+size>len(raw):reject('aligned_extent')
    return raw[at:at+size]
def offsets(raw):
    if len(raw)%4 or not raw or u32(raw,len(raw)-4)!=0xffffffff:reject('fixup_terminator')
    values=[u32(raw,i) for i in range(0,len(raw)-4,4)]
    if len(set(values))!=len(values) or any(value%4 for value in values):reject('fixup_duplicate_or_alignment')
    return values


def native_layout_proof(path):
    raw=Path(path).read_bytes()
    if sha(raw)!=EXE_SHA:reject('exact_native_image_required')
    pe=u32(raw,60)
    if raw[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',raw,pe+4)[0]!=0x14c:reject('native_x86_pe')
    section=pe+24+struct.unpack_from('<H',raw,pe+20)[0];base=u32(raw,pe+52)
    sections=[struct.unpack_from('<IIII',raw,section+40*i+8) for i in range(struct.unpack_from('<H',raw,pe+6)[0])]
    checked=[]
    for address,expected in LAYOUT_PINS.items():
        size=len(expected)//2;value=None
        for vs,rva,extent_,offset in sections:
            if base+rva<=address and address+size<=base+rva+min(vs,extent_):value=raw[offset+address-base-rva:offset+address-base-rva+size]
        if value!=bytes.fromhex(expected):reject('native_layout_signature')
        checked.append(dict(address=hex(address),bytes=expected))
    return dict(executable_sha256=EXE_SHA,pins=checked,tactic_stride_bytes=68,
        tactic_array_offset='0x3c',tactic_enum_offset=4,end_if_state_turns_off_offset='0x41',
        zero_score_conditional_cleanup_call='0x8bc010',script_flag_string_pointer_offset=8,
        static_only=True,native_calls=0)


def unpack(raw):
    if len(raw)<2 or raw[1]!=0xfb or raw[0]&0x7e!=0x10:return raw
    width=4 if raw[0]&0x80 else 3;cursor=2+width*(2 if raw[0]&1 else 1)
    if len(raw)<cursor:reject('refpack_header')
    expected=int.from_bytes(raw[2:2+width],'big')
    if expected>128*1024*1024:reject('refpack_bound')
    out=bytearray();done=False
    while cursor<len(raw):
        control=raw[cursor];cursor+=1;length=0;distance=0
        extra=1 if control<0x80 else 2 if control<0xc0 else 3 if control<0xe0 else 0
        if cursor+extra>len(raw):reject('refpack_truncated')
        if control<0x80:
            value=raw[cursor];cursor+=1;literal=control&3;length=((control>>2)&7)+3;distance=((control&0x60)<<3)+value+1
        elif control<0xc0:
            a,b=raw[cursor:cursor+2];cursor+=2;literal=a>>6;length=(control&0x3f)+4;distance=((a&0x3f)<<8)+b+1
        elif control<0xe0:
            a,b,d=raw[cursor:cursor+3];cursor+=3;literal=control&3;length=((control&12)<<6)+d+5;distance=((control&16)<<12)+(a<<8)+b+1
        elif control<0xfc:literal=((control&31)<<2)+4
        else:literal=control&3;done=True
        if cursor+literal>len(raw) or len(out)+literal+length>expected:reject('refpack_extent')
        out.extend(raw[cursor:cursor+literal]);cursor+=literal
        if length:
            if not 1<=distance<=len(out):reject('refpack_distance')
            begin=len(out)-distance
            if length<=distance:out.extend(out[begin:begin+length])
            else:out.extend((out[begin:]*((length+distance-1)//distance))[:length])
        if done:break
    if not done or cursor!=len(raw) or len(out)!=expected:reject('refpack_end')
    return bytes(out)


class Archive:
    def __init__(self,path):
        self.path=Path(path);self.size=self.path.stat().st_size;self.index={}
        with self.path.open('rb') as stream:
            raw=stream.read(16)
            if len(raw)!=16 or raw[:4] not in (b'BIG4',b'BIGF'):reject('big_header')
            if struct.unpack_from('<I',raw,4)[0]!=self.size:reject('big_size')
            count,end=struct.unpack_from('>II',raw,8)
            if not 1<=count<=200000 or not 16<=end<=min(self.size,32*1024*1024):reject('big_index_bound')
            index=stream.read(end-16);at=0;intervals=[]
            for _ in range(count):
                if at+9>len(index):reject('big_index_truncated')
                begin,size=struct.unpack_from('>II',index,at);at+=8
                try:stop=index.index(0,at,min(len(index),at+1025));name=index[at:stop].decode('ascii').replace('\\','/').lower()
                except (ValueError,UnicodeError):reject('big_entry_name')
                at=stop+1
                if (not name or ':' in name or any(p in ('','.','..') for p in name.split('/'))
                        or name in self.index or begin<end or begin+size>self.size or size>128*1024*1024):reject('big_entry_extent')
                self.index[name]=(begin,size)
                if size:intervals.append((begin,begin+size))
            if index[at:] not in (b'',b'L219\0\0\0\0',b'L280\x15\x05\0\0',b'L280\x15\x05\0\x01'):reject('big_index_suffix')
            intervals.sort()
            if any(a[1]>b[0] for a,b in zip(intervals,intervals[1:])):reject('big_overlap')

    def entry(self,name):
        name=name.replace('\\','/').lower()
        if name not in self.index:reject('big_required_entry_missing')
        at,size=self.index[name]
        with self.path.open('rb') as stream:stream.seek(at);packed=stream.read(size)
        if len(packed)!=size:reject('big_read_truncated')
        return unpack(packed)


@dataclass(frozen=True)
class Asset:
    name:str
    key:tuple
    flags:int
    payload:bytes
    imports:bytes
    relocations:bytes
    refs:tuple
    type_hash:int
    instance_hash:int


def manifest(raw):
    if len(raw)<48:reject('manifest_header')
    h=struct.unpack_from('<12I',raw);count=h[3];refs=48+48*count;names=refs+h[8]+h[9];sources=names+h[10]
    if count>200000 or sources+h[11]!=len(raw):reject('manifest_extent')
    def name(at):
        if not 0<=at<h[10]:reject('manifest_name_offset')
        try:return raw[names+at:raw.index(0,names+at,names+h[10])].decode('utf-8')
        except (ValueError,UnicodeError):reject('manifest_name')
    result=[];binary=imp=relo=4;seen=set();seen_names=set()
    for i in range(count):
        a=struct.unpack_from('<12I',raw,48+48*i);label=name(a[6]);key=(a[0],a[1])
        if key in seen or label in seen_names or a[4]+a[5]*8>h[8]:reject('manifest_duplicate_or_refs')
        seen.add(key);seen_names.add(label);r=tuple(struct.unpack_from('<II',raw,refs+a[4]+8*j) for j in range(a[5]))
        result.append(dict(name=label,key=key,type_hash=a[2],instance_hash=a[3],flags=a[11],refs=r,binary_offset=binary,binary_size=a[8],
            imp_offset=imp,imp_size=a[10],relo_offset=relo,relo_size=a[9]))
        binary+=a[8];imp+=a[10];relo+=a[9]
    return result


def stream_assets(archive,stem):
    parts={ext:archive.entry(stem+'.'+ext) for ext in ('manifest','bin','imp','relo')}
    result={}
    for row in manifest(parts['manifest']):
        def data(ext,offset,size):
            at,n=row[offset],row[size]
            if at+n>len(parts[ext]):reject('asset_extent')
            return parts[ext][at:at+n]
        result[row['name']]=Asset(row['name'],row['key'],row['flags'],data('bin','binary_offset','binary_size'),
            data('imp','imp_offset','imp_size'),data('relo','relo_offset','relo_size'),row['refs'],row['type_hash'],row['instance_hash'])
    return result,parts


def reference(asset,at):
    index=u32(asset.payload,at)
    if at not in offsets(asset.imports) or not 1<=index<=len(asset.refs):reject('reference_fixup_or_index')
    return asset.refs[index-1]


def decode_heuristics(asset):
    raw=asset.payload;count,start=u32(raw,4),u32(raw,8)
    if not 1<=count<=16:reject('heuristic_count')
    extent(raw,start,4*count);locations=[u32(raw,start+4*i) for i in range(count)]
    if len(set(locations))!=len(locations) or locations!=sorted(locations):reject('heuristic_alias_or_order')
    rows=[]
    for index,at in enumerate(locations):
        kind=u32(raw,at)
        if kind not in HEURISTICS:reject('unsupported_heuristic')
        name,size=HEURISTICS[kind];fields={}
        if name=='scripted_flag':
            length,chars=u32(raw,at+4),u32(raw,at+8)
            if length!=len(FLAG.encode()) or chars!=at+12:reject('flag_string_layout')
            value=extent(raw,chars,(length+1+3)//4*4)
            if value[:length+1]!=FLAG.encode()+b'\0' or any(value[length+1:]):reject('flag_string_exact')
            size=12+len(value);fields=dict(flag=value[:length].decode())
        else:
            extent(raw,at,size)
            if name=='opening_complete':fields=dict(complete=boolean(raw,at+4))
            elif name=='time_since_last_expansion':fields=dict(seconds=f32(raw,at+4),past=boolean(raw,at+8))
            elif name=='not_building':fields=dict(kindof_words=[hex(u32(raw,at+4+4*i)) for i in range(9)],pass_if_building=boolean(raw,at+40))
            elif name=='enemy_nearby':fields=dict(distance=f32(raw,at+4),minimum_enemy_value=u32(raw,at+8),enemy_filter_pointer=u32(raw,at+12),enemy_nearby=boolean(raw,at+16))
            elif name=='resource_node_share':fields=dict(percent_of_fair_share=f32(raw,at+4),above=boolean(raw,at+8))
            elif name=='constant':fields=dict(weight=f32(raw,at+4))
        expected_end=locations[index+1] if index+1<len(locations) else len(raw)
        if at+size!=expected_end:reject('heuristic_span_or_hidden_bytes')
        rows.append(dict(kind=name,type_hash=hex(kind),offset=at,size=size,fields=fields,raw=raw[at:at+size]))
    return start,rows


def decode_state_fields(asset):
    raw=asset.payload
    if asset.flags!=0 or len(raw)<0x130:reject('state_native_layout')
    # The complete fixed stock tactic/team region is compared independently
    # below. Named fields here are actual binary values, not XML defaults.
    if (u32(raw,0x30),u32(raw,0x34),u32(raw,0x38),u32(raw,0x3c))!=(1,0x44,1,0x4c):reject('state_target_or_tactic_array')
    if (u32(raw,0x84),u32(raw,0x88),u32(raw,0x104),u32(raw,0x108))!=(1,0x90,1,0x120):reject('team_or_create_array')
    return dict(max_targets=u32(raw,0xc),max_running_copies=u32(raw,u32(raw,0x10)),
        target=dict(reference=[hex(n) for n in reference(asset,0x44)],priority=u32(raw,0x48)),
        tactic=dict(id_hash=hex(u32(raw,0x4c)),enum=u32(raw,0x50),end_behavior_enum=u32(raw,0x54),
            disband_after_retreat_team_size=u32(raw,0x58),aesthetics_idle_seconds=f32(raw,0x5c),
            aesthetics_min_harvester_distance=f32(raw,0x60),difficulty_mask=u32(raw,0x64),distance=f32(raw,0x68),
            combat_leash_slack=f32(raw,0x6c),target_disposition_raw=hex(u32(raw,0x70)),
            gather_waypoint_pointer=u32(raw,0x74),update_seconds=f32(raw,0x78),
            target_base_criteria_pointer=u32(raw,0x7c),home_base_criteria_pointer=u32(raw,0x80),
            targetless=boolean(raw,0x8c),end_if_state_turns_off=boolean(raw,0x8d),
            use_aesthetics_manager=boolean(raw,0x8e),use_transports=boolean(raw,0x8f)),
        team=dict(min_units=u32(raw,0x90),max_units=u32(raw,u32(raw,0x94)),
            min_power_advantage=f32(raw,u32(raw,0x98)),max_types_pointer=u32(raw,0x9c),
            include_kindof_words=[hex(u32(raw,0xa0+4*i)) for i in range(9)],
            exclude_kindof_words=[hex(u32(raw,0xc4+4*i)) for i in range(9)],priority_enum=u32(raw,0xe8),
            release_type_enum=u32(raw,0xec),micro_reference=[hex(n) for n in reference(asset,0xf0)],
            locomotor_mask=u32(raw,0xf4),distance_sort_point_enum=u32(raw,0xf8),registered_object_set=u32(raw,0xfc),
            base_defense_max_distance_pointer=u32(raw,0x100),object_filter_pointer=u32(raw,0x10c),
            always_recruit=boolean(raw,0x110),allow_recruit_in_combat=boolean(raw,0x111),
            require_can_attack_target=boolean(raw,0x112),sort_by_distance=boolean(raw,0x113),is_base_defense=boolean(raw,0x114)),
        native_stock_create_rule=dict(min_units=u32(raw,0x120),max_units=u32(raw,0x124),
            unit_template_weak_hash=hex(u32(raw,0x128)),experience_level=u32(raw,0x12c)))


def validate_state(stock,candidate):
    if type(stock) is not Asset or type(candidate) is not Asset:reject('typed_asset')
    if stock.name!=STOCK_STATE or stock.key!=STOCK_KEY or sha(stock.payload)!=STOCK_PAYLOAD_SHA:reject('trusted_stock_state')
    if (candidate.name!=NEW_STATE or candidate.key!=NEW_KEY or len(candidate.payload)!=512
            or candidate.type_hash!=0xd63de874):reject('fixed_candidate_state')
    if stock.refs!=(TARGET_KEY,MICRO_KEY) or candidate.refs!=stock.refs:reject('target_or_micro_reference_changed')
    if offsets(stock.imports)!=[0x44,0xf0] or offsets(candidate.imports)!=[0x44,0xf0]:reject('state_import_set')
    stock_fields=decode_state_fields(stock);fields=decode_state_fields(candidate)
    if fields!=stock_fields:reject('stock_target_tactic_team_or_creation_changed')
    a,b=bytearray(stock.payload[:0x130]),bytearray(candidate.payload[:0x130])
    a[4:8]=b'\0'*4;b[4:8]=b'\0'*4
    if a!=b:reject('stock_complete_prefix_changed')
    stock_start,original=decode_heuristics(stock);start,rows=decode_heuristics(candidate)
    if stock_start!=0x130 or start!=0x130:reject('heuristic_array_location')
    if [r['kind'] for r in original]!=CORE_ORDER or [r['kind'] for r in rows]!=['scripted_flag',*CORE_ORDER,'constant']:reject('heuristic_contract_order')
    if [r['raw'] for r in rows[1:-1]]!=[r['raw'] for r in original]:reject('native_stock_conditions_changed')
    if rows[-1]['fields']!={'weight':100.0}:reject('preference_weight')
    base={0x10,0x34,0x3c,8,0x88,0x94,0x98,0x108}
    if set(offsets(stock.relocations))!=base|{stock_start+4*i for i in range(6)}:reject('stock_relocations')
    if set(offsets(candidate.relocations))!=base|{start+4*i for i in range(8)}|{rows[0]['offset']+8}:reject('candidate_relocations')
    return dict(fields=fields,heuristics=[{k:v for k,v in r.items() if k!='raw'} for r in rows],
        complete_stock_prefix_preserved=True,all_stock_condition_bytes_preserved=True,
        compiled_fields_verified=True,field_verified=False,dispatch_allowed=False,product_capability_granted=False)


def personality_registrations(asset,offset,expected_type):
    count,start=u32(asset.payload,offset),u32(asset.payload,offset+4)
    if not 1<=count<=512:reject('personality_registration_count')
    extent(asset.payload,start,count*12)
    if offset+4 not in offsets(asset.relocations):reject('personality_array_relocation')
    result=[]
    for i in range(count):
        at=start+12*i;key=reference(asset,at+4)
        if key[0]!=expected_type:reject('personality_registration_reference_type')
        difficulty=u32(asset.payload,at+8)
        if not 0<difficulty<=15:reject('personality_registration_difficulty')
        result.append(dict(id_hash=hex(u32(asset.payload,at)),reference=key,difficulty=difficulty))
    return result


def validate_personality(stock,candidate):
    if stock.name!=STOCK_PROFILE or sha(stock.payload)!=STOCK_PROFILE_SHA:reject('trusted_stock_personality')
    if (candidate.name!=NEW_PROFILE or candidate.key!=(0xd6d4f18e,0x799613e0)
            or candidate.type_hash!=0xcb3c9d2b):reject('candidate_personality')
    original=personality_registrations(stock,0x154,0x242ff6d4)
    actual=personality_registrations(candidate,0x154,0x242ff6d4)
    if len(original)!=67 or actual[:67]!=original or len(actual)!=74:reject('inherited_strategic_registration_changed')
    if sum(row['reference']==NEW_KEY and row['difficulty']==15 for row in actual)!=1:reject('new_expansion_registration')
    if sum(row['reference']==STOCK_KEY and row['difficulty']==2 for row in actual)!=1:reject('original_expansion_registration')
    # BuildState refs are validated by their actual original type key, without
    # substituting an XML list. No custom precise consumer may be appended.
    original_type=None
    bstart=u32(stock.payload,0x168)
    original_type=reference(stock,bstart+4)[0]
    old_builds=personality_registrations(stock,0x164,original_type)
    new_builds=personality_registrations(candidate,0x164,original_type)
    if old_builds!=new_builds:reject('inherited_native_build_registrations_changed')
    return dict(original_strategic_registrations=67,additional_strategic_registrations=7,
        stock_medium_expansion_still_registered=True,additional_expansion_registered=True,
        native_build_registrations_preserved=len(old_builds),
        global_single_expansion_guaranteed=False,compiled_inherited_registrations_verified=True)


def config_archives(game_root,path=None,seen=()):
    game_root=Path(game_root).resolve();path=(path or game_root/'RA3_chinese_t_1.12.SkuDef').resolve()
    if not path.is_relative_to(game_root) or path in seen or len(seen)>24:reject('stock_config_scope_or_cycle')
    archives=[];configs=[path]
    for line in path.read_text(encoding='utf-8').splitlines():
        parts=line.strip().split(maxsplit=1)
        if len(parts)!=2:continue
        if parts[0].lower() not in ('add-big','add-config'):continue
        target=(path.parent/parts[1].replace('\\','/')).resolve()
        if not target.is_relative_to(game_root):reject('stock_config_target_scope')
        if parts[0].lower()=='add-big':
            if target.name.lower().startswith(('core','globalstream')):archives.append(target)
        else:
            more,inputs=config_archives(game_root,target,(*seen,path));archives.extend(more);configs.extend(inputs)
    return archives,configs


def stock_references(game_root):
    wanted={STOCK_STATE,STOCK_PROFILE,'AITargetingHeuristic:ExpansionHeuristic','AIMicroManagerData:ExpansionMicroManager'}
    paths,configs=config_archives(game_root);found={};provenance={};sources={str(p):file_sha(p) for p in configs};aliases=[]
    for path in paths:
        archive=Archive(path);sources[str(path)]=file_sha(path)
        for name in archive.index:
            if re.fullmatch(r'data/global(?:_[lm])?(?:\.\d+)?\.manifest',name) is None:continue
            raw=archive.entry(name);rows=[r for r in manifest(raw) if r['name'] in wanted]
            # Zero-payload patch rows are aliases, not definitions filled with
            # zeroes. Resolve to the first lower-priority actual payload.
            for row in rows:
                if not row['binary_size']:aliases.append(dict(archive=str(path),manifest=name,asset=row['name']))
            pending=[row for row in rows if row['name'] not in found and row['binary_size']]
            if not pending:continue
            stem=name[:-9];assets,parts=stream_assets(archive,stem)
            for row in pending:
                asset=assets[row['name']];found[row['name']]=asset
                provenance[row['name']]=dict(archive=str(path),manifest=name,key=[hex(n) for n in asset.key],
                    payload_sha256=sha(asset.payload),imports_sha256=sha(asset.imports),
                    relocations_sha256=sha(asset.relocations),refs=[list(n) for n in asset.refs])
    if set(found)!=wanted:reject('stock_reference_missing')
    if found['AITargetingHeuristic:ExpansionHeuristic'].key!=TARGET_KEY or found['AIMicroManagerData:ExpansionMicroManager'].key!=MICRO_KEY:
        reject('stock_target_micro_identity')
    return found,dict(source_pins=sources,effective_assets=provenance,zero_payload_aliases=aliases)


def loose_assets(directory,stem):
    parts={ext:(Path(directory)/(stem+'.'+ext)).read_bytes() for ext in ('manifest','bin','imp','relo')}
    class Loose:
        def entry(self,name):return parts[name.rsplit('.',1)[1]]
    return stream_assets(Loose(),stem)


def validate_package(package_dir,game_root=Path('E:/RedRar3'),*,expected_package_sha256=PACKAGE_SHA):
    """Recompute real BIG/three streams/stock fields. Never trusts report JSON.

    This is a pinned fixed-candidate admission validator, not an action grant.
    No compiler, model, transport, registry or process is accessed.
    """
    package_dir=Path(package_dir).resolve();path=package_dir/'TFMacroProbe.big'
    validator_source_sha256=file_sha(Path(__file__))
    native_image=Path(game_root)/'Data/RA3_1.12.game'
    native_layout=native_layout_proof(native_image)
    if type(expected_package_sha256) is not str or re.fullmatch('[0-9a-f]{64}',expected_package_sha256) is None:reject('expected_package_digest')
    before=file_sha(path)
    if before!=expected_package_sha256:reject('package_digest')
    archive=Archive(path)
    expected_entries={'data/gamestrings.csf'}|{'data/'+stem+'.'+ext for stem in ('mod','mod_m','mod_l') for ext in ('manifest','bin','imp','relo')}
    if set(archive.index)!=expected_entries:reject('candidate_archive_entry_set')
    for name in expected_entries:
        loose=package_dir/'package'/name
        if archive.entry(name)!=loose.read_bytes():reject('archive_loose_mismatch')
    stock,stock_evidence=stock_references(game_root)
    expected_custom={
        'AIPersonalityDefinition:'+PREFIX+'_Soviet',
        *('AIStrategicStateDefinition:'+PREFIX+'_'+n for n in ('Scout','RegroupHome','WithdrawHome','ReinforceBase','DeployAttack','DeployDefense','StockExpansionPreference')),
        *('AIBudgetStateDefinition:'+PREFIX+'_'+n for n in ('BudgetEconomy','BudgetArmy','BudgetTech')),
        *('AITargetingHeuristic:'+PREFIX+'_Waypoint_'+n for n in ('Player_1_Start','Player_2_Start'))}
    qualities=[];fingerprints=[]
    for quality,stem in [('high','mod'),('medium','mod_M'),('low','mod_L')]:
        assets,parts=stream_assets(archive,'data/'+stem.lower())
        baseline,base_parts=loose_assets(package_dir/'baseline/data',stem)
        if len(baseline)!=854 or set(assets)-set(baseline)!=expected_custom or set(baseline)-set(assets):reject('actual_asset_set')
        for name,old in baseline.items():
            if assets[name]!=old:reject('original_asset_or_fixup_changed')
        if any(name.startswith('AIBuildStateDefinition:') for name in expected_custom):reject('custom_precision_asset')
        fields=validate_state(stock[STOCK_STATE],assets[NEW_STATE])
        personality=validate_personality(stock[STOCK_PROFILE],assets[NEW_PROFILE])
        fingerprint=sha(assets[NEW_STATE].payload+assets[NEW_STATE].imports+assets[NEW_STATE].relocations)
        fingerprints.append(fingerprint)
        qualities.append(dict(quality=quality,stream=stem,original_assets_preserved=854,custom_assets=13,
            state_payload_sha256=sha(assets[NEW_STATE].payload),state_fixup_fingerprint=fingerprint,
            manifest_sha256=sha(parts['manifest']),state=fields,personality=personality))
    if len(set(fingerprints))!=1:reject('three_quality_state_mismatch')
    if file_sha(path)!=before:reject('package_changed_during_validation')
    for source,expected in stock_evidence['source_pins'].items():
        if file_sha(source)!=expected:reject('stock_sources_changed_during_validation')
    if file_sha(Path(__file__))!=validator_source_sha256:reject('validator_source_changed_during_validation')
    if file_sha(native_image)!=EXE_SHA:reject('native_image_changed_during_validation')
    return dict(kind='compiled_stock_expansion_definition_validation_v1',package_sha256=before,
        validator_source_sha256=validator_source_sha256,native_layout=native_layout,stock_evidence=stock_evidence,qualities=qualities,
        compiled_fields_verified=True,compiled_inherited_registrations_verified=True,archive_loose_roundtrip_verified=True,
        xml_or_generator_report_used_as_field_evidence=False,global_single_expansion_guaranteed=False,
        native_adoption_verified=False,field_verified=False,dispatch_allowed=False,product_capability_granted=False,
        game_processes_opened=0,native_calls=0,compiled=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir',type=Path,required=True)
    parser.add_argument('--game-root',type=Path,default=Path('E:/RedRar3'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():reject('fresh_report_required')
    value=validate_package(args.package_dir,args.game_root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),compiled_fields_verified=True,field_verified=False,dispatch_allowed=False)))
