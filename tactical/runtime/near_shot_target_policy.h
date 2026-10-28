#pragma once
// Passive observations only. The ordinary NearBuildPolicy remains Conscript
// only. This private factory additionally locks the audited Flak source file;
// both infantry classes still need the same full current player3 footprint.
#include "near_build_policy.h"
#include <windows.h>
#include <wincrypt.h>
#include <cstdio>
namespace tacticore::runtime::shot_probe {
class DiagnosticTargetPolicy final:public near_combat::TemplatePolicy {
    Binding binding_;const near_combat::NearBuildPolicy& base_;HANDLE file_;
    DiagnosticTargetPolicy(Binding b,const near_combat::NearBuildPolicy&p,HANDLE f):binding_(b),base_(p),file_(f){}
public:
    ~DiagnosticTargetPolicy()override{if(file_!=INVALID_HANDLE_VALUE)CloseHandle(file_);}
    static std::unique_ptr<DiagnosticTargetPolicy> verify(Binding b,const near_combat::NearBuildPolicy&base){
        if(base.reviewed_range(b,0x19ab11af,0x447ea26e)!=150)return nullptr;
        auto file=CreateFileW(L"E:\\RA3Modding\\SDK\\Mods\\TriadFront\\data\\objects\\SovietAntiVehicleInfantry.xml",GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file==INVALID_HANDLE_VALUE)return nullptr;
        HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
        if(CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
            BYTE bytes[65536]{},digest[32]{};DWORD count=0,size=32;BOOL success=TRUE;
            while((success=ReadFile(file,bytes,sizeof(bytes),&count,nullptr))&&count){if(!CryptHashData(hash,bytes,count,0)){success=FALSE;break;}}
            char actual[65]{};if(success&&CryptGetHashParam(hash,HP_HASHVAL,digest,&size,0)&&size==32){
                for(unsigned i=0;i<32;i++)std::snprintf(actual+2*i,3,"%02x",digest[i]);
                okay=!std::strcmp(actual,"5cca74a426d79dddcb395fb575b0c229fc4a0be41a4e167f9aa3bee5735011d4");
            }
        }
        if(hash){CryptDestroyHash(hash);}if(provider){CryptReleaseContext(provider,0);}
        if(!okay){CloseHandle(file);return nullptr;}
        return std::unique_ptr<DiagnosticTargetPolicy>(new DiagnosticTargetPolicy(b,base,file));
    }
    bool target_class_supported(const Binding&b,uint32_t hash)const override{return b==binding_&&file_!=INVALID_HANDLE_VALUE&&(hash==0x19ab11af||hash==0x2c358c61);}
    bool reviewed(const Binding&b,uint32_t tpl,uint32_t hash)const override{
        return target_class_supported(b,hash)&&tpl>=0x10000&&(hash==0x2c358c61||base_.reviewed(b,tpl,hash));
    }
};
}
