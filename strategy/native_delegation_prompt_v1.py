"""Strategic-only model instructions; execution details remain native AI-owned."""
import json


def prompt(profile, context, example, allowed, preferences):
    example=dict(example,valid_for_game_seconds=60)
    choices = {key:'|'.join(value) if isinstance(value,list) else value for key,value in allowed.items()}
    choices.pop('production_focus',None)
    offered=context.get('allowed_macro_actions',[])
    from macro_policy import restore_public_defaults
    catalog=restore_public_defaults(context).get('macro_policy_catalog',{})
    region_map={action:catalog[action]['target_region'] for action in offered
                if isinstance(catalog.get(action),dict) and 'target_region' in catalog[action]}
    from native_unified_contract_v5 import GATE_ACTIONS,FOCUS_ACTIONS,INDEPENDENT_DEVELOPMENT_CONTRACT
    unified=any(action in GATE_ACTIONS or action=='expand' for action in offered)
    native7=any(action in FOCUS_ACTIONS for action in offered)
    independent=context.get('macro_intent_contract')==INDEPENDENT_DEVELOPMENT_CONTRACT
    choices['work_actions_choose_at_most_one']='|'.join(action for action in offered if not action.startswith('budget') and action not in GATE_ACTIONS and action not in FOCUS_ACTIONS and not (independent and action=='expand'))
    if independent:
        choices['development_actions_choose_at_most_one']='|'.join(action for action in offered if action=='expand')
    choices['budget_actions_choose_at_most_one']='|'.join(action for action in offered if action.startswith('budget'))
    if unified:
        for name in ('construction','production'):
            choices[name+'_gate_choose_at_most_one']='|'.join(a for a in offered if a in GATE_ACTIONS and name in a)
    if native7:
        choices['enemy_focus_choose_at_most_one']='|'.join(action for action in offered if action in FOCUS_ACTIONS)
    text = (
        'Return Example-shaped JSON;copy IDs/time;strategy fields only inside macro_strategy. '
        'Original native AI owns ALL building, production, unit, movement, combat and skill details. '
        'No templates/counts/coordinates/unit orders/scripts. '
        'production_focus=native_baseline;macro_production=null;tactical_tasks=[];runtime_task=null. '
        'macro_actions=flat Enums strings;choose within the independent Enums groups. '
        'objective_region=RegionMap[selected action] if present,else null. '
        '[] restores native baseline execution. '
        'Budget means priority preference;capabilities come only from allowed actions. '
        'Use lawful timed facts;unknown stays unknown;no unknown retry. ACK/state/task/movement leave '
        'success/attribution unverified. Preserve contact ages/visibility. '
        'Seek natural match victory. Assess economy,forces,lawful threats and opponents;reassess stagnation and home pressure. '
        'Assess contact regions/ages relative to home before defending; seek counterattack opportunities. '
        'Reassess army-only priority when mining or force growth stalls; evaluate economy, expansion and tech alongside threats. '
        'Budget preferences have no upfront purchase cost. '
        'Feedback native_account_shares=current own weights; catalog shares=preset weights. Compare before choosing. '
        'own_combat_change=net audited presence change since previous prepared request;casualties/causality unverified. '
        'Counts cover audited presence. building_presence_counts include foundations;operation/tech unverified. '
        'own.present.ore_collector=audited own miner forms;income unverified. '
        'TTL5..60 starts at based_on_game_time_seconds, including inference and dispatch time. '
        'Use valid_for_game_seconds=60 for sustained intents. '
        'Allow time for native scheduling. Expiry is never extended automatically. '
        'Budget economy/army/tech/reserve each0..1,sum1;reserve0.05..0.6. Style grants no authority. '
    )
    if native7:
        text=(
            'Return Example-shaped JSON. Copy binding IDs/time. Put strategy declaration inside macro_strategy. '
            'Original native AI owns ALL building, production, unit, movement, combat and skill details. '
            'Use allowed Enums strings only. Templates, quantities, coordinates and unit orders are unavailable. '
            'production_focus=native_baseline,macro_production=null,tactical_tasks=[],runtime_task=null. '
            'Each plan replaces all extra intents. Omitted domains return captured native baseline. '
            '[] restores native baseline execution. '
            'Assess economy,force growth,home pressure and counterattack opportunities against allied enemies. '
            'Contact groups retain owner_player_id,visibility and time bounds. Enemy counts cover lawful observations. '
            'Choose eligible focusenemy4/5 using public match state and lawful intelligence. '
            'Focus sets native enemy priority. Native AI selects targets and executes combat. '
            'Reassess after an announced elimination. Preserve uncertainty for unseen or old contacts. '
            'Budget actions express preferences with no upfront cost. Compare feedback current native_account_shares '
            'against catalog preset weights. Omit budget to let native AI choose. '
            'Reassess stalled growth through economy,expansion,tech and threats. expand retains stock guards. '
            'Native opening/committed tasks may continue. '
            'Own counts cover audited presence. Building operation,tech,income,casualties and exclusive causality remain unverified. '
            'Use TTL5..60 from based_on_game_time_seconds,including inference/dispatch. Use60 for sustained intents. '
            'Fresh plans can renew verified preferences. Expiry is finite. Unknown delivery forbids replay. '
            'ACK/state/task/movement leave mission success unverified. Seek natural match victory. '
            'objective_region=RegionMap[selected work] if present,else null. '
            'Budget economy/army/tech/reserve each0..1,sum1,reserve0.05..0.6. Style grants no authority. '
        )
    if context.get('working_memory', {}).get('match_state') is not None and not native7:
        text += 'working_memory.match_state gives actual public combatants,alliances and announced defeats. '
    if context.get('battlefield_summary') is not None:
        text += ('battlefield_summary separates home/mining proximity from distant visible forces. '
                 'Mobile counts include scouts;compare unit types and own identified scouts before assessing strength. '
                 'Proximity uses grid cells,not path distance. Zero observations preserve uncertainty. '
                 'Assess native raideconomy when enemy pressure is distant and mobile forces exist. '
                 'Enemy main-force contact alone does not establish a home emergency. '
                 'Reassess raid,regroup,defense and development as the economic and force picture changes. ')
    if 'attackenemy' in offered and not native7:
        text += 'Fresh plans may renew unchanged verified flags. '
    if independent:
        text += ('length<=6. Choose<=1 work,1 development,1 budget,1 enemy_focus,1 construction_gate,1 production_gate. '
                 'Development and military intents may coexist. Include each intent to retain it in a replacement plan. ')
        if catalog.get('expand',{}).get('strategic_timing_owner')=='agent':
            text += ('expand timing follows your intent while native target selection,readiness and execution remain native. '
                     'raideconomy reuses the native attackenemy executor with native safest harvester selection. '
                     'pauseconstruction suspends the whole native construction manager,including expansion follow-up and recovery. ')
    elif native7:
        text += 'length<=5. Choose<=1 work,1 budget,1 enemy_focus,1 construction_gate,1 production_gate. '
    elif unified:
        text += ('length<=4;<=1 construction_gate+1 production_gate. Native opening/committed tasks may continue. '
                 'expand retains stock guards and may outlive preference. [] restores captured baseline,possibly disabled. ')
    else:
        text += 'length<=2. '
    if isinstance(context.get('macro_strategy'), dict):
        from macro_strategy import STRATEGY_DECLARATION_SCHEMA
        from macro_policy import strategic_default_prompt
        schema = STRATEGY_DECLARATION_SCHEMA
        facts = context['macro_strategy'].get('fact_catalog', {})
        # The SDK sorts context keys. Keep preparation and send-time prompts identical.
        ref = ('own.credits' if facts.get('own.credits') is not None else
               next((key for key in sorted(facts) if facts[key] is not None), next(iter(sorted(facts)), None)))
        example['macro_strategy'] = dict(
            strategy_id=None, objective='hold', phase='wait', public_fact_refs=[ref],
            expected_observation='no_change', continue_conditions=['capability_available'],
            replan_conditions=['facts_changed'], resource_priorities=dict(example['budget']))
        choices.update({key: '|'.join(schema[key]) for key in ('objective', 'phase', 'expected_observation')})
        choices['conditions'] = '|'.join(schema['condition_values'])
        defaults = ('Schema-masked verification flags, automatic_retry_allowed and grants_capability default false. '
                    'Explicit values prevail. Native AI owns unit operations. '
                    if 'attackenemy' in offered else strategic_default_prompt(strategic_only=True))
        text += ('Always include macro_strategy,including []. strategy_id=JSON null for absent current strategy '
                 'or changed objective;otherwise copy macro_strategy.current_strategy.strategy_id exactly. '
                 'Use1..4 fact_catalog refs. Each condition list needs1..3 unique Enums.conditions strings. '
                 'Priorities0..1,sum1. ' + defaults)
    return (text + '\nRegionMap: ' + json.dumps(region_map,ensure_ascii=False,separators=(',',':'))
            + '\nEnums: ' + json.dumps(choices, ensure_ascii=False, separators=(',', ':'))
            + '\nExample: ' + json.dumps(example, ensure_ascii=False, separators=(',', ':'))
            + '\nStyle: ' + json.dumps(preferences, ensure_ascii=False, separators=(',', ':')))
