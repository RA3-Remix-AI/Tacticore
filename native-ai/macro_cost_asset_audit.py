"""Offline compiled cost-source inventory; no runtime upper-bound grant.

Inspect actual installed stock streams and the fixed expanded BIG, resolving
zero-payload patch/quality aliases before parsing current definitions. XML and
SDK prices are not substituted for compiled fields. Catalog closure and native
payment-path closure are deliberately reported separately.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tactical.runtime.audit_near_weapon_asset import big_index, unpack, manifest_rows

PACKAGE_SHA256 = 'd516540d3d51a48a2d385dd1534e329bd5139bc67a6a0bde3e59a3ea5b9690a5'
PRODUCTION = 0x6ec75439
GIVE_BONUS = 0x8ed33e53
COST_UPGRADE = 0xcdc0eff7
FIELDS = dict(Behaviors=0xb3b9cd7d, ProductionModifier=0xef83869a,
    CostMultiplier=0x5213e2bc, BuildCostBonus=0x4876d51c,
    BuildCostBonusAllies=0x19b8b59a, ObjectResourceInfo=0x6aaad2bb,
    BuildCost=0xf108bcf1, Account=0x04ab249d, Amount=0x5011b1a4)
TARGETS = {'SovietPowerPlant', 'SovietBarracks', 'SovietWarFactory',
    'SovietRefinery', 'SovietTechStructure', 'SovietAntiInfantryVehicle',
    'SovietAntiAirShip_Ground', 'SovietPowerPlantAdvanced', 'SovietConstructionYard'}


def sha(raw): return hashlib.sha256(raw).hexdigest()


class Tokens:
    """Bounded partial Tokenized reader, only the fields needed for costs."""
    def __init__(self, blob): self.blob = blob
    def words(self, at, count):
        if type(at) is not int or at < 0 or at+count*4 > len(self.blob):
            raise ValueError('cost_token_extent')
        return struct.unpack_from('<'+'I'*count, self.blob, at)
    def scalar(self, at, *, real=False):
        raw = self.words(at, 1)[0]
        if not real: return raw
        value = struct.unpack('<f', struct.pack('<I', raw))[0]
        if not math.isfinite(value): raise ValueError('cost_token_nonfinite')
        return value
    def fields(self, at=0, seen=()):
        if at in seen or len(seen) > 12: raise ValueError('cost_token_cycle')
        result = {}; seen = (*seen, at)
        first, kind, data = self.words(at, 3)
        if first == 2: return self.fields(data, seen)
        for index in range(2048):
            key, kind, data = self.words(at+12*index, 3)
            if key == kind == data == 0: return result
            if key == 1:
                parent = self.fields(data, seen)
                if set(parent).intersection(result): raise ValueError('cost_token_duplicate_parent')
                result.update(parent)
            else:
                if key in result: raise ValueError('cost_token_duplicate_field')
                if data: self.words(data, 1)
                result[key] = (kind, data)
        raise ValueError('cost_token_unterminated')
    def array(self, at):
        key, kind, count_at = self.words(at, 3)
        if key != 0x6c827073 or kind != 0x5d448fd8:
            raise ValueError('cost_token_array_header')
        count = self.scalar(count_at)
        if count > 4096: raise ValueError('cost_token_array_bound')
        result = []
        for index in range(count):
            key, kind, data = self.words(at+12*(index+1), 3)
            if key != 0xb151a0eb or kind != 0 or not data:
                raise ValueError('cost_token_array_entry')
            result.append(data)
        return result
    def field(self, fields, name, *, real=False):
        if FIELDS[name] not in fields: raise ValueError('cost_token_required_field_missing:'+name)
        kind, data = fields[FIELDS[name]]
        if not data: raise ValueError('cost_token_required_value_missing:'+name)
        if real and kind != 0x645864f3 and name == 'CostMultiplier':
            raise ValueError('cost_token_multiplier_type')
        return self.scalar(data, real=real)
    def modules(self):
        fields = self.fields(); entry = fields.get(FIELDS['Behaviors'])
        if entry is None or not entry[1]: return []
        result = []
        for at in self.array(entry[1]):
            key, kind, data = self.words(at, 3)
            if key != 2 or not data: raise ValueError('cost_token_module_type')
            result.append((kind, at, self.fields(data)))
        return result


def parse_object(blob, name):
    tokens = Tokens(blob); modules = tokens.modules(); result = dict(name=name)
    production = []; bonuses = []; cost_upgrades = []
    for kind, at, fields in modules:
        if kind == PRODUCTION:
            record = fields.get(FIELDS['ProductionModifier'])
            if not record or not record[1]: raise ValueError('cost_production_modifier_array_missing')
            modifiers = []
            for entry in tokens.array(record[1]):
                fields_of_modifier = tokens.fields(entry)
                modifiers.append(tokens.field(fields_of_modifier, 'CostMultiplier', real=True))
            production.append(dict(token_offset=at, multipliers=modifiers))
        elif kind == GIVE_BONUS:
            bonuses.append(dict(token_offset=at,
                own=tokens.field(fields, 'BuildCostBonus', real=True),
                allies=tokens.field(fields, 'BuildCostBonusAllies', real=True)))
        elif kind == COST_UPGRADE:
            cost_upgrades.append(dict(token_offset=at))
    result.update(production_modules=production, production_bonus_modules=bonuses,
        cost_modifier_upgrade_modules=cost_upgrades)
    if name.split(':', 1)[-1] in TARGETS:
        fields = tokens.fields(); record = fields.get(FIELDS['ObjectResourceInfo'])
        if not record or not record[1]: raise ValueError('cost_object_resource_missing')
        resource = tokens.fields(record[1]); record = resource.get(FIELDS['BuildCost'])
        if not record or not record[1]: raise ValueError('cost_object_buildcost_missing')
        result['compiled_resource_costs'] = [dict(account=tokens.field(fields, 'Account'),
            amount=tokens.field(fields, 'Amount')) for fields in
            (tokens.fields(entry) for entry in tokens.array(record[1]))]
    return result


def parse_attribute(blob):
    # Current 1.12 native 4da950 reads count+30/array+34 and stride8. Older
    # nonwinning streams have a different schema and must not be parsed here.
    if len(blob) < 0x38: raise ValueError('cost_attribute_extent')
    count, start = struct.unpack_from('<II', blob, 0x30)
    if count > 128 or (count and (start < 0x38 or start+count*8 > len(blob))):
        raise ValueError('cost_attribute_array_extent')
    values = []
    for index in range(count):
        kind, value = struct.unpack_from('<If', blob, start+8*index)
        if not math.isfinite(value): raise ValueError('cost_attribute_nonfinite')
        if kind == 14: values.append(value)
    return dict(production_cost_values=values, stacking_limit=struct.unpack_from('<I', blob, 0x24)[0])


def parse_player_template(blob):
    if len(blob) < 0xb8: raise ValueError('cost_player_template_extent')
    count, start = struct.unpack_from('<II', blob, 0xb0)
    if count > 64 or (count and (start < 0xb8 or start+count*28 > len(blob))):
        raise ValueError('cost_player_template_bonus_extent')
    values = []
    for index in range(count):
        entry = struct.unpack_from('<I6f', blob, start+28*index)
        if not all(math.isfinite(value) for value in entry[1:]): raise ValueError('cost_player_bonus_nonfinite')
        values.append(dict(required_tech_serialized_reference=entry[0], own=entry[1], allies=entry[2]))
    return dict(production_cost_bonuses=values)


def config_archives(path, *, seen=()):
    path = path.resolve()
    if path in seen or len(seen) > 24: raise ValueError('cost_config_cycle')
    paths = []
    for line in path.read_text(encoding='utf8').splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2: continue
        if parts[0].lower() == 'add-big': paths.append(path.parent / parts[1].replace('\\', '/'))
        elif parts[0].lower() == 'add-config':
            paths.extend(config_archives(path.parent / parts[1], seen=(*seen, path)))
    return paths


def audit(package, game_root, output):
    package = Path(package).resolve(); game_root = Path(game_root).resolve(); output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports'): raise ValueError('cost_fresh_report_required')
    if sha(package.read_bytes()) != PACKAGE_SHA256: raise ValueError('cost_fixed_expansion_package_required')
    archives = [package] + [p for p in config_archives(game_root/'RA3_chinese_t_1.12.SkuDef')
        if p.name.lower().startswith(('core', 'staticstream', 'globalstream'))]
    winners = {}; declared = {}; manifests = []; inventories = []
    for archive in archives:
        with archive.open('rb') as stream:
            entries = big_index(stream)
            for name, (at, size) in entries.items():
                match = re.fullmatch(r'data\\(global|static|mod)(?:_([lm]))?(?:\.\d+)?\.manifest', name)
                if not match: continue
                stream.seek(at); packed = stream.read(size); manifest = unpack(packed)
                rows = manifest_rows(manifest)
                qualities = [match[2] or 'high'] if match[1] != 'global' else ['high', 'l', 'm']
                selected = [r for r in rows if r['name'].startswith(('AttributeModifier:', 'PlayerTemplate:', 'GameObject:'))]
                manifests.append(dict(archive=str(archive), entry=name, packed_sha256=sha(packed),
                    manifest_sha256=sha(manifest), qualities=qualities, selected_rows=len(selected),
                    zero_payload_aliases=sum(not r['binary_size'] for r in selected)))
                for quality in qualities:
                    for row in selected:
                        key = (quality, row['type_id'], row['instance_id'])
                        declared.setdefault(key, row['name'])
                        if key not in winners and row['binary_size']:
                            winners[key] = (archive, name[:-9]+'.bin', row)
    # Quality zero-payload rows can alias the high-quality base asset. Resolve
    # by the same type+instance key, never by a guessed name or empty payload.
    fallback_aliases = []
    for key, name in declared.items():
        if key not in winners and key[0] != 'high' and ('high', *key[1:]) in winners:
            winners[key] = winners[('high', *key[1:])]
            fallback_aliases.append(dict(quality=key[0], name=name, resolved_to='high'))
    groups = {}
    for key, (archive, binary, row) in winners.items():
        groups.setdefault((archive, binary), []).append((key[0], row))
    output.mkdir(); errors = []; objects = []; attributes = []; players = []
    for (archive, binary_name), selected in groups.items():
        with archive.open('rb') as stream:
            entries = big_index(stream); at, size = entries[binary_name]
            stream.seek(at); packed = stream.read(size); binary = unpack(packed)
        inventories.append(dict(archive=str(archive), binary_entry=binary_name,
            packed_sha256=sha(packed), binary_sha256=sha(binary), selected_definitions=len(selected)))
        for quality, row in selected:
            begin, end = row['binary_offset'], row['binary_offset']+row['binary_size']
            if end > len(binary): raise ValueError('cost_compiled_asset_extent')
            blob = binary[begin:end]
            meta = dict(name=row['name'], quality=quality, archive=str(archive), binary_entry=binary_name,
                binary_offset=begin, binary_size=len(blob), payload_sha256=sha(blob), flags=row['flags'])
            try:
                if row['name'].startswith('GameObject:'):
                    if row['flags'] != 1: raise ValueError('cost_gameobject_not_tokenized')
                    parsed = parse_object(blob, row['name'])
                    if (any(parsed[k] for k in ['production_modules', 'production_bonus_modules',
                            'cost_modifier_upgrade_modules']) or 'compiled_resource_costs' in parsed):
                        objects.append(dict(meta, **{k:v for k,v in parsed.items() if k!='name'}))
                elif row['name'].startswith('AttributeModifier:'):
                    if row['flags'] != 0: raise ValueError('cost_attribute_not_native_schema')
                    attributes.append(dict(meta, **parse_attribute(blob)))
                else:
                    if row['flags'] != 0: raise ValueError('cost_player_template_not_native_schema')
                    players.append(dict(meta, **parse_player_template(blob)))
            except (ValueError, struct.error) as exc:
                errors.append(dict(meta, reason=str(exc)))
    result = dict(kind='native_compiled_cost_source_inventory', schema_version=1,
        package_sha256=PACKAGE_SHA256, qualities=['high','l','m'], manifest_records=manifests,
        binary_records=inventories, effective_asset_count=len(winners), parsing_errors=errors,
        unresolved_payload_aliases=[dict(quality=k[0],name=name) for k,name in declared.items() if k not in winners],
        high_quality_fallback_aliases=fallback_aliases,
        objects=objects, attribute_modifiers=attributes, player_templates=players,
        native_upper_cost=None, native_upper_cost_verified=False,
        asset_source_closure_proven=False, native_modifier_creation_closure_proven=False,
        construction_payment_context_proven=False, native_reserved_credits=None,
        source_sha256=sha(Path(__file__).read_bytes()), no_process_opened=True,
        native_calls=0, process_writes=0, field_verified=False, grants_capability=False)
    (output/'audit.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(output=str(output), effective_assets=len(winners), errors=len(errors),
        objects=len(objects), attributes=len(attributes), players=len(players), upper_cost_verified=False)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); audit(args.package, args.game_root, args.output)


if __name__ == '__main__': main()
