// Native SDK boundary only. No direct private Move, state/path/enum memory writes.
#include "memory_io.h"
#include <windows.h>
#include <cstring>

namespace tacticore::runtime {
static bool bytes(uint32_t address,const unsigned char* expected,size_t count){
    unsigned char actual[20]={};SIZE_T got=0;
    return count<=sizeof(actual)&&ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(address),actual,count,&got)&&got==count&&!std::memcmp(actual,expected,count);
}
// The pinned original entry checks happen before every call. A hooked entry
// requires the observer's independently verified trampoline and cannot use this
// direct provider. No unknown bytes are trusted as a normal API.
Delivery runtime_v1_original_sdk_call(Action action,const Actor* actor,const NativeBinding* native,const Point* target,uint32_t stance){
    if(!actor||!native||!target)return Delivery::NotSent;
    using Move=void(__attribute__((thiscall))*)(void*,float*,uint32_t);
    using Stop=void(__attribute__((thiscall))*)(void*,uint32_t);
    using Transfer=void(__attribute__((thiscall))*)(void*,void*,uint32_t);
    using Stance=bool(__attribute__((thiscall))*)(void*,uint32_t);
    const unsigned char move[]={0x83,0xec,0x5c,0x8b,0x44,0x24,0x64,0x56,0x6a,0x01,0x50,0x8b,0xf1};
    const unsigned char stop[]={0x83,0xec,0x5c,0x8b,0x44,0x24,0x60,0x56,0x6a,0x01,0x50,0x8b,0xf1};
    const unsigned char transfer[]={0x8b,0x81,0x8c,0,0,0,0x85,0xc0,0x74,0x4f,0x56,0x8b,0xb1,0x90,0,0,0};
    const unsigned char setter[]={0x83,0xec,0x14,0x53,0x8b,0xd9,0x8b,0x43,0x08};
    switch(action){
    case Action::Move:{if(!finite(*target)||!bytes(0x571d90,move,sizeof(move)))return Delivery::NotSent;float xyz[]={target->x,target->y,target->z};reinterpret_cast<Move>(0x571d90)(reinterpret_cast<void*>(actor->update+0x24),xyz,1);break;}
    case Action::Stop:if(!bytes(0x54b0a0,stop,sizeof(stop)))return Delivery::NotSent;reinterpret_cast<Stop>(0x54b0a0)(reinterpret_cast<void*>(actor->update+0x24),1);break;
    case Action::Borrow:case Action::TransferBack:if(!bytes(0x838820,transfer,sizeof(transfer)))return Delivery::NotSent;reinterpret_cast<Transfer>(0x838820)(reinterpret_cast<void*>(native->owner),reinterpret_cast<void*>(actor->thing),action==Action::TransferBack?1:0);break;
    case Action::HoldStance:case Action::RestoreStance:{
        uint32_t module=0;SIZE_T read=0;
        if(stance>3||!bytes(0x7640f0,setter,sizeof(setter))||!ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(actor->thing+0x380),&module,4,&read)||read!=4||!module)return Delivery::NotSent;
        reinterpret_cast<Stance>(0x7640f0)(reinterpret_cast<void*>(module),stance);break;}
    default:return Delivery::NotSent;
    }
    return Delivery::Sent; // Receipt still needs subsequent independent observation.
}
}
