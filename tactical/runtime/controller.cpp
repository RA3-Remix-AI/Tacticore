#include "controller.h"
#include <algorithm>
#include <stdexcept>

namespace tacticore::runtime {
Controller::Controller(Binding b,IO& io,Limits l,uint64_t seq):binding_(b),io_(io),limits_(l),last_sequence_(seq){
    if(!nonzero(b.session)||!nonzero(b.commander)||!nonzero(b.host)||b.player>15||!b.pid||!b.thread||!b.process_start||b.binding_hash==Digest{}||l.settle_samples<3||!l.max_lease_frames||!l.max_no_progress_frames||!l.max_home_clearance_wait_frames||l.max_home_clearance_wait_frames>l.max_lease_frames||!l.watchdog_ms||l.max_lease_ms<l.watchdog_ms||l.recovery_return_ms<l.watchdog_ms||l.recovery_return_ms>l.max_lease_ms||l.max_distance<=0||l.arrival_radius<=0)throw std::invalid_argument("invalid_runtime_binding_or_limits");
}
const char* Controller::guard(const Sample& s,const Actor& actor,bool require_guard){
    if(!(s.binding==binding_)||!s.identity||s.current_thread!=binding_.thread)return "native_binding_or_thread_changed";
    if(clock_seen_&&(s.frame<last_frame_||s.monotonic_ms<last_ms_))return "dual_clock_regressed";
    if(!(s.actor==actor)||!actor.generation||!actor.born_frame||s.frame<actor.born_frame||!s.actor_birth_verified)return "actor_incarnation_unverified";
    if(!s.live_list_member||!s.grounded||!finite(s.xyz))return "actor_not_live_owned_ground";
    if(!s.team||!s.default_team||!s.script_team||s.default_team==s.script_team)return "native_team_binding_invalid";
    if(require_guard&&!s.interference_guard_ready)return "command_interference_guard_unavailable";
    return nullptr;
}
void Controller::publish(const Sample& s,const char* kind,const char* reason){
    result_.frame=s.frame;result_.monotonic_ms=s.monotonic_ms;result_.reason=reason;
    last_frame_=s.frame;last_ms_=s.monotonic_ms;clock_seen_=true;
    io_.event(Event{result_,kind,s});
}
Receipt Controller::reject(const Command& c,const char* why){
    Receipt r=result_;r.command=c.command;r.task=c.task;r.lease=c.lease;r.sequence=c.sequence;r.accepted=false;r.reason=why;
    io_.event(Event{r,"command_rejected"});return r;
}
Receipt Controller::uncertain(const Sample& s,const char* why){
    io_.clear_native_preemption();
    result_.phase=Phase::Uncertain;action_pending_=false;publish(s,"uncertain",why);return result_;
}
void Controller::phase(Phase p,const Sample& s,const char* why){
    result_.phase=p;phase_frame_=s.frame;stable_=0;last_stable_frame_=s.frame;previous_=s.xyz;action_pending_=false;publish(s,"phase",why);
    if(p==Phase::Moving||p==Phase::Returning){last_progress_frame_=s.frame;best_target_distance_=distance(s.xyz,p==Phase::Moving?current_.target:home_);}
}
bool Controller::issue(Action a,const Sample& s,Point target,uint32_t stance){
    // A pending attempt is never repeated, including after a timeout.
    if(action_pending_)return false;
    if(a==Action::Move&&result_.phase==Phase::Returning){
        if(home_move_attempted_){uncertain(s,"home_move_already_attempted_no_retry");return false;}
        // Count the attempt even when IO refuses before calling the SDK.
        home_move_attempted_=true;
    }
    action_pending_=true;pending_for_=result_.phase;phase_frame_=s.frame;
    auto d=io_.issue(a,target,stance);
    if(d!=Delivery::NotSent)result_.sdk_calls[static_cast<unsigned>(a)-1]++;
    publish(s,"sdk_attempt",d==Delivery::Sent?"native_attempt_waiting_observation":d==Delivery::NotSent?"native_admission_lost":"native_delivery_unknown");
    if(d==Delivery::NotSent&&a==Action::Borrow&&result_.sdk_calls[0]==0){
        auto fresh=io_.sample();
        // The last-frame lender recheck can fail after Reserve. An explicit
        // NotSent and a fresh native non-script owner prove we never acquired
        // this actor. Close only the logical claim, without a compensating SDK
        // call, home assertion or retry. Unknown delivery still retains it.
        if(!guard(fresh,current_.actor)&&fresh.team!=fresh.script_team){
            action_pending_=false;have_lease_=false;result_.held=false;
            result_.physical_home=false;result_.control_released=true;
            result_.stance_restored=fresh.stance==original_stance_;
            phase(Phase::Released,fresh,"borrow_not_sent_no_control_transfer");
            return false;
        }
    }
    if(d!=Delivery::Sent)uncertain(s,d==Delivery::NotSent?"native_admission_lost":"native_delivery_unknown");
    return d==Delivery::Sent;
}
bool Controller::settled(const Sample& s){
    if(s.frame==last_stable_frame_)return false;
    bool ok=s.settled&&s.stance==2&&s.team==s.script_team&&distance(s.xyz,previous_)<=1;
    previous_=s.xyz;last_stable_frame_=s.frame;stable_=ok?stable_+1:0;
    return stable_>=limits_.settle_samples;
}
Receipt Controller::submit(const Command& c){
    auto found=std::find_if(seen_.begin(),seen_.end(),[&](const Command& x){return x.command==c.command;});
    if(found!=seen_.end())return *found==c?reject(c,"duplicate_command_no_dispatch"):reject(c,"command_identity_conflict");
    if(!nonzero(c.command)||!nonzero(c.task)||!nonzero(c.lease)||!c.sequence||c.sequence<=last_sequence_||seen_.size()>=1024)return reject(c,"command_identity_or_sequence_invalid");
    if(c.operation!=Operation::Reserve&&c.operation!=Operation::MoveHold&&c.operation!=Operation::ReturnHome&&c.operation!=Operation::EmergencyRelease&&c.operation!=Operation::Query&&c.operation!=Operation::ReconcileRelease&&c.operation!=Operation::ReconcileReturnHome&&c.operation!=Operation::DiagnosticForeignMove)return reject(c,"operation_unreviewed");
    auto s=io_.sample();
    if(auto why=guard(s,c.actor))return reject(c,why);
    if(c.expires_frame<=s.frame||c.expires_monotonic_ms<=s.monotonic_ms)return reject(c,"command_expired");
    if(s.paused)return reject(c,"game_paused");
    if(c.operation!=Operation::Reserve&&(!have_lease_||c.task!=current_.task||c.lease!=current_.lease||!(c.actor==current_.actor)))return reject(c,"lease_task_actor_mismatch");
    if(recovery_home_&&result_.phase!=Phase::Uncertain&&c.operation!=Operation::Query&&c.operation!=Operation::EmergencyRelease)return reject(c,"safety_recovery_already_active");
    if(c.operation==Operation::Reserve){
        if(have_lease_||result_.phase==Phase::Uncertain)return reject(c,"prior_lease_not_released");
        if(s.team==s.script_team||s.stance!=0||c.lease_deadline_frame<=s.frame||c.lease_deadline_frame-s.frame>limits_.max_lease_frames)return reject(c,"reserve_scope_invalid");
        if(std::any_of(seen_.begin(),seen_.end(),[&](const Command& x){return x.lease==c.lease;}))return reject(c,"lease_id_reused");
        if(!io_.independent_borrow_permitted(s))return reject(c,"native_lender_quiescence_unverified");
        if(!io_.remember_home(s))return reject(c,"private_home_ground_or_vacancy_unverified");
    }else if(c.operation==Operation::MoveHold){
        if(result_.phase!=Phase::Ready)return reject(c,"actor_not_ready");
        if(!finite(c.target)||distance(c.target,home_)>limits_.max_distance||distance(c.target,home_)<20||std::fabs(c.target.z-home_.z)>limits_.height_delta||!io_.ground_target(c.target)||c.hold_frames>limits_.max_lease_frames)return reject(c,"target_outside_local_ground_scope");
        if(c.lease_deadline_frame!=current_.lease_deadline_frame)return reject(c,"lease_deadline_changed");
    }else if(c.operation==Operation::DiagnosticForeignMove){
        if(!io_.diagnostic_fault_enabled()||diagnostic_fault_used_)return reject(c,"diagnostic_fault_disabled_or_used");
        if(result_.phase!=Phase::Holding||s.team!=s.script_team||!s.settled||s.stance!=2||s.foreign_epoch!=foreign_epoch_||s.frame>=current_.lease_deadline_frame||s.monotonic_ms-last_observation_ms_>limits_.watchdog_ms)return reject(c,"diagnostic_fault_actor_not_holding");
        if(c.hold_frames||c.lease_deadline_frame!=current_.lease_deadline_frame||!finite(c.target)||distance(s.xyz,c.target)<30||distance(s.xyz,c.target)>120||distance(c.target,home_)<30||std::fabs(s.xyz.z-c.target.z)>limits_.height_delta||!io_.ground_target(c.target))return reject(c,"diagnostic_fault_target_unverified");
        last_sequence_=c.sequence;seen_.push_back(c);diagnostic_fault_used_=true;
        auto notice=result_;notice.command=c.command;notice.task=c.task;notice.lease=c.lease;notice.sequence=c.sequence;notice.frame=s.frame;notice.monotonic_ms=s.monotonic_ms;notice.reason="controlled_diagnostic_native_move_intent";
        io_.event(Event{notice,"diagnostic_fault_intent",s});
        auto delivered=io_.diagnostic_foreign_move(c);
        // The fault has its own acknowledgement, never the old work identity.
        // Sent does NOT mint Uncertain: the genuine foreign hook/guard must do it.
        if(delivered==Delivery::Unknown)uncertain(io_.sample(),"diagnostic_fault_delivery_unknown");
        Receipt reply=result_;reply.command=c.command;reply.task=c.task;reply.lease=c.lease;reply.sequence=c.sequence;reply.frame=s.frame;reply.monotonic_ms=s.monotonic_ms;
        reply.accepted=delivered!=Delivery::NotSent;reply.reason=delivered==Delivery::Sent?"controlled_native_move_sent":delivered==Delivery::NotSent?"controlled_native_move_not_sent":"controlled_native_move_delivery_unknown";
        return reply;
    }else if(c.operation==Operation::Query){
        last_sequence_=c.sequence;seen_.push_back(c);publish(s,"query","query_only");
        // A query acknowledges its own command identity without replacing the
        // executing task's last action. This is observation, never a new SDK call.
        Receipt reply=result_;reply.command=c.command;reply.task=c.task;reply.lease=c.lease;
        reply.sequence=c.sequence;reply.accepted=true;reply.reason="query_only";return reply;
    }else if(c.operation==Operation::ReconcileRelease||c.operation==Operation::ReconcileReturnHome){
        if(result_.phase!=Phase::Uncertain||s.team!=s.script_team||!io_.independent_recovery_permitted(s))return reject(c,"independent_recovery_quiescence_unverified");
        if(c.operation==Operation::ReconcileReturnHome){
            // current_ retains the Reserve binding, not the last action opcode.
            // Match the original accepted action to its actual receipt instead.
            auto prior=std::find_if(seen_.begin(),seen_.end(),[&](const Command& x){return x.command==result_.command;});
            if(prior==seen_.end()||prior->operation!=Operation::MoveHold||result_.sdk_calls[3]!=1||home_move_attempted_)return reject(c,"recovery_return_requires_unattempted_home");
            if(!(c.target==Point{})||c.hold_frames||c.lease_deadline_frame!=current_.lease_deadline_frame)return reject(c,"recovery_return_intent_changed");
            if(distance(s.xyz,home_)>limits_.max_distance||std::fabs(s.xyz.z-home_.z)>limits_.height_delta)return reject(c,"recovery_return_home_outside_scope");
        }
        publish(s,"recovery_prior_unknown","new_recovery_will_reference_this_prior_unknown");
        foreign_epoch_=s.foreign_epoch;last_observation_ms_=s.monotonic_ms;lease_start_ms_=s.monotonic_ms;
    }else if(result_.phase==Phase::Uncertain)return reject(c,"unknown_action_requires_explicit_reconciliation");
    last_sequence_=c.sequence;seen_.push_back(c);
    result_.command=c.command;result_.task=c.task;result_.lease=c.lease;result_.sequence=c.sequence;result_.accepted=true;
    if(c.operation==Operation::Reserve){
        current_=c;home_=s.xyz;original_stance_=s.stance;foreign_epoch_=s.foreign_epoch;lease_start_ms_=s.monotonic_ms;
        have_lease_=true;result_.held=true;result_.physical_home=false;result_.control_released=false;result_.stance_restored=false;result_.sdk_calls.fill(0);emergency_=false;stop_requested_=false;effect_completed_=false;recovery_home_=false;home_move_attempted_=false;
        phase(Phase::Borrowing,s,"reserve_admitted");
    }else if(c.operation==Operation::MoveHold){current_.target=c.target;current_.hold_frames=c.hold_frames;phase(Phase::Moving,s,"move_hold_admitted");}
    else {
        recovery_home_=c.operation==Operation::ReconcileReturnHome;
        emergency_=c.operation==Operation::EmergencyRelease||c.operation==Operation::ReconcileRelease||recovery_home_;
        if(recovery_home_){effect_completed_=false;result_.physical_home=false;}
        bool reconcile=c.operation==Operation::ReconcileRelease||recovery_home_;
        phase(reconcile?Phase::Stance:emergency_?Phase::HomeBraking:Phase::ReturnBraking,s,recovery_home_?"new_explicit_first_home_recovery":reconcile?"new_explicit_recovery_stance_then_brake":emergency_?"emergency_release_without_home_claim":"return_home_requested");
    }
    last_observation_ms_=s.monotonic_ms;return result_;
}
Receipt Controller::tick(){
    if(!have_lease_||result_.phase==Phase::Uncertain)return result_;
    auto s=io_.sample();
    if(auto why=guard(s,current_.actor))return uncertain(s,why);
    // Preserve the actual samples used by Stop3/arrival decisions. Phase-only
    // events cannot independently establish the first two stable observations.
    if(!clock_seen_||s.frame!=last_frame_||s.monotonic_ms!=last_ms_)publish(s,"observation","native_sample");
    auto total_limit=recovery_home_?limits_.recovery_return_ms:emergency_?limits_.watchdog_ms:limits_.max_lease_ms;
    if(s.monotonic_ms-last_observation_ms_>limits_.watchdog_ms||s.monotonic_ms-lease_start_ms_>total_limit)return uncertain(s,"runtime_watchdog_expired");
    last_observation_ms_=s.monotonic_ms;
    if(s.paused){publish(s,"waiting","game_paused_no_sdk");return result_;}
    if(stop_requested_&&!emergency_&&result_.phase!=Phase::ReturnBraking&&result_.phase!=Phase::Returning&&result_.phase!=Phase::HomeBraking&&result_.phase!=Phase::Restoring&&result_.phase!=Phase::Releasing){
        if(result_.phase==Phase::Borrowing&&s.team==s.default_team){
            if(action_pending_)return uncertain(s,"stop_waits_unknown_borrow_outcome");
            result_.held=false;have_lease_=false;phase(Phase::Released,s,"stopped_before_borrow_no_control_transfer");return result_;
        }
        phase(Phase::ReturnBraking,s,"native_safety_stop_return_home");
    }
    if(s.foreign_epoch!=foreign_epoch_)return uncertain(s,"unknown_native_command_observed");
    if(result_.phase!=Phase::Borrowing&&s.team!=s.script_team&&result_.phase!=Phase::Releasing)return uncertain(s,"actor_control_owner_changed");
    auto preemption=io_.take_native_preemption(s);
    if(preemption==NativePreemption::UnverifiedYield)return uncertain(s,"native_yield_witness_unverified_or_expired");
    if(preemption==NativePreemption::WaitingYield){effect_completed_=false;publish(s,"waiting","native_yield_state_confirmation_pending");return result_;}
    if(preemption==NativePreemption::VerifiedYield){
        if(recovery_home_&&home_move_attempted_)return uncertain(s,"recovery_home_interrupted_no_retry");
        effect_completed_=false;result_.physical_home=false;
        publish(s,"native_yield_preemption","verified_native_yield_abort_goal");
        phase(Phase::ReturnBraking,s,"native_yield_abort_return_home_without_goal_effect");
    }
    bool owned_moving=(result_.phase==Phase::Moving||result_.phase==Phase::Returning)&&s.normal_move_owned;
    if(action_pending_&&!owned_moving&&s.frame-phase_frame_>limits_.action_ack_frames)return uncertain(s,"native_action_ack_timeout_no_retry");
    auto p=result_.phase;
    if(!emergency_&&s.frame>=current_.lease_deadline_frame&&p!=Phase::ReturnBraking&&p!=Phase::Returning&&p!=Phase::HomeBraking&&p!=Phase::Restoring&&p!=Phase::Releasing){phase(Phase::ReturnBraking,s,"lease_deadline_return_home");p=Phase::ReturnBraking;}
    switch(p){
    case Phase::Borrowing:
        if(!action_pending_)issue(Action::Borrow,s);
        else if(s.team==s.script_team)phase(Phase::Stance,s,"borrow_observed");
        break;
    case Phase::Stance:
        if(emergency_&&!action_pending_&&s.stance==2)phase(Phase::HomeBraking,s,"recovery_existing_hold_stance_no_repeat");
        else if(!action_pending_)issue(Action::HoldStance,s,{},2);
        else if(s.stance==2)phase(emergency_?Phase::HomeBraking:Phase::Braking,s,"hold_stance_observed");
        break;
    case Phase::Braking:case Phase::TargetBraking:case Phase::HomeBraking:case Phase::ReturnBraking:
        if(!action_pending_)issue(Action::Stop,s);
        else if(settled(s)){
            if(p==Phase::Braking)phase(Phase::Ready,s,"ready_after_physical_stop");
            else if(p==Phase::TargetBraking){hold_start_=s.frame;phase(Phase::Holding,s,"target_hold_observed");}
            else if(p==Phase::ReturnBraking)phase(Phase::Returning,s,"prior_motion_stopped_before_return");
            else {
                bool at_home=distance(s.xyz,home_)<=limits_.arrival_radius&&std::fabs(s.xyz.z-home_.z)<=limits_.height_delta;
                if(recovery_home_&&!home_move_attempted_&&!at_home)phase(Phase::Returning,s,"recovery_new_stop_before_first_home_move");
                else {result_.physical_home=(!emergency_||recovery_home_)&&at_home;phase(Phase::Restoring,s,result_.physical_home?"physical_home_observed":"emergency_release_home_unproven");}
            }
        }
        break;
    case Phase::Ready:publish(s,"waiting","ready_waiting_commit");break;
    case Phase::Moving:case Phase::Returning:{
        auto target=p==Phase::Moving?current_.target:home_;
        if(!action_pending_){
            if(p==Phase::Returning){
                // No Move has been attempted in this phase. Wait for fresh
                // vacancy plus the same distinct Stop3 samples used elsewhere.
                // An attempted/unknown Move never returns to this branch.
                if(s.frame-phase_frame_>=limits_.max_no_progress_frames&&s.frame>=current_.lease_deadline_frame)return uncertain(s,"return_home_clearance_lease_deadline_no_move");
                if(s.frame-phase_frame_>=limits_.max_home_clearance_wait_frames)return uncertain(s,"return_home_clearance_timeout_no_move");
                if(!io_.return_home_clear(s,home_)){
                    stable_=0;last_stable_frame_=s.frame;previous_=s.xyz;
                    publish(s,"waiting","return_home_current_clearance_unverified_no_move");break;
                }
                if(!settled(s)){publish(s,"waiting","return_home_clearance_needs_distinct_stop_samples");break;}
            }
            if(!io_.ground_target(target))return uncertain(s,"ground_target_no_longer_admissible");
            issue(Action::Move,s,target);
        }
        else {
            if(!s.normal_move_owned){publish(s,"waiting","normal_move_waiting_lineage_no_retry");break;}
            auto remaining=distance(s.xyz,target);
            if(remaining+1<best_target_distance_){best_target_distance_=remaining;last_progress_frame_=s.frame;}
            if(remaining<=limits_.arrival_radius&&std::fabs(s.xyz.z-target.z)<=limits_.height_delta)phase(p==Phase::Moving?Phase::TargetBraking:Phase::HomeBraking,s,p==Phase::Moving?"target_arrival_observed":"home_arrival_needs_stop");
            else if(s.frame-last_progress_frame_>=limits_.max_no_progress_frames){
                if(p==Phase::Moving)phase(Phase::ReturnBraking,s,"outbound_stalled_return_home_without_goal_effect");
                else return uncertain(s,"return_stalled_control_release_unknown");
            }
        }break;}
    case Phase::Holding:
        if(!s.settled||s.stance!=2)return uncertain(s,"held_state_changed");
        if(s.frame-hold_start_>=current_.hold_frames){effect_completed_=true;phase(Phase::ReturnBraking,s,"hold_interval_complete");}else publish(s,"waiting","holding");
        break;
    case Phase::Restoring:
        if(!action_pending_)issue(Action::RestoreStance,s,{},original_stance_);
        else if(s.stance==original_stance_){result_.stance_restored=true;phase(Phase::Releasing,s,"original_stance_observed");}
        break;
    case Phase::Releasing:
        if(!action_pending_){
            if(!issue(Action::TransferBack,s))break;
            // Transfer synchronously returns to the common pool. Observe that
            // actual state before yielding to native AI, which may immediately
            // recruit the released actor into a different own squad.
            auto after=io_.sample();
            if(auto why=guard(after,current_.actor))return uncertain(after,why);
            if(after.team==after.default_team&&after.stance==original_stance_&&result_.stance_restored){
                result_.control_released=true;result_.held=false;have_lease_=false;
                phase(Phase::Released,after,effect_completed_?"native_control_release_observed":"native_control_release_without_goal_effect");
            }
        }else if(s.team==s.default_team&&s.stance==original_stance_&&result_.stance_restored){result_.control_released=true;result_.held=false;have_lease_=false;phase(Phase::Released,s,effect_completed_?"native_control_release_observed":"native_control_release_without_goal_effect");}
        break;
    default:break;
    }
    return result_;
}
Receipt Controller::request_stop(){
    if(stop_requested_||!have_lease_)return result_;
    stop_requested_=true;
    if(result_.phase==Phase::Uncertain)return result_;
    auto s=io_.sample();if(auto why=guard(s,current_.actor))return uncertain(s,why);
    publish(s,"native_safety_stop","native_safety_stop_requested");
    // Tick owns effects and clock/watchdog policy. No new command ID or seq,
    // and no retry of an attempted native action is minted by host shutdown.
    return result_;
}
}
