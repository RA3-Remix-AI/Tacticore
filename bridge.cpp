#include "bridge.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static float destination[3];
static bool read_at(uintptr_t p, void* out, size_t n) {
    SIZE_T got=0;
    return ReadProcessMemory(GetCurrentProcess(),(void*)p,out,n,&got) && got==n;
}
static uint32_t word(uintptr_t p) { uint32_t v=0; read_at(p,&v,4); return v; }
static bool module_ptr(uint32_t p) { return p>=0x400000 && p<0xD3B000; }
static void execute(Request* r) {
    r->thread=GetCurrentThreadId();
    // Exact entry signature, preferred image base, and object-vtable hypothesis.
    const unsigned char signature[]={0x56,0x8b,0xf1,0x8b,0x4e,0x3c,0x8b,0x01,0x8b,0x50,0x38,0xff,0xd2};
    unsigned char actual[sizeof(signature)];
    if ((uintptr_t)GetModuleHandleW(NULL)!=0x400000 ||
        !read_at(0x6eff70,actual,sizeof(actual)) || memcmp(signature,actual,sizeof(actual))) {r->result=10;return;}
    if (r->operation==0) {r->result=1;return;}
    unsigned char object[0x41c];
    if (!read_at(r->thing,object,sizeof(object)) || word(r->thing)!=0xc4db60) {r->result=11;return;}
    r->actual_owner=word(r->thing+0x418);
    r->actual_hash=word(word(r->thing+4)+8);
    r->ai=word(r->thing+0x374);
    memcpy(r->before,object+0x38,12);
    uint32_t body=word(r->thing+0x33c);
    if(!body || !read_at(body+4,&r->hp,4) || !isfinite(r->hp) || r->hp<=0 ||
       !module_ptr(word(r->actual_owner)) || !r->ai || !module_ptr(word(r->ai))) {r->result=12;return;}
    if (r->operation==1) {r->result=1;return;}
    if (r->operation!=2 || r->owner!=r->actual_owner || r->hash!=r->actual_hash) {r->result=13;return;}
    float distance=0;
    for(int i=0;i<3;i++) {
        if(!isfinite(r->target[i]) || !isfinite(r->before[i])) {r->result=14;return;}
        float delta=r->target[i]-r->before[i]; distance+=delta*delta;
    }
    if(distance>150*150 || distance<1 || fabsf(r->target[2]-r->before[2])>2) {r->result=14;return;}
    memcpy(destination,r->target,12);
    typedef void (__attribute__((thiscall)) *Move)(void*,float*,int);
    ((Move)0x6eff70)((void*)r->ai,destination,0);
    r->result=2; // Call returned, NOT proof of movement or arrival.
}

extern "C" __declspec(dllexport) LRESULT CALLBACK BridgeHook(int code,WPARAM wp,LPARAM lp) {
    if(code>=0 && wp==PM_REMOVE && lp && ((MSG*)lp)->message==BRIDGE_MESSAGE) {
        char name[80]; snprintf(name,sizeof(name),"Local\\RA3BridgeProbe_%lu",GetCurrentProcessId());
        HANDLE mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);
        if(mapping) {
            Request* r=(Request*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Request));
            if(r) {
                if(r->magic==BRIDGE_MAGIC && InterlockedCompareExchange(&r->done,-1,0)==0) {
                    execute(r); InterlockedExchange(&r->done,1);
                }
                UnmapViewOfFile(r);
            }
            CloseHandle(mapping);
        }
    }
    return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID) {
    if(reason==DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(instance);
    return TRUE;
}

