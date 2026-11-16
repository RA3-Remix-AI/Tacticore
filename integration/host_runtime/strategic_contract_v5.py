"""Load one fixed pure grammar in the isolated desktop bridge import layout."""
import importlib.util
from pathlib import Path

_path=Path(__file__).resolve().parents[2]/'strategy/native_unified_contract_v5.py'
_spec=importlib.util.spec_from_file_location('_bound_strategic_grammar_v5',_path)
_grammar=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_grammar)
FLAG_ACTIONS=_grammar.FLAG_ACTIONS
GATE_ACTIONS=_grammar.GATE_ACTIONS
STRATEGIC_ACTIONS=_grammar.STRATEGIC_ACTIONS
split_intents=_grammar.split_intents
FOCUS_ACTIONS=_grammar.FOCUS_ACTIONS
split_native7_intents=_grammar.split_native7_intents
INDEPENDENT_DEVELOPMENT_CONTRACT=_grammar.INDEPENDENT_DEVELOPMENT_CONTRACT
RAID_ACTION=_grammar.RAID_ACTION
