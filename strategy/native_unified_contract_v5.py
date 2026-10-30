"""High-level strategy grammar; no unit/building/quantity/order parameters."""
FLAG_ACTIONS=('regroup','scout','withdraw','reinforce','budgeteconomy','budgetarmy','budgettech','deployattack','deploydefense','expand')
GATE_ACTIONS={'pauseconstruction':(0,False),'advanceconstruction':(0,True),
              'pauseproduction':(1,False),'advanceproduction':(1,True)}
STRATEGIC_ACTIONS=frozenset(FLAG_ACTIONS)|frozenset(GATE_ACTIONS)
NEW_DOMAINS={'expand':'expansion','pauseconstruction':'construction_gate','advanceconstruction':'construction_gate',
             'pauseproduction':'production_gate','advanceproduction':'production_gate'}
WORK_ACTIONS=frozenset(a for a in FLAG_ACTIONS if not a.startswith('budget'))

def split_intents(actions):
    if type(actions) not in (tuple,list) or len(actions)>4 or any(type(a) is not str or a not in STRATEGIC_ACTIONS for a in actions) or len(set(actions))!=len(actions):
        raise ValueError('unified_high_level_actions_required')
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

def additional_catalog(actions):
    result={}
    for action in actions:
        if action=='expand':
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
