"""G8 descriptive comparison; small uncontrolled samples do not prove win uplift."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'acceptance')]
from assess_macro_desktop import load,records,sha


def verified_report(relative):
    path=ROOT/relative;value=load(path)
    if sha(path.parent/'assessor.py')!=value['assessor_sha256']:raise ValueError('comparison_assessor_changed')
    if not value.get('evidence') or any(sha(Path(p))!=digest for p,digest in value['evidence'].items()):
        raise ValueError('comparison_evidence_changed')
    return path,value


def evaluate():
    base_path=ROOT/'reports/macro-baseline-outcome-77056-20261028-v1/assessment.json';base=load(base_path)
    baseline_sources={str((ROOT/p).resolve()):digest for p,digest in base['sources'].items()}
    if any(sha(Path(p))!=digest for p,digest in baseline_sources.items()):raise ValueError('baseline_source_changed')
    rows=records(Path(next(iter(baseline_sources))));live=[r for r in rows if r['simulation_frame']>0]
    last=live[-1];native=last['result_records']
    baseline_native=(native[0]['defeat_frame']>0 and native[0]['victory_frame']==0
        and native[1]['victory_frame']>0 and native[1]['defeat_frame']==0
        and base['recorded_participant_mapping_verified'] is True
        and [(r['player_index'],r['manager_index']) for r in base['participants']]==[(3,0),(4,1)]
        and base['model_calls']==0 and base['native_commands']==0)
    fixed_path,fixed=verified_report('reports/macro-fixed-outcome-72168-20261028-v1/assessment.json')
    fixed_effect_path,fixed_effect=verified_report('reports/macro-base-defense-assessment-72168-20261028-v1/assessment.json')
    model_path,model=verified_report('reports/macro-complete-match-77280-20261028-v1/assessment.json')
    budget_path,budget=verified_report('reports/macro-budget-lifecycles-9284-20261028-v1/assessment.json')
    regions_path,regions=verified_report('reports/macro-desktop-regions-9284-20261028-v1/assessment.json')
    style_paths=[];styles=[]
    for pid in (77356,9284):
        p,s=verified_report(f'reports/macro-style-shadow-assessment-{pid}-20261028-v1/assessment.json')
        style_paths.append(p);styles.append(s)
    checks=dict(
        native_baseline_has_no_model_or_commands_and_native_loss=baseline_native,
        fixed_policy_has_native_effect_and_natural_outcome=fixed['native_winner_mapping_verified'] is True
            and fixed['model_calls']==0 and fixed['unit_orders']==0 and fixed['fixed_macro_intents']==2
            and fixed['fixed_policy_released_before_natural_result'] is True
            and fixed_effect['bounded_native_base_defense_effect_verified'] is True,
        model_has_genuine_closed_loop_and_natural_outcome=model['full_G7_verified'] is True
            and model['real_model_responses']==58 and model['native_macro_plan_dispatches']==52,
        styles_consumed_with_same_historical_observation=all(s['actual_style_profile_consumed'] is True
            and s['same_public_observation'] is True and s['same_wire_request_within_each_style'] is True for s in styles),
        valid_style_decisions_differ=all(s['valid_decision_difference_pairs']>=1 for s in styles),
        directed_live_choices_have_separate_native_effect=budget['model_technology_adoption_verified'] is True
            and budget['bounded_budget_feedback_loop_verified'] is True
            and any(r['action']=='budgettech' and r['native_adoption_verified']
                and r['feedback_to_later_genuine_response_verified'] for r in budget['budget_results'])
            and regions['bounded_regional_feedback_loop_verified'] is True,
        shadow_is_separate_from_live=all(s['native_dispatches']==0 and s['live_game_access'] is False for s in styles),
        causal_and_winrate_limits_preserved=all(s['causal_style_effect_verified'] is False
            and s['model_nondeterminism_controlled'] is False and s['win_rate_effect_verified'] is False for s in styles))
    comparisons=[dict(mode='native_baseline',pid=77056,model_responses=0,model_plans=0,native_macro_commands=0,
        outcome='defeat',native_behavior='original_native_ai',prospective_ai_identity_verified=False),
        dict(mode='fixed_macro',pid=72168,model_responses=0,model_plans=0,fixed_intents=2,
            native_flag_commands_including_clears=5,outcome=fixed['controlled_side_outcome'],
            native_behavior='owned_native_defenders_near_own_infrastructure',policy_window='released_before_natural_result'),
        dict(mode='model_macro',pid=77280,model_responses=58,model_plans=52,outcome=model['model_side_outcome'],
            native_behavior='budget_production_scout_effects_with_later_genuine_feedback',policy_window='opening_to_natural_result')]
    paths=[base_path,fixed_path,fixed_effect_path,model_path,budget_path,regions_path,*style_paths]
    return dict(kind='user_macro_G8_descriptive_contribution_assessment',checks=checks,full_G8_verified=all(checks.values()),
        comparisons=comparisons,style_pairs=sum(s['pairs'] for s in styles),
        genuine_shadow_responses=sum(s['real_provider_returns'] for s in styles),
        valid_shadow_policies=sum(s['valid_policies'] for s in styles),
        valid_style_difference_pairs=sum(s['valid_decision_difference_pairs'] for s in styles),
        configuration_applied_verified=True,decision_difference_observed=True,
        separate_live_native_adoption_verified=checks['directed_live_choices_have_separate_native_effect'],
        causal_live_style_behavior_difference_verified=False,controlled_random_seeds=False,
        equal_policy_windows=False,win_rate_improvement_verified=False,statistical_strength='descriptive_single_cases',
        micro_or_combat_damage_contribution_claimed=False,formal_goal_complete=False,
        evidence={**baseline_sources,**{str(p.resolve()):sha(p) for p in paths}})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_contribution_report_required')
    value=evaluate();out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))


if __name__=='__main__':main()
