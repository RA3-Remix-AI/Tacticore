"""Synthetic, offline Agent.run demonstration using the existing host contract."""
import asyncio
import json


async def main():
    from engine import StrategyEngine, parse_model_json
    from fixtures import COMMANDER, CONNECTION, binding, policy, snapshot
    from http_adapter import Endpoint, Profile, system_prompt
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
    from .pydantic_backend import PydanticBackend

    selected = Profile(COMMANDER, "Offline fixture", CONNECTION, "自定义", "fixture-model", 0, "", Endpoint.parse("http://127.0.0.1:1/v1"), "")
    async def fake(messages, info):
        payload = next(part.content for message in reversed(messages) for part in message.parts if isinstance(part, UserPromptPart))
        return ModelResponse(parts=[TextPart(json.dumps(policy(json.loads(payload))))], finish_reason="stop")
    adapter = PydanticBackend(FunctionModel(fake), parse_json=parse_model_json,
        system_prompt=lambda ctx: system_prompt(selected, ctx), commander_id=COMMANDER)
    engine = StrategyEngine(binding())
    result = await engine.decide(snapshot(), adapter)
    print(json.dumps({"backend": "pydantic", "fixture": True,
        "status": result.status, "production_focus": result.plan.production_focus,
        "execution_enabled": engine.public_status()["execution"]["enabled"]}, ensure_ascii=False))


if __name__ == "__main__": asyncio.run(main())
