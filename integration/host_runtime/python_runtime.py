"""Trusted Python argv construction; Windows venv redirectors are never owners."""
from __future__ import annotations
import os,sys
from pathlib import Path
from .contracts import ContractError

ROOT=Path(__file__).resolve().parents[2]


def interpreter():
    path=Path(sys.base_prefix)/'python.exe' if os.name=='nt' and sys.prefix!=sys.base_prefix else Path(sys.executable)
    return path.resolve(strict=True)


def script_command(script,args=(),*,python=None):
    script=Path(script).resolve(strict=True)
    if not script.is_relative_to(ROOT):raise ContractError('runtime_layout_unavailable')
    command=[str(Path(python).resolve(strict=True) if python else interpreter()),'-I','-S','-B']
    prefix=Path(sys.prefix).resolve(strict=True)
    imports=[str(ROOT)]+[str(ROOT/p) for p in ('integration','strategy','production','production/persistent','native-ai','tactical','visibility','agent_runtime/src')]
    imports.append(str(prefix/'Lib/site-packages'))
    code='import sys,runpy;sys.prefix=sys.exec_prefix='+repr(str(prefix))+';sys.path[:0]='+repr(imports)+';sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")'
    command.extend(['-c',code])
    command.append(str(script));command.extend(map(str,args));return command
