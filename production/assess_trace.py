"""Strict offline correlation. A primitive pass is not macro strategy acceptance."""
import argparse,json,math,struct
from pathlib import Path

def integer(value):return int(value,0) if isinstance(value,str) else value
def floating(bits):return struct.unpack('<f',struct.pack('<I',bits))[0]

def assess(report,records,natural_candidate=None):
 checks={};issues=[]
 stopped=report.get('stopped',{})
 checks['trace_complete']=report.get('status')=='trace_finished' and report.get('native_exit_code')==0 and report.get('session_unchanged_after') is True and stopped.get('state')==2 and stopped.get('restore_mask')==31 and stopped.get('error')==0 and stopped.get('active_detours')==0 and stopped.get('dropped')==0 and stopped.get('emitted_events')==stopped.get('total_events')
 events=[r for r in records if r.get('record')=='event']
 checks['event_sequence_complete']=[e.get('seq') for e in events]==list(range(len(events))) and len(events)==stopped.get('total_events')
 action=report.get('enqueue_result',{});native=action.get('native_result',{})
 checks['bridge_enqueue']=native.get('state')==2 and native.get('error')==0 and native.get('active_enqueue_attempted') is True and native.get('queue_preserved') is True and native.get('initial_paid')==0 and native.get('queue_id',0)>0 and integer(native.get('node',0))>0 and action.get('session_id')==report.get('session_id') and action.get('pid')==report.get('pid') and action.get('mod_sha256')==report.get('mod_sha256') and action.get('session_unchanged_after') is True
 if not checks['bridge_enqueue'] and natural_candidate is None:
  return dict(status='incomplete',production_primitive_verified=False,runtime_direction_switch_verified=False,checks=checks,issues=['No successful session-correlated bridge enqueue receipt.'])
 source=natural_candidate if natural_candidate is not None else native
 node=integer(source['node']);qid=source['queue_id'];cost=source['native_cost'];owner=integer(report['preflight']['player']['address']);resource=integer(report['preflight']['player']['resource']);factory=integer(report['preflight']['factory']['address']);thread=report['installed']['callback_thread']
 relevant=[e for e in events if e.get('node')==node and e.get('queue_id')==qid]
 checks['identity_chain']=bool(relevant) and all(e.get('thread')==thread and e.get('owner')==owner and e.get('factory')==factory and e.get('template_hash')==0x2c358c61 for e in relevant)
 pays=[e for e in relevant if e['kind']==2];debits=[e for e in relevant if e['kind']==3]
 checks['debit_call_chain']=bool(debits) and all(e.get('caller')==0x70f578 and e.get('context_valid')==1 and e.get('resource')==resource and 0<e.get('actual',0)<=e.get('requested',0) and ((e.get('cash_before_raw',0)-e.get('cash_after_raw',0))&0xffffffff)==e.get('actual') for e in debits)
 payment_valid=bool(pays) and pays[0].get('paid_before')==0;previous=0;used=set()
 for index,pay in enumerate(pays):
  upper=pays[index+1]['seq'] if index+1<len(pays) else float('inf')
  nested=[e for e in debits if pay['seq']<e['seq']<upper and e['frame']==pay['frame']]
  used.update(e['seq'] for e in nested)
  delta=pay.get('paid_after',0)-pay.get('paid_before',0)
  payment_valid=payment_valid and pay.get('caller')==0x7baaff and pay.get('context_valid')==1 and pay.get('cost')==cost and pay.get('paid_before')==previous and delta==sum(e['actual'] for e in nested) and 0<=pay.get('paid_before',-1)<=pay.get('paid_after',-1)<=cost
  previous=pay.get('paid_after')
 checks['node_paid_accumulator']=payment_valid and previous==cost and used=={e['seq'] for e in debits}
 checks['cost_fully_attributed']=checks['debit_call_chain'] and checks['node_paid_accumulator'] and sum(e['actual'] for e in debits)==cost and cost>0
 creates=[e for e in relevant if e['kind']==4 and e.get('caller')==0x7baffe and e.get('context_valid')==1 and e.get('object',0)>0 and e.get('object_id',0)>0 and e.get('object')==e.get('returned') and e.get('object_owner')==owner and e.get('object_hash')==0x2c358c61 and e.get('paid_before')==cost]
 checks['native_factory_creation']=len(creates)==1
 completions=[];live=[];max_distance=None
 if creates:
  born=creates[0]
  same_object=lambda e:e.get('object')==born['object'] and e.get('object_id')==born['object_id'] and e.get('object_hash')==0x2c358c61 and e.get('object_owner')==owner
  completions=[e for e in relevant if e['kind']==5 and e.get('seq')>born['seq'] and e.get('caller')==0x7bb7b6 and e.get('context_valid')==1 and e.get('paid_before')==cost and same_object(e)]
  if completions:
   for e in relevant:
    if e['kind']==7 and e.get('seq')>completions[0]['seq'] and e.get('frame')>=completions[0]['frame'] and same_object(e):
     hp=floating(e.get('object_hp_bits',0));coords=[floating(e.get(k,0)) for k in ['object_x_bits','object_y_bits','object_z_bits','factory_x_bits','factory_y_bits','factory_z_bits']]
     if math.isfinite(hp) and hp>0 and all(math.isfinite(v) for v in coords):
      live.append(e);distance=math.dist(coords[:2],coords[3:5]);max_distance=max(distance,max_distance or 0)
 checks['production_completion']=bool(completions)
 checks['created_object_remains_live']=bool(live)
 for name,passed in checks.items():
  if not passed:issues.append(name+' missing or inconsistent')
 chain_verified=all(value for key,value in checks.items() if key!='bridge_enqueue')
 first_frame=pays[0]['frame'] if pays else None;last_frame=creates[0]['frame'] if creates else None
 return dict(status='native_chain_observed' if natural_candidate is not None and chain_verified else ('primitive_verified' if all(checks.values()) else 'incomplete'),production_primitive_verified=natural_candidate is None and all(checks.values()),natural_chain_verified=natural_candidate is not None and chain_verified,runtime_direction_switch_verified=False,checks=checks,issues=issues,node=hex(node),queue_id=qid,native_cost=cost,attributed_debits=sum(e.get('actual',0) for e in debits),debit_count=len(debits),object=hex(creates[0]['object']) if creates else None,object_id=creates[0]['object_id'] if creates else None,live_samples=len(live),max_live_distance_from_factory=max_distance,first_payment_frame=first_frame,creation_frame=last_frame,payment_to_creation_frame_span=last_frame-first_frame if first_frame is not None and last_frame is not None else None,payment_sample_count=len(pays),note='Cost is attributed by synchronous production-node TLS -> original resource debit return -> node+0x68, not global cash deltas. Creation is attributed by production tick context and exact native creation/completion callers. A natural chain is not a bridge enqueue. Macro direction/baseline acceptance remains separate.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('report',type=Path);ap.add_argument('--natural-only',action='store_true');args=ap.parse_args();report=json.loads(args.report.read_text(encoding='utf-8-sig'));records=[]
 for line in Path(report['stream']).read_text(encoding='utf-8-sig').splitlines():
  try:records.append(json.loads(line))
  except ValueError:pass
 if args.natural_only:
  targets={(e['node'],e['queue_id'],e['cost']) for e in records if e.get('record')=='event' and e.get('kind')==2 and e.get('paid_before')==0}
  chains=[assess(report,records,dict(node=n,queue_id=q,native_cost=c)) for n,q,c in sorted(targets)]
  result=dict(status='natural_review',production_primitive_verified=False,runtime_direction_switch_verified=False,natural_chains=chains,verified_natural_chains=sum(x['natural_chain_verified'] for x in chains))
 else:result=assess(report,records)
 target=args.report.with_name(args.report.stem+('-natural-assessment.json' if args.natural_only else '-assessment.json'));target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(report=str(target),**result),ensure_ascii=False))
if __name__=='__main__':main()
