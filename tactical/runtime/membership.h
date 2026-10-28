#pragma once
#include "protocol.h"
namespace tacticore::runtime {
// These are AIPlayer roster methods, NOT Team add/remove methods. Their
// exact self/callers follow the pinned original 0x838820 transfer branches.
inline bool owned_roster_member(bool add,uint32_t self,uint32_t caller,uint32_t thread,
                                uint32_t bound_thread,uint32_t ai,bool scope,Action action){
    return thread==bound_thread&&scope&&self==ai+0x104&&
        (add?(action==Action::TransferBack&&caller==0x83885b):
             (action==Action::Borrow&&caller==0x838877));
}
// Removing passive instrumentation before any Borrow is not a control return.
// The native AI may have assigned that unclaimed actor to a different team.
inline bool observer_detach_admissible(bool borrow_attempted,bool held,bool scope,uint32_t active,
                                      bool pending,uint32_t team,uint32_t default_team,
                                      bool return_observed=false,bool current_team_owned=false,uint32_t script_team=0){
    return !held&&!scope&&!active&&!pending&&(!borrow_attempted||(default_team&&
        (team==default_team||(return_observed&&current_team_owned&&team&&team!=script_team))));
}
}
