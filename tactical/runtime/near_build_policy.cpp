#include "near_build_policy.h"
#include <windows.h>
#include <wincrypt.h>
#include <cstdio>
#include <cwchar>
#include <vector>

namespace tacticore::runtime::near_combat {
struct NearBuildPolicy::Files {
    std::vector<HANDLE> handles;
    ~Files(){for(auto file:handles)CloseHandle(file);}
    bool checked(const wchar_t* path,const char* expected){
        if(!path||!*path)return false;
        auto file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file==INVALID_HANDLE_VALUE)return false;
        handles.push_back(file);HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
        if(CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)
            &&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
            BYTE buffer[65536]{},digest[32]{};DWORD count=0,size=32;BOOL read_ok=TRUE;
            while((read_ok=ReadFile(file,buffer,sizeof(buffer),&count,nullptr))&&count){
                if(!CryptHashData(hash,buffer,count,0)){read_ok=FALSE;break;}
            }
            char actual[65]{};
            if(read_ok&&CryptGetHashParam(hash,HP_HASHVAL,digest,&size,0)&&size==32){
                for(unsigned i=0;i<32;i++)std::snprintf(actual+2*i,3,"%02x",digest[i]);
                okay=std::strcmp(actual,expected)==0;
            }
        }
        if(hash)CryptDestroyHash(hash);
        if(provider)CryptReleaseContext(provider,0);
        return okay;
    }
};
NearBuildPolicy::NearBuildPolicy(Binding b,std::unique_ptr<Files> f):files_(std::move(f)),binding_(b){}
NearBuildPolicy::~NearBuildPolicy()=default;
std::unique_ptr<NearBuildPolicy> NearBuildPolicy::verify_current_game(Binding b,const wchar_t* mod,const wchar_t* cap,const wchar_t* safety){
    uint32_t digest=0;for(auto part:b.binding_hash)digest|=part;
    if(!nonzero(b.session)||!nonzero(b.commander)||!nonzero(b.host)||!digest||b.player!=3
        ||b.pid!=GetCurrentProcessId()||b.thread!=GetCurrentThreadId()||!b.process_start
        ||reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr))!=0x400000)return nullptr;
    FILETIME created{},exited{},kernel{},user{};
    if(!GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user)
        ||((uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime)!=b.process_start)return nullptr;
    wchar_t game[32768]{};auto size=GetModuleFileNameW(nullptr,game,32768);
    if(!size||size>=32768)return nullptr;
    auto base=std::wcsrchr(game,L'\\');if(!base||_wcsicmp(base+1,L"RA3_1.12.game"))return nullptr;
    auto files=std::make_unique<Files>();
    if(!files->checked(game,"ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165")
        ||!files->checked(mod,"2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665")
        ||!files->checked(cap,"667ee10c6eb9549a33d63a02aff6bd45df9438ca309b563ac89e3cc9273476c8")
        ||!files->checked(safety,"1d14e41e10224fb2a8215a2321a7fbbbeae8434b8c006a80fd314f4a11e7719e")
        ||!files->checked(L"E:\\RA3Modding\\SDK\\Mods\\TriadFront\\data\\objects\\SovietAntiInfantryInfantry.xml","b9ffa952bf30200ed5e99744dfed87e7ec0d5071f772ce9039863ab4cbe80841")
        ||!files->checked(L"E:\\RA3Modding\\SDK\\Mods\\TriadFront\\data\\bases\\BaseInfantry.xml","734d6d7a46521cc751146b32882c25926a4572a56a5fb21d9ad3aaeeff010f9e")
        ||!files->checked(L"E:\\RA3Modding\\SDK\\SAGEXML\\BaseObjects\\BaseObject.xml","427972d37dd68f0f09d5ce53092f495b7ea2bb7fa970053bd1a81a2869635292")
        ||!files->checked(L"E:\\RA3Modding\\SDK\\SAGEXML\\GlobalData\\Weapon.xml","7a82e52aa6142f96271173195366227b21a552657bd683f7a33a22e770e1bad1"))return nullptr;
    return std::unique_ptr<NearBuildPolicy>(new NearBuildPolicy(b,std::move(files)));
}
bool NearBuildPolicy::reviewed(const Binding& b,uint32_t pointer,uint32_t hash)const{
    return files_&&b==binding_&&pointer>=0x10000&&hash==0x19ab11af;
}
float NearBuildPolicy::reviewed_range(const Binding& b,uint32_t type,uint32_t weapon)const{
    return files_&&b==binding_&&type==0x19ab11af&&weapon==0x447ea26e?150.0f:0;
}
}
