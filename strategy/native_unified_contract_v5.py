"""High-level strategy grammar; no unit/building/quantity/order parameters."""
FLAG_ACTIONS=('regroup','scout','withdraw','reinforce','budgeteconomy','budgetarmy','budgettech','deployattack','deploydefense','expand')
GATE_ACTIONS={'pauseconstruction':(0,False),'advanceconstruction':(0,True),
              'pauseproduction':(1,False),'advanceproduction':(1,True)}
NATIVE_ATTACK_ACTION='attackenemy'
FOCUS_ACTIONS={'focusenemy4':4,'focusenemy5':5}
RAID_ACTION='raideconomy'
STRATEGIC_ACTIONS=frozenset(FLAG_ACTIONS)|frozenset(GATE_ACTIONS)|{NATIVE_ATTACK_ACTION,RAID_ACTION}|frozenset(FOCUS_ACTIONS)
NEW_DOMAINS={'expand':'expansion','pauseconstruction':'construction_gate','advanceconstruction':'construction_gate',
             'pauseproduction':'production_gate','advanceproduction':'production_gate',NATIVE_ATTACK_ACTION:'native_attack'}
NEW_DOMAINS.update({action:'enemy_focus' for action in FOCUS_ACTIONS})
NEW_DOMAINS[RAID_ACTION]='native_attack'
WORK_ACTIONS=frozenset(a for a in FLAG_ACTIONS if not a.startswith('budget'))|{NATIVE_ATTACK_ACTION,RAID_ACTION}
INDEPENDENT_DEVELOPMENT_CONTRACT='native7_independent_development_v1'

def split_intents(actions):
    if type(actions) not in (tuple,list) or len(actions)>4 or any(type(a) is not str or a not in STRATEGIC_ACTIONS for a in actions) or len(set(actions))!=len(actions):
        raise ValueError('unified_high_level_actions_required')
    if any(action in FOCUS_ACTIONS for action in actions):
        raise ValueError('enemy_focus_requires_native7')
    if RAID_ACTION in actions:raise ValueError('economic_raid_requires_native7')
    if sum(a in WORK_ACTIONS for a in actions)>1 or sum(a.startswith('budget') for a in actions)>1:
        raise ValueError('unified_conflicting_flags')
    gates={};flags=[]
    for action in actions:
        if action in GATE_ACTIONS:
            gate,enabled=GATE_ACTIONS[action]
            if gate in gates:raise ValueError('unified_conflicting_manager_intents')
            gates[gate]=enabled
        else:flags.append(action)
    return tuple(flags),gates

def split_native7_intents(actions):
    if (type(actions) not in (tuple,list) or len(actions)>6
            or any(type(action) is not str or action not in STRATEGIC_ACTIONS for action in actions)
            or len(set(actions))!=len(actions)):
        raise ValueError('unified_high_level_actions_required')
    focus=[action for action in actions if action in FOCUS_ACTIONS]
    if len(focus)>1:raise ValueError('unified_conflicting_enemy_focus')
    # Expansion is an independent native builder preference. Military intents
    # still replace one another because they share native combat recruitment.
    military=[action for action in actions if action in WORK_ACTIONS and action!='expand']
    if len(military)>1:raise ValueError('unified_conflicting_flags')
    flags,gates=split_intents([action for action in actions if action not in FOCUS_ACTIONS and action not in ('expand',RAID_ACTION)])
    if 'expand' in actions:flags=flags+('expand',)
    if RAID_ACTION in actions:flags=flags+(RAID_ACTION,)
    return flags,gates,FOCUS_ACTIONS[focus[0]] if focus else None

def additional_catalog(actions):
    result={}
    for action in actions:
        if action in FOCUS_ACTIONS:
            result[action]=dict(domain='enemy_focus',goal='prefer_public_enemy_player',
                target_player_id=FOCUS_ACTIONS[action],target_policy='original_native_enemy_selector',
                details_owner='native_ai',maximum_duration_seconds=60,mission_success_verified=False)
        elif action==RAID_ACTION:
            result[action]=dict(domain='native_attack',goal='disrupt_enemy_mining',
                target_policy='original_native_safest_ground_harvester',
                execution_policy='original_medium_native_harassment_task',
                details_owner='native_ai',native_task_readiness_preserved=True,dispatch_timing_owner='agent',
                maximum_duration_seconds=60,mission_success_verified=False)
        elif action==NATIVE_ATTACK_ACTION:
            result[action]=dict(domain='native_attack',goal='pressure_enemy_through_native_target_selection',
                target_policy='original_native_closest_ground_structure_all_enemies',details_owner='native_ai',
                maximum_duration_seconds=60,mission_success_verified=False)
        elif action=='expand':
            result[action]=dict(domain='expansion',goal='additional_native_expansion_preference',
                target_policy='native_ai_selects_expansion_location_and_plan',details_owner='native_ai',
                stock_conditions_preserved=True,release_cancels_committed_work=False,
                release_blocks_autonomous_expansion=False,completion_guaranteed=False)
        elif action in GATE_ACTIONS:
            gate,enabled=GATE_ACTIONS[action]
            result[action]=dict(domain=NEW_DOMAINS[action],goal='advance_normal_native_scheduling' if enabled else 'defer_normal_native_scheduling',
                native_manager='base_builder' if gate==0 else 'unit_and_prerequisite_builder_family',
                details_owner='native_ai',opening_and_committed_work_not_globally_stopped=True,
                empty_action_restores_original_native_baseline=True,
                observed_enabled_state_is_not_completed_construction_or_production=True)
    return result
