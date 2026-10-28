#pragma once
#include "protocol.h"
#include <vector>

namespace tacticore::runtime {
class Controller {
public:
    Controller(Binding,IO&,Limits={},uint64_t persisted_last_sequence=0);
    Receipt submit(const Command&);
    Receipt tick();
    Receipt request_stop();
    Receipt status()const{return result_;}
    uint64_t last_sequence()const{return last_sequence_;}
private:
    Binding binding_;IO& io_;Limits limits_;Receipt result_{};Command current_{};
    std::vector<Command> seen_;uint64_t last_sequence_=0,last_ms_=0,lease_start_ms_=0;
    uint32_t last_frame_=0,phase_frame_=0,hold_start_=0,stable_=0,last_stable_frame_=0,foreign_epoch_=0,original_stance_=0;
    uint64_t last_observation_ms_=0;
    Point home_{},previous_{};bool clock_seen_=false,have_lease_=false,action_pending_=false,emergency_=false,stop_requested_=false,effect_completed_=false;
    bool recovery_home_=false,home_move_attempted_=false;
    bool diagnostic_fault_used_=false;
    uint32_t last_progress_frame_=0;float best_target_distance_=0;
    Phase pending_for_=Phase::Idle;
    const char* guard(const Sample&,const Actor&,bool require_guard=true);
    Receipt reject(const Command&,const char*);
    Receipt uncertain(const Sample&,const char*);
    void phase(Phase,const Sample&,const char*);
    bool issue(Action,const Sample&,Point={},uint32_t stance=0);
    bool settled(const Sample&);
    void publish(const Sample&,const char*kind,const char*reason);
};
}
