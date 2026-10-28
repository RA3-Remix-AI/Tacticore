#pragma once
#include "endpoints.h"
#include <functional>
#include <cstring>
#include <vector>

namespace tacticore::runtime {
// Pinned read-only cell/raster predicates, not an SDK query or route planner.
// Actor lifecycle/control admission remains exclusively with MemoryIO.
class NativeLandEndpoints:public SurfacePoints {
public:
    struct Proof {uint32_t frame=0;std::array<uint32_t,24> actor{},raster{},cell{};};
private:
    struct Read {uint32_t address=0;std::vector<unsigned char> bytes;};
    class Batch {
        Memory& m_;std::vector<Read> reads_;bool okay_=true;
    public:
        explicit Batch(Memory& m):m_(m){}
        template<class T>T get(uint32_t address){
            T v{};if(!address||!m_.read(address,&v,sizeof(v))){okay_=false;return v;}
            Read r;r.address=address;r.bytes.resize(sizeof(v));std::memcpy(r.bytes.data(),&v,sizeof(v));reads_.push_back(std::move(r));return v;
        }
        uint32_t word(uint32_t p){return get<uint32_t>(p);}
        bool paired(){
            if(!okay_)return false;
            for(const auto& r:reads_){std::vector<unsigned char> now(r.bytes.size());if(!m_.read(r.address,now.data(),static_cast<uint32_t>(now.size()))||now!=r.bytes)return false;}
            return true;
        }
    };
    Binding binding_;NativeBinding native_;Memory& memory_;Endpoints& occupancy_;Actor actor_{};
    std::function<void(const Proof&)> sink_;mutable std::vector<Point> offered_;
    mutable uint32_t group_=0;
    static uint32_t bits(float v){uint32_t w=0;std::memcpy(&w,&v,4);return w;}
    static float scalar(uint32_t w){float v=0;std::memcpy(&v,&w,4);return v;}
    static float f32(float v){volatile float stored=v;return stored;}
    bool sample(Point request,Point& result,Proof& proof,bool exact_z)const{
        if(!(memory_.current_binding()==binding_)||memory_.thread()!=binding_.thread||!actor_.generation
            ||!finite(request)||request.x<0||request.y<0||request.x>=1000000||request.y>=1000000)return false;
        Batch b(memory_);auto word=[&](uint32_t p){return b.word(p);};
        auto logic=word(0xcd8ce4),frame=word(logic+0x50);if(logic!=native_.logic||word(logic)!=0xbeb630||!frame)return false;
        auto thing_vt=word(actor_.thing),tpl=word(actor_.thing+4),u=word(actor_.thing+0x374),owner=word(actor_.thing+0x418);
        auto update_vt=word(u),facade_vt=word(u+0x24),back=word(u+8);
        auto geometry=word(tpl+0x14),radius=word(actor_.thing+0x120),override_bits=word(geometry+0x110);
        auto set_vt=word(u+0x1fc),mask=word(u+0x210);
        if(thing_vt!=0xc4db60||tpl!=actor_.template_ptr||u!=actor_.update||owner!=actor_.owner
            ||word(actor_.thing+0xdc)!=actor_.object_id||word(tpl+8)!=0x19ab11af||actor_.type_hash!=0x19ab11af
            ||update_vt!=0xc48670||facade_vt!=0xc48528||back!=actor_.thing||set_vt!=0xc37620||mask!=1
            ||radius!=bits(5)||override_bits!=bits(-1))return false;
        // Exactly the demonstrated radius5/override-1 native width1 footprint.
        // Ignored-object fields180/184 never act as surface masks.
        const std::array<uint32_t,11> masks{{9,10,12,24,40,72,72,136,8,520,1032}};
        if(b.get<std::array<uint32_t,11>>(0xcb122c)!=masks||word(0xcb11f4)!=0x3d4ccccd)return false;
        const std::array<unsigned char,15> coordinates{{0x8b,0x54,0x24,0x08,0xf3,0x0f,0x10,0x02,0xf3,0x0f,0x59,0x05,0xf4,0x11,0xcb}};
        const std::array<unsigned char,12> cell_code{{0x53,0x8b,0x5c,0x24,0x0c,0x56,0x8b,0xf1,0x3b,0x5e,0x0c,0x57}};
        // Include the final zero of the coordinate function's absolute operand.
        if(b.get<std::array<unsigned char,15>>(0x68d010)!=coordinates||b.get<unsigned char>(0x68d01f)!=0
            ||b.get<std::array<unsigned char,12>>(0x544720)!=cell_code)return false;
        auto origin=b.get<Point>(actor_.thing+0x38);
        if(!finite(origin)||distance(origin,request)<30||distance(origin,request)>120)return false;
        auto path_root=word(0xce3e30),path_data=word(path_root+0x28);
        if(path_root<0x10000||path_root%4||word(path_root)!=0xc18e20||path_data<0x10000||path_data%4
            ||!(word(path_data+8)&0xff))return false;
        auto bounds=b.get<std::array<int32_t,4>>(path_data+0xc);auto table=word(path_data+4);
        if(bounds[0]<0||bounds[1]<0||bounds[2]<bounds[0]||bounds[3]<bounds[1]
            ||bounds[2]>=8192||bounds[3]>=8192||table<0x10000||table%4)return false;
        auto col=static_cast<uint32_t>(f32(request.x*scalar(0x3d4ccccd))),row=static_cast<uint32_t>(f32(request.y*scalar(0x3d4ccccd)));
        if(col<static_cast<uint32_t>(bounds[0])||row<static_cast<uint32_t>(bounds[1])
            ||col>static_cast<uint32_t>(bounds[2])||row>static_cast<uint32_t>(bounds[3]))return false;
        auto column=word(table+col*4);uint64_t cell_address=static_cast<uint64_t>(column)+48ull*row;
        if(column<0x10000||column%4||cell_address+48>0x100000000ull)return false;
        auto cell=b.get<std::array<uint32_t,12>>(static_cast<uint32_t>(cell_address));auto flags=cell[3];
        if(cell[0]||(flags&15)!=0||((flags>>4)&63)!=1||(flags&0x40000)||!(masks[flags&15]&mask))return false;
        auto height_root=word(0xce9c40),data=word(height_root+0x14);
        const std::array<unsigned char,12> height_code{{0x83,0xec,0x20,0x8b,0xc1,0x8b,0x48,0x14,0x85,0xc9,0x89,0x04}};
        if(height_root<0x10000||height_root%4||word(height_root)!=0xc0a6f0||word(0xc0a744)!=0x8ed070
            ||data<0x10000||data%4||b.get<std::array<unsigned char,12>>(0x8ed070)!=height_code
            ||b.get<unsigned char>(0x8ed07c)!=0x24||word(0xbe6670)!=0x3dcccccd||word(0xc0930c)!=0x3d200000)return false;
        auto width=word(data+0x24),height=word(data+0x28),border=word(data+0x2c),grid=word(data+0x44);
        if(width<4||width>8192||height<4||height>8192||border>std::min(width,height)/2||grid<0x10000||grid%2
            ||static_cast<uint64_t>(grid)+static_cast<uint64_t>(width)*height*2>0x100000000ull)return false;
        float sx=f32(request.x*scalar(0x3dcccccd)),sy=f32(request.y*scalar(0x3dcccccd));
        auto ix=static_cast<uint32_t>(sx),iy=static_cast<uint32_t>(sy),hc=ix+border,hr=iy+border;
        if(hc<1||hr<1||hc>width-3||hr>height-3)return false;
        uint32_t index=hr*width+hc;std::array<uint32_t,4> indices{{index,index+1,index+width,index+width+1}};
        std::array<uint32_t,4> vertices{};for(size_t i=0;i<4;i++)vertices[i]=b.get<uint16_t>(grid+indices[i]*2);
        float fx=f32(sx-ix),fy=f32(sy-iy),middle=static_cast<float>(vertices[fy>fx?2:1]);
        float small=fy>fx?fx:fy,large=fy>fx?fy:fx;
        float first=f32(f32(static_cast<float>(vertices[3])-middle)*small);
        float second=f32(f32(static_cast<float>(vertices[0])-middle)*f32(1-large));
        float z=f32(f32(f32(second+first)+middle)*scalar(0x3d200000));
        result={request.x,request.y,z};
        if(!finite(result)||std::fabs(z-origin.z)>2||(exact_z&&request.z!=z))return false;
        if(!b.paired()||word(logic+0x50)!=frame||!(memory_.current_binding()==binding_))return false;
        proof.frame=frame;auto& a=proof.actor;
        a[0]=1;a[2]=actor_.object_id;a[3]=tpl;a[4]=owner;a[5]=geometry;a[6]=radius;a[7]=override_bits;
        a[8]=set_vt;a[9]=mask;a[10]=1;std::memcpy(a.data()+11,&result,12);std::memcpy(a.data()+14,&origin,12);
        a[17]=logic;a[18]=frame;a[19]=thing_vt;a[20]=update_vt;a[21]=facade_vt;a[22]=back;a[23]=actor_.type_hash;
        auto& h=proof.raster;h[0]=1;h[2]=height_root;h[3]=data;h[4]=grid;h[5]=width;h[6]=height;h[7]=border;
        h[8]=hc;h[9]=hr;std::copy(vertices.begin(),vertices.end(),h.begin()+10);h[14]=bits(fx);h[15]=bits(fy);h[16]=bits(z);
        h[17]=0x3dcccccd;h[18]=0x3d200000;h[19]=index;h[20]=grid+index*2;h[21]=0x8ed070;
        auto& c=proof.cell;c[0]=1;c[2]=path_root;c[3]=path_data;c[4]=table;c[5]=column;c[6]=col;c[7]=row;c[8]=static_cast<uint32_t>(cell_address);
        std::copy(cell.begin(),cell.end(),c.begin()+9);c[21]=0x3d4ccccd;
        c[22]=static_cast<uint32_t>(bounds[0])|(static_cast<uint32_t>(bounds[1])<<16);
        c[23]=static_cast<uint32_t>(bounds[2])|(static_cast<uint32_t>(bounds[3])<<16);
        return true;
    }
public:
    NativeLandEndpoints(Binding b,NativeBinding n,Memory& m,Endpoints& occupied,std::function<void(const Proof&)> sink):binding_(b),native_(n),memory_(m),occupancy_(occupied),sink_(std::move(sink)){}
    void bind_actor(Actor a){actor_=a;offered_.clear();}
    std::vector<Point> candidates(Point origin)const{
        offered_.clear();if(!finite(origin)||origin.x<0||origin.y<0)return {};
        int col=static_cast<int>(f32(origin.x*scalar(0x3d4ccccd))),row=static_cast<int>(f32(origin.y*scalar(0x3d4ccccd)));
        for(int n:{2,4})for(auto offset:std::array<std::array<int,2>,8>{{{{n,0}},{{-n,0}},{{0,n}},{{0,-n}},{{n,n}},{{-n,n}},{{n,-n}},{{-n,-n}}}}){
            Point p{static_cast<float>((col+offset[0])*20+10),static_cast<float>((row+offset[1])*20+10),0},value{};Proof proof{};
            if(sample(p,value,proof,false)&&occupancy_.vacancy_verified(value))offered_.push_back(value);
        }
        return offered_;
    }
    bool contains(const Binding& b,Point p)const override{
        if(group_>=64||!(b==binding_)||!occupancy_.vacancy_verified(p)||std::none_of(offered_.begin(),offered_.end(),[&](Point q){return q==p;}))return false;
        Point actual{};Proof proof{};if(!sample(p,actual,proof,true))return false;
        // Bounded control checks only: successful native admission is logged,
        // candidate enumeration is not a stream of manufactured field tickets.
        proof.actor[1]=proof.raster[1]=proof.cell[1]=++group_;if(sink_)sink_(proof);return true;
    }
};
}
