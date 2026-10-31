"""Stage the beta's locked Python environment; this is not a game release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from locked_python_runtime import APPLICATION_SOURCES, copy_application, copy_python, digest, plain, seal_stage

REPO = Path(__file__).resolve().parents[2]


def stage(destination):
    tool_names = ('stage-python-runtime.py', 'locked_python_runtime.py')
    tool_pins = {name: digest(Path(__file__).parent / name) for name in tool_names}
    destination = Path(destination).absolute()
    if '..' in destination.parts:
        raise ValueError('unsafe_output')
    if destination.exists():
        raise ValueError('output_must_be_new')
    if destination.is_relative_to(REPO) or REPO.is_relative_to(destination):
        raise ValueError('unsafe_output')
    ancestor = destination.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    plain(ancestor)
    destination.mkdir(parents=True)
    provenance, notices = copy_python(destination / 'python', REPO / 'agent_runtime/requirements-pydantic.lock')
    source_inventory = copy_application(REPO, destination / 'app')
    imports = ['Lib', 'DLLs', 'Lib/site-packages', '../app', *('../app/' + name for name in APPLICATION_SOURCES)]
    (destination / 'python/python312._pth').write_text('\n'.join(imports) + '\n', encoding='utf-8')
    (destination / 'python-provenance.json').write_text(json.dumps(provenance, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    (destination / 'application-sources.json').write_text(json.dumps(source_inventory, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    if {name: digest(Path(__file__).parent / name) for name in tool_names} != tool_pins:
        raise ValueError('runtime_packaging_tools_changed_during_copy')
    (destination / 'build-inputs.json').write_text(json.dumps(dict(schema_version=1, tools=tool_pins), sort_keys=True) + '\n', encoding='utf-8')
    (destination / 'third-party-inventory.json').write_text(json.dumps(dict(schema_version=1, scope='python_stage_only', dependencies=notices), sort_keys=True, indent=2) + '\n', encoding='utf-8')
    (destination / 'release-stage.json').write_text(json.dumps(dict(schema_version=1, kind='locked_python_stage',
        native_transport_included=False, game_qualified=False, public_release_ready=False), sort_keys=True) + '\n', encoding='utf-8')
    return dict(seal_stage(destination), kind='locked_python_stage', distributions=len(provenance['distributions']),
                credentials_collected=False, game_files_collected=False, public_release_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(stage(parser.parse_args().output)))
