"""Aggregate bounded G6 domains without requiring every intent to succeed."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'acceptance')]
from assess_macro_desktop import load,sha
from assess_macro_contribution import verified_report
from assess_macro_desktop_production import assess as recompute_production
from assess_macro_desktop_construction import assess as recompute_construction


def replay_legacy_domain(path,assessor):
    """Older domain reports omit a source ledger; reconstruct it from raw data."""
    old=load(path)
    if sha(path.parent/'assessor.py')!=old['assessor_sha256']:raise ValueError('domain_assessor_changed')
    matches=[p.parent for p in (ROOT/'acceptance/runs').glob('*/session.json')
        if load(p).get('session_id')==old['session_id']]
    if len(matches)!=1:raise ValueError('domain_exact_session_required')
    run=matches[0];value=assessor(run,old['run_id']);host=run/'battle-host'
    native=ROOT/'reports'/('macro-desktop-'+old['run_id'])
    files=[path,host/'host-events.jsonl',host/'host-status.json',host/'sources.json',host/'profile.json',
        native/'preflight.json',native/'final-state.json',native/'policy-probe.jsonl']
    return value,{str(p.resolve()):sha(p) for p in files}


def evaluate(defense_path):
    specs={
        'construction':'macro-desktop-construction-80688-20261028-v1',
        'budget':'macro-budget-lifecycles-9284-20261028-v1',
        'production':'macro-desktop-production-77280-20261028-v2',
        'production_user_stop':'macro-desktop-production-68212-20261028-v2',
        'scouting':'macro-desktop-scouting-77280-20261028-v1',
        'regions':'macro-desktop-regions-9284-20261028-v1'}
    evidence={};values={}
    for name,folder in specs.items():
        p=ROOT/f'reports/{folder}/assessment.json'
        if name in ('construction','production','production_user_stop'):
            v,raw_evidence=replay_legacy_domain(p,recompute_construction if name=='construction' else recompute_production)
            evidence.update(raw_evidence)
        else:p,v=verified_report(str(p))
        values[name]=v;evidence[str(p)]=sha(p)
    p,d=verified_report(str(defense_path.resolve().relative_to(ROOT)));values['defense']=d;evidence[str(p)]=sha(p)
    if sha(p.parent/'presence-helper.py')!=d['presence_helper_sha256']:raise ValueError('defense_helper_changed')
    c,b,prod,stop,s,r=(values[k] for k in ('construction','budget','production','production_user_stop','scouting','regions'))
    positive_prod=[x for x in prod['production_results'] if x['model_plan_bound'] and x['native_ack_matches']
        and x['observed_queue_goal_met'] and x['bounded_release_verified']
        and any(f['observed_counts_match'] and f['within_freshness'] for f in x['production_feedback_in_followup_requests'])]
    scout_positive=[x for x in s['scouting_results'] if x['real_model_plan_bound'] and x['native_ack_matches']
        and x['own_native_group_movement_verified'] and x['new_legal_contacts_in_bound_window']>0
        and x['feedback_returned_to_later_model_verified']]
    adopted={x['action'] for x in b['budget_results'] if x['model_and_ack_bound'] and x['native_adoption_verified']
        and x['feedback_to_later_genuine_response_verified']}
    checks=dict(
        model_build_intent_native_queue_and_foundation_feedback=c['durable_construction_loop_verified'] is True
            and c['some_model_construction_effect_verified'] is True and c['bounded_construction_lifecycle_verified'] is True,
        economic_and_technology_allocation_native_adoption_and_feedback=b['bounded_budget_feedback_loop_verified'] is True
            and {'budgeteconomy','budgettech'}<=adopted,
        model_unit_type_and_quantity_native_queue_effect_and_feedback=bool(positive_prod)
            and prod['bounded_production_lifecycle_verified'] is True,
        actual_user_stop_preserves_bounded_production=stop['durable_production_loop_verified'] is True
            and stop['user_stop_completed'] is True,
        scout_native_movement_lawful_contact_and_later_model_feedback=bool(scout_positive)
            and s['bounded_scouting_feedback_loop_verified'] is True,
        two_regions_native_group_movement_and_later_model_feedback=r['bounded_regional_feedback_loop_verified'] is True
            and set(r['model_selected_public_regions'])=={'region_1_3','region_8_3'},
        same_owned_units_later_reassigned=r['same_units_reassigned_verified'] is True,
        real_native_infrastructure_defense_and_later_model_feedback=d['bounded_model_defense_feedback_loop_verified'] is True,
        unit_operations_remain_native=all(v.get('mission_success_verified',False) is False for v in (s,r,d))
            and d['native_ai_selects_structure_and_operates_units'] is True)
    return dict(kind='user_macro_G6_bounded_domain_coverage',checks=checks,full_G6_verified=all(checks.values()),
        positive_production_types=sorted({x['action'] for x in positive_prod}),
        positive_production_quantities=sorted({x['additional_count'] for x in positive_prod}),
        observed_budget_actions_with_later_feedback=sorted(adopted),
        construction_is_directed_qualification=c['directed_acceptance_scenario'],
        autonomous_free_build_choice_verified=False,all_intents_successful=False,
        coverage=dict(building='SovietPowerPlantAdvanced preference; queue and own foundation',
            budgets='economy, army, technology native account shares',
            production='qualified Conscript1, Flak2/3, HammerTank1 preferences; quantities are new native queue acceptances',
            scouting='timing and native target selection; lawful contacts not exclusively attributed',
            deployment='two fixed public regions and owned-group reassignment in qualified region package',
            defense='native AI chooses own infrastructure and operates defenders in new package'),
        arbitrary_map_or_faction_coverage_verified=False,arbitrary_unit_selection_verified=False,
        guaranteed_arrival_or_combat_success=False,forced_physical_return_required=False,
        full_G7_verified=False,full_G8_verified=False,formal_goal_complete=False,evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--defense-assessment',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_capability_coverage_required')
    value=evaluate(a.defense_assessment);out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))


if __name__=='__main__':main()
