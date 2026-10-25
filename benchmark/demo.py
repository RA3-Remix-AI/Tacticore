"""Generate labeled synthetic runs; does not connect to a model or game."""
import argparse
import copy
import json
from pathlib import Path
import uuid
from aggregate import aggregate, compare

def manifest(style="assault", trial=1):
    ids={"assault":"10000000-0000-4000-8000-000000000001", "economic":"10000000-0000-4000-8000-000000000002", "raider":"10000000-0000-4000-8000-000000000003"}
    names={"assault":"铁锤", "economic":"堡垒", "raider":"幽灵"}
    return dict(schema_version=1, run_id="synthetic-"+style+"-"+str(trial), source_kind="synthetic",
                session_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "ra3-demo-"+style+str(trial))), player_id=3,
                commander_id=ids[style], commander_name=names[style], commander_profile_sha256={"assault":"d","economic":"e","raider":"f"}[style]*64, style=style, trial_index=trial,
                map_id="map_mp_2_feasel6", faction="Japan", opponent_profile="fixed_scripted_opponent",
                difficulty="easy", game_sha256="a"*64, mod_sha256="b"*64,
                model_provider="synthetic_adapter", model_name="deterministic_fixture",
                prompt_sha256="c"*64, duration_game_seconds=300,
                seed_control="uncontrolled", seed=None, live_control_verified=False)

def events(m):
    records=[]
    def event(kind, time, **data):
        records.append(dict(event_id="event-"+str(len(records)+1), kind=kind, run_id=m["run_id"],
            session_id=m["session_id"], player_id=m["player_id"], commander_id=m["commander_id"],
            source_kind=m["source_kind"], game_time_seconds=time, data=data, evidence=None))
    event("decision_requested",1,request_id="request-1")
    event("decision_result",2,request_id="request-1",status="accepted")
    event("plan_activated",2,plan_id="plan-1",intent_sha256="1"*64)
    event("task_planned",3,task_id="task-1")
    event("task_started",4,task_id="task-1")
    event("production_requested",5,production_id="production-1",unit_type="JapanAntiAirInfantry")
    event("queue_observed",6,production_id="production-1")
    event("spend_observed",7,production_id="production-1",amount=300)
    event("unit_produced",20,production_id="production-1",unit_id="unit-1")
    event("task_result",50,task_id="task-1",status="completed")
    event("decision_requested",60,request_id="request-2")
    event("decision_result",61,request_id="request-2",status="rejected")
    event("task_planned",62,task_id="never-started")
    return records

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=Path(__file__).parent/"synthetic-demo")
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    runs=[]
    for trial in range(1,4):
        for style in ("assault","economic","raider"):
            m=manifest(style,trial);records=events(m);directory=args.output/m["run_id"];directory.mkdir(exist_ok=True)
            (directory/"manifest.json").write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
            (directory/"events.jsonl").write_text("".join(json.dumps(e,ensure_ascii=False)+"\n" for e in records),encoding="utf-8")
            summary=aggregate(m,records,directory);runs.append((m,summary))
            (directory/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    result=compare(runs)
    (args.output/"comparison.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SYNTHETIC ONLY:",len(runs),"fixture runs; no live game/style conclusion")

if __name__=="__main__":main()
