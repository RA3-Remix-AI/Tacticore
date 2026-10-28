#pragma once
#include "protocol.h"
#include <map>
#include <stdexcept>

namespace tacticore::runtime {
// Invoked by the private producer/lifecycle observer, never decoded from a UI
// command. Epoch and registry contents must persist for the life of this binding.
struct PaidBirth {
    Id command{},task{};uint64_t sequence=0;
    uint32_t object_id=0,thing=0,owner=0,type_hash=0,first_observed_frame=0,completion_frame=0,cost=0,paid=0;
    bool raw_receipt_verified=false,created=false,completion_observed=false;
};
// Only fixed local codes cross the native channel. No arbitrary exception text.
class BirthAdmissionError:public std::invalid_argument {
public:
    explicit BirthAdmissionError(const char* code):std::invalid_argument(code){}
};
class Incarnations {
    struct Record {Actor actor;PaidBirth receipt;bool retired=false;};
    std::map<uint32_t,Record> records_;uint64_t next_=1;
public:
    Actor register_paid_birth(const PaidBirth& birth,const Sample& a,const Sample& b){
        if(!birth.raw_receipt_verified||!birth.created||!birth.completion_observed||!nonzero(birth.command)||!nonzero(birth.task)||!birth.sequence||birth.type_hash!=0x19ab11af||birth.cost!=85||birth.paid!=85||!birth.completion_frame)throw BirthAdmissionError("paid_birth_receipt_unverified");
        if(birth.first_observed_frame!=a.frame||a.frame<birth.completion_frame||a.frame!=b.frame)throw BirthAdmissionError("paid_birth_frame_unstable");
        if(!(a.binding==b.binding))throw BirthAdmissionError("paid_birth_binding_unstable");
        if(!a.identity||!b.identity)throw BirthAdmissionError("paid_birth_identity_unverified");
        if(!a.live_list_member||!b.live_list_member)throw BirthAdmissionError("paid_birth_live_list_unverified");
        if(!a.grounded||!b.grounded)throw BirthAdmissionError("paid_birth_grounded_unverified");
        if(!(a.actor==b.actor))throw BirthAdmissionError("paid_birth_actor_unstable");
        if(!(a.xyz==b.xyz))throw BirthAdmissionError("paid_birth_position_unstable");
        if(a.actor.object_id!=birth.object_id||a.actor.thing!=birth.thing||a.actor.owner!=birth.owner||a.actor.type_hash!=birth.type_hash||!a.actor.template_ptr||!a.actor.update)throw BirthAdmissionError("paid_birth_actor_tuple_mismatch");
        if(records_.count(birth.object_id))throw BirthAdmissionError("actor_id_never_reused_within_binding");
        for(const auto& item:records_)if(item.second.actor.thing==birth.thing)throw BirthAdmissionError("actor_address_reuse_requires_new_binding_audit");
        // born_frame means first stable host observation linked to the actual
        // native creation receipt, not an invented engine birth timestamp.
        Actor actor=a.actor;actor.generation=next_++;actor.born_frame=birth.first_observed_frame;
        records_.emplace(actor.object_id,Record{actor,birth,false});return actor;
    }
    bool current(const Actor& actor,const Sample& observation){
        auto found=records_.find(actor.object_id);if(found==records_.end())return false;
        auto& record=found->second;
        if(record.retired||!(actor==record.actor))return false;
        if(!observation.live_list_member||!(observation.actor==actor)){record.retired=true;return false;}
        return true;
    }
};
}
