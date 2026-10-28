"""Join local macro G0-G8 evidence, restoration, cleanup and final delivery."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'acceptance')]
from assess_macro_desktop import load,records,sha
from assess_macro_contribution import verified_report

CURRENT_RUN=ROOT/'acceptance/runs/20261028-133800-macro-probe'


def evaluate(delivery):
    reports={};evidence={}
    for stage,folder in [('G6','macro-capability-coverage-20261028-v1'),
            ('G7','macro-complete-match-77280-20261028-v1'),('G8','macro-contribution-comparison-20261028-v1'),
            ('defense','macro-desktop-base-defense-11428-20261028-v1')]:
        p,v=verified_report(f'reports/{folder}/assessment.json');reports[stage]=v;evidence[str(p)]=sha(p)
    run=CURRENT_RUN;host=run/'battle-host';status=load(host/'host-status.json');executed=load(run/'executed-client.json')
    events=records(host/'host-events.jsonl');requests=[r['context'] for r in events if r['kind']=='model_macro_request_context']
    plans=[r['plan'] for r in events if r['kind']=='plan_applied'];frozen=load(host/'sources.json')['sources']
    retained=all(sha(host/'source'/r['copy'])==r['sha256'] for r in frozen)
    frontend=all(sha(run/'executed-client-dist'/r['path'])==r['sha256'] for r in executed['frontend'])
    active_exe=ROOT/'desktop-ui/src-tauri/target/debug/tacticore-desktop.exe'
    release=load(host/'macro-release.json');ended=load(run/'fixture-ended.json')
    restore_path=ROOT/'reports/macro-base-defense-style-restoration-20261028.json';restore=load(restore_path)
    original=load(ROOT/'reports/macro-base-defense-directed-original-profile-20261028.json')
    restored=load(ROOT/'reports/macro-base-defense-restored-profile-20261028.json')
    same_draft=lambda a,b:{k:v for k,v in a['draft'].items() if k!='revision'}=={k:v for k,v in b['draft'].items() if k!='revision'}
    audit_path=ROOT/'reports/macro-base-defense-from-regions-preservation-20261028-v1/audit.json';audit=load(audit_path)
    preserved=all(sha(Path(p))==h for p,h in audit['evidence'].items()) and audit['original_micro_assets_preserved'] is True
    bundle=load(run/'macro-budget-bundle.json')
    guard_logs={
        'macro':('macro-base-defense-macro-tests-20261028-v1.log','Ran 113 tests'),
        'host':('macro-base-defense-host-tests-20261028-v1.log','Ran 456 tests'),
        'strategy':('macro-base-defense-strategy-tests-20261028-v1.log','Ran 250 tests'),
        'opening':('macro-base-defense-opening-tests-20261028-v1.log','Ran 15 tests'),
        'expiry':('macro-production-native-expiry-replay-tests-20261028-v1.log','Ran 6 tests')}
    guards=all(expected in (ROOT/'reports'/name).read_text(encoding='utf8')
        and (ROOT/'reports'/name).read_text(encoding='utf8').rstrip().endswith('OK') for name,expected in guard_logs.values())
    dispatch_kinds={'model_macro_native_acknowledged','model_macro_production_acknowledged',
        'model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged'}
    qualified_roles=set(reports['G6'].get('independently_qualified_model_deployment_roles',[]))
    # Existing direct evidence establishes these three bounded roles. It does
    # not automatically turn movement into regroup/reinforce/withdraw support.
    if reports['G6']['checks']['two_regions_native_group_movement_and_later_model_feedback']:
        qualified_roles.add('attack')
    if reports['G6']['checks']['same_owned_units_later_reassigned']:qualified_roles.add('reassign')
    if reports['defense']['bounded_model_defense_feedback_loop_verified']:qualified_roles.add('defense')
    stop=next(i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started')
    quiet=not any(r['kind']=='commander_model_call_started' or r['kind'].endswith('_prepared')
        or r['kind'] in dispatch_kinds for r in events[stop+1:])
    scope=dict(
        G0=retained and status['jobs']==[] and all(c.get('control_mode')=='macro_native' for c in requests)
            and all(p.get('runtime_task') is None and not p.get('tactical_tasks') for p in plans)
            and preserved and sha(ROOT.parent/'Mods/TFCommanderPlay/TFNames.big')=='2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665',
        G1=bundle['schema_version']==8 and len(bundle['pins'])>=150
            and all(c.get('macro_policy_catalog',{}).get('deploydefense',{}).get('goal')=='original_native_defense_of_own_infrastructure'
                for c in requests if 'deploydefense' in c.get('allowed_macro_actions',[]))
            and reports['G6']['full_G6_verified'],
        G2=guards and reports['defense']['shared_checks']['exact_public_request_context_retained']
            and reports['G6']['checks']['actual_user_stop_preserves_bounded_production']
            and reports['defense']['bounded_defense_lifecycles_verified'],
        G3=reports['G7']['prior_strategy_memory_rounds']>=2 and len(requests)>=2
            and reports['defense']['shared_checks']['multiple_real_model_rounds']
            and not any(r['kind']=='host_fault' for r in events),
        G4=reports['G6']['full_G6_verified'] and preserved,
        G5=retained and frontend and sha(active_exe)==executed['executable_sha256']
            and executed['opening_wait_armed_via_actual_ui'] is True and executed['profile_revision']==load(host/'profile.json')['revision']
            and all(reports['defense']['shared_checks'].values()) and status['state']=='stopped'
            and status['reason_code']=='user_stop' and quiet and release['native_release_verified'] is True,
        G6=reports['G6']['full_G6_verified'] and {'attack','defense','regroup','reinforce','withdraw','reassign'}<=qualified_roles,
        G7=reports['G7']['full_G7_verified'],G8=reports['G8']['full_G8_verified'])
    manifest=load(delivery/'manifest.json')
    integrity=all((delivery/name).parent==delivery and sha(delivery/name)==v['sha256']
        and (delivery/name).stat().st_size==v['bytes'] for name,v in manifest['files'].items())
    review_path=ROOT/'reports/macro-timeline-base-defense-11428-20261028-v1/browser-review.json';review=load(review_path)
    playback=all(sha(review_path.parent/n)==h for n,h in review['files'].items()) and all(review[k] is True for k in
        ('play_verified','pause_verified','seek_verified','defender_feedback_visible','stop_release_visible'))
    final_checks=dict(all_G0_G8=all(scope.values()),final_delivery_integrity=integrity,
        standalone_playable_timelines=playback and sha(delivery/'defense-timeline.html')==sha(review_path.parent/'macro-timeline.html')
            and sha(delivery/'macro-timeline.html')==sha(ROOT/'reports/macro-timeline-77280-20261028-v2/macro-timeline.html'),
        replay_fidelity_limits_disclosed=manifest['native_replay_fidelity_verified'] is False
            and '不保证重现外部宏观指令' in (delivery/'README.txt').read_text(encoding='utf8'),
        temporary_style_restored=restore['restore_required'] is False and restore['restored_via_actual_ui'] is True
            and same_draft(original,restored) and restored['revision']==15,
        owned_research_session_cleaned=ended['exact_owned_process_handle_terminated'] is True
            and ended['all_macro_flags_clear'] is True and ended['native_macro_lease_absent'] is True
            and ended['natural_settlement'] is True,
        no_new_commands_after_user_stop=quiet)
    paths=[run/'session.json',run/'executed-client.json',run/'fixture-ended.json',run/'macro-budget-bundle.json',
        host/'host-status.json',host/'host-events.jsonl',host/'sources.json',host/'macro-release.json',restore_path,
        ROOT/'reports/macro-base-defense-directed-original-profile-20261028.json',
        ROOT/'reports/macro-base-defense-restored-profile-20261028.json',audit_path,review_path,delivery/'manifest.json',active_exe]
    paths.extend(ROOT/'reports'/name for name,_ in guard_logs.values())
    evidence.update({str(p.resolve()):sha(p) for p in paths})
    return dict(kind='user_macro_G0_G8_local_goal_assessment',objective='docs/commander-macro-goal-20261027.md',
        phase_checks=scope,final_checks=final_checks,formal_goal_complete=all(final_checks.values()),
        local_scope='fixed RA3 1.12 / TemplePrime / P3 Soviet / individually qualified macro consumers',
        micro_control_enabled=False,win_rate_uplift_verified=False,arbitrary_map_or_faction_coverage_verified=False,
        client_cross_machine_portability_verified=False,native_replay_fidelity_verified=False,
        current_model_responses=reports['defense']['real_model_responses'],current_model_plan_dispatches=len(plans),
        missing_independent_model_deployment_roles=sorted({'attack','defense','regroup','reinforce','withdraw','reassign'}
            -qualified_roles),
        complete_match_model_side_outcome=reports['G7']['model_side_outcome'],
        configuration_revision_restored=restored['revision'],delivery=str(delivery),evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--delivery',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_goal_assessment_required')
    value=evaluate(a.delivery.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))


if __name__=='__main__':main()
