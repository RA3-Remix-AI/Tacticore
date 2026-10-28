#pragma once
#include "memory_io.h"
#include <set>
#include <vector>

namespace tacticore::runtime {
struct GroundFrame {
    bool verified=false;uint32_t frame=0;
    std::vector<Sample> foot;std::vector<Point> occupied;
};
// Read-only geometry, deliberately not an IO/NativeCalls implementation. The
// shared foot-object layout was independently sampled for own Conscript, Flak
// and Bear. No birth token, lease, Stop ownership or command permission is made.
class GroundGeometry {
    Binding binding_;NativeBinding native_;Memory& memory_;bool reads_ok_=true;
    uint32_t word(uint32_t p){uint32_t v=0;if(!p||!memory_.read(p,&v,4))reads_ok_=false;return v;}
    float scalar(uint32_t p){float v=0;if(!p||!memory_.read(p,&v,4))reads_ok_=false;return v;}
    Point point(uint32_t p){Point v{};if(!p||!memory_.read(p,&v,12))reads_ok_=false;return v;}
    bool root(){
        return memory_.current_binding()==binding_&&memory_.thread()==binding_.thread
            &&word(0xcd8ce4)==native_.logic&&word(native_.logic)==0xbeb630
            &&word(native_.owner)==0xc5bce0&&word(native_.owner+0x20)==binding_.player
            &&word(native_.owner+0x10)==native_.player_template&&word(native_.owner+0x90)==native_.ai
            &&word(native_.ai)==0xc60f60&&word(native_.ai+8)==native_.owner
            &&word(native_.ai+0x8b0)==native_.personality&&word(native_.personality+0x18)==native_.personality_id;
    }
public:
    GroundGeometry(Binding binding,NativeBinding native,Memory& memory):binding_(binding),native_(native),memory_(memory){}
    GroundFrame sample(){
        reads_ok_=true;GroundFrame result;
        if(!root())return {};
        auto frame=word(native_.logic+0x50),head=word(native_.logic+0xb4),cursor=head;
        std::set<uint32_t> addresses,own_ids;
        while(cursor){
            if(cursor%4||addresses.size()>=20000||!addresses.insert(cursor).second||word(cursor)!=0xc4db60)return {};
            if(word(cursor+0x418)==native_.owner){
                auto object_id=word(cursor+0xdc);auto xyz=point(cursor+0x38);
                if(!object_id||!own_ids.insert(object_id).second||!finite(xyz))return {};
                result.occupied.push_back(xyz);
                auto tpl=word(cursor+4),hash=word(tpl+8);
                if(hash==0x19ab11af||hash==0x2c358c61||hash==0x33026fa1){
                    auto update=word(cursor+0x374);
                    if(word(update)==0xc48670&&word(update+0x24)==0xc48528&&word(update+8)==cursor){
                        Sample s{};s.binding=binding_;s.frame=frame;s.current_thread=memory_.thread();s.xyz=xyz;
                        s.actor=Actor{object_id,cursor,tpl,update,native_.owner,hash,0,0};
                        s.team=word(cursor+0x414);auto machine=word(update+0x3c),state=word(machine+4);
                        s.identity=s.team&&word(word(s.team+4)+8)==native_.owner
                            &&word(machine+0x24)==cursor&&word(state+0x18)==machine;
                        auto body=word(cursor+0x33c);float hp=scalar(body+4),height=scalar(cursor+0x5c);
                        uint32_t flags[7]={};if(!memory_.read(cursor+0x80,flags,28))reads_ok_=false;
                        s.grounded=word(cursor+0x238)==0&&!(flags[0]&0x181)&&!(flags[1]&0x20080000)
                            &&!(flags[5]&2)&&!(flags[6]&0x88000)&&(word(cursor+0x48)&4)
                            &&std::isfinite(height)&&std::fabs(height)<=.5f&&std::isfinite(hp)&&hp>0;
                        s.path=word(update+0x150);s.state_flags=word(machine+0x78);
                        s.state_id=word(state+4);s.state_vtable=word(state);
                        result.foot.push_back(s);
                    }
                }
            }
            cursor=word(cursor+0x7c);
        }
        if(addresses.empty()||word(native_.logic+0x50)!=frame||word(native_.logic+0xb4)!=head||!root()||!reads_ok_)return {};
        result.frame=frame;result.verified=true;
        for(auto& s:result.foot)s.live_list_member=true;
        return result;
    }
};
}
