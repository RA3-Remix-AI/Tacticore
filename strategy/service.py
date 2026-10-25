"""File-snapshot HTTP strategy service. Real game execution is unavailable."""
from __future__ import annotations
import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

from engine import Binding, ContractError, Snapshot, StrategyEngine
from http_adapter import AdapterError, ChatAdapter, TransportPool, decode_json, load_profile
from battle_agent import BattleAgent


def read_json(path: Path, maximum=262144):
    try:
        with path.open("rb") as stream:raw=stream.read(maximum+1)
    except OSError:raise AdapterError("snapshot_unavailable") from None
    return decode_json(raw,maximum),hashlib.sha256(raw).digest()


@contextmanager
def player_lease(directory: Path, binding: Binding):
    """OS-released file lock; lease is session/player, not commander name."""
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/(binding.session_id+"-player-"+str(binding.player_id)+".lock")
    stream=path.open("a+b");locked=False
    try:
        stream.seek(0)
        if os.name=="nt":
            import msvcrt
            if path.stat().st_size==0:stream.write(b"\0");stream.flush();stream.seek(0)
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise AdapterError("player_lease_conflict") from None
        else:
            import fcntl
            try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise AdapterError("player_lease_conflict") from None
        locked=True
        stream.seek(1);stream.truncate()
        stream.write(json.dumps({"schema_version":1,"session_id":binding.session_id,"player_id":binding.player_id,"commander_id":binding.commander_id,"pid":os.getpid(),"mode":"read_only"}).encode("ascii"));stream.flush()
        yield path
    finally:
        if locked:
            stream.seek(0)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        stream.close()


def atomic_json(path,payload):
    import tempfile
    path.parent.mkdir(parents=True,exist_ok=True)
    name=None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,prefix=".health-",delete=False) as stream:
            name=Path(stream.name);json.dump(payload,stream,ensure_ascii=False,indent=2,allow_nan=False)
        name.replace(path)
    finally:
        if name is not None and name.exists():name.unlink()


def stop_requested(path: Path | None,binding: Binding):
    if path is None or not path.exists():return False
    try:
        value,_=read_json(path,4096)
        return isinstance(value,dict) and set(value)=={"stop","session_id","player_id","commander_id"} and value["stop"] is True and value["session_id"]==binding.session_id and type(value["player_id"]) is int and value["player_id"]==binding.player_id and value["commander_id"]==binding.commander_id
    except AdapterError:return False


async def serve(args):
    # Read only the selected stored credential. No environment/key fallback and
    # no automatic migration or profile changes are performed by this service.
    profile=load_profile(args.library,args.commander)
    raw,first_digest=read_json(args.snapshot_file)
    first=Snapshot.from_dict(raw)
    if first.player_id!=args.player or (args.session is not None and first.session_id!=args.session):
        raise AdapterError("initial_snapshot_binding")
    binding=Binding(first.session_id,args.player,profile.commander_id,profile.commander_name,profile.connection_id)
    instance=args.runtime/binding.session_id/("player-"+str(binding.player_id))/binding.commander_id
    with player_lease(args.runtime/"leases",binding):
        adapter=ChatAdapter(profile,pool=TransportPool(args.max_inflight),total_timeout=args.model_timeout,max_retries=args.http_retries,max_tokens=args.max_tokens,max_input_bytes=args.max_input_bytes)
        engine=StrategyEngine(binding,timeout_seconds=args.model_timeout+.25,max_response_age_seconds=args.max_response_age,min_hold_game_seconds=args.min_hold,audit_path=instance/"plans.jsonl",status_path=instance/"status.json",provenance_description="File snapshots and HTTP model adapter; no game actuator is connected.")
        agent=BattleAgent(engine,context_budget_bytes=args.context_bytes,memory_path=instance/"agent-state.json",jobs_path=instance/"jobs.json")
        agent.observe(first)
        pending=None;next_snapshot=raw;last_digest=first_digest;decisions=0;input_error=None
        def health():
            atomic_json(instance/"service-health.json",{"schema_version":1,"session_id":binding.session_id,"player_id":binding.player_id,"commander_id":binding.commander_id,"state":engine.public_status()["service_state"],"input_error":input_error,"transport":{**adapter.metrics,"last_error_code":adapter.last_error_code},"agent":agent.metrics,"policy_structure":adapter.last_diagnostics,"execution_enabled":False,"dry_run":True})
        try:
            while True:
                if stop_requested(args.stop_file,binding):
                    agent.stop()
                    if pending is not None:await asyncio.gather(pending,return_exceptions=True)
                    health();return {"state":"stopped","decisions":decisions,"execution_enabled":False}
                if pending is not None and pending.done():
                    try:result=pending.result()
                    except asyncio.CancelledError:raise
                    except Exception:raise AdapterError("decision_service_error") from None
                    decisions+=1;pending=None;health()
                    if args.once or (args.max_decisions and decisions>=args.max_decisions):
                        return {"state":result.status,"reason_code":result.reason_code,"decisions":decisions,"metrics":engine.metrics,"execution_enabled":False,"dry_run":True}
                try:
                    current,digest=read_json(args.snapshot_file)
                    if digest!=last_digest:
                        last_digest=digest
                        validated=agent.observe(current)
                        next_snapshot=validated
                        input_error=None
                except (AdapterError,ContractError) as error:
                    # Local parser/contract error codes only; never file contents.
                    input_error=str(error);health()
                if pending is None and next_snapshot is not None:
                    pending=asyncio.create_task(agent.decide(next_snapshot,adapter));next_snapshot=None
                await asyncio.sleep(args.poll_seconds)
        finally:
            if pending is not None and not pending.done():
                agent.stop();pending.cancel();await asyncio.gather(pending,return_exceptions=True)
            health()


def parser():
    p=argparse.ArgumentParser(description="HTTP model decisions from file snapshots; game execution remains disabled.")
    default=Path(os.environ.get("LOCALAPPDATA",Path.home()/".local/share"))/"TriadFrontCommander/library.v2.json"
    p.add_argument("--library",type=Path,default=default)
    p.add_argument("--commander",required=True,help="Stable commander UUID from desktop library")
    p.add_argument("--check-profile",action="store_true",help="Report only redacted readiness; makes no HTTP request")
    p.add_argument("--player",type=int)
    p.add_argument("--session",help="Optional pinned session UUID; first snapshot otherwise pins it")
    p.add_argument("--snapshot-file",type=Path)
    p.add_argument("--runtime",type=Path,default=Path(__file__).resolve().parent/"runtime-http")
    p.add_argument("--stop-file",type=Path)
    p.add_argument("--once",action="store_true")
    p.add_argument("--max-decisions",type=int,default=0)
    p.add_argument("--model-timeout",type=float,default=12)
    p.add_argument("--max-response-age",type=float,default=20)
    p.add_argument("--min-hold",type=float,default=15)
    p.add_argument("--poll-seconds",type=float,default=.25)
    p.add_argument("--http-retries",type=int,choices=[0,1],default=0)
    p.add_argument("--max-inflight",type=int,choices=[1,2,3,4],default=2)
    p.add_argument("--max-tokens",type=int,default=2048)
    p.add_argument("--context-bytes",type=int,default=8192,help="Bounded summary+delta budget; no full map is sent")
    p.add_argument("--max-input-bytes",type=int,default=16384,help="Total HTTP JSON input limit, including system preferences")
    return p


def main():
    args=parser().parse_args()
    if args.check_profile:
        try:
            profile=load_profile(args.library,args.commander)
            print(json.dumps({"ready":True,"model_configured":True,"credential_available":bool(profile.key),"keyless_loopback":not bool(profile.key) and profile.endpoint.loopback,"commander_id":profile.commander_id,"connection_id":profile.connection_id,"provider":profile.provider}))
            return 0
        except (AdapterError,ContractError) as error:
            print(json.dumps({"ready":False,"reason_code":str(error)}));return 2
        except Exception:
            print(json.dumps({"ready":False,"reason_code":"profile_unavailable"}));return 2
    if args.player is None or args.snapshot_file is None or not 0<=args.player<=15 or not .01<=args.poll_seconds<=5 or not .01<=args.model_timeout<=120 or not 0<=args.max_response_age<=60 or not 0<=args.min_hold<=60 or not 0<=args.max_decisions<=1000000 or not 4096<=args.context_bytes<=16384 or not 4096<=args.max_input_bytes<=32768:
        print(json.dumps({"error":"invalid_service_options"}));return 2
    try:
        result=asyncio.run(serve(args));print(json.dumps(result,ensure_ascii=False));return 0
    except KeyboardInterrupt:
        print(json.dumps({"state":"stopped","reason_code":"keyboard_interrupt","execution_enabled":False}));return 0
    except (AdapterError,ContractError) as error:
        print(json.dumps({"error":str(error),"execution_enabled":False}));return 2
    except Exception:
        print(json.dumps({"error":"service_unavailable","execution_enabled":False}));return 2


if __name__=="__main__":sys.exit(main())
