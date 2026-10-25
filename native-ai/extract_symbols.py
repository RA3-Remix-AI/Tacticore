"""Version-pinned offline signatures for research candidates, not a call API."""
from pathlib import Path
import sys,hashlib,json,struct
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'reference/Ra3-Copilot/ra3-copilot/tools'))
from precheck_aob import parse_pe,rva_to_off
game=Path(r'E:\RedRar3\Data\RA3_1.12.game');data=game.read_bytes();base,size,sections=parse_pe(data)
symbols={
 'privateMoveToPosition':(0x6eff70,'thiscall AIUpdate*, Coord3D*, CommandSource; writes AIUpdate+0x50'),
 'ScriptEngineExecuteActionLua':(0x582c50,'Lua C function; shared Lua stack/context; not independently exercised'),
 'ScriptActionDispatcher':(0x5a2b40,'thiscall ScriptEngine*, ScriptAction*; case handlers are NOT APIs'),
 'ScriptToggleAIComponent':(0x583a20,'thiscall? ScriptEngine*, component, playerNameStringObject*, enabled; three stack args'),
 'AIPlayerToggleComponent':(0x880e40,'thiscall AIPlayer*, componentEnum, enabled'),
 'EmbeddedAIManagerToggle':(0x87f7c0,'thiscall AIPlayer+0x104, componentEnum, enabled'),
 'AIUnitEconomyEnabledSetter':(0x885ae0,'thiscall embedded component*, enabled byte; writes this+0x10'),
 'AIBaseEnabledSetter':(0x893020,'thiscall embedded base component*, enabled byte; writes this+0x1c'),
 'TransferNamedUnitAI':(0x583a70,'ScriptEngine wrapper requiring named/ref object; not callable with raw Thing'),
 'TransferThingAIAtPlayer':(0x838820,'thiscall Player*, Thing*, transferToAI bool'),
 'ScriptNamedCommandAbility':(0x590020,'thiscall ScriptEngine*, ScriptParam*, commandNameKey'),
 'ThingCommandAbility':(0x790990,'thiscall Thing*, CommandButtonInfo*, source, flag; forwards to 0x7904e0'),
 'ThingCommandDispatcher':(0x7904e0,'thiscall Thing*, 6 stack args; UNIT_BUILD goes to 0x790732'),
 'PlayerResourceByIndex':(0x83be10,'thiscall Player*, index; vector +0xe4/+0xe8'),
 'AIPlayerSetStrategicDirective':(0x8a0940,'thiscall AIPlayer*, AIStrategicDirective; ret4; native state/feedback side effects; NOT runtime validated'),
 'AIPlayerSetStrategicDirectiveWithFeedback':(0x8a0a90,'thiscall AIPlayer*, directive; ret4; co-op beacon callers; target context unresolved'),
 'EnemySelectorSetPriority':(0x8bdb50,'thiscall [[AIPlayer+0x6f8]+0x34], enemy Player+0x20, priority; ret8; requires lock word+0x30 == 0'),
 'EnemySelectorClearPriorities':(0x8af990,'thiscall selector*; native clear/flags, no arguments'),
 'EnemySelectorClearOnePriority':(0x8af9c0,'thiscall selector*, enemyIndex; ret4'),
 'EnemySelectorAutomaticScheme':(0x8bdbc0,'thiscall selector*, scheme enum; ret4; recalculates priorities'),
 'EnemySelectorDefaultAutomaticScheme':(0x8bdbe0,'thiscall selector*; resets default scheme'),
 'PauseManagerDoPause':(0x4e03f0,'thiscall GameLogic+0x150, type and three additional args; RESEARCH ONLY, never called'),
 'NativeResultRecordByIndex':(0x600600,'pure getter index0..5 returns 0xce3378+index*0x20; slot mapping unverified'),
}
rows=[]
for name,(va,notes) in symbols.items():
    off=rva_to_off(va-base,sections)
    rows.append(dict(name=name,va=hex(va),rva=hex(va-base),first_24_bytes=data[off:off+24].hex(),notes=notes,call_validated=False))
report=dict(game=str(game),sha256=hashlib.sha256(data).hexdigest(),image_base=hex(base),machine='x86',symbols=rows,
            important='Signatures identify this local binary only. Static ABI candidates are not proof of safe thread or gameplay effect.')
(ROOT/'native-symbols.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Wrote',len(rows),'offline symbol candidates')
