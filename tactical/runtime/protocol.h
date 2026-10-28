#pragma once
#if defined(_WIN32) && !defined(_WIN32_WINNT)
#define _WIN32_WINNT 0x0601
#endif
// Active runtime v1. No Win32, game SDK or model dependency in this protocol.
#include <array>
#include <cstdint>
#include <cmath>

namespace tacticore::runtime {
constexpr uint32_t protocol_version=1;
using Id=std::array<uint32_t,4>;
using Digest=std::array<uint32_t,8>;
inline bool nonzero(const Id& id){return id[0]||id[1]||id[2]||id[3];}
struct Point {float x=0,y=0,z=0;};
inline bool finite(Point p){return std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z);}
inline bool operator==(Point a,Point b){return a.x==b.x&&a.y==b.y&&a.z==b.z;}
inline float distance(Point a,Point b){return std::hypot(a.x-b.x,a.y-b.y);}
struct Binding {
    Id session{},commander{},host{};
    Digest binding_hash{};
    uint32_t player=0,pid=0,thread=0;
    uint64_t process_start=0;
    bool operator==(const Binding& x)const{return session==x.session&&commander==x.commander&&host==x.host&&binding_hash==x.binding_hash&&player==x.player&&pid==x.pid&&thread==x.thread&&process_start==x.process_start;}
};
struct Actor {
    uint32_t object_id=0,thing=0,template_ptr=0,update=0,owner=0,type_hash=0,born_frame=0;
    // Host-observed identity incarnation, NOT an alleged engine generation field.
    uint64_t generation=0;
    bool operator==(const Actor& x)const{return object_id==x.object_id&&thing==x.thing&&template_ptr==x.template_ptr&&update==x.update&&owner==x.owner&&type_hash==x.type_hash&&born_frame==x.born_frame&&generation==x.generation;}
};
enum class Operation:uint32_t {Reserve=1,MoveHold=2,ReturnHome=3,EmergencyRelease=4,Query=5,ReconcileRelease=6,ReconcileReturnHome=7,DiagnosticForeignMove=8};
enum class Action:uint32_t {Borrow=1,HoldStance=2,Stop=3,Move=4,RestoreStance=5,TransferBack=6};
enum class Delivery:uint32_t {Sent=1,NotSent=2,Unknown=3};
enum class Phase:uint32_t {Idle=0,Borrowing=1,Stance=2,Braking=3,Ready=4,Moving=5,TargetBraking=6,Holding=7,Returning=8,HomeBraking=9,Restoring=10,Releasing=11,Released=12,Uncertain=13,ReturnBraking=14};
struct Command {
    Id command{},task{},lease{};
    uint64_t sequence=0;
    Operation operation=Operation::Query;
    Actor actor{};
    Point target{}; // Home is never accepted here: captured before Borrow.
    uint32_t expires_frame=0,lease_deadline_frame=0,hold_frames=0;
    uint64_t expires_monotonic_ms=0;
    bool operator==(const Command& x)const{return command==x.command&&task==x.task&&lease==x.lease&&sequence==x.sequence&&operation==x.operation&&actor==x.actor&&target==x.target&&expires_frame==x.expires_frame&&lease_deadline_frame==x.lease_deadline_frame&&hold_frames==x.hold_frames&&expires_monotonic_ms==x.expires_monotonic_ms;}
};
struct Sample {
    Binding binding{};Actor actor{};
    uint32_t frame=0,current_thread=0,team=0,default_team=0,script_team=0,stance=0,foreign_epoch=0;
    uint32_t state_id=0,state_vtable=0,path=0,command_source=0,state_flags=0;
    uint64_t monotonic_ms=0;
    Point xyz{};
    bool identity=false,actor_birth_verified=false,live_list_member=false,grounded=false,paused=true,settled=false,
         normal_move_owned=false,interference_guard_ready=false;
};
struct Receipt {
    Id command{},task{},lease{};uint64_t sequence=0;
    Phase phase=Phase::Idle;
    const char* reason="idle";
    uint32_t frame=0;uint64_t monotonic_ms=0;
    bool accepted=false,physical_home=false,control_released=false,stance_restored=false,held=false;
    std::array<uint32_t,6> sdk_calls{};
};
struct Event {Receipt receipt{};const char* kind="observation";Sample observation{};};
// Passive native-hook facts, separate from controller observations/receipts.
struct HookTrace {
    uint32_t frame=0,thread=0,kind=0,self=0,target=0,caller=0,operation=0,scope=0,source=0,
             epoch_before=0,epoch_after=0,word_count=0;
    std::array<uint32_t,24> words{};
};
struct Limits {
    uint32_t max_lease_frames=900,settle_samples=3,action_ack_frames=60,max_no_progress_frames=90;
    // Waiting before a home Move is distinct from an attempted Move stalling.
    // Only the extra wait beyond the original90 frames needs an unexpired
    // work lease. The existing bounded safety return at expiry is retained.
    uint32_t max_home_clearance_wait_frames=180;
    uint64_t watchdog_ms=10000,max_lease_ms=120000;
    uint64_t recovery_return_ms=30000;
    float max_distance=300,arrival_radius=15,height_delta=2;
};
enum class NativePreemption:uint32_t {None=0,WaitingYield=1,VerifiedYield=2,UnverifiedYield=3};
class IO {
public:
    virtual ~IO()=default;
    virtual Sample sample()=0;
    // Guard target against actual terrain; never infer this from an actor flag.
    virtual bool ground_target(Point)=0;
    // Private origin admission uses fresh native samples, never UI coordinates.
    virtual bool remember_home(const Sample&){return false;}
    // An idle position alone does not prove the native director has no order.
    // Default deny; require a fresh local lender check before any claim/call.
    virtual bool independent_borrow_permitted(const Sample&){return false;}
    virtual bool diagnostic_fault_enabled()const{return false;}
    virtual Delivery diagnostic_foreign_move(const Command&){return Delivery::NotSent;}
    // A privately admitted origin can become occupied while the lease is away.
    // Read-only current clearance; never a route/arrival or retry permission.
    virtual bool return_home_clear(const Sample&,Point){return false;}
    // Must independently sample/admit immediately before EACH native SDK call.
    virtual Delivery issue(Action,Point,uint32_t stance)=0;
    virtual void event(const Event&)=0;
    // Only trusted local IO may supply fresh independent quiescence proof.
    // Default denial cannot be elevated by command dictionaries or UI booleans.
    virtual bool independent_recovery_permitted(const Sample&){return false;}
    virtual NativePreemption take_native_preemption(const Sample&){return NativePreemption::None;}
    virtual void clear_native_preemption(){}
};
}
