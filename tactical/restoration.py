"""Batch restoration is separate from tactical goal completion."""
import math

def single_control_release(report,expected_restore_mask):
 """A dead actor can release a lease without claiming an AI pool return.
 Disposed proof is deliberately strict and is not yet a live capability grant.
 """
 n=report.get('native',{});pre=report.get('preflight',{});rq=report.get('request',{});ev=report.get('events',[]);oid=pre.get('selected',{}).get('object_id');thread=pre.get('window_thread');owner=int(pre.get('owner','0'),0);manager=int(pre.get('ai','0'),0)+0x104
 bound=bool(oid) and n.get('session_id')==report.get('session_id')==pre.get('session_id') and n.get('commander_id')==pre.get('commander_id') and n.get('command_id')==rq.get('command_id') and n.get('task_id')==rq.get('task_id') and type(rq.get('seq')) is int and rq['seq']>0 and n.get('seq')==rq['seq'] and n.get('callback_thread')==thread
 clean=expected_restore_mask in [31,127,255,2047,4095] and n.get('phase') in [3,4] and n.get('restore_mask')==expected_restore_mask and n.get('active')==0 and n.get('overflow',0)==0
 remove=any(e.get('kind')==18 and e.get('tag')==1 and e.get('caller')==0x838877 and e.get('arg')==manager and e.get('thread')==thread for e in ev) and any(e.get('kind')==19 and e.get('tag')==1 and e.get('arg')==manager for e in ev)
 add=any(e.get('kind')==16 and e.get('tag')==3 and e.get('caller')==0x83885b and e.get('arg')==manager and e.get('thread')==thread for e in ev) and any(e.get('kind')==17 and e.get('tag')==3 and e.get('arg')==manager for e in ev)
 ret=[e for e in ev if e.get('kind')==15 and e.get('tag')==3 and e.get('arg')==1 and e.get('owner')==owner and e.get('thread')==thread]
 normal=n.get('phase')==3 and n.get('error')==0 and n.get('detach_calls')==n.get('return_calls')==n.get('return_verified')==1 and remove and add and len(ret)==1 and 0<n.get('issued_frame',0)<=ret[0]['frame']<=n.get('returned_frame',0)
 scans=report.get('disposal_scans',[]);disposed=False
 if n.get('disposed_verified')==1 and n.get('error')==32 and n.get('detach_calls')==1 and n.get('return_calls')==n.get('return_verified')==0 and remove and len(scans)==2:
  valid=all(s.get('complete') is True and type(s.get('frame')) is int and s['frame']==s.get('end_frame') and n.get('issued_frame',0)<=s['frame']<=n.get('disposed_frame',0) and s.get('thread')==thread and s.get('logic')==pre.get('logic') and type(s.get('ids')) is list and 1<=len(s['ids'])<=20000 and len(s['ids'])==s.get('count') and len(set(s['ids']))==len(s['ids']) and all(type(x) is int and x>0 for x in s['ids']) and oid not in s['ids'] for s in scans)
  disposed=valid and scans[0]['frame']<scans[1]['frame']==n.get('disposed_frame') and any(e.get('kind')==39 and e.get('arg')==2 and e.get('frame')==n.get('disposed_frame') and e.get('thread')==thread for e in ev)
 verified=bool(bound and clean and (normal or disposed))
 return dict(control_release_verified=verified,restoration_verified=verified,return_verified=bool(bound and clean and normal),disposed_verified=bool(bound and clean and disposed),semantics='native_pool_return' if verified and normal else 'actor_id_disposed_exclusive_control_released' if verified and disposed else 'unknown',completion_claim=False)

def formation_restoration(report,expected_restore_mask=31):
 n=report.get('native',{});units=report.get('units',[]);events=report.get('events',[]);pre=report.get('preflight',{});request=report.get('request',{});expected=[request.get('front_id'),request.get('support_id')];owner=int(pre.get('owner','0'),0);manager=int(pre.get('ai','0'),0)+0x104
 clean=expected_restore_mask in [31,127] and n.get('phase') in [3,4] and n.get('restore_mask')==expected_restore_mask and n.get('active')==0 and n.get('error') in [0,32,35,38,43,44] and n.get('session_id')==report.get('session_id')==pre.get('session_id') and n.get('command_id')==request.get('command_id') and n.get('task_id')==request.get('task_id') and bool(pre.get('commander_id')) and n.get('commander_id')==pre.get('commander_id') and type(request.get('seq')) is int and request['seq']>0 and n.get('seq')==request['seq'] and n.get('callback_thread')==pre.get('window_thread')
 result=[]
 if len(units)!=2 or None in expected or [u.get('id') for u in units]!=expected:return dict(restoration_verified=False,members=[],reason='batch_member_binding')
 for u in units:
  ev=[e for e in events if e.get('unit_id')==u['id']];remove=any(e['kind']==18 and e['tag']==1 and e['arg']==manager and e['caller']==0x838877 for e in ev) and any(e['kind']==19 and e['tag']==1 and e['arg']==manager for e in ev);add=any(e['kind']==16 and e['tag']==3 and e['arg']==manager and e['caller']==0x83885b for e in ev) and any(e['kind']==17 and e['tag']==3 and e['arg']==manager for e in ev)
  returned=u.get('detach_calls')==1 and u.get('return_calls')==1 and u.get('returned')==1 and remove and add and any(e['kind']==15 and e['tag']==3 and e['arg']==1 and e['owner']==owner for e in ev)
  disposed=False;why=u.get('disposed_reason');stamp=u.get('disposed_frame',0)
  if u.get('disposed_verified')==1 and u.get('detach_calls')==1 and u.get('return_calls')==0 and n.get('issued_frame',0)<=stamp<=n.get('returned_frame',0) and remove and any(e['kind']==30 and e['arg']==why and e['frame']==stamp for e in ev):
   disposed=why==1 and type(u.get('disposed_hp')) in [int,float] and math.isfinite(u['disposed_hp']) and u['disposed_hp']<=0 or why==2 and type(u.get('disposed_list_count')) is int and 0<=u['disposed_list_count']<=20000
  untouched=u.get('detach_calls')==u.get('return_calls')==u.get('move_calls')==u.get('stop_calls',0)==0 and not any(e['kind']==14 and e['arg']==0 for e in ev)
  result.append(dict(object_id=u['id'],returned=bool(returned),disposed_verified=bool(disposed),never_held=bool(untouched),settled=bool(returned or disposed or untouched)))
 return dict(restoration_verified=clean and all(x['settled'] for x in result),members=result,reason='all_batch_members_settled' if clean and all(x['settled'] for x in result) else 'unknown_member_or_cleanup')
