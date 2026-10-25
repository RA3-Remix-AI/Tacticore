"""Independent, read-only review of native lease reports. No game/API imports."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def review(report,*,expected_session=None,expected_commander=None):
    pre=report.get("preflight",{});native=report.get("native",{});events=report.get("events",[]);request=report.get("request",{}) or {}
    def pointer(value):
        try:return int(value,0) if isinstance(value,str) else int(value)
        except (ValueError,TypeError):return -1
    owner=pointer(pre.get("owner"));script=pointer(pre.get("script_team"));default=pointer(pre.get("default_team"));manager=pointer(pre.get("ai"))+0x104
    issued=native.get("issued_frame",0);returned=native.get("returned_frame",0);thread=pre.get("window_thread")
    def count(kind,tag,**fields):return sum(e.get("kind")==kind and e.get("tag")==tag and all(e.get(k)==v for k,v in fields.items()) for e in events)
    frames=type(issued) is int and type(returned) is int and 0<issued<=returned
    samples=[e for e in events if frames and e.get("kind")==3 and issued<=e.get("frame",-1)<=returned]
    tagged=[e for e in events if e.get("tag") in {1,2,3}]
    interference=[e for e in events if frames and e.get("tag")==0 and e.get("kind") in {10,12,14,16,18} and issued<=e.get("frame",-1)<returned]
    checks={
        "report_identity":report.get("session_id")==pre.get("session_id") and bool(report.get("session_id")) and (expected_session is None or report.get("session_id")==expected_session) and (expected_commander is None or pre.get("commander_id")==expected_commander),
        "clean_native_restore":native.get("phase")==3 and native.get("restore_mask")==31 and native.get("active")==0 and native.get("error")==0 and native.get("lifecycle_fail")==0 and native.get("overflow")==0 and native.get("return_verified")==1,
        "one_detach_move_return":native.get("detach_calls")==1 and native.get("move_calls")==1 and native.get("return_calls")==1,
        "event_sequence_complete":bool(events) and all(e.get("seq")==i+1 for i,e in enumerate(events)) and native.get("count")==len(events),
        "game_thread":type(thread) is int and thread>0 and native.get("callback_thread")==thread and bool(tagged) and all(e.get("thread")==thread for e in tagged),
        "owner_preserved":owner>0 and bool(events) and all(e.get("owner")==owner for e in events),
        "frame_order":frames,
        "transfer_false_chain":count(14,1,arg=0)==1 and count(15,1,arg=0)==1 and count(18,1,arg=manager,caller=0x838877)==1 and count(19,1,arg=manager)==1,
        "private_move_chain":count(10,2,arg=0)==1 and count(11,2,arg=0)==1,
        "transfer_true_chain":count(14,3,arg=1)==1 and count(15,3,arg=1)==1 and count(16,3,arg=manager,caller=0x83885b)==1 and count(17,3,arg=manager)==1,
        "leased_script_team":script>0 and bool(samples) and all(e.get("team")==script for e in samples),
        "no_observed_native_override":not interference,
    }
    target=request.get("target",[]);native_target=native.get("target",[])
    def finite_triplet(value):return isinstance(value,list) and len(value)==3 and all(type(x) in {int,float} and math.isfinite(x) for x in value)
    target_bound=finite_triplet(target) and finite_triplet(native_target) and all(abs(a-b)<.001 for a,b in zip(target,native_target))
    checks["requested_target_recorded_and_echoed"]=target_bound
    checks["command_transport_binding"]=bool(request.get("command_id")) and request.get("command_id")==native.get("command_id") and bool(request.get("task_id")) and request.get("task_id")==native.get("task_id") and type(request.get("seq")) is int and request["seq"]==native.get("seq") and report.get("session_id")==native.get("session_id") and bool(pre.get("commander_id")) and pre.get("commander_id")==native.get("commander_id")
    checks["bounded_lease"]=frames and type(request.get("lease_frames")) is int and 30<=request["lease_frames"]<=180 and returned-issued<=request["lease_frames"]+5
    end_seq=min([e.get("seq",0) for e in events if e.get("kind")==14 and e.get("tag")==3],default=0)
    arrivals=[];distances=[]
    if target_bound:
        for e in samples:
            if end_seq and e.get("seq",0)>=end_seq:continue
            point=[e.get("x"),e.get("y"),e.get("z")]
            if not finite_triplet(point):continue
            distance=math.hypot(point[0]-target[0],point[1]-target[1]);distances.append(distance)
            if distance<=15 and abs(point[2]-target[2])<=2:arrivals.append(e)
    checks["arrival_independently_observed"]=target_bound and request.get("arrival_radius")==15 and len(arrivals)>=3 and len(arrivals)==native.get("arrival_samples")
    post=[e for e in events if frames and e.get("frame",-1)>returned]
    recruited=[e for e in post if (e.get("kind")==3 and type(e.get("team")) is int and e["team"]>0 and e["team"]!=default) or (e.get("tag")==0 and e.get("kind") in {10,12})]
    transfer_keys=[key for key in checks if key not in {"requested_target_recorded_and_echoed","command_transport_binding","bounded_lease","arrival_independently_observed"}]
    return {"schema_version":1,"source":"independent_read_only_review","session_id":report.get("session_id"),"checks":checks,"transfer_and_return_observed":all(checks[k] for k in transfer_keys),"move_and_return_primitive_verified":all(checks.values()),"arrival_radius":15,"arrival_samples_independent":len(arrivals),"arrival_samples_reported":native.get("arrival_samples"),"minimum_distance_independent":min(distances) if distances else None,"lease_frames_observed":returned-issued if frames else None,"native_recruitment_observed":bool(recruited),"recruitment_delay_frames":min(e["frame"] for e in recruited)-returned if recruited else None,"raid_verified":False,"attack_verified":False,"combined_arms_verified":False,"restore_semantics":pre.get("restore_semantics"),"note":"Transfer/return evidence is separate from arrival and tactical goals. Missing request/transport fields cannot be reconstructed by assumption. No original squad restoration is inferred."}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("report",type=Path);parser.add_argument("--output",type=Path);parser.add_argument("--session");parser.add_argument("--commander")
    args=parser.parse_args();raw=args.report.read_bytes()
    if len(raw)>4*1024*1024:raise ValueError("report_size")
    report=json.loads(raw.decode("utf-8-sig"));result=review(report,expected_session=args.session,expected_commander=args.commander)
    result["report_sha256"]=hashlib.sha256(raw).hexdigest()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":main()
