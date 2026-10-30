"""Strategic-only model instructions; execution details remain native AI-owned."""
import json


def prompt(profile, context, example, allowed, preferences):
    choices = {key:'|'.join(value) if isinstance(value,list) else value for key,value in allowed.items()}
    choices.pop('production_focus',None)
    offered=context.get('allowed_macro_actions',[])
    from macro_policy import restore_public_defaults
    catalog=restore_public_defaults(context).get('macro_policy_catalog',{})
    region_map={action:catalog[action]['target_region'] for action in offered
                if isinstance(catalog.get(action),dict) and 'target_region' in catalog[action]}
    from native_unified_contract_v5 import GATE_ACTIONS
    unified=any(action in GATE_ACTIONS or action=='expand' for action in offered)
    choices['work_actions_choose_at_most_one']='|'.join(action for action in offered if not action.startswith('budget') and action not in GATE_ACTIONS)
    choices['budget_actions_choose_at_most_one']='|'.join(action for action in offered if action.startswith('budget'))
    if unified:
        for name in ('construction','production'):
            choices[name+'_gate_choose_at_most_one']='|'.join(a for a in offered if a in GATE_ACTIONS and name in a)
    text = (
        'JSON only;Example=shape;copy IDs/time. Strategic intent only. '
        'Original native AI owns ALL building selection/placement/order, unit types/counts, '
        'production/composition/cooperation and combat. No templates/quantities/coords/unit orders/scripts. '
        'production_focus=native_baseline;macro_production=null;tactical_tasks=[];runtime_task=null. '
        'macro_actions=flat allowed_macro_actions strings;ZERO OR ONE work_actions_choose_at_most_one '
        'plus ZERO OR ONE budget_actions_choose_at_most_one. NEVER combine scout with deploy/withdraw/regroup/reinforce/expand. '
        'objective_region MUST equal RegionMap[selected action] when that action is in RegionMap; otherwise null. '
        'Never invent region strings or coordinates. '
        'Budget=priority preference,not build permission or expansion proof;[] releases extras, '
        'does NOT stop all native building/production/combat. Unavailable intents stay unavailable. '
        'Lawful timed facts only;unknown stays unknown;ACK!=success;native effects not exclusively yours. '
        'Contact groups count observations,not exact units;retain oldest/newest ages and visible/last-seen distinction. '
        'Keep justified strategy;replan changed facts/no effect;no unknown retry. '
        'TTL5..60;budget has economy/army/tech/reserve, each0..1, EXACT sum1;reserve0.05..0.6. '
        'Budget fractions describe priorities,not currency;style grants no authority. '
    )
    text += ('length<=4;may also choose ZERO OR ONE construction_gate and ZERO OR ONE production_gate. '
             'advance/pause gates affect native scheduling only; native AI still selects all details; '
             'opening and committed tasks may continue. expand requests native expansion subject to stock guards; '
             '[] restores captured manager baseline, possibly disabled. State/task/movement!=completed mission. '
             if unified else 'length<=2. ')
    if isinstance(context.get('macro_strategy'), dict):
        from macro_strategy import STRATEGY_DECLARATION_SCHEMA
        from macro_policy import strategic_default_prompt
        schema = STRATEGY_DECLARATION_SCHEMA
        facts = context['macro_strategy'].get('fact_catalog', {})
        ref = next((key for key, value in facts.items() if value is not None), next(iter(facts), None))
        example['macro_strategy'] = dict(
            strategy_id=None, objective='hold', phase='wait', public_fact_refs=[ref],
            expected_observation='no_change', continue_conditions=['capability_available'],
            replan_conditions=['facts_changed'], resource_priorities=dict(example['budget']))
        choices.update({key: '|'.join(schema[key]) for key in ('objective', 'phase', 'expected_observation')})
        choices['conditions'] = '|'.join(schema['condition_values'])
        text += ('macro_strategy REQUIRED even for []. strategy_id MUST be JSON null if '
                 'macro_strategy.current_strategy is null OR objective changes; otherwise copy '
                 'macro_strategy.current_strategy.strategy_id EXACTLY. Never generate strategy IDs '
                 'or copy plan/session/commander IDs into strategy_id. refs1..4 from fact_catalog; '
                 'continue_conditions/replan_conditions MUST each be arrays of 1..3 unique EXACT strings from Enums.conditions; '
                 'priorities0..1 sum1. ' + strategic_default_prompt(strategic_only=True))
    return (text + '\nRegionMap: ' + json.dumps(region_map,ensure_ascii=False,separators=(',',':'))
            + '\nEnums: ' + json.dumps(choices, ensure_ascii=False, separators=(',', ':'))
            + '\nExample: ' + json.dumps(example, ensure_ascii=False, separators=(',', ':'))
            + '\nStyle: ' + json.dumps(preferences, ensure_ascii=False, separators=(',', ':')))
