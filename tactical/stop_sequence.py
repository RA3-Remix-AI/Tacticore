"""Rebuild a normal Stop/settle boundary from immutable raw callback samples."""
import math

def settled_stop(events,unit_id=None):
 ev=[e for e in events if unit_id is None or e.get('unit_id')==unit_id]
 stops=[e for e in ev if e.get('kind')==23 and e.get('arg')==1 and e.get('caller')==0x787791]
 gates=[e for e in ev if e.get('kind')==24]
 if len(stops)!=1 or len(gates)!=1:return dict(verified=False,reason='stop_or_gate_count')
 stop,gate=stops[0],gates[0]
 rows=[];seen=set()
 for e in sorted(ev,key=lambda x:x.get('seq',0)):
  if e.get('kind')!=3 or not stop['seq']<e.get('seq',0)<gate['seq'] or not stop['frame']<e.get('frame',0)<=gate['frame']:continue
  if e['frame'] in seen:continue
  seen.add(e['frame']);rows.append(e)
 rows=rows[-3:]
 clean=len(rows)==3 and all(e.get('path')==0 and e.get('sm_flags',0xffff)&0xffff==0 and e.get('source')==1 and all(type(e.get(k)) in [int,float] and math.isfinite(e[k]) for k in ['x','y','z']) for e in rows)
 stable=clean and all(math.hypot(a['x']-b['x'],a['y']-b['y'])<=1 for a,b in zip(rows,rows[1:])) and math.hypot(rows[-1]['x']-gate['x'],rows[-1]['y']-gate['y'])<=1
 return dict(verified=bool(stable),frames=[e['frame'] for e in rows],xyz=[[e['x'],e['y'],e['z']] for e in rows],stop_frame=stop['frame'],move_boundary_frame=gate['frame'],reason='three_distinct_clean_stable_frames' if stable else 'not_three_clean_stable_frames')
