"""Entirely synthetic multi-turn session; no HTTP, credentials, or game process."""
import argparse
import asyncio
import json
from pathlib import Path
import uuid

from battle_agent import BattleAgent,BuildEvidence
from engine import StrategyEngine
from fixtures import SESSION,COMMANDER,binding,policy,snapshot


async def run(directory):
    agent=BattleAgent(StrategyEngine(binding(),audit_path=directory/"plans.jsonl",status_path=directory/"status.json"),event_capacity=8,build_evidence=BuildEvidence(str(uuid.uuid4()),SESSION,3,"simulated"),memory_path=directory/"agent-state.json",jobs_path=directory/"jobs.json")
    requests=0
    async def model(context):
        nonlocal requests
        requests+=1
        return policy(context)
    for index in range(1,61):
        await agent.decide(snapshot(index,100+index*4,events=[],enemy_observations=[]),model)
        task=agent.goals.tasks[0]
        if task.status=="planned":
            status,reason=("failed","insufficient_funds") if requests==3 else ("completed","ok")
            # This is a simulator receipt, explicitly source=simulated.
            agent.record_feedback({"session_id":SESSION,"player_id":3,"commander_id":COMMANDER,"task_id":task.task_id,"status":status,"reason_code":reason,"at_game_seconds":agent.latest.game_time_seconds,"source":"simulated"})
    print(json.dumps({"mode":"simulation","snapshots":60,"model_requests":requests,"memory_metrics":agent.metrics,"execution_enabled":False,"dry_run":True}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--runtime",type=Path,default=Path(__file__).resolve().parent/"runtime-battle-demo")
    asyncio.run(run(parser.parse_args().runtime))
