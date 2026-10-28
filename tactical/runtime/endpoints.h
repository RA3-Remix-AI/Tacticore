#pragma once
#include "memory_io.h"
#include <algorithm>
#include <vector>
#include <limits>
#include <cstring>

namespace tacticore::runtime {
// A transient position on a walking actor is ground-positive, but it is not a
// demonstrated stopping point. Keep these separate from stable destinations.
class Endpoints:public SurfacePoints {
    struct Tracked {Actor actor{};Point point{};uint32_t frame=0,samples=0;};
    Binding binding_;std::vector<Point> observed_,occupied_;std::vector<Tracked> tracked_;
    bool occupancy_verified_=true;
    bool vacant(Point p)const{return occupancy_verified_&&std::none_of(occupied_.begin(),occupied_.end(),[&](Point current){return distance(current,p)<20&&std::fabs(current.z-p.z)<=2;});}
public:
    struct Diagnostics {std::array<uint32_t,24> summary{};std::vector<std::array<uint32_t,24>> points;};
    explicit Endpoints(Binding b):binding_(b){}
    void begin_frame(bool verified=true){occupied_.clear();occupancy_verified_=verified;}
    void occupy(Point p){if(finite(p))occupied_.push_back(p);else occupancy_verified_=false;}
    bool vacancy_verified(Point p)const{return vacant(p);}
    void record_native_foot(const Sample& a,const Sample& b,uint32_t script_team){
        // A unit under script control cannot establish new destinations with
        // our own motion. Other native units remain independent witnesses.
        if(!script_team||a.team==script_team||b.team==script_team)return;
        record(a,b);
    }
    void record(const Sample& a,const Sample& b){
        if(!(a.binding==binding_)||!(b.binding==binding_)||!a.identity||!b.identity||!a.grounded||!b.grounded
            ||!a.live_list_member||!b.live_list_member||a.frame!=b.frame||!(a.actor==b.actor)||!(a.xyz==b.xyz))return;
        occupied_.push_back(a.xyz);
        // Physical ground evidence is not a Stop3/control-state authorization.
        // Real native squads also stand in states 10/13; no command semantics
        // are inferred from those IDs. They still need the same actual stable
        // position, grounded actor, clear path and vacancy proof as other points.
        bool stationary=!a.path&&!b.path&&!(a.state_flags&0xffff)&&!(b.state_flags&0xffff)
            &&a.state_id==b.state_id&&a.state_vtable==b.state_vtable;
        auto found=std::find_if(tracked_.begin(),tracked_.end(),[&](const Tracked& t){return t.actor.thing==a.actor.thing;});
        if(found==tracked_.end()){
            if(tracked_.size()>=256)tracked_.erase(tracked_.begin());
            tracked_.push_back(Tracked{a.actor,a.xyz,a.frame,stationary?1u:0u});return;
        }
        if(a.frame==found->frame)return;
        bool continuous=a.actor==found->actor&&a.frame>found->frame&&a.frame-found->frame<=10&&a.xyz==found->point;
        found->samples=stationary?(continuous?std::min(3u,found->samples+1):1u):0u;
        found->actor=a.actor;found->point=a.xyz;found->frame=a.frame;
        if(found->samples>=3&&std::none_of(observed_.begin(),observed_.end(),[&](Point p){return distance(p,a.xyz)<5;})){
            if(observed_.size()>=256)observed_.erase(observed_.begin());
            observed_.push_back(a.xyz);
        }
    }
    std::vector<Point> available(Point home)const{
        std::vector<Point> points;
        for(auto p:observed_)if(distance(p,home)>=30&&distance(p,home)<=120
            &&vacant(p))points.push_back(p);
        return points;
    }
    Diagnostics diagnostics(Point home)const{
        auto bits=[](float value){uint32_t word=0;std::memcpy(&word,&value,4);return word;};
        Diagnostics out;auto& s=out.summary;s[0]=1;s[1]=static_cast<uint32_t>(observed_.size());
        s[2]=static_cast<uint32_t>(available(home).size());s[3]=occupancy_verified_;s[4]=static_cast<uint32_t>(occupied_.size());
        s[5]=bits(30);s[6]=bits(120);s[7]=bits(20);s[8]=bits(2);std::memcpy(s.data()+10,&home,12);
        for(uint32_t i=0;i<observed_.size();i++){
            auto p=observed_[i];float nearest=std::numeric_limits<float>::max();
            if(occupancy_verified_)for(auto current:occupied_)if(std::fabs(current.z-p.z)<=2)nearest=std::min(nearest,distance(current,p));
            auto gap=distance(p,home),height=std::fabs(p.z-home.z);
            uint32_t flags=(!occupancy_verified_?1u:0u)|(gap<30?2u:0u)|(gap>120?4u:0u)
                |(occupancy_verified_&&nearest<20?8u:0u)|(height>2?16u:0u);
            std::array<uint32_t,24> row{};row[0]=1;row[1]=i;row[2]=s[1];row[3]=occupancy_verified_;row[4]=flags;
            std::memcpy(row.data()+5,&p,12);std::memcpy(row.data()+8,&home,12);
            row[11]=bits(gap);row[12]=bits(nearest);row[13]=s[4];row[14]=bits(30);row[15]=bits(120);row[16]=bits(20);row[17]=bits(height);
            // Height is a downstream controller/planner check. Report the
            // actual available() policy separately rather than changing it.
            row[18]=gap>=30&&gap<=120&&vacant(p);out.points.push_back(row);
        }
        return out;
    }
    bool contains(const Binding& b,Point point)const override{
        return b==binding_&&vacant(point)&&std::any_of(observed_.begin(),observed_.end(),[&](Point p){return p==point;});
    }
};
}
